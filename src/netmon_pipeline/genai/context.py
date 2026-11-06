"""Grounded incident context for the NOC assistant and the customer SMS drafts.

For one incident (an open incident of `netmon_rca.open_incidents`, or an evaluation case) the context is a
compact, structured dict built **only** from the build's own operational tables, as visible at the decision
time `as_of`:

| block | source |
|---|---|
| `incident` | the detection record: reference, region, time detected, decision time (`open_incidents` / the case) |
| `suspects` | the ranker's top-3 with calibrated scores and their detection-time signals (`rca_live_scores` / the scored candidate rows of the case: the same rows the ranker scored) |
| `suspects[].neighbourhood` | topology: parent chain, children by type, impacted children, element type, region, transport (`silver_topology_nodes`) |
| `alarms` | alarms on the suspects and their parents / children, raised in the last hour and arrived by `as_of` (`silver_alarms`), free text sanitised (`guards.sanitize_free_text`) |
| `kpi` | KPI deviation summary of the impacted cells over the last 15 visible 1-minute windows (`gold_cell_health_1m`) |
| `impact` | impacted cell / site counts and an affected-subscriber **count** by region and segment (cell urbanity), from connected users (`gold_cell_health_1m.active_users`) and sampled xDR failures (`gold_cell_sessions_5m`) |
| `maintenance`, `customer_eta` | the change calendar (`silver_maintenance_windows`): the only source of an ETA |

Hard rules (tested in tests/test_genai_context.py):

- **No per-subscriber data.** Only aggregate tables are read (no `silver_sessions`); every column is taken from an
  allowlist, so an IMSI / MSISDN / subscriber key column in an input frame can never reach the context; free text
  is redacted; `guards.assert_no_pii` scans the serialised context before any prompt is sent.
- **No ground truth.** No input is a ground-truth table and every key is checked against
  `rca.features.LABEL_COLUMNS`; label columns in the case rows (e.g. `is_root`) are ignored (tested: present,
  permuted or absent, the context is identical).
- **Nothing after `as_of`.** Windows and alarms count only if they had arrived (`evidence_ts <= as_of`).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from netmon_pipeline.genai import guards

CONTEXT_VERSION = "ctx-v1"
KPI_WINDOWS = 15  # last 15 visible 1-minute windows for the KPI summary
USERS_LOOKBACK_MIN = 60  # connected users before the impact: max over the last hour of visible windows
ALARM_LOOKBACK_MIN = 60
MAX_ALARMS = 25
MAX_LISTED_CHILDREN = 6

TOPOLOGY_COLUMNS = ["element_id", "element_type", "parent_id", "level", "region_code", "region", "urbanity",
                    "transport_medium", "technology", "lat", "lon", "timezone"]
SUSPECT_SIGNALS = {  # context key -> candidate feature column (rca.features.FEATURE_COLUMNS)
    "impacted_fraction": "impacted_fraction", "silent_fraction": "silent_fraction",
    "degraded_fraction": "degraded_fraction", "coverage_of_case": "coverage", "n_impacted_cells": "n_impacted_cells",
    "parent_impacted_fraction": "parent_impacted_fraction", "impacted_children_fraction": "impacted_children_fraction",
    "latency_z_now": "lat_now", "latency_z_slope15": "lat_slope15", "loss_z_now": "loss_now",
    "loss_z_slope15": "loss_slope15", "dl_throughput_z_now": "thr_now", "rrc_success_z_now": "rrc_now",
    "drop_rate_z_now": "drop_now", "attach_success_pct_now": "attach_now", "availability_pct_now": "avail_now",
    "prb_util_pct_now": "prb_now", "minutes_since_first_anomaly": "minutes_since_first_anomaly",
    "n_alarms": "n_alarms", "n_critical_alarms": "n_critical_alarms", "n_service_down_alarms": "n_service_down_alarms",
    "n_subtree_alarms": "n_subtree_alarms", "alarmed_children_fraction": "alarmed_children_fraction",
    "in_maintenance": "in_maintenance",
}
KPI_Z = {"latency": "latency_ms_z", "packet_loss": "packet_loss_pct_z", "dl_throughput": "dl_throughput_mbps_z",
         "rrc_success": "rrc_setup_success_pct_z", "drop_rate": "session_drop_rate_pct_z"}
HEALTH_COLUMNS = ["cell_id", "window_start", "evidence_ts", "is_degraded", "active_users", "availability_pct",
                  *KPI_Z.values()]
SESSION_COLUMNS = ["cell_id", "window_start", "window_end", "n_sessions", "n_setup_failed", "n_dropped",
                   "n_no_service", "n_subscribers_approx"]
ALARM_COLUMNS = ["alarm_id", "event_type", "element_id", "alarm_code", "severity", "event_ts", "evidence_ts",
                 "is_service_down", "additional_text"]


@dataclass
class IncidentRef:
    """The detection record. `suspects`: [(element_id, element_type, score)] in rank order (top-3)."""

    ref: str
    region_code: str
    as_of: pd.Timestamp  # decision time the suspects were scored at
    detected_ts: pd.Timestamp | None
    suspects: list[tuple[str, str, float]]
    model_version: str = ""
    alert_threshold: float | None = None


@dataclass
class ContextInputs:
    incident: IncidentRef
    case_rows: pd.DataFrame  # scored candidate rows of the case at `as_of` (rca ID + feature columns + score)
    topology: pd.DataFrame  # TOPOLOGY_COLUMNS (at least the region)
    alarms: pd.DataFrame = field(default_factory=pd.DataFrame)  # ALARM_COLUMNS
    health: pd.DataFrame = field(default_factory=pd.DataFrame)  # HEALTH_COLUMNS of (at least) the case's cells
    sessions: pd.DataFrame = field(default_factory=pd.DataFrame)  # SESSION_COLUMNS
    maintenance: pd.DataFrame = field(default_factory=pd.DataFrame)  # element_id, planned_start_ts, planned_end_ts
    xdr_sample_rate: float | None = None  # xDR sampling of the session feed (collection setting), for scaling


# ---------------------------------------------------------------------------------------------------

def _utc(x) -> pd.Timestamp | None:
    if x is None or (isinstance(x, float) and math.isnan(x)) or x is pd.NaT:
        return None
    t = pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _iso(t) -> str | None:
    t = _utc(t)
    return None if t is None else t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(v, nd: int = 2):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, nd)


def _digits(key: str) -> int:
    """Decimals in the context: fractions / shares 2, everything else (z-scores, %, counts, minutes) 1. Short numbers
    keep the prompt compact and stop the gateway's PII detector reading long decimals (e.g. `-10.292`) as phone
    numbers (measured: 3 / 40 dev prompts blocked at 3 decimals, 0 / 40 at this precision)."""
    return 2 if ("fraction" in key or "coverage" in key or key.startswith("share")) else 1


def _frame(df: pd.DataFrame | None, cols: list[str]) -> pd.DataFrame:
    """Allowlisted columns only (missing ones as null): nothing else of an input frame can reach the context."""
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame(index=df.index)
    for c in cols:
        out[c] = df[c] if c in df.columns else None
    for c in ("window_start", "window_end", "evidence_ts", "event_ts", "planned_start_ts", "planned_end_ts"):
        if c in out.columns and len(out):
            out[c] = pd.to_datetime(out[c], utc=True)
    return out


class _Tree:
    def __init__(self, topo: pd.DataFrame):
        t = _frame(topo, TOPOLOGY_COLUMNS).drop_duplicates("element_id").set_index("element_id", drop=False)
        self.t = t
        self.parent = {k: (v if isinstance(v, str) and v else None) for k, v in t["parent_id"].items()}
        self.children: dict[str, list[str]] = {}
        for k, p in self.parent.items():
            if p:
                self.children.setdefault(p, []).append(k)
        cells = t.index[t["element_type"] == "CELL"]
        self.n_cells: dict[str, int] = {}
        for c in cells:
            for a in self.chain(c):
                self.n_cells[a] = self.n_cells.get(a, 0) + 1

    def chain(self, eid: str) -> list[str]:
        out, e = [], eid
        while e is not None and e not in out:
            out.append(e)
            e = self.parent.get(e)
        return out

    def get(self, eid: str, col: str):
        if eid not in self.t.index:
            return None
        v = self.t.at[eid, col]
        return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


# ---------------------------------------------------------------------------------------------------

def impacted_cells(case_rows: pd.DataFrame) -> tuple[list[str], list[str]]:
    """(impacted cells, silent cells) of the case: cell candidates with an impacted / silent window now."""
    c = case_rows[case_rows["level"] == 5] if "level" in case_rows else case_rows.iloc[0:0]
    imp = sorted(c.loc[c["n_impacted_cells"].fillna(0) > 0, "element_id"].unique())
    sil = sorted(c.loc[c["silent_fraction"].fillna(0) >= 1.0, "element_id"].unique())
    return imp, sil


def _suspects(inp: IncidentRef, rows: pd.DataFrame, tree: _Tree, impacted: set[str]) -> list[dict]:
    by_el = rows.drop_duplicates("element_id").set_index("element_id") if len(rows) else pd.DataFrame()
    imp_count: dict[str, int] = {}
    for c in impacted:
        for a in tree.chain(c):
            imp_count[a] = imp_count.get(a, 0) + 1
    out = []
    for rank, (eid, etype, score) in enumerate(inp.suspects, start=1):
        r = by_el.loc[eid] if eid in by_el.index else None
        signals = {k: (None if r is None else _num(r.get(col), _digits(k))) for k, col in SUSPECT_SIGNALS.items()}
        for k in signals:
            if k.startswith("n_") and signals[k] is not None:
                signals[k] = int(round(signals[k]))  # counts as integers (also: `168.0` read as a phone number)
        if signals.get("in_maintenance") is not None:
            signals["in_maintenance"] = bool(signals["in_maintenance"])
        anc = tree.chain(eid)[1:]
        kids = tree.children.get(eid, [])
        kid_types: dict[str, int] = {}
        for k in kids:
            kt = tree.get(k, "element_type") or "UNKNOWN"
            kid_types[kt] = kid_types.get(kt, 0) + 1
        imp_kids = sorted((k for k in kids if imp_count.get(k, 0) > 0), key=lambda k: (-imp_count[k], k))
        out.append({
            "rank": rank, "element_id": eid, "element_type": etype or tree.get(eid, "element_type"),
            "ranker_score": _num(score, 2), "signals": signals,
            "neighbourhood": {
                "region_code": tree.get(eid, "region_code"),
                "parent": None if not anc else {"element_id": anc[0], "element_type": tree.get(anc[0], "element_type")},
                "ancestors": [{"element_id": a, "element_type": tree.get(a, "element_type")} for a in anc],
                "n_children": len(kids), "children_by_type": kid_types,
                "n_impacted_children": len(imp_kids),
                "impacted_children": [{"element_id": k, "element_type": tree.get(k, "element_type"),
                                       "n_impacted_cells": imp_count[k]} for k in imp_kids[:MAX_LISTED_CHILDREN]],
                "n_desc_cells": tree.n_cells.get(eid, 0), "n_impacted_desc_cells": imp_count.get(eid, 0),
                "transport_medium": tree.get(eid, "transport_medium"), "urbanity": tree.get(eid, "urbanity"),
                "technology": tree.get(eid, "technology"),
            },
        })
    return out


def _alarms(alarms: pd.DataFrame, focus: set[str], tree: _Tree, as_of: pd.Timestamp) -> tuple[list[dict], dict]:
    a = _frame(alarms, ALARM_COLUMNS)
    a = a[a["evidence_ts"].notna() & (a["evidence_ts"] <= as_of)]
    raises = a[(a["event_type"] == "RAISE") & (a["event_ts"] >= as_of - pd.Timedelta(minutes=ALARM_LOOKBACK_MIN))]
    clears = set(a.loc[a["event_type"] == "CLEAR", "alarm_id"])
    raises = raises[raises["element_id"].isin(focus)].drop_duplicates("alarm_id")
    sev_rank = {"CRITICAL": 0, "MAJOR": 1, "MINOR": 2, "WARNING": 3}
    raises = raises.assign(is_active_=~raises["alarm_id"].isin(clears),
                           sev_rank_=raises["severity"].map(sev_rank).fillna(4))
    raises = raises.sort_values(["is_active_", "sev_rank_", "event_ts"], ascending=[False, True, False])
    listed, n_flagged = [], 0
    for r in raises.head(MAX_ALARMS).itertuples(index=False):
        text, flag = guards.sanitize_free_text(r.additional_text)
        n_flagged += int(flag)
        listed.append({"element_id": r.element_id, "element_type": tree.get(r.element_id, "element_type"),
                       "alarm_code": r.alarm_code, "alarm_severity": r.severity,
                       "raised_min_before_as_of": _num((as_of - r.event_ts).total_seconds() / 60, 1),
                       "active": bool(r.is_active_), "service_down": bool(r.is_service_down), "text": text,
                       "text_flagged": flag})
    codes = raises.groupby("alarm_code").size().sort_values(ascending=False)
    summary = {"n_alarms_in_scope": int(len(raises)), "n_active": int(raises["is_active_"].sum()),
               "n_listed": len(listed), "n_text_flagged": n_flagged,
               "by_code": {k: int(v) for k, v in codes.head(12).items()}}
    return listed, summary


def _kpi(health: pd.DataFrame, cells: list[str], silent: list[str], as_of: pd.Timestamp) -> dict:
    h = _frame(health, HEALTH_COLUMNS)
    h = h[h["cell_id"].isin(cells) & h["evidence_ts"].notna() & (h["evidence_ts"] <= as_of)]
    if h.empty:
        return {"n_cells": len(cells), "n_silent_cells": len(silent), "n_windows": 0}
    last = sorted(h["window_start"].unique())[-KPI_WINDOWS:]
    w = h[h["window_start"].isin(last)]
    half = len(last) // 2
    early, late = w[w["window_start"].isin(last[:half])], w[w["window_start"].isin(last[half:])]
    med = {k: _num(w[c].astype(float).median(), 1) for k, c in KPI_Z.items()}
    trend = {k: _num(late[c].astype(float).median() - early[c].astype(float).median(), 1)
             for k, c in KPI_Z.items()} if half else {}
    latest = w[w["window_start"] == last[-1]]
    return {"n_cells": len(cells), "n_silent_cells": len(silent), "n_windows": len(last),
            "window_minutes": len(last), "first_window": _iso(last[0]), "last_window": _iso(last[-1]),
            "share_cells_degraded_latest_window": _num(latest["is_degraded"].astype(float).mean(), 2),
            "median_z": med, "z_change_second_half_vs_first_half": trend,
            "median_availability_pct": _num(w["availability_pct"].astype(float).median(), 1)}


def _impact(tree: _Tree, cells: list[str], health: pd.DataFrame, sessions: pd.DataFrame, as_of: pd.Timestamp,
            region_code: str, xdr_rate: float | None) -> dict:
    h = _frame(health, HEALTH_COLUMNS)
    h = h[h["cell_id"].isin(cells) & h["evidence_ts"].notna() & (h["evidence_ts"] <= as_of)
          & (h["window_start"] >= as_of - pd.Timedelta(minutes=USERS_LOOKBACK_MIN))]
    users = h.groupby("cell_id")["active_users"].max().astype(float) if len(h) else pd.Series(dtype=float)
    seg_rows: dict[tuple[str, str], dict] = {}
    for c in cells:
        reg = tree.get(c, "region_code") or region_code
        seg = tree.get(c, "urbanity") or "unknown"
        d = seg_rows.setdefault((reg, seg), {"region_code": reg, "segment": seg, "n_cells": 0,
                                            "est_affected_subscribers": 0.0, "n_cells_without_user_data": 0})
        d["n_cells"] += 1
        u = users.get(c)
        if u is None or np.isnan(u):
            d["n_cells_without_user_data"] += 1
        else:
            d["est_affected_subscribers"] += u
    segs = sorted(seg_rows.values(), key=lambda d: (d["region_code"], -d["est_affected_subscribers"]))
    for d in segs:
        d["est_affected_subscribers"] = int(round(d["est_affected_subscribers"] / 10.0) * 10)
    sites = {tree.get(c, "parent_id") for c in cells} - {None}
    s = _frame(sessions, SESSION_COLUMNS)
    s = s[s["cell_id"].isin(cells) & s["window_end"].notna() & (s["window_end"] <= as_of)
          & (s["window_start"] >= as_of - pd.Timedelta(minutes=15))]
    failed = int(s[["n_setup_failed", "n_dropped"]].fillna(0).to_numpy().sum()) if len(s) else 0
    sess = {"window_minutes": 15, "sampled_sessions": int(s["n_sessions"].fillna(0).sum()) if len(s) else 0,
            "sampled_failed_or_dropped": failed,
            "sampled_no_service": int(s["n_no_service"].fillna(0).sum()) if len(s) else 0}
    if xdr_rate:
        sess["xdr_sample_rate"] = xdr_rate
        sess["est_failed_or_dropped_sessions"] = int(round(failed / xdr_rate / 10.0) * 10)
    regions = sorted({d["region_code"] for d in segs} or {region_code})
    return {"n_impacted_cells": len(cells), "n_impacted_sites": len(sites), "regions": regions,
            "est_affected_subscribers_total": int(sum(d["est_affected_subscribers"] for d in segs)),
            "by_region_segment": segs, "estimate_method": "max connected users per impacted cell over the last hour "
                                                          "of visible 1-minute windows, rounded to 10",
            "sessions_last_15min": sess}


def _maintenance(maint: pd.DataFrame, elements: set[str], as_of: pd.Timestamp) -> dict:
    m = _frame(maint, ["element_id", "planned_start_ts", "planned_end_ts"])
    m = m[m["element_id"].isin(elements) & (m["planned_start_ts"] <= as_of) & (m["planned_end_ts"] >= as_of)]
    if m.empty:
        return {"in_planned_window": False, "elements": [], "planned_end": None}
    return {"in_planned_window": True, "elements": sorted(m["element_id"].unique()),
            "planned_end": _iso(m["planned_end_ts"].max())}


def _localities(tree: _Tree, cells: list[str], region_code: str) -> list[str]:
    """Customer-facing area names: the region's population centres nearest to the impacted sites."""
    try:
        from netmon_datagen.topology import REGION_BY_CODE
    except ImportError:  # the generator package ships in the same wheel; be defensive anyway
        return []
    reg = REGION_BY_CODE.get(region_code)
    if reg is None:
        return []
    counts: dict[str, int] = {}
    for c in cells:
        lat, lon = tree.get(c, "lat"), tree.get(c, "lon")
        if lat is None or lon is None:
            continue
        k = math.cos(math.radians(float(lat)))
        hub = min(reg.hubs, key=lambda h: (h.lat - float(lat)) ** 2 + ((h.lon - float(lon)) * k) ** 2)
        counts[hub.name] = counts.get(hub.name, 0) + 1
    return [n for n, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:2]]


