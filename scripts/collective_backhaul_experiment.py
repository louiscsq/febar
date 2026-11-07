"""Step 6: OFFLINE collective-degradation detector for slow backhaul faults (docs/pipeline.md, "Collective backhaul
detector (offline experiment)"). Reads existing tables only; writes only `netmon_eval.eval_collective_backhaul_experiment`
and evidence/step6/.

    python scripts/collective_backhaul_experiment.py calibrate                  # history_1m DEV days only
    python scripts/collective_backhaul_experiment.py score --reading dev        # after the freeze commit
    python scripts/collective_backhaul_experiment.py score --reading holdout    # ONCE: the detector holdout reading
    python scripts/collective_backhaul_experiment.py score --reading stream     # the old live run (3 faults)
    python scripts/collective_backhaul_experiment.py rescore --reading holdout --note "..."  # stored detections only
    python scripts/collective_backhaul_experiment.py verify                     # nothing existing changed

Protocol. `calibrate` sweeps a declared grid on the history_1m dev days (the RCA's dev split, 2026-10-14 .. 10-15),
applies the declared selection rule and writes evidence/step6/01_calibration.md. The chosen thresholds are then frozen in
`detection.COLLECTIVE_BACKHAUL` and committed. `score` refuses to run unless that rule exists and the worktree is clean,
records the commit SHA it ran at, and refuses a second holdout reading. Detections are computed in SQL on the warehouse
(`windows.parent_health_sql` + `detection.collective_detections_sql`) from gold_cell_health_1m, topology and the change
calendar only; ground truth is read afterwards, by the scoring step (`netmon_pipeline.collective_eval`), and never feeds
a detection. The Python mirror recomputes the detections from the same parent-minute statistic and must agree exactly.
"""

from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from capture_evidence import md_table  # noqa: E402

from netmon_pipeline import collective_eval as ce  # noqa: E402
from netmon_pipeline import detection, scoring, windows  # noqa: E402

CAT = "telco_netmon_febar_catalog"
HEALTH = f"{CAT}.netmon_gold.gold_cell_health_1m"
TOPO = f"{CAT}.netmon_silver.silver_topology_nodes"
MAINT = f"{CAT}.netmon_silver.silver_maintenance_windows"
GT = f"{CAT}.netmon_eval.eval_gt_incidents"
INCIDENT_DETECTION = f"{CAT}.netmon_eval.eval_incident_detection"
DETECTION_LOG = f"{CAT}.netmon_eval.eval_detection_log"
EXPERIMENT_TABLE = f"{CAT}.netmon_eval.eval_collective_backhaul_experiment"
OUT = ROOT / "evidence" / "step6"
FAULT = "BACKHAUL_DEGRADATION"

# reading -> (source_run, [lo, hi) UTC). dev = the RCA split's dev days of history_1m (rca.model.TimeSplit:
# train 10-10..10-12, val 10-13, dev from 10-14); an incident belongs to the reading its impact starts in.
READINGS = {
    "dev": ("history_1m", "2026-10-14T00:00:00Z", "2026-10-16T00:00:00Z"),
    "holdout": ("holdout_1m", "2026-10-17T00:00:00Z", "2026-10-19T00:00:00Z"),
    "stream": ("stream", "2026-10-08T18:55:00Z", "2026-10-09T00:55:00Z"),
}

# --- calibration: grid and selection rule, declared before the sweep ran --------------------------------------------
GRID_Z = (1.5, 2.0, 2.5, 3.0)
GRID_LAT_FLOOR_MS = (3.0, 4.0, 6.0, 8.0, 10.0)  # loss / drop floors scale with it by the fault's own ratio
GRID_CONSISTENCY = (0.25, 0.4, 0.6)  # > 0: the guard is part of the design (one cell cannot carry the mean)
GRID_PERSIST = (1, 2, 3)
MIN_REPORTING_SHARE = 0.8
MAX_FALSE_ALARMS_PER_100_LINK_DAYS = 1.0  # the report's go / no-go bar for version (b)
MIN_DETECTED_PCT = 90.0
SELECTION_RULE = (
    f"Feasible: false collective alerts <= {MAX_FALSE_ALARMS_PER_100_LINK_DAYS} per 100 healthy link-days AND >= "
    f"{MIN_DETECTED_PCT:.0f} % of dev {FAULT} incidents detected by the collective rule. Among feasible configurations, "
    "pick the lowest median collective TTD (undetected = +inf); ties: fewer false alarms, then larger persist, larger z, "
    "larger consistency (the more conservative).")


def floors_for(lat_ms: float) -> tuple[tuple[str, float], ...]:
    # BACKHAUL_DEGRADATION at full intensity: +140 ms, +6 pp loss, +3 pp drop (netmon_datagen.faults)
    lat_ms = float(lat_ms)
    return (("latency_ms", lat_ms), ("packet_loss_pct", round(lat_ms * 6 / 140, 4)),
            ("session_drop_rate_pct", round(lat_ms * 3 / 140, 4)))


def _iso_s(iso: str) -> float:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


# --- warehouse access ------------------------------------------------------------------------------------------------

