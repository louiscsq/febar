"""Follow one real fault through every layer of the build and write the text evidence (evidence/step5/03*_trace_*.md).

    python scripts/trace_end_to_end.py --profile febar --warehouse <id> --incident RCA-c7276c3238a27971 \
        --out 03_trace_site_power.md --title "SITE-NSW-00105 site power outage"

Hops, each with its real output: raw JSON line in the landing Volume -> bronze row (`_source_file`) -> silver row and
its data-quality outcome (the pipeline's own drop rules re-evaluated on the raw line, quarantine check) -> gold
customer-impact detections and the operational time to detect -> the RCA ranker's scores (stored live scores and a
fresh call to the `banksia-rca-ranker` endpoint with the same features) -> Lakebase rows read with psycopg
(`lb_open_incidents`, `lb_element_status`, `lb_incident_ai_latest`, the app's SMS reviews) -> Gen AI summary and SMS
draft in Unity Catalog -> the deployed app's API (incident panel and topology pinpoint) -> a Genie answer asked through
the app -> Unity Catalog lineage between the tables -> finally, and only as a check, the generator's ground truth.

Identity: the capturing user (CLI OAuth); the app is called with the same user's token through the Apps proxy.
No secret is read or written.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from capture_evidence import Runner, md_table  # noqa: E402

from netmon_pipeline import rules  # noqa: E402
from netmon_pipeline.rca.features import FEATURE_COLUMNS  # noqa: E402

EVIDENCE = Path(__file__).resolve().parents[1] / "evidence" / "step5"
CAT = "telco_netmon_febar_catalog"
B, S, G, R, AI, NOC, EV = (f"{CAT}.{s}" for s in ("netmon_bronze", "netmon_silver", "netmon_gold", "netmon_rca",
                                                    "netmon_genai", "netmon_noc", "netmon_eval"))
ENDPOINT = "banksia-rca-ranker"
INSTANCE, DATABASE = "banksia-netmon-lakebase", "netmon_serving"


class Trace:
    def __init__(self, r: Runner, title: str, incident: str):
        self.r, self.n = r, 0
        self.parts = [f"# End-to-end trace: {title}\n",
                      f"Captured {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC from workspace profile `{r.profile}` "
                      f"by `scripts/trace_end_to_end.py --incident {incident}`. Every block below is the real output "
                      "of that hop; nothing is hand-edited.\n"]

    def hop(self, title: str, why: str) -> None:
        self.n += 1
        self.parts.append(f"## {self.n}. {title}\n\n{why.strip()}\n")

    def sql(self, sql: str, note: str = "", max_cell: int = 110) -> list[dict]:
        cols, rows = self.r.sql(sql)
        self.parts += [note.strip() + "\n" if note else "", "```sql\n" + sql.strip() + "\n```\n",
                       md_table(cols, rows, max_cell=max_cell)]
        return [dict(zip(cols, row, strict=True)) for row in rows]

    def code(self, obj, lang: str = "json", note: str = "") -> None:
        body = obj if isinstance(obj, str) else json.dumps(obj, indent=2, default=str)
        self.parts += [note.strip() + "\n" if note else "", f"```{lang}\n{body}\n```\n"]

    def table(self, rows: list[dict], note: str = "", max_cell: int = 110) -> None:
        cols = list(rows[0]) if rows else []
        self.parts += [note.strip() + "\n" if note else "",
                       md_table(cols, [[x.get(c) for c in cols] for x in rows], max_cell=max_cell)]

    def text(self, s: str) -> None:
        self.parts.append(s.strip() + "\n")

    def write(self, name: str) -> Path:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        p = EVIDENCE / name
        p.write_text("\n".join(x for x in self.parts if x))
        print("wrote", p)
        return p


def cli_token(profile: str) -> str:
    out = subprocess.run(["databricks", "auth", "token", "-p", profile], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)["access_token"]


def app_call(url: str, token: str, path: str, body: dict | None = None,
             extra_headers: dict | None = None) -> tuple[int, dict, float]:
    import httpx

    t0 = time.perf_counter()
    h = {"Authorization": f"Bearer {token}", **(extra_headers or {})}
    resp = (httpx.post(url + path, json=body, headers=h, timeout=240) if body is not None
            else httpx.get(url + path, headers=h, timeout=240))
    try:
        payload = resp.json()
    except ValueError:
        payload = {"raw": resp.text[:500]}
    return resp.status_code, payload, (time.perf_counter() - t0) * 1000


def pg_rows(w, sql: str, params: dict | None = None) -> list[dict]:
    import psycopg
    from psycopg.rows import dict_row

    inst = w.database.get_database_instance(INSTANCE)
    cred = w.database.generate_database_credential(request_id=str(uuid.uuid4()), instance_names=[INSTANCE])
    with psycopg.connect(host=inst.read_write_dns, port=5432, dbname=DATABASE, user=w.current_user.me().user_name,
                         password=cred.token, sslmode="require", row_factory=dict_row) as c:
        return list(c.execute(sql, params or {}).fetchall())


def topo_trim(t: dict) -> dict:
    g = t["graph"]
    return {"region": t["region"], "incident_id": t["incident_id"], "view": g["view"], "pinpoint": g["pinpoint"],
            "path": g["path"], "n_nodes_drawn": len(g["nodes"]), "n_edges": len(g["edges"]),
            "highlighted": [{k: n.get(k) for k in ("id", "element_type", "state", "highlight", "suspect_rank",
                                                   "suspect_score", "lat", "lon")}
                            for n in g["nodes"] if n.get("highlight")],
            "map_suspects": [p for p in t["map"] if p.get("suspect_rank")]}


def run(a) -> None:
    from databricks.sdk import WorkspaceClient

    r = Runner(a.profile, a.warehouse)
    w = WorkspaceClient(profile=a.profile)
    tok = cli_token(a.profile)
    t = Trace(r, a.title, a.incident)
    inc_id = a.incident

    inc = pg_rows(w, "SELECT * FROM netmon_rca.lb_open_incidents WHERE incident_id = %(i)s", {"i": inc_id})
    assert inc, f"{inc_id} is not an open incident in Lakebase"
    inc = inc[0]
    root, region, run_id = inc["suspect_1_id"], inc["region_code"], inc["source_run"]
    t.text(f"""
