"""Evaluation of the root-cause ranker against ground truth, side by side with the step-2 localiser.

Primary measures (on the held-out time split, scored incidents only: customer-impacting, uncensored faults):

- **top-1 / top-3 accuracy** (`rank_incidents`): the cases attributed to the incident (labels.py: its
  footprint contains one of the case's impacted cells), decision times in the first 15 minutes of impact
  (from 5 minutes before, step 2's `eval_rca_baseline` window), each candidate ranked by its highest score
  in that span. Step 2's heuristic is reported both as published (`eval_rca_baseline`, region-wide) and on
  exactly the same cases (`heuristic_score`), so the model's gain is separated from the case framing. A hit when the incident's valid root-cause list
  contains the top-ranked element (top-1) or one of the top three (top-3).
- **early catch** (`early_catch`): the model scores every 1-minute decision time; an incident is localised
  at the first decision time whose top-1 element is a valid root **and** whose calibrated score is at least
  the alert threshold chosen on the validation days. Reported as the share localised within 5 minutes of
  impact start and the median time to correct localisation.

Secondary (reported, never optimised): **alert-level fault precision** (`alert_precision`). Model alerts are
top-1 elements above the threshold; they are grouped and labelled with step 2's own definitions
(`netmon_pipeline.scoring`: `label_detection`, `alerts`, `alert_label`, `fault_precision`), and the same code
scores the step-2 detections of the same period.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from netmon_pipeline import scoring

RANK_PRE = pd.Timedelta(minutes=5)
RANK_POST = pd.Timedelta(minutes=15)
CATCH_PRE = pd.Timedelta(minutes=10)


class _Index:
    """Scored candidate rows sorted per (source_run, region) for fast time slicing."""

    def __init__(self, scored: pd.DataFrame):
        self.groups = {}
        for key, g in scored.sort_values("decision_ts").groupby(["source_run", "region_code"], sort=False):
            self.groups[key] = (g, g["decision_ts"].to_numpy())

    def slice(self, run, region, lo, hi) -> pd.DataFrame:
        g = self.groups.get((run, region))
        if g is None:
            return pd.DataFrame()
        df, ts = g
        a = np.searchsorted(ts, _np(lo, ts), side="left")
        b = np.searchsorted(ts, _np(hi, ts), side="left")
        return df.iloc[a:b]


def _np(t: pd.Timestamp, like: np.ndarray):
    if like.dtype == object:
        return t
    return np.datetime64(t.tz_convert("UTC").tz_localize(None), "ns") if t.tzinfo else np.datetime64(t, "ns")


def _scored_incidents(inc: pd.DataFrame) -> pd.DataFrame:
    return inc[inc["is_scored"]]


def _cases_by_incident(scored: pd.DataFrame) -> dict[tuple, set]:
    """(source_run, incident_id) -> case_ids attributed to it (labels.label's `incident_ids`)."""
    c = scored[["source_run", "case_id", "incident_ids"]].drop_duplicates("case_id")
    c = c[c["incident_ids"].map(lambda v: isinstance(v, list | np.ndarray) and len(v) > 0)].explode("incident_ids")
    out: dict[tuple, set] = {}
    for run, case, inc in zip(c["source_run"], c["case_id"], c["incident_ids"], strict=True):
        out.setdefault((run, inc), set()).add(case)
    return out


def heuristic_score(df: pd.DataFrame) -> pd.Series:
    """Step 2's topology heuristic (eval_rca_baseline) as a score: most impacted descendant cells first, then
    higher in the tree. Used to rank the *same* cases as the model."""
    ok = (df["impacted_fraction"] >= 0.8) | (df["n_service_down_alarms"] > 0)  # eval_rca_baseline's filter
    return (df["n_impacted_cells"].astype(float) - 0.001 * df["level"].astype(float)).where(ok, -np.inf)


def rank_incidents(scored: pd.DataFrame, inc: pd.DataFrame, k: int = 3, score: str = "score") -> pd.DataFrame:
    """Per scored incident: top-k candidates by max `score` over the cases attributed to the incident with
    decision times in [impact_start - 5 min, impact_start + 15 min) (step 2's baseline window)."""
    idx = _Index(scored)
    by_inc = _cases_by_incident(scored)
    rows = []
    for r in _scored_incidents(inc).itertuples(index=False):
        s = idx.slice(r.source_run, r.region_code, r.impact_start_ts - RANK_PRE, r.impact_start_ts + RANK_POST)
        if not s.empty:
            s = s[s["case_id"].isin(by_inc.get((r.source_run, r.incident_id), set()))]
        roots = set(r.roots)
        if s.empty:
            top, n_cases, in_cand = [], 0, False
        else:
            best = s.groupby("element_id")[score].max().sort_values(ascending=False, kind="stable")
            top, n_cases, in_cand = list(best.index[:k]), s["case_id"].nunique(), bool(roots & set(best.index))
        rows.append({"source_run": r.source_run, "incident_id": r.incident_id, "fault_type": r.fault_type,
                     "root_element_ids": sorted(roots), "top_candidates": top, "n_cases": n_cases,
                     "root_in_candidates": in_cand, "hit_at_1": scoring.rca_hit(top, sorted(roots), 1),
                     "hit_at_3": scoring.rca_hit(top, sorted(roots), 3)})
    return pd.DataFrame(rows)


def case_top1(scored: pd.DataFrame) -> pd.DataFrame:
    """The highest-scoring candidate of every case."""
    i = scored.groupby(["source_run", "case_id"])["score"].idxmax()
    return scored.loc[i.to_numpy()]


def early_catch(scored: pd.DataFrame, inc: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Per scored incident: first decision time whose top-1 is a valid root with score >= threshold."""
    top = case_top1(scored)
    idx = _Index(top)
    by_inc = _cases_by_incident(scored)
    rows = []
    for r in _scored_incidents(inc).itertuples(index=False):
        end = r.impact_end_ts if pd.notna(r.impact_end_ts) else r.end_ts
        s = idx.slice(r.source_run, r.region_code, r.impact_start_ts - CATCH_PRE, end + pd.Timedelta(minutes=1))
        if not s.empty:
            s = s[s["case_id"].isin(by_inc.get((r.source_run, r.incident_id), set()))]
        hit = s[s["element_id"].isin(set(r.roots)) & (s["score"] >= threshold)] if not s.empty else s
        t = hit["decision_ts"].min() if not hit.empty else pd.NaT
        ttl = max(0.0, (t - r.impact_start_ts).total_seconds()) if pd.notna(t) else None
        rows.append({"source_run": r.source_run, "incident_id": r.incident_id, "fault_type": r.fault_type,
                     "impact_start_ts": r.impact_start_ts, "localised_ts": t, "localisation_s": ttl,
                     "within_5min": ttl is not None and ttl <= scoring.SLA_S})
    return pd.DataFrame(rows)


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
