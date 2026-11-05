"""Evaluation of the root-cause ranker against ground truth, side by side with the step-2 localiser.

Two stages, and ground truth only enters the second:

1. **Score (GT-free).** `case_outputs` turns the scored candidate rows of every case into what the live scorer
   publishes: per case and 1-minute decision time, the ranked top-k elements with their scores, plus the case's
   own evidence (its impacted cells and service-down-alarmed elements). It reads only the ID and feature
   columns and the score; label columns are dropped before anything is ranked (tested: removing or permuting
   them changes nothing). The step-2 heuristic is turned into outputs from exactly the same cases.
2. **Match (after scoring).** `match_outputs` attributes outputs to ground-truth incidents: same run and
   region, decision time in the incident's window, and case evidence overlapping the incident footprint. Per
   incident and decision time the *primary* output is the matched case with the largest overlap. Matching only
   picks which already-ranked outputs belong to an incident; it never adds, removes or re-ranks candidates.

Primary measures (scored incidents: customer-impacting, uncensored faults):

- **top-1 / top-3** (`rank_incidents`): the primary output at the first decision time at least 5 minutes after
  impact start (the SLA moment) that has a matched output, looking up to 15 minutes after impact start. A hit
  when the incident's valid root list contains its top-1 / one of its top-3.
- **early catch** (`early_catch`): over every 1-minute decision time from 5 minutes before impact start to
  impact end, the first time the primary output's top-1 is a valid root **and** its score is at least the
  validation-chosen threshold. Times are signed (`decision_ts - impact_start_ts`): a catch before the impact
  starts is negative and counted separately, never clipped to 0.

Non-oracle companion (`any_alert_at_sla`): the primary measures judge the case output that ground truth *picked*
(largest footprint overlap). The companion uses no footprint: at the same fixed decision time (the first decision
time at least 5 minutes after impact start), is **any** live alert of the incident's region (a case whose top-1
score is at least the threshold) naming a valid root? It is what a NOC reading every page at that minute would
see, without knowing which page belongs to which incident.

Secondary (reported, never optimised): **alert-level fault precision** (`alert_precision`): case top-1 elements
at or above the threshold, grouped and labelled with step 2's own definitions (`netmon_pipeline.scoring`); the
same code scores the step-2 detections of the same period.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from netmon_pipeline import scoring
from netmon_pipeline.rca.features import FEATURE_COLUMNS, ID_COLUMNS

SNAPSHOT_AFTER = pd.Timedelta(minutes=5)
SNAPSHOT_LIMIT = pd.Timedelta(minutes=15)
CATCH_PRE = pd.Timedelta(minutes=5)
CASE_KEYS = ["source_run", "case_id"]


# ---------------------------------------------------------------------------------------------------
# Stage 1: GT-free outputs
# ---------------------------------------------------------------------------------------------------

def heuristic_score(df: pd.DataFrame) -> pd.Series:
    """Step 2's topology heuristic (eval_rca_baseline) as a score on the same candidates: elements passing its
    filter (>= 80 % of descendant cells impacted, or a service-down alarm) first, then most impacted descendant
    cells, then higher in the tree."""
    ok = (df["impacted_fraction"] >= 0.8) | (df["n_service_down_alarms"] > 0)
    return ok.astype(float) * 1e6 + df["n_impacted_cells"].astype(float) - 0.001 * df["level"].astype(float)


def case_outputs(scored: pd.DataFrame, score: str = "score", k: int = 3) -> pd.DataFrame:
    """Per (source_run, case_id): decision_ts, region_code, top-k elements / types / scores (ranked by `score`,
    ties by element_id) and the case's evidence elements. Only ID / feature columns and `score` are read."""
    cols = list(dict.fromkeys([*ID_COLUMNS, *FEATURE_COLUMNS, score]))
    x = scored[cols].sort_values([*CASE_KEYS, score, "element_id"], ascending=[True, True, False, True],
                                 kind="stable")
    x["_rank"] = x.groupby(CASE_KEYS, sort=False).cumcount()
    top = x[x["_rank"] < k]
    g = top.groupby(CASE_KEYS, sort=False)
    out = g.agg(decision_ts=("decision_ts", "first"), region_code=("region_code", "first"),
                top_elements=("element_id", list), top_types=("element_type", list), top_scores=(score, list))
    out["top1_element"] = out["top_elements"].str[0]
    out["top1_score"] = out["top_scores"].str[0]
    ev = x[((x["level"] == 5) & (x["n_impacted_cells"] > 0)) | (x["n_service_down_alarms"] > 0)]
    out = out.join(ev.groupby(CASE_KEYS)["element_id"].agg(list).rename("evidence"))
    out["evidence"] = out["evidence"].map(lambda v: v if isinstance(v, list) else [])
    out["n_candidates"] = x.groupby(CASE_KEYS, sort=False).size()
    return out.reset_index()