class Warehouse:
    def __init__(self, profile: str, warehouse: str):
        from databricks.sdk import WorkspaceClient

        self.w, self.warehouse = WorkspaceClient(profile=profile), warehouse

    def _run(self, statement: str, fetch: bool):
        from databricks.sdk.service.sql import Disposition, Format, StatementState

        kw = {"disposition": Disposition.EXTERNAL_LINKS, "format": Format.ARROW_STREAM} if fetch else {}
        r = self.w.statement_execution.execute_statement(statement=statement, warehouse_id=self.warehouse,
                                                         wait_timeout="50s", **kw)
        while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
            time.sleep(3)
            r = self.w.statement_execution.get_statement(r.statement_id)
        if r.status.state != StatementState.SUCCEEDED:
            raise RuntimeError(f"{r.status.state}: {r.status.error and r.status.error.message}\n{statement[:3000]}")
        return r

    def execute(self, statement: str) -> None:
        self._run(statement, fetch=False)

    def frame(self, statement: str) -> pd.DataFrame:
        import pyarrow as pa
        import requests

        r = self._run(statement, fetch=True)
        cols = [c.name for c in r.manifest.schema.columns]
        tables, links = [], list(r.result.external_links or []) if r.result else []
        while links:
            nxt = None
            for link in links:
                resp = requests.get(link.external_link, timeout=300)  # pre-signed URL: no auth header
                resp.raise_for_status()
                tables.append(pa.ipc.open_stream(resp.content).read_all())
                nxt = link.next_chunk_index
            links = (self.w.statement_execution.get_statement_result_chunk_n(r.statement_id, nxt).external_links or []
                     if nxt is not None else [])
        n = sum(t.num_rows for t in tables)
        if r.manifest.total_row_count is not None and n != r.manifest.total_row_count:
            raise RuntimeError(f"fetched {n} rows, statement returned {r.manifest.total_row_count}")
        if not tables:
            return pd.DataFrame(columns=cols)
        return pa.concat_tables(tables).to_pandas()


def _secs(s: pd.Series) -> pd.Series:
    s = pd.to_datetime(s, utc=True)
    return (s - pd.Timestamp(0, tz="UTC")).dt.total_seconds()


# --- inputs ----------------------------------------------------------------------------------------------------------

def stats_sql(reading: str, watermark_s: int = windows.COLLECTIVE_WATERMARK_S) -> str:
    run, lo, hi = READINGS[reading]
    return windows.parent_health_sql(HEALTH, TOPO, MAINT, f"source_run = '{run}' AND window_start >= '{lo}' "
                                     f"AND window_start < '{hi}'", watermark_s)


def fetch_stats(wh: Warehouse, reading: str, watermark_s: int = windows.COLLECTIVE_WATERMARK_S) -> pd.DataFrame:
    df = wh.frame(stats_sql(reading, watermark_s))
    df["window_start_s"], df["window_end_s"] = _secs(df["window_start"]), _secs(df["window_end"])
    df["available_s"] = _secs(df["available_ts"])
    return df


def fetch_topology(wh: Warehouse) -> tuple[dict[str, set[str]], dict[str, int]]:
    cells = wh.frame(f"SELECT DISTINCT element_id, site_id, backhaul_id FROM {TOPO} WHERE element_type = 'CELL'")
    members: dict[str, set[str]] = {}
    for r in cells.itertuples():
        members.setdefault(r.backhaul_id, set()).update((r.element_id, r.site_id))
    return members, cells.groupby("backhaul_id")["element_id"].nunique().to_dict()


def fetch_incidents(wh: Warehouse, run: str) -> list[dict]:
    df = wh.frame(f"SELECT * FROM {GT} WHERE source_run = '{run}'")
    out = []
    for r in df.to_dict("records"):
        def s(col, r=r):
            v = r.get(col)
            return None if v is None or pd.isna(v) else pd.Timestamp(v).timestamp()
        impact_end = s("impact_end_ts") if s("impact_end_ts") is not None else s("end_ts")
        out.append({**{k: r[k] for k in ("source_run", "incident_id", "event_class", "fault_type", "root_element_id",
                                         "root_element_type", "is_customer_impacting", "is_censored")},
                    **{k: list(r[k]) if r[k] is not None else [] for k in
                       ("root_element_ids", "affected_element_ids", "affected_cell_ids")},
                    "start_s": s("start_ts"), "end_s": s("end_ts"), "impact_start_s": s("impact_start_ts"),
                    "impact_end_s": impact_end})
    return out


def fetch_before(wh: Warehouse, run: str) -> dict[tuple[str, str], float | None]:
    """Published step-2 metric (a): first per-cell / alarm detection on the incident's footprint, as an availability
    time (impact_start + the published, 0-clipped impact_ttd_s: the clip does not change which detector is first).
    Undetected incidents (`impact_detected` false) are None: the MV's `greatest(NULL, 0)` gives them impact_ttd_s = 0."""
    df = wh.frame(f"SELECT source_run, incident_id, impact_detected, impact_start_ts, impact_ttd_s FROM {INCIDENT_DETECTION} "
                  f"WHERE source_run = '{run}'")
    return {(r.source_run, r.incident_id): (pd.Timestamp(r.impact_start_ts).timestamp() + float(r.impact_ttd_s)
                                            if bool(r.impact_detected) and not pd.isna(r.impact_ttd_s) else None)
            for r in df.itertuples()}