def build_context(inp: ContextInputs) -> dict:
    """The grounded context (JSON-serialisable dict). Raises if PII or a label key would reach it."""
    i = inp.incident
    as_of = _utc(i.as_of)
    tree = _Tree(inp.topology)
    rows = inp.case_rows
    cells, silent = impacted_cells(rows)
    sus = _suspects(i, rows, tree, set(cells))
    focus = set()
    for s in i.suspects:
        e = s[0]
        focus.add(e)
        p = tree.parent.get(e)
        if p:
            focus.add(p)
        focus.update(tree.children.get(e, []))
    alarms, alarm_summary = _alarms(inp.alarms, focus, tree, as_of)
    minutes_anom = None
    if len(rows) and "minutes_since_first_anomaly" in rows:
        minutes_anom = _num(rows["minutes_since_first_anomaly"].max(), 1)
    det = _utc(i.detected_ts)
    maint = _maintenance(inp.maintenance, focus, as_of)
    region_name = tree.get(i.suspects[0][0], "region") if i.suspects else None
    tz = tree.get(i.suspects[0][0], "timezone") if i.suspects else None
    ctx = {
        "context_version": CONTEXT_VERSION,
        "incident": {
            "ref": i.ref, "region_code": i.region_code, "region_name": region_name, "timezone": tz,
            "as_of": _iso(as_of), "detected_at": _iso(det),
            "minutes_since_detected": None if det is None else _num((as_of - det).total_seconds() / 60, 1),
            "minutes_since_first_anomaly": minutes_anom, "ranker_model_version": str(i.model_version),
            "ranker_alert_threshold": _num(i.alert_threshold, 2), "n_candidates_ranked": int(rows["element_id"].nunique())
            if len(rows) else 0,
        },
        "suspects": sus,
        "alarms": alarms,
        "alarm_summary": alarm_summary,
        "kpi": _kpi(inp.health, cells, silent, as_of),
        "impact": _impact(tree, cells, inp.health, inp.sessions, as_of, i.region_code, inp.xdr_sample_rate),
        "customer_areas": _localities(tree, cells, i.region_code),
        "maintenance": maint,
        "customer_eta": maint["planned_end"] if maint["in_planned_window"] else None,
    }
    guards.assert_no_pii(to_json(ctx))
    assert_no_label_keys(ctx)
    return ctx