**The fault.** Incident `{inc_id}` in `{region}`, live feed (`source_run = '{run_id}'`). The root-cause ranker's
suspect 1 is `{root}` ({inc['suspect_1_type']}). The trace starts from the first customer-impact detection on that
element's subtree and walks back to the raw file, then forward to the operator's screen and Genie.
""")

    # ---- 1-4: raw -> bronze -> silver -> gold ------------------------------------------------------------------
    first = r.sql(f"""
        SELECT detection_id, signal_source, element_id, cell_id, record_id, signal_start_ts, evidence_ts,
               pipeline_latency_s, flags
        FROM {G}.gold_impact_detections
        WHERE source_run = '{run_id}' AND '{root}' IN (element_id, cell_id, site_id, backhaul_id, router_id)
          AND signal_start_ts BETWEEN timestamp'{inc['detected_ts']:%Y-%m-%d %H:%M:%S}' - INTERVAL 2 HOURS
                                  AND timestamp'{inc['detected_ts']:%Y-%m-%d %H:%M:%S}' + INTERVAL 10 MINUTES
        ORDER BY timestampadd(MILLISECOND, CAST(pipeline_latency_s * 1000 AS BIGINT), evidence_ts), signal_start_ts
        LIMIT 1""")
    d0 = dict(zip(first[0], first[1][0], strict=True))
    feed = "kpis" if d0["signal_source"] == "kpi" else "alarms"
    rec_id = d0["record_id"]

    t.hop("Raw file in the Unity Catalog Volume", f"""