def fetch_percell(wh: Warehouse, reading: str) -> list[dict]:
    """Today's per-cell KPI detections on the reading's cells, mapped to their backhaul link (link-level pages)."""
    run, lo, hi = READINGS[reading]
    df = wh.frame(f"""
        SELECT detection_id, source_run, element_id AS cell_id, backhaul_id, signal_start_ts, signal_end_ts,
               bool_or(in_maintenance) AS in_maintenance
        FROM {DETECTION_LOG}
        WHERE source_run = '{run}' AND signal_source = 'kpi' AND signal_start_ts >= '{lo}' AND signal_start_ts < '{hi}'
        GROUP BY ALL""")  # GROUP BY: the documented in-maintenance join fan-out writes some rows twice
    df["s0"], df["s1"] = _secs(df["signal_start_ts"]), _secs(df["signal_end_ts"])
    return [{"source_run": r.source_run, "element_id": r.backhaul_id, "label_element_id": r.cell_id,
             "signal_start_s": r.s0, "signal_end_s": r.s1, "in_maintenance": bool(r.in_maintenance)}
            for r in df.itertuples()]


# --- detections and evaluation ---------------------------------------------------------------------------------------

def detections(df: pd.DataFrame, rule: detection.CollectiveRule) -> list[dict]:
    """Python mirror of the SQL detections over the fetched parent-minute statistic."""
    sel = df[rule.fires_frame(df)]
    return [{"source_run": r.source_run, "element_id": r.parent_id, "signal_start_s": r.window_start_s,
             "signal_end_s": r.window_end_s, "available_s": r.available_s, "in_maintenance": bool(r.in_maintenance),
             "w_prb_util_pct": None if pd.isna(r.w_prb_util_pct) else float(r.w_prb_util_pct),
             "window_start": r.window_start} for r in sel.itertuples()]


class Context:
    def __init__(self, wh: Warehouse, reading: str):
        self.reading = reading
        self.run, lo, hi = READINGS[reading]
        self.lo, self.hi = _iso_s(lo), _iso_s(hi)
        self.members, self.n_desc = fetch_topology(wh)
        self.incidents = fetch_incidents(wh, self.run)
        self.index = ce.IncidentIndex(self.incidents)
        self.before = fetch_before(wh, self.run)
        self.scored = [i for i in self.incidents if i["fault_type"] == FAULT and scoring.is_scored(i)
                       and self.lo <= i["impact_start_s"] < self.hi]
        self.link_days = ce.healthy_link_days(self.n_desc, self.members, self.incidents, self.run, self.lo, self.hi)


def evaluate(ctx: Context, dets: list[dict]) -> dict:
    rows = ce.score_incidents(ctx.scored, dets, ctx.before, ctx.n_desc)
    alerts = ce.alert_table(dets, ctx.index, ctx.members)
    return {"rows": rows, "alerts": alerts, "fa": ce.false_alarm_summary(alerts, ctx.link_days),
            "coll": ce.summary(rows, "collective_ttd_s")}


def ttd_table(rows: list[dict]) -> tuple[list[str], list[list]]:
    cols = ["subset", "n", "detector", "detected", "median_ttd_s", "p90_ttd_s", "within_5min_pct"]
    out = []
    subsets = {"all": rows,
               f"link <= {ce.SMALL_LINK_MAX_CELLS} cells": [r for r in rows if (r["n_desc_cells"] or 0) <= ce.SMALL_LINK_MAX_CELLS],
               f"link > {ce.SMALL_LINK_MAX_CELLS} cells": [r for r in rows if (r["n_desc_cells"] or 0) > ce.SMALL_LINK_MAX_CELLS]}
    for name, sub in subsets.items():
        for key, label in (("before_ttd_s", "before: per-cell (published metric a)"),
                           ("collective_ttd_s", "collective alone"),
                           ("combined_ttd_s", "after: per-cell + collective (first of)")):
            s = ce.summary(sub, key)
            out.append([name, s["n_incidents"], label, s["n_detected"], _r(s["median_ttd_s"]), _r(s["p90_ttd_s"]),
                        s["within_sla_pct"]])
    gains = [r["before_ttd_s"] - r["combined_ttd_s"] for r in rows
             if r["before_ttd_s"] is not None and r["combined_ttd_s"] is not None]
    out.append(["all", len(gains), "median gain, before - after (s)", len(gains), _r(scoring.percentile(gains, 0.5)),
                _r(scoring.percentile(gains, 0.9)), None])
    return cols, out


def _r(x):
    return None if x is None else round(float(x), 1)


def percell_false_alarms(ctx: Context, percell: list[dict]) -> tuple[dict, list[dict]]:
    alerts = ce.alert_table(percell, ctx.index, None)
    return ce.false_alarm_summary(alerts, ctx.link_days), alerts


def added_pages(coll_alerts: list[dict], cell_alerts: list[dict]) -> int:
    """Collective false alarms on a link with no per-cell alert of that link within ALERT_GAP_S: new pages."""
    by_link: dict[tuple, list[tuple[float, float]]] = {}
    for a in cell_alerts:
        by_link.setdefault((a["source_run"], a["element_id"]), []).append((a["signal_start_s"], a["signal_end_s"]))
    n = 0
    for a in coll_alerts:
        if not ce.is_false_alarm(a):
            continue
        spans = by_link.get((a["source_run"], a["element_id"]), [])
        if not any(s0 - scoring.ALERT_GAP_S < a["signal_end_s"] and a["signal_start_s"] < s1 + scoring.ALERT_GAP_S
                   for s0, s1 in spans):
            n += 1
    return n