def known_elements(ctx: dict) -> set[str]:
    """Every element ID present in the context (the hallucination guard's allowlist)."""
    out: set[str] = set()
    for s in ctx.get("suspects", []):
        out.add(s["element_id"])
        nb = s.get("neighbourhood") or {}
        out.update(a["element_id"] for a in nb.get("ancestors", []))
        out.update(c["element_id"] for c in nb.get("impacted_children", []))
    out.update(a["element_id"] for a in ctx.get("alarms", []))
    out.update((ctx.get("maintenance") or {}).get("elements", []))
    return out


def suspect_ids(ctx: dict) -> list[str]:
    return [s["element_id"] for s in ctx.get("suspects", [])]


def assert_no_label_keys(ctx: dict) -> None:
    from netmon_pipeline.rca.features import LABEL_COLUMNS

    bad = set(LABEL_COLUMNS) & set(all_keys(ctx))
    if bad:
        raise ValueError(f"ground-truth / label keys in the context: {sorted(bad)}")


def all_keys(obj) -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(k)
            out.extend(all_keys(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(all_keys(v))
    return out


def resolve_path(ctx: dict, path: str):
    """Value at a dotted path with list indices, e.g. `suspects[0].signals.latency_z_now`; KeyError if absent."""
    cur = ctx
    for part in path.replace("]", "").replace("[", ".").split("."):
        if part == "":
            continue
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            cur = cur[part]
        else:
            raise KeyError(path)
    return cur


def to_json(ctx: dict) -> str:
    return json.dumps(ctx, separators=(",", ":"), sort_keys=False, default=str)


def customer_view(ctx: dict) -> dict:
    """What the SMS drafter sees: no element IDs, no scores, no internal jargon, only customer-relevant facts."""
    k = ctx.get("kpi") or {}
    z = k.get("median_z") or {}
    n_cells = max(1, int(k.get("n_cells") or 0))
    silent_share = (k.get("n_silent_cells") or 0) / n_cells
    avail = k.get("median_availability_pct")
    effects = []
    if silent_share >= 0.5 or (avail is not None and avail < 50):
        effects.append("no mobile service")
    elif (z.get("latency") or 0) >= 2 or (z.get("packet_loss") or 0) >= 2 or (z.get("dl_throughput") or 0) <= -2:
        effects.append("slow mobile data")
    if (z.get("rrc_success") or 0) <= -2 or (z.get("drop_rate") or 0) >= 2:
        effects.append("calls and data may drop or fail to connect")
    if not effects:
        effects.append("intermittent mobile service")
    imp = ctx.get("impact") or {}
    regions = []
    for reg in imp.get("regions") or [ctx["incident"]["region_code"]]:
        segs = [d for d in imp.get("by_region_segment", []) if d["region_code"] == reg]
        regions.append({"region_code": reg,
                        "region_name": ctx["incident"].get("region_name") if reg == ctx["incident"]["region_code"]
                        else reg,
                        "areas": ctx.get("customer_areas") or [],
                        "est_affected_customers": int(sum(d["est_affected_subscribers"] for d in segs)),
                        "segments": sorted({d["segment"] for d in segs})})
    return {"brand": "Banksia Mobile", "service_effect": effects, "regions": regions,
            "timezone": ctx["incident"].get("timezone"), "eta": ctx.get("customer_eta"),
            "detected_at": ctx["incident"].get("detected_at") or ctx["incident"].get("as_of")}