# ---------------------------------------------------------------------------------------------------
# Stage 2: matching outputs to ground truth (after scoring)
# ---------------------------------------------------------------------------------------------------

def match_outputs(outputs: pd.DataFrame, incidents: pd.DataFrame) -> pd.DataFrame:
    """(incident, case output) pairs: same run and region, decision time in [impact_start - 5 min,
    impact_end + 10 min], case evidence overlapping the footprint. `overlap` = shared elements."""
    inc = incidents[incidents["is_scored"]]
    fp = inc[["source_run", "incident_id", "region_code", "footprint", "match_from", "match_to"]] \
        .explode("footprint").rename(columns={"footprint": "element_id"})
    ev = outputs[["source_run", "case_id", "region_code", "decision_ts", "evidence"]].explode("evidence") \
        .rename(columns={"evidence": "element_id"}).dropna(subset=["element_id"])
    m = ev.merge(fp, on=["source_run", "region_code", "element_id"])
    m = m[(m["decision_ts"] >= m["match_from"]) & (m["decision_ts"] <= m["match_to"])]
    m = m.groupby(["source_run", "incident_id", "case_id", "decision_ts"]).size().rename("overlap").reset_index()
    return m.merge(outputs.drop(columns=["region_code", "decision_ts", "evidence"]), on=CASE_KEYS)


def primary_outputs(matches: pd.DataFrame) -> pd.DataFrame:
    """Per (incident, decision time) the matched output with the largest overlap (ties: more candidates,
    then case_id), so an incident split over several cases is judged on one ranking per minute."""
    m = matches.sort_values(["source_run", "incident_id", "decision_ts", "overlap", "n_candidates", "case_id"],
                            ascending=[True, True, True, False, False, True])
    return m.drop_duplicates(["source_run", "incident_id", "decision_ts"])


def _scored_incidents(inc: pd.DataFrame) -> pd.DataFrame:
    return inc[inc["is_scored"]]


def rank_incidents(outputs: pd.DataFrame, incidents: pd.DataFrame) -> pd.DataFrame:
    """Per scored incident: the primary output at the first decision time >= impact_start + 5 min (up to + 15
    min) and whether its top-1 / top-3 contains a valid root."""
    prim = primary_outputs(match_outputs(outputs, incidents))
    prim = prim.merge(incidents[["source_run", "incident_id", "impact_start_ts"]], on=["source_run", "incident_id"])
    prim = prim[(prim["decision_ts"] >= prim["impact_start_ts"] + SNAPSHOT_AFTER)
                & (prim["decision_ts"] <= prim["impact_start_ts"] + SNAPSHOT_LIMIT)]
    first = prim.sort_values("decision_ts").drop_duplicates(["source_run", "incident_id"]) \
        .set_index(["source_run", "incident_id"])
    rows = []
    for r in _scored_incidents(incidents).itertuples(index=False):
        roots = sorted(r.roots)
        key = (r.source_run, r.incident_id)
        o = first.loc[key] if key in first.index else None
        top = list(o["top_elements"]) if o is not None else []
        rows.append({"source_run": r.source_run, "incident_id": r.incident_id, "fault_type": r.fault_type,
                     "root_element_ids": roots, "case_id": None if o is None else o["case_id"],
                     "evaluated_at_s": None if o is None else (o["decision_ts"] - r.impact_start_ts).total_seconds(),
                     "top_candidates": top, "has_output": o is not None,
                     "hit_at_1": scoring.rca_hit(top, roots, 1), "hit_at_3": scoring.rca_hit(top, roots, 3)})
    return pd.DataFrame(rows)


