"""Labels for the root-cause ranker, from the generator's ground truth (`eval_gt_incidents`).

Ground truth is joined to the feature rows only here, after the features are built. A case (one impact
cluster at one decision time) is matched to an incident of the same run and region when the incident's
impact footprint (roots, affected elements and cells) contains one of the case's impacted cells or
service-down-alarmed elements, and the decision
time lies in `[impact_start - 5 min, impact_end + 10 min]` (`start`/`end` for incidents without impact).

- `case_label`, in step 2's priority order: `fault` (an uncensored, customer-impacting fault), `censored`
  (overlaps an incident that was not fully observed: excluded from training and scoring), `planned`,
  `red_herring`, `none`.
- `is_root` (the training target): the candidate is in the valid root-cause list (`root_element_ids`,
  falling back to `root_element_id`) of a matched fault incident. For bushfire / cyclone clusters every
  listed site / link counts.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from netmon_pipeline import scoring

PRE_S = 5 * 60
POST_S = scoring.MATCH_SLACK_S
CASE_KEYS = ["source_run", "case_id"]


def _roots(row) -> list[str]:
    r = row.get("root_element_ids")
    r = list(r) if r is not None and len(r) else []
    return r or [row["root_element_id"]]


def prepare_incidents(gt: pd.DataFrame) -> pd.DataFrame:
    """Typed incidents with `roots`, `footprint`, the matching window and `is_scored`."""
    g = gt.copy()
    for c in ("start_ts", "end_ts", "impact_start_ts", "impact_end_ts"):
        g[c] = pd.to_datetime(g[c], utc=True)
    g["roots"] = g.apply(_roots, axis=1)

    def footprint(row):
        ids = set(row["roots"])
        for k in ("root_element_ids", "affected_element_ids", "affected_cell_ids"):
            v = row.get(k)
            if v is not None:
                ids.update(list(v))
        return sorted(ids)

    g["footprint"] = g.apply(footprint, axis=1)
    start = g["impact_start_ts"].fillna(g["start_ts"])
    end = g["impact_end_ts"].fillna(g["end_ts"]).fillna(pd.Timestamp.max.tz_localize("UTC") - pd.Timedelta(days=1))
    g["match_from"] = start - pd.Timedelta(seconds=PRE_S)
    g["match_to"] = end + pd.Timedelta(seconds=POST_S)
    g["is_scored"] = (g["event_class"] == "fault") & g["is_customer_impacting"].fillna(False).astype(bool) \
        & ~g["is_censored"].fillna(False).astype(bool) & g["impact_start_ts"].notna()
    return g


def match_cases(features: pd.DataFrame, incidents: pd.DataFrame) -> pd.DataFrame:
    """(source_run, case_id, incident_id) for every case / incident match."""
    fp = incidents[["source_run", "incident_id", "region_code", "footprint", "match_from", "match_to"]] \
        .explode("footprint").rename(columns={"footprint": "element_id"})
    # A case is attributed through its own evidence: its impacted cells and its service-down alarms
    # (not every candidate: an AMF is a candidate of every case in its region).
    ev = features[((features["level"] == 5) & (features["n_impacted_cells"] > 0))
                  | (features["n_service_down_alarms"] > 0)]
    x = ev[["source_run", "case_id", "region_code", "decision_ts", "element_id"]].merge(
        fp, on=["source_run", "region_code", "element_id"])
    x = x[(x["decision_ts"] >= x["match_from"]) & (x["decision_ts"] <= x["match_to"])]
    return x[["source_run", "case_id", "incident_id"]].drop_duplicates()


def label(features: pd.DataFrame, gt: pd.DataFrame) -> pd.DataFrame:
    """`features` plus `case_label`, `is_root` and `incident_ids` (the matched scored fault incidents).
    The returned label columns are for training / scoring only (features.LABEL_COLUMNS)."""
    inc = prepare_incidents(gt)
    m = match_cases(features, inc).merge(
        inc[["source_run", "incident_id", "event_class", "is_censored", "is_scored", "roots"]],
        on=["source_run", "incident_id"])
    m["kind"] = np.select(
        [m["is_scored"], m["is_censored"].fillna(False).astype(bool), m["event_class"] == "planned",
         m["event_class"] == "red_herring"],
        ["fault", "censored", "planned", "red_herring"], default="none")
    prio = {"fault": 0, "censored": 1, "planned": 2, "red_herring": 3, "none": 4}
    m["p"] = m["kind"].map(prio)
    case_label = m.groupby(CASE_KEYS)["p"].min().map({v: k for k, v in prio.items()}).rename("case_label")
    faults = m[m["kind"] == "fault"]
    roots = faults.explode("roots")[["source_run", "case_id", "roots"]].drop_duplicates() \
        .rename(columns={"roots": "element_id"}).assign(is_root=True)
    ids = faults.groupby(CASE_KEYS)["incident_id"].agg(lambda s: sorted(set(s))).rename("incident_ids")
    out = features.merge(case_label.reset_index(), on=CASE_KEYS, how="left") \
        .merge(ids.reset_index(), on=CASE_KEYS, how="left") \
        .merge(roots, on=["source_run", "case_id", "element_id"], how="left")
    out["case_label"] = out["case_label"].fillna("none")
    out["is_root"] = out["is_root"].fillna(False).astype(bool)
    return out