def other_fault_tp(alerts: list[dict]) -> list[list]:
    counts: dict[str, int] = {}
    for a in alerts:
        if a["label"] == "fault":
            for f in a["fault_types"] or ["?"]:
                counts[f] = counts.get(f, 0) + 1
    return [[f, n] for f, n in sorted(counts.items())]


# --- evidence --------------------------------------------------------------------------------------------------------

class Doc:
    def __init__(self, title: str, intro: str):
        self.parts = [f"# {title}\n", f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by "
                      f"`scripts/collective_backhaul_experiment.py`.\n", intro.strip() + "\n"]

    def h(self, title: str, text: str = "") -> None:
        self.parts.append(f"## {title}\n" + (f"\n{text.strip()}\n" if text else ""))

    def sql(self, sql: str) -> None:
        self.parts.append("```sql\n" + "\n".join(x.rstrip() for x in sql.strip("\n").splitlines()) + "\n```\n")

    def table(self, cols, rows) -> None:
        self.parts.append(md_table(cols, rows) + "\n")

    def text(self, t: str) -> None:
        self.parts.append(t.strip() + "\n")

    def write(self, name: str) -> Path:
        OUT.mkdir(parents=True, exist_ok=True)
        p = OUT / name
        p.write_text("\n".join(self.parts))
        print("wrote", p)
        return p


def fa_rows(fa: dict) -> tuple[list[str], list[list]]:
    return ["measure", "value"], [[k, v] for k, v in fa.items()]


# --- commands --------------------------------------------------------------------------------------------------------