The generator's live stream writes one JSON-lines micro-batch per feed per simulated minute into
`/Volumes/{CAT}/netmon_raw/landing/stream/`. The first detection on `{root}`'s subtree came from record `{rec_id}`
(feed `{feed}`). Its file, from the bronze row's `_source_file` (Auto Loader `_metadata.file_path`):""")
    br = r.sql(f"SELECT _source_file, _ingested_at FROM {B}.bronze_{feed} WHERE record_id = '{rec_id}' "
               f"AND _source_run = '{run_id}' LIMIT 1")
    src_file = br[1][0][0]
    content = w.files.download(src_file).contents.read().decode()
    lines = content.splitlines()
    line = next(ln for ln in lines if rec_id in ln)
    t.code(f"path:  {src_file}\nlines: {len(lines)} in the file\nline with {rec_id}:\n{line}", lang="text")
    raw = rules.parse_json_line(line)

    t.hop("Bronze (Auto Loader, explicit schema, lineage columns)", "The same record as bronze stores it:")
    t.sql(f"SELECT * EXCEPT (_rescued_data) FROM {B}.bronze_{feed} WHERE record_id = '{rec_id}' "
          f"AND _source_run = '{run_id}'")

    t.hop("Silver (typed, deduplicated, topology-joined) and its data-quality outcome", f"""
Silver parses the UTC timestamps, deduplicates on `record_id`, joins the topology and applies the drop
expectations of `netmon_pipeline.rules` (failures go to `silver_quarantine`). Re-evaluating the pipeline's own rule
predicates on the raw line above: failed drop rules = `{rules.failed_rules_py(feed, raw)}`, late
(`on_time` warn rule) = `{rules.is_late_py(feed, raw)}`. The silver row, the quarantine for this record (expected empty)
and what the quarantine caught from the same micro-batch file:""")
    cols = ("record_id, event_ts, availability_pct, attach_success_pct, rrc_setup_success_pct, latency_ms, "
            "is_late, lag_s, landed_ts, evidence_ts, cell_id, site_id, backhaul_id, router_id, region_code"
            if feed == "kpis" else
            "record_id, alarm_id, alarm_code, severity, element_id, element_type, event_ts, is_service_down, is_late, "
            "lag_s, landed_ts, evidence_ts, site_id, backhaul_id, router_id, region_code")
    t.sql(f"SELECT {cols} FROM {S}.silver_{feed} WHERE record_id = '{rec_id}' AND source_run = '{run_id}'")
    t.sql(f"SELECT count(*) AS n_quarantined FROM {S}.silver_quarantine WHERE record_id = '{rec_id}'")
    t.sql(f"""SELECT feed, failed_rules, count(*) AS n_rows FROM {S}.silver_quarantine
              WHERE _source_file = '{src_file}' GROUP BY ALL ORDER BY n_rows DESC""")

    t.hop("Gold: customer-impact detections and time to detect", f"""
Stateless per-record detection (`netmon_pipeline.detection`) turns degraded KPI records and element-down alarms
into `gold_impact_detections` rows. Detections on `{root}`'s subtree around the incident (first 12 by availability to
the NOC; `available_ts = evidence_ts + pipeline_latency_s`, the measured wall-clock pipeline latency):""")
    t.sql(f"""
        SELECT signal_source, element_id, cell_id, signal_start_ts, evidence_ts, pipeline_latency_s,
               timestampadd(MILLISECOND, CAST(pipeline_latency_s * 1000 AS BIGINT), evidence_ts) AS available_ts,
               flags, in_maintenance
        FROM {G}.gold_impact_detections
        WHERE source_run = '{run_id}' AND '{root}' IN (element_id, cell_id, site_id, backhaul_id, router_id)
          AND signal_start_ts BETWEEN timestamp'{inc['detected_ts']:%Y-%m-%d %H:%M:%S}' - INTERVAL 2 HOURS
                                  AND timestamp'{inc['detected_ts']:%Y-%m-%d %H:%M:%S}' + INTERVAL 10 MINUTES
        ORDER BY available_ts LIMIT 12""")
    t.sql(f"SELECT * FROM {NOC}.incident_detection_times WHERE incident_id = '{inc_id}'",
          note="The operational (ground-truth-free) timing the app and Genie show, from the `netmon_noc` view:")

    # ---- 5: RCA ranker -----------------------------------------------------------------------------------------
    t.hop("RCA ranker: stored live scores and a fresh endpoint call", f"""
The scoring job ranks every candidate element of the case with `rca_ranker@champion` (v{inc['model_version']}) and
publishes `open_incidents`. Below: the case's top candidates at its latest decision time as stored in
`rca_live_scores`, then the same feature rows (the model's {len(FEATURE_COLUMNS)} feature columns) sent to the
serving endpoint `{ENDPOINT}`.""")
    case = inc["case_id"]
    # rca_live_scores is append-only across scoring runs (one set of rows per model version that scored the case),
    # so select the version that published this incident.
    mv = inc["model_version"]
    cols_, rows_ = r.sql(f"""SELECT * FROM {R}.rca_live_scores WHERE case_id = '{case}' AND model_version = '{mv}'
                             AND decision_ts = (SELECT max(decision_ts) FROM {R}.rca_live_scores
                                                WHERE case_id = '{case}' AND model_version = '{mv}')
                             ORDER BY score DESC, element_id""")
    recs = [dict(zip(cols_, x, strict=True)) for x in rows_]
    t.table([{k: x[k] for k in ("decision_ts", "element_id", "element_type", "impacted_fraction", "silent_fraction",
                                 "n_alarms", "n_service_down_alarms", "score")} for x in recs[:5]],
            note=f"`rca_live_scores`, case `{case}`, model version {mv} ({len(recs)} candidates; "
                 f"open_incidents.n_candidates = {inc['n_candidates']}):")
    body = [{c: (None if x[c] is None else float(x[c])) for c in FEATURE_COLUMNS} for x in recs]
    t0 = time.perf_counter()
    resp = w.serving_endpoints.query(ENDPOINT, dataframe_records=body)
    ms = (time.perf_counter() - t0) * 1000
    ranked = sorted(({"element_id": x["element_id"], "element_type": x["element_type"],
                      "endpoint_p_root": round(float(p[1]), 4), "stored_score": round(float(x["score"]), 4)}
                     for x, p in zip(recs, resp.predictions, strict=True)), key=lambda z: -z["endpoint_p_root"])
    t.code({"endpoint": ENDPOINT, "request": {"dataframe_records": f"{len(body)} records x {len(FEATURE_COLUMNS)} "
                                              "features (first record below)", "first_record": body[0]},
            "latency_ms": round(ms), "response_top3": ranked[:3]})
    t.text(f"Endpoint top-1 `{ranked[0]['element_id']}` vs Lakebase suspect 1 `{root}`: "
           f"{'match' if ranked[0]['element_id'] == root else 'MISMATCH'}.")

    # ---- 6: Lakebase -------------------------------------------------------------------------------------------
    t.hop("Lakebase (Postgres, read with psycopg + OAuth)", """
The synced tables (Delta -> Postgres, TRIGGERED by the scoring and assistant jobs) the app reads on its hot path, and
the app's own SMS review table. Read here with psycopg as the capturing user:""")
    t.table([inc], note="`netmon_rca.lb_open_incidents`:")
    sus = [inc[f"suspect_{k}_id"] for k in (1, 2, 3) if inc.get(f"suspect_{k}_id")]
    t.table(pg_rows(w, """SELECT element_id, element_type, parent_id, state, rca_score, n_impacted_cells, n_desc_cells,
                                 silent_fraction, n_alarms, n_service_down_alarms, open_incident_id, suspect_rank
                          FROM netmon_rca.lb_element_status
                          WHERE element_id = ANY(%(s)s) OR parent_id = %(root)s ORDER BY suspect_rank NULLS LAST,
                          element_id""", {"s": sus, "root": root}),
            note="`netmon_rca.lb_element_status` (the suspects and the root's children):")
    t.table(pg_rows(w, """SELECT incident_id, summary_id, generated_at, likely_root_cause, fault_hypothesis, confidence,
                                 est_affected_subscribers, impacted_cells, impacted_sites, sms_draft_status, generated_by
                          FROM netmon_genai.lb_incident_ai_latest WHERE incident_id = %(i)s""", {"i": inc_id}),
            note="`netmon_genai.lb_incident_ai_latest`:")
    t.table(pg_rows(w, """SELECT review_id, decision, reviewed_by, reviewed_at, app_identity, sent_at, send_channel
                          FROM netmon_app.sms_draft_reviews WHERE incident_id = %(i)s ORDER BY reviewed_at""",
                    {"i": inc_id}), note="`netmon_app.sms_draft_reviews` (written by the app; empty until reviewed):")

    # ---- 7: Gen AI ---------------------------------------------------------------------------------------------
    t.hop("Gen AI NOC summary and customer SMS draft (Unity Catalog)", """
The assistant (`databricks-gpt-5-4-mini` through AI Gateway) wrote, for this incident, the summary and the SMS draft
(status `draft`, never sent). Latest versions:""")
    t.sql(f"""SELECT summary_id, generated_at, status, likely_root_cause, fault_hypothesis, confidence, summary,
                     next_steps_json, latency_ms, prompt_tokens, completion_tokens, noc_prompt_version
              FROM {AI}.incident_ai_summaries WHERE incident_id = '{inc_id}' ORDER BY generated_at DESC LIMIT 1""",
          max_cell=700)
    t.sql(f"""SELECT draft_id, generated_at, status, requires_human_approval, approved_by, sent_at, chars, text
              FROM {AI}.customer_notice_drafts WHERE incident_id = '{inc_id}' ORDER BY generated_at DESC LIMIT 1""",
          max_cell=400)

    # ---- 8: app --------------------------------------------------------------------------------------------------
    t.hop("The deployed app: incident panel and topology pinpoint", f"""
`{a.app_url}` called with the capturing user's token through the Databricks Apps proxy (the proxy forwards the user's
identity and on-behalf-of token to the app). Incident panel (`GET /api/incidents/{inc_id}`):""")
    code, body_, ms = app_call(a.app_url, tok, f"/api/incidents/{inc_id}")
    t.code({"http_status": code, "latency_ms": round(ms), "body": body_})
    code, topo, ms = app_call(a.app_url, tok, f"/api/regions/{region}/topology?incident_id={inc_id}")
    t.code({"http_status": code, "latency_ms": round(ms), "body (trimmed to the highlighted elements)": topo_trim(topo)},
           note=f"Topology for the incident (`GET /api/regions/{region}/topology?incident_id={inc_id}`):")

    # ---- 9: Genie ----------------------------------------------------------------------------------------------
    q = (f"For the open incident whose top suspect is {root}: what is the failing element, how long did it take to "
         "detect, and how many subscribers are affected?")
    t.hop("Genie, asked through the app", f"""
`POST /api/genie/ask` on the app, which calls the Genie Conversation API on the NOC space as the signed-in user.
Question: *{q}*""")
    code, ans, ms = app_call(a.app_url, tok, "/api/genie/ask", {"question": q})
    t.code({"http_status": code, "latency_ms": round(ms), "answer_text": ans.get("text"),
            "columns": ans.get("columns"), "rows": ans.get("rows"), "conversation_id": ans.get("conversation_id")})
    if ans.get("sql"):
        t.code(ans["sql"], lang="sql", note="SQL Genie generated and ran:")

    # ---- 10: lineage -------------------------------------------------------------------------------------------
    t.hop("Unity Catalog lineage linking the tables", """
Captured automatically by Unity Catalog (`system.access.table_lineage`, filtered to this workspace). Edges between the
tables this trace touched (the Volume -> bronze hop has a NULL source on this workspace and is shown by `_source_file`
above; Lakebase synced tables are written by their sync pipelines):""")
    wsid = w.get_workspace_id()
    names = [f"{B}.bronze_{feed}", f"{S}.silver_{feed}", f"{S}.silver_topology_nodes", f"{G}.gold_impact_detections",
             f"{G}.gold_cell_health_1m", f"{G}.gold_element_impact_5m", f"{R}.rca_live_scores", f"{R}.open_incidents",
             f"{R}.element_status", f"{R}.lb_open_incidents", f"{R}.lb_element_status", f"{AI}.incident_ai_summaries",
             f"{AI}.incident_ai_latest", f"{AI}.customer_notice_drafts", f"{AI}.lb_incident_ai_latest",
             f"{NOC}.open_incidents", f"{NOC}.incident_detection_times", f"{NOC}.incident_ai_summary",
             f"{NOC}.element_status"]
    inlist = ", ".join(f"'{n}'" for n in names)
    t.sql(f"""
        SELECT source_table_full_name AS source, target_table_full_name AS target, entity_type,
               max(event_time) AS last_seen, count(*) AS n_events
        FROM system.access.table_lineage
        WHERE workspace_id = '{wsid}' AND event_date >= current_date() - INTERVAL 60 DAYS
          AND target_table_full_name IN ({inlist}) AND source_table_full_name IN ({inlist})
        GROUP BY ALL ORDER BY target, source""", max_cell=90)

    t.text("""
**Across the job boundary.** The RCA scoring job and the Gen AI assistant read Delta into pandas and write back through
a Parquet scratch file, so Unity Catalog records their reads with a NULL target and their writes with a NULL (or Volume
path) source: there is no direct table-to-table edge into `rca_live_scores` / `open_incidents` / `incident_ai_latest`.
The link is still in `system.access.table_lineage`: the read and write events of one job run share `entity_run_id`.
Latest run of each job that writes the incident tables, with everything that run read and wrote:""")
    rows = t.sql(f"""
        WITH ev AS (
          SELECT entity_id, entity_run_id, event_time, source_table_full_name AS s, target_table_full_name AS t
          FROM system.access.table_lineage
          WHERE workspace_id = '{wsid}' AND event_date >= current_date() - INTERVAL 60 DAYS AND entity_type = 'JOB'),
        runs AS (
          SELECT entity_id AS job_id, entity_run_id AS job_run_id, max(event_time) AS last_seen,
                 array_sort(collect_set(s)) AS tables_read, array_sort(collect_set(t)) AS tables_written
          FROM ev GROUP BY 1, 2)
        SELECT * FROM runs
        WHERE array_contains(tables_written, '{R}.open_incidents')
           OR array_contains(tables_written, '{AI}.incident_ai_latest')
        QUALIFY row_number() OVER (PARTITION BY job_id ORDER BY last_seen DESC) = 1""", max_cell=900)
    names_ = {}
    for x in rows:
        try:
            names_[x["job_id"]] = w.jobs.get(int(x["job_id"])).settings.name
        except Exception:  # noqa: BLE001
            names_[x["job_id"]] = "?"
    t.text("Job IDs: " + ", ".join(f"`{k}` = `{v}`" for k, v in names_.items()) + ".")

    # ---- 11: final verification against ground truth (never shown by the app or Genie) ---------------------------
    t.hop("FINAL VERIFICATION against the generator's ground truth (not part of the operational path)", """
Everything above is operational: the app, the Genie space, the ranker's features and the assistant never read
`netmon_eval`, and no number above comes from it (enforced by `tests/test_no_ground_truth_surface.py`). This section
alone reads ground truth, after the fact, to confirm the trace followed a real fault:""")
    gt = t.sql(f"""SELECT incident_id, event_class, fault_type, root_element_ids, impact_start_ts, impact_end_ts,
                          is_censored, n_affected_cells, estimated_impacted_subscribers, description
                   FROM {EV}.eval_gt_incidents
                   WHERE source_run = '{run_id}' AND array_contains(root_element_ids, '{root}')
                     AND is_customer_impacting ORDER BY impact_start_ts DESC LIMIT 1""", max_cell=120)
    if gt:
        det = r.sql(f"SELECT first_detection_ts, time_to_detect_s FROM {NOC}.incident_detection_times "
                    f"WHERE incident_id = '{inc_id}'")
        fd = datetime.fromisoformat(det[1][0][0].replace("Z", "+00:00"))
        ops = float(det[1][0][1])
        st = datetime.fromisoformat(gt[0]["impact_start_ts"].replace("Z", "+00:00"))
        t.text(f"Ground-truth time to detect = first detection available ({fd:%H:%M:%S}) - true impact start "
               f"({st:%H:%M:%S}) = **{(fd - st).total_seconds():.0f} s** (5-minute SLA: "
               f"{'met' if (fd - st).total_seconds() <= 300 else 'missed'}), against the operational time to "
               f"detect of {ops:.0f} s shown by the app and Genie, which can only start at the first anomaly visible "
               "in the telemetry (a lower bound when a fault ramps up slowly before any KPI rule fires). The incident is `is_censored` when the "
               "live run ended before the fault cleared; censored incidents are excluded from the scored KPIs "
               "(`eval_ttd_summary`, an offline evaluation table), which is why this open incident is not in them.")
    t.write(a.out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="febar")
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--incident", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--app-url", default="https://banksia-noc-topology-7474648429104135.aws.databricksapps.com")
    run(ap.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