def early_catch(outputs: pd.DataFrame, incidents: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Per scored incident: first decision time in [impact_start - 5 min, impact_end] whose primary output's
    top-1 is a valid root with score >= threshold. `localisation_s` is signed (negative = before impact)."""
    prim = primary_outputs(match_outputs(outputs, incidents))
    inc = _scored_incidents(incidents).set_index(["source_run", "incident_id"])
    rows = []
    groups = dict(tuple(prim.groupby(["source_run", "incident_id"]))) if len(prim) else {}
    for key, r in inc.iterrows():
        end = r["impact_end_ts"] if pd.notna(r["impact_end_ts"]) else r["end_ts"]
        g = groups.get(key)
        t = pd.NaT
        if g is not None:
            g = g[(g["decision_ts"] >= r["impact_start_ts"] - CATCH_PRE) & (g["decision_ts"] <= end)]
            hit = g[g["top1_element"].isin(set(r["roots"])) & (g["top1_score"] >= threshold)]
            t = hit["decision_ts"].min() if len(hit) else pd.NaT
        s = (t - r["impact_start_ts"]).total_seconds() if pd.notna(t) else None
        rows.append({"source_run": key[0], "incident_id": key[1], "fault_type": r["fault_type"],
                     "impact_start_ts": r["impact_start_ts"], "localised_ts": t, "localisation_s": s,
                     "localised": s is not None, "pre_impact": s is not None and s < 0,
                     "within_5min": s is not None and s <= scoring.SLA_S})
    return pd.DataFrame(rows)


def catch_summary(catch: pd.DataFrame, step2: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per fault type: localised %, within 5 min % (signed time <= 300 s, pre-impact included), pre-impact
    count, median signed time; plus step 2's published localisation (clipped at 0 by step 2) when given."""
    c = catch.copy()
    if step2 is not None:
        c = c.merge(step2[["incident_id", "localisation_ttd_s", "localised_within_sla"]].rename(
            columns={"localisation_ttd_s": "step2_localisation_s", "localised_within_sla": "step2_within_5min"}),
            on="incident_id", how="left")
        c["step2_within_5min"] = c["step2_within_5min"].fillna(False).astype(bool)
    rows = []
    for ft, g in [("ALL", c), *c.groupby("fault_type")]:
        row = {"fault_type": ft, "n": len(g),
               "model_localised_pct": round(100 * g["localised"].mean(), 1),
               "model_within_5min_pct": round(100 * g["within_5min"].mean(), 1),
               "model_pre_impact_n": int(g["pre_impact"].sum()),
               "model_median_signed_s": median_or_none(g["localisation_s"])}
        if step2 is not None:
            row.update({"step2_localised_pct": round(100 * g["step2_localisation_s"].notna().mean(), 1),
                        "step2_within_5min_pct": round(100 * g["step2_within_5min"].mean(), 1),
                        "step2_median_s": median_or_none(g["step2_localisation_s"])})
        rows.append(row)
    return pd.DataFrame(rows)


def any_alert_at_sla(outputs: pd.DataFrame, incidents: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Per scored incident, without footprint matching: at the first decision time of the incident's run and
    region at least 5 minutes after impact start (up to 15 minutes), the region's live alerts (case outputs
    whose top-1 score >= threshold), and whether any of them names a valid root as its top-1. Ground truth
    only supplies the region, the impact start and the root list; it never chooses which output is judged."""
    alerts = outputs[outputs["top1_score"] >= threshold]
    times = {k: np.sort(g["decision_ts"].unique()) for k, g in outputs.groupby(["source_run", "region_code"])}
    by_t = {k: g for k, g in alerts.groupby(["source_run", "region_code", "decision_ts"])}
    rows = []
    for r in _scored_incidents(incidents).itertuples(index=False):
        ts = times.get((r.source_run, r.region_code), np.array([], dtype="datetime64[ns]"))
        lo, hi = r.impact_start_ts + SNAPSHOT_AFTER, r.impact_start_ts + SNAPSHOT_LIMIT
        cand = [t for t in pd.to_datetime(ts, utc=True) if lo <= t <= hi]
        t = cand[0] if cand else None
        a = by_t.get((r.source_run, r.region_code, t)) if t is not None else None
        tops = [] if a is None else sorted(a["top1_element"].tolist())
        roots = set(r.roots)
        rows.append({"source_run": r.source_run, "incident_id": r.incident_id, "fault_type": r.fault_type,
                     "region_code": r.region_code, "decision_ts": t,
                     "evaluated_at_s": None if t is None else (t - r.impact_start_ts).total_seconds(),
                     "n_region_alerts": len(tops), "alert_top1_elements": tops,
                     "n_correct_alerts": sum(e in roots for e in tops),
                     "any_alert_correct": any(e in roots for e in tops)})
    return pd.DataFrame(rows)


def any_alert_summary(per_incident: pd.DataFrame, ranks: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per fault type: n, any-alert-correct %, median live alerts in the region at that minute, and (when the
    ranking table is given) the oracle-matched top-1 % on the same incidents, side by side."""
    x = per_incident.copy()
    if ranks is not None:
        x = x.merge(ranks[["source_run", "incident_id", "hit_at_1"]], on=["source_run", "incident_id"], how="left")
    rows = []
    for ft, g in [("ALL", x), *x.groupby("fault_type")]:
        row = {"fault_type": ft, "n": len(g), "any_alert_correct_pct": round(100 * g["any_alert_correct"].mean(), 1),
               "median_region_alerts": median_or_none(g["n_region_alerts"].astype(float))}
        if ranks is not None:
            row["matched_top1_pct"] = round(100 * g["hit_at_1"].fillna(False).astype(bool).mean(), 1)
        rows.append(row)
    return pd.DataFrame(rows)


def case_top1(scored: pd.DataFrame) -> pd.DataFrame:
    """The highest-scoring candidate of every case."""
    i = scored.groupby(["source_run", "case_id"])["score"].idxmax()
    return scored.loc[i.to_numpy()]


def _matched_labels(dets: pd.DataFrame, gt: pd.DataFrame) -> pd.Series:
    """Step 2's detection label (scoring.label_detection) per detection row: which incidents it overlaps."""
    g = gt.copy()
    g["m_from"] = g["start_ts"] - pd.Timedelta(minutes=5)
    g["m_to"] = g["end_ts"].fillna(g["impact_end_ts"]) + pd.Timedelta(seconds=scoring.MATCH_SLACK_S)
    elems = g[["source_run", "incident_id", "event_class", "is_censored", "footprint", "m_from", "m_to"]] \
        .explode("footprint").rename(columns={"footprint": "element_id"})
    d = dets.reset_index(drop=True).assign(_row=lambda x: np.arange(len(x)))
    m = d[["_row", "source_run", "element_id", "signal_start_ts", "signal_end_ts"]].merge(
        elems, on=["source_run", "element_id"])
    m = m[(m["signal_end_ts"] > m["m_from"]) & (m["m_to"].isna() | (m["signal_start_ts"] < m["m_to"]))]
    # Vectorised scoring.label_detection: each match is "censored" if the incident is censored, else its
    # event class; the detection takes the first of scoring.LABEL_PRIORITY found (tested to be identical).
    kind = np.where(m["is_censored"].fillna(False).astype(bool), "censored", m["event_class"].astype(str))
    order = {k: i for i, k in enumerate(scoring.LABEL_PRIORITY)}
    prio = pd.Series(kind, index=m.index).map(order).fillna(len(order))
    best = prio.groupby(m["_row"]).min()
    names = {i: k for k, i in order.items()}
    return d["_row"].map(best.map(lambda i: names.get(int(i), "unexplained"))).fillna("unexplained")


def alert_precision(dets: pd.DataFrame, gt: pd.DataFrame) -> dict:
    """Alert-level fault precision with step 2's definitions. `dets`: source_run, element_id,
    signal_start_ts, signal_end_ts, in_maintenance (one row per detection / per alerting decision time)."""
    if dets.empty:
        return scoring.fault_precision([]) | {"n_alerts": 0}
    d = dets.copy()
    d["label"] = _matched_labels(d, gt).to_numpy()
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    d["signal_start_s"] = (d["signal_start_ts"] - epoch).dt.total_seconds()
    d["signal_end_s"] = (d["signal_end_ts"] - epoch).dt.total_seconds()
    groups = scoring.alerts(d.to_dict("records"))
    labelled = [scoring.alert_label(a) for a in groups]
    return scoring.fault_precision(labelled) | {"n_alerts": len(groups)}


def model_alert_rows(scored: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Model alerts as detection rows: the top-1 element of each case whose score is >= threshold."""
    top = case_top1(scored)
    top = top[top["score"] >= threshold]
    return pd.DataFrame({"source_run": top["source_run"].to_numpy(), "element_id": top["element_id"].to_numpy(),
                         "signal_start_ts": top["decision_ts"].to_numpy(),
                         "signal_end_ts": (top["decision_ts"] + pd.Timedelta(minutes=1)).to_numpy(),
                         "in_maintenance": top["in_maintenance"].astype(bool).to_numpy()})


def summarise(per_incident: pd.DataFrame, cols: dict[str, str], by: str = "fault_type") -> pd.DataFrame:
    """Overall and per-`by` rates (%) of boolean columns, with n. `cols`: output name -> column."""
    def agg(g):
        out = {"n": len(g)}
        for name, c in cols.items():
            out[name] = round(100.0 * g[c].astype(bool).mean(), 1) if len(g) else None
        return pd.Series(out)

    overall = agg(per_incident).to_frame().T.assign(**{by: "ALL"})
    parts = [overall] + [agg(g).to_frame().T.assign(**{by: k}) for k, g in per_incident.groupby(by)]
    out = pd.concat(parts, ignore_index=True)
    return out[[by, "n", *cols]]


def median_or_none(x: pd.Series) -> float | None:
    x = x.dropna()
    return float(x.median()) if len(x) else None