def calibrate(wh: Warehouse) -> None:
    ctx = Context(wh, "dev")
    df = fetch_stats(wh, "dev")
    results = []
    for z, lat, c, p in itertools.product(GRID_Z, GRID_LAT_FLOOR_MS, GRID_CONSISTENCY, GRID_PERSIST):
        rule = detection.CollectiveRule("candidate", z, floors_for(lat), c, MIN_REPORTING_SHARE, p)
        ev = evaluate(ctx, detections(df, rule))
        ttds = [r["collective_ttd_s"] if r["collective_ttd_s"] is not None else float("inf") for r in ev["rows"]]
        med = scoring.percentile(ttds, 0.5)
        results.append({"z": z, "lat_floor_ms": lat, "consistency": c, "persist": p,
                        "detected_pct": ev["coll"]["detected_pct"], "median_ttd_s": med,
                        "p90_ttd_s": ev["coll"]["p90_ttd_s"], "within_5min_pct": ev["coll"]["within_sla_pct"],
                        "false_alarms": ev["fa"]["n_false_alarms"],
                        "fa_per_100": ev["fa"]["false_alarms_per_100_link_days"], "tp_alerts": ev["fa"]["n_fault_tp"]})
    res = pd.DataFrame(results)
    res["feasible"] = (res.fa_per_100 <= MAX_FALSE_ALARMS_PER_100_LINK_DAYS) & (res.detected_pct >= MIN_DETECTED_PCT)
    ranked = res[res.feasible].sort_values(["median_ttd_s", "false_alarms", "persist", "z", "consistency"],
                                           ascending=[True, True, False, False, False])
    d = Doc("Step 6 calibration: collective backhaul detector on history_1m DEV days", f"""
Calibration of `detection.CollectiveRule` on the **dev days of `history_1m`** (2026-10-14 .. 10-15 UTC: the RCA's dev split;
train 10-10 .. 10-12 and validation 10-13 are not read). No other run was read by this step; `holdout_1m` and `stream` are
scored only after the chosen thresholds were frozen in code and committed.

- input: `gold_cell_health_1m` (on-time 1-minute cell windows), `silver_topology_nodes`, `silver_maintenance_windows`;
  ground truth (`eval_gt_incidents`) and the published per-cell first detection (`eval_incident_detection`) are read only to
  score each candidate.
- parent: backhaul link (133 links, 1,431 cells). Watermark {windows.COLLECTIVE_WATERMARK_S} s (the watermark of the table read).
- scored incidents: {len(ctx.scored)} customer-impacting, uncensored `{FAULT}` faults whose impact starts in the dev days.
- healthy link-days (outside every ground-truth footprint touching the link, its cells or sites): {ctx.link_days:.1f}.
- grid: z in {list(GRID_Z)}; latency floor in {list(GRID_LAT_FLOOR_MS)} ms with loss floor = latency x 6/140 pp and drop floor =
  latency x 3/140 pp (the fault's own ratio); consistency in {list(GRID_CONSISTENCY)} (fraction of reporting cells with z > 1);
  persist in {list(GRID_PERSIST)} minutes; reporting share >= {MIN_REPORTING_SHARE}. {len(res)} configurations.
- selection rule (declared in the script before the sweep): {SELECTION_RULE}
""")
    d.h("Parent-minute statistic (SQL, dev days)")
    d.sql(stats_sql("dev"))
    d.h("Feasible configurations, best first (top 15)")
    show = ["z", "lat_floor_ms", "consistency", "persist", "detected_pct", "median_ttd_s", "p90_ttd_s",
            "within_5min_pct", "false_alarms", "fa_per_100", "tp_alerts"]
    d.table(show, ranked[show].head(15).values.tolist())
    d.h("Fastest configurations regardless of false alarms (top 15 by median TTD)")
    d.table(show + ["feasible"], res.sort_values(["median_ttd_s", "false_alarms"])[show + ["feasible"]].head(15)
            .values.tolist())
    d.h("Full grid")
    d.table(show + ["feasible"], res.sort_values(["z", "lat_floor_ms", "consistency", "persist"])[show + ["feasible"]]
            .values.tolist())
    if ranked.empty:
        d.h("Chosen", "No configuration is feasible under the selection rule.")
    else:
        best = ranked.iloc[0]
        d.h("Chosen (to be frozen as `detection.COLLECTIVE_BACKHAUL`)")
        d.sql(f"z = {best.z}, floors = {floors_for(best.lat_floor_ms)}, min_consistency = {best.consistency}, "
              f"min_reporting_share = {MIN_REPORTING_SHARE}, persist = {int(best.persist)}")
    d.write("01_calibration.md")
    res.to_csv(OUT / "01_calibration_grid.csv", index=False)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def score(wh: Warehouse, reading: str, replace: bool) -> None:
    rule = getattr(detection, "COLLECTIVE_BACKHAUL", None)
    if rule is None:
        sys.exit("detection.COLLECTIVE_BACKHAUL is not frozen yet: run `calibrate`, freeze and commit first")
    if _git("status", "--porcelain", "--", "src"):
        sys.exit("src/ has uncommitted changes: the frozen rule must be committed before scoring")
    head = _git("rev-parse", "HEAD")
    # the freeze: the last commit that changed the detector code (rule, thresholds, parent aggregate)
    sha = _git("log", "-1", "--format=%H", "--", "src/netmon_pipeline/detection.py", "src/netmon_pipeline/windows.py")
    run, lo, hi = READINGS[reading]
    rule_json = json.dumps({"name": rule.name, "z": rule.z, "floors": dict(rule.floors),
                            "min_consistency": rule.min_consistency,
                            "min_reporting_share": rule.min_reporting_share, "persist": rule.persist,
                            "consistency_z": detection.CONSISTENCY_Z, "watermark_s": windows.COLLECTIVE_WATERMARK_S})
    stats = stats_sql(reading)
    det_sql = detection.collective_detections_sql(rule, stats)
    wh.execute(f"""CREATE TABLE IF NOT EXISTS {EXPERIMENT_TABLE}
        COMMENT 'Step 6 OFFLINE experiment: collective (backhaul-link) degradation detections from on-time 1-minute cell
 windows. One row per firing link-minute per reading. Not read by the pipeline, the eval MVs, the ranker, the app or Genie.'
        AS SELECT 'x' AS reading, 'x' AS freeze_sha, 'x' AS rule_json, current_timestamp() AS scored_at, *
        FROM ({det_sql}) WHERE false""")
    prior = wh.frame(f"SELECT count(*) AS n, min(freeze_sha) AS sha FROM {EXPERIMENT_TABLE} WHERE reading = '{reading}'")
    if int(prior.n[0]) > 0:
        if reading == "holdout" or not replace:
            sys.exit(f"reading {reading} already scored at {prior.sha[0]}: the holdout is read once")
        wh.execute(f"DELETE FROM {EXPERIMENT_TABLE} WHERE reading = '{reading}'")
    # MERGE, not INSERT: idempotent if the client retries the statement (an INSERT once landed twice that way)
    insert = (f"MERGE INTO {EXPERIMENT_TABLE} t\nUSING (SELECT '{reading}' AS reading, '{sha}' AS freeze_sha, "
              f"'{rule_json}' AS rule_json, current_timestamp() AS scored_at, *\nFROM ({det_sql})) s\n"
              f"ON t.reading = s.reading AND t.detection_id = s.detection_id\nWHEN NOT MATCHED THEN INSERT *")
    wh.execute(insert)

    # --- the Python mirror over the same statistic must give the same detections
    df = fetch_stats(wh, reading)
    py = detections(df, rule)
    py_ids = {detection.collective_detection_id(run, d["element_id"],
                                                pd.Timestamp(d["window_start"]).strftime("%Y-%m-%dT%H:%M:%SZ"))
              for d in py}
    tab = wh.frame(f"SELECT detection_id, element_id, signal_start_ts, signal_end_ts, available_ts, in_maintenance, "
                   f"w_prb_util_pct, qualifying_metrics, n_reporting_cells, n_desc_cells FROM {EXPERIMENT_TABLE} "
                   f"WHERE reading = '{reading}'")
    sql_ids = set(tab.detection_id)
    mirror = [["SQL detections (table rows)", len(tab)], ["distinct detection_id", len(sql_ids)],
              ["Python mirror detections", len(py)], ["in SQL only", len(sql_ids - py_ids)],
              ["in Python only", len(py_ids - sql_ids)]]
    stats_check = mirror_check_stats(wh, reading, df)

    ctx = Context(wh, reading)
    ev = evaluate(ctx, py)
    cell_fa, cell_alerts = percell_false_alarms(ctx, fetch_percell(wh, reading))
    wm60 = evaluate(ctx, detections(fetch_stats(wh, reading, 60), rule))

    titles = {"dev": "DEV reading (history_1m dev days, calibrated on: in-sample)",
              "holdout": "DETECTOR HOLDOUT READING (holdout_1m, read once, after the freeze)",
              "stream": "Old live `stream` run (only 3 scored backhaul faults)"}
    d = Doc(f"Step 6 collective backhaul detector: {titles[reading]}", f"""
- reading `{reading}`: source_run `{run}`, windows {lo} .. {hi}.
- frozen rule `detection.COLLECTIVE_BACKHAUL`, frozen at commit `{sha}` (last change to the detector code), scored at
  HEAD `{head}`: `{rule_json}`
- detections computed in SQL on the warehouse from `gold_cell_health_1m`, topology and the change calendar only, written
  to `{EXPERIMENT_TABLE}` (reading = `{reading}`). Ground truth was read afterwards, for scoring only.
- timing: a link-minute is available at max(window_end + {windows.COLLECTIVE_WATERMARK_S} s watermark, latest evidence_ts of the
  on-time cell windows used); a cell window arriving after window_end + watermark is not used. No record-level timing.
  "before" is the published step-2 metric (a) (`eval_incident_detection.impact_ttd_s`: first per-cell KPI or alarm
  detection on the incident footprint, evidence time + measured live pipeline latency). For the batch runs that latency
  is 0 on both sides; for `stream` the collective side has no measured pipeline latency (a lower bound).
- scored incidents: {len(ctx.scored)} customer-impacting, uncensored `{FAULT}` (impact start in the reading).
  Healthy link-days: {ctx.link_days:.1f}.
""")
    if reading == "holdout":
        d.text("**Declared detector holdout reading.** The collective detector's thresholds were calibrated on the "
               "history_1m dev days only and frozen at the commit above; this run was never read by the detector before. "
               "(`holdout_1m` was already used once by the RCA model; this is a separate reading for a separate detector.)")
    d.h("Write (SQL)")
    d.sql(insert)
    d.h("SQL vs Python mirror: detections")
    d.table(["check", "value"], mirror)
    d.h("SQL vs Python mirror: parent-minute statistic recomputed from the cell windows (one hour)")
    d.table(*stats_check)
    d.h(f"Time to detect, {FAULT} (n = {len(ctx.scored)})", "Ground truth used for scoring only. Undetected incidents "
        "count against 'within 5 min' but not in the percentiles.")
    d.table(*ttd_table(ev["rows"]))
    d.h("Per incident")
    d.table(["incident_id", "link", "n_cells", "before_ttd_s", "collective_ttd_s", "combined_ttd_s"],
            [[r["incident_id"], r["root_element_id"], r["n_desc_cells"], _r(r["before_ttd_s"]),
              _r(r["collective_ttd_s"]), _r(r["combined_ttd_s"])] for r in ev["rows"]])
    d.h("False-alarm cost", f"""Alerts: detections grouped per (run, link) with the step-2 rule (a new alert when a
detection starts > {scoring.ALERT_GAP_S // 60} min after the previous one ended), labelled by the ground truth whose footprint
holds the link (fault > censored > planned > red herring > unexplained). False alarm = unexplained, red herring, or planned
work not suppressed by the change window. Per 100 healthy link-days ({ctx.link_days:.1f}). The per-cell column applies the
same grouping to today's per-cell KPI detections on the link's cells (labelled by the cell's own footprint).""")
    keys = list(ev["fa"])
    d.table(["measure", "collective", "per-cell KPI rules (today), grouped per link"],
            [[k, ev["fa"][k], cell_fa.get(k)] for k in keys])
    d.table(["measure", "value"], [["collective false alarms on a link with no per-cell alert within 10 min (new pages)",
                                    added_pages(ev["alerts"], cell_alerts)],
                                   ["TRAFFIC_SURGE incidents in this run (ground truth)",
                                    sum(i["fault_type"] == "TRAFFIC_SURGE" for i in ctx.incidents)]])
    d.h("Collective alerts that are true positives, by fault type")
    d.table(["fault_type", "collective TP alerts"], other_fault_tp(ev["alerts"]) or [["(none)", 0]])
    d.h("Collective false alarms (all)")
    d.table(["link", "start_utc", "rows", "label", "suppressed", "busy_hour (w. PRB >= 70 %)", "nearby incidents"],
            [[a["element_id"], datetime.fromtimestamp(a["signal_start_s"], timezone.utc).strftime("%Y-%m-%d %H:%M"),
              a["n_rows"], a["label"], a["suppressed"], a["busy_hour"], ", ".join(a["nearby"])]
             for a in ev["alerts"] if ce.is_false_alarm(a)] or [["(none)", "", "", "", "", "", ""]])
    d.h("Sensitivity (secondary, not the headline): a dedicated 60 s watermark",
        "The same frozen rule over the statistic rebuilt with a 60 s watermark, as a separate streaming flow with its own "
        "watermark would allow. The headline above uses the 120 s watermark of the table actually read.")
    d.table(*ttd_table(wm60["rows"]))
    d.table(["measure", "value"], [["false alarms per 100 healthy link-days", wm60["fa"]["false_alarms_per_100_link_days"]]])
    name = {"dev": "02_dev_reading.md", "holdout": "03_holdout_reading.md", "stream": "04_stream_reading.md"}[reading]
    d.write(name)
    summary = {"reading": reading, "freeze_sha": sha, "head_sha": head, "ttd": ttd_table(ev["rows"])[1], "fa": ev["fa"], "percell_fa": cell_fa,
               "added_pages": added_pages(ev["alerts"], cell_alerts), "other_tp": other_fault_tp(ev["alerts"]),
               "mirror": mirror, "wm60": ttd_table(wm60["rows"])[1]}
    (OUT / name.replace(".md", ".json")).write_text(json.dumps(summary, indent=1, default=str))


def rescore(wh: Warehouse, reading: str, note: str) -> None:
    """Re-score a reading from its STORED detections (the experiment table): no detection is recomputed and no KPI /
    health data of the run is read again. Used once, for the holdout, after the baseline-lookup fix in `fetch_before`."""
    run, lo, hi = READINGS[reading]
    tab = wh.frame(f"SELECT freeze_sha, element_id, signal_start_ts, signal_end_ts, available_ts, in_maintenance, "
                   f"w_prb_util_pct FROM {EXPERIMENT_TABLE} WHERE reading = '{reading}'")
    if tab.empty:
        sys.exit(f"no stored detections for {reading}")
    sha = tab.freeze_sha.iloc[0]
    tab["s0"], tab["s1"], tab["av"] = _secs(tab.signal_start_ts), _secs(tab.signal_end_ts), _secs(tab.available_ts)
    dets = [{"source_run": run, "element_id": r.element_id, "signal_start_s": r.s0, "signal_end_s": r.s1,
             "available_s": r.av, "in_maintenance": bool(r.in_maintenance),
             "w_prb_util_pct": None if pd.isna(r.w_prb_util_pct) else float(r.w_prb_util_pct)} for r in tab.itertuples()]
    ctx = Context(wh, reading)
    ev = evaluate(ctx, dets)
    cell_fa, cell_alerts = percell_false_alarms(ctx, fetch_percell(wh, reading))
    name = {"dev": "02b_dev_rescore.md", "holdout": "03b_holdout_rescore.md", "stream": "04b_stream_rescore.md"}[reading]
    d = Doc(f"Step 6: {reading} reading re-scored from its stored detections", f"""
- reading `{reading}` (`{run}`, {lo} .. {hi}); {len(dets)} detections read back from `{EXPERIMENT_TABLE}`, as written by the
  single scoring run with the rule frozen at `{sha}`. **No detection was recomputed and no KPI / health row of `{run}` was
  read again.** Only the scoring changed.
- {note.strip()}
- scored incidents: {len(ctx.scored)}; healthy link-days: {ctx.link_days:.1f}.
""")
    d.h(f"Time to detect, {FAULT} (n = {len(ctx.scored)})", "Undetected incidents count against 'within 5 min' but not in "
        "the percentiles.")
    d.table(*ttd_table(ev["rows"]))
    d.h("Per incident")
    d.table(["incident_id", "link", "n_cells", "before_ttd_s", "collective_ttd_s", "combined_ttd_s"],
            [[r["incident_id"], r["root_element_id"], r["n_desc_cells"], _r(r["before_ttd_s"]),
              _r(r["collective_ttd_s"]), _r(r["combined_ttd_s"])] for r in ev["rows"]])
    d.h("False-alarm cost (does not use the per-cell first detection, so unchanged by the fix)")
    d.table(["measure", "collective", "per-cell KPI rules (today), grouped per link"],
            [[k, ev["fa"][k], cell_fa.get(k)] for k in ev["fa"]])
    d.table(["measure", "value"], [["collective false alarms on a link with no per-cell alert within 10 min (new pages)",
                                    added_pages(ev["alerts"], cell_alerts)]])
    d.h("Collective alerts that are true positives, by fault type")
    d.table(["fault_type", "collective TP alerts"], other_fault_tp(ev["alerts"]) or [["(none)", 0]])
    d.write(name)
    (OUT / name.replace(".md", ".json")).write_text(json.dumps(
        {"reading": reading, "freeze_sha": sha, "ttd": ttd_table(ev["rows"])[1], "fa": ev["fa"], "percell_fa": cell_fa,
         "added_pages": added_pages(ev["alerts"], cell_alerts), "other_tp": other_fault_tp(ev["alerts"])},
        indent=1, default=str))


def mirror_check_stats(wh: Warehouse, reading: str, stats: pd.DataFrame) -> tuple[list[str], list[list]]:
    """Recompute the parent-minute statistic in Python (`windows.parent_health`) from the raw cell windows of one
    hour (12:00 UTC on the first day; 2 h into the 6-hour stream) and compare it with the SQL statistic."""
    run, lo, _hi = READINGS[reading]
    hour = pd.Timestamp(lo) + pd.Timedelta(hours=2 if reading == "stream" else 12)
    h0, h1 = hour.strftime("%Y-%m-%dT%H:%M:%SZ"), (hour + pd.Timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ms = detection.COLLECTIVE_METRICS
    cells = wh.frame(f"""
        SELECT source_run, cell_id, site_id, backhaul_id, router_id, window_start, window_end, evidence_ts, flags,
               active_users, prb_util_pct, n_late_reports, {", ".join(f"{m}, b_{m}_mean, b_{m}_std" for m in ms)}
        FROM {HEALTH} WHERE source_run = '{run}' AND window_start >= '{h0}' AND window_start < '{h1}'""")
    mw = wh.frame(f"SELECT element_id, planned_start_ts, planned_end_ts FROM {MAINT} WHERE source_run = '{run}'")
    mw["a"], mw["b"] = _secs(mw["planned_start_ts"]), _secs(mw["planned_end_ts"])
    cells["window_start_s"], cells["window_end_s"] = _secs(cells["window_start"]), _secs(cells["window_end"])
    cells["evidence_s"] = _secs(cells["evidence_ts"])
    spans: dict[str, list[tuple[float, float]]] = {}
    for m in mw.itertuples():
        spans.setdefault(m.element_id, []).append((m.a, m.b))
    cells["in_maintenance"] = [any(a < we and b > ws for e in (si, bi, ri) for a, b in spans.get(e, ()))
                               for si, bi, ri, ws, we in zip(cells.site_id, cells.backhaul_id, cells.router_id,
                                                             cells.window_start_s, cells.window_end_s, strict=True)]
    recs = cells.to_dict("records")
    for r in recs:
        r["flags"] = list(r["flags"]) if r["flags"] is not None else []
        for k, v in list(r.items()):
            if isinstance(v, float) and pd.isna(v):
                r[k] = None
    _members, n_desc = fetch_topology(wh)
    py = {(r["parent_id"], r["window_start_s"]): r for r in windows.parent_health(recs, n_desc)}
    sq = stats[(stats.window_start_s >= _iso_s(h0)) & (stats.window_start_s < _iso_s(h1))]
    keys_sql = {(r.parent_id, r.window_start_s) for r in sq.itertuples()}
    diffs = {c: 0.0 for c in ["reporting_share", "available_s"] + [f"{p}_{m}" for m in ms
                                                                     for p in ("wz", "wdelta", "frac_z1")]}
    n_int_mismatch = 0
    for r in sq.to_dict("records"):
        p = py.get((r["parent_id"], r["window_start_s"]))
        if p is None:
            continue
        n_int_mismatch += int(p["n_reporting_cells"] != r["n_reporting_cells"])
        for c in diffs:
            a, b = p.get(c), r.get(c)
            if a is None or b is None or pd.isna(b):
                if not ((a is None) and (b is None or pd.isna(b))):
                    diffs[c] = float("inf")
                continue
            diffs[c] = max(diffs[c], abs(float(a) - float(b)))
    rows = [["hour", f"{h0} .. {h1}"], ["link-minutes (SQL)", len(keys_sql)], ["link-minutes (Python)", len(py)],
            ["keys only in one side", len(keys_sql ^ set(py))], ["n_reporting_cells mismatches", n_int_mismatch]]
    rows += [[f"max abs diff {c}", f"{v:.3g}"] for c, v in diffs.items()]
    return ["check", "value"], rows


def verify(wh: Warehouse, since: str) -> None:
    """Evidence that the experiment changed nothing that existed: only the new table was written since `since`, the
    published step-2 backhaul numbers are unchanged, and the experiment table holds exactly one row set per reading."""
    d = Doc("Step 6: nothing existing changed", f"""
Checks after the three readings. `since` = {since} (before this step's first query).""")
    for title, sql in [
        ("Tables / views in the netmon_* schemas altered since the step began",
         f"SELECT table_schema, table_name, table_type, last_altered FROM {CAT}.information_schema.tables "
         f"WHERE table_schema LIKE 'netmon%' AND last_altered >= '{since}' ORDER BY 1, 2"),
        ("Published step-2 BACKHAUL_DEGRADATION figures (eval_ttd_summary), unchanged",
         f"SELECT source_run, n_incidents, impact_median_ttd_s, impact_p90_ttd_s, impact_within_5min_pct, "
         f"median_evidence_lag_s FROM {CAT}.netmon_eval.eval_ttd_summary WHERE fault_type = '{FAULT}' ORDER BY 1"),
        ("Experiment table: one row set per reading, all from the frozen rule",
         f"SELECT reading, freeze_sha, count(*) AS n_detections, count(DISTINCT detection_id) AS n_ids, "
         f"min(scored_at) AS first_scored, max(scored_at) AS last_scored FROM {EXPERIMENT_TABLE} GROUP BY 1, 2 ORDER BY 1"),
        ("Experiment table history (every write; the holdout was written once)",
         f"SELECT version, timestamp, operation, operationMetrics.numOutputRows AS rows_written, "
         f"operationMetrics.numDeletedRows AS rows_deleted, operationMetrics.numTargetRowsInserted AS rows_merged, "
         f"operationParameters.predicate AS predicate FROM (DESCRIBE HISTORY {EXPERIMENT_TABLE}) ORDER BY version"),
    ]:
        df = wh.frame(sql)
        d.h(title)
        d.sql(sql)
        d.table(list(df.columns), df.astype(object).where(df.notna(), None).values.tolist())
    d.write("05_no_change.md")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["calibrate", "score", "rescore", "verify"])
    ap.add_argument("--note", default="", help="rescore: why the reading is re-scored")
    ap.add_argument("--since", default="2026-11-07T00:00:00Z", help="verify: start of this step")
    ap.add_argument("--reading", choices=list(READINGS))
    ap.add_argument("--replace", action="store_true", help="re-score dev or stream (never the holdout)")
    ap.add_argument("--profile", default="febar")
    ap.add_argument("--warehouse", default="d7fa853ab15b20a3")
    a = ap.parse_args()
    wh = Warehouse(a.profile, a.warehouse)
    if a.command == "calibrate":
        calibrate(wh)
    elif a.command == "verify":
        verify(wh, a.since)
    elif a.command == "rescore":
        if not a.reading or not a.note:
            ap.error("rescore needs --reading and --note")
        rescore(wh, a.reading, a.note)
    else:
        if not a.reading:
            ap.error("score needs --reading")
        score(wh, a.reading, a.replace)


if __name__ == "__main__":
    main()
