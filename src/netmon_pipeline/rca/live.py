"""Live outputs of the ranker for the NOC app: open incidents with their top-3 suspects, and the current
status of every network element. Pure pandas over scored candidate rows (features + `score`).

- **open incident**: a model alert that is still active at the latest decision time. A case alerts when
  its top-1 candidate's calibrated score is at least the champion's threshold; alerts on one element are
  grouped with step 2's alert rule (`scoring.alerts`: a new alert after a 10-minute gap), so `detected_ts`
  is when the current alert on that element started. The incident's suspects are the top-3 candidates of
  its case at the latest decision time.
- **element status**: per element at the latest decision time: `down` (most descendant cells silent, or a
  service-down alarm), `degraded` (at least half its cells impacted), `impacted`, `alarm` or `ok`, with the
  impact counts and the element's highest root-cause score.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from netmon_pipeline import scoring
from netmon_pipeline.rca import evaluate

OPEN_INCIDENT_COLUMNS = [
    "incident_id", "source_run", "region_code", "case_id", "detected_ts", "last_scored_ts", "status",
    "suspect_1_id", "suspect_1_type", "suspect_1_score", "suspect_2_id", "suspect_2_type", "suspect_2_score",
    "suspect_3_id", "suspect_3_type", "suspect_3_score", "n_impacted_cells", "n_candidates", "model_version",
]

# Explicit Spark schemas (DDL): the frames can be empty or have all-null columns.
OPEN_INCIDENTS_DDL = (
    "incident_id STRING, source_run STRING, region_code STRING, case_id STRING, detected_ts TIMESTAMP, "
    "last_scored_ts TIMESTAMP, status STRING, suspect_1_id STRING, suspect_1_type STRING, suspect_1_score DOUBLE, "
    "suspect_2_id STRING, suspect_2_type STRING, suspect_2_score DOUBLE, suspect_3_id STRING, suspect_3_type STRING, "
    "suspect_3_score DOUBLE, n_impacted_cells BIGINT, n_candidates BIGINT, model_version STRING, "
    "refreshed_at TIMESTAMP")
ELEMENT_STATUS_DDL = (
    "element_id STRING, element_type STRING, parent_id STRING, region_code STRING, n_desc_cells DOUBLE, "
    "n_impacted_cells DOUBLE, impacted_fraction DOUBLE, silent_fraction DOUBLE, n_alarms DOUBLE, "
    "n_service_down_alarms DOUBLE, rca_score DOUBLE, state STRING, open_incident_id STRING, suspect_rank DOUBLE, "
    "last_updated_ts TIMESTAMP, refreshed_at TIMESTAMP, model_version STRING")


def open_incidents(scored: pd.DataFrame, threshold: float, model_version: str) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame(columns=OPEN_INCIDENT_COLUMNS)
    t_last = scored["decision_ts"].max()
    alerts = evaluate.model_alert_rows(scored, threshold)
    if alerts.empty:
        return pd.DataFrame(columns=OPEN_INCIDENT_COLUMNS)
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    recs = alerts.assign(signal_start_s=(alerts["signal_start_ts"] - epoch).dt.total_seconds(),
                         signal_end_s=(alerts["signal_end_ts"] - epoch).dt.total_seconds()).to_dict("records")
    started = {}
    for grp in scoring.alerts(recs):
        last = max(grp, key=lambda d: d["signal_start_s"])
        if last["signal_start_ts"] == t_last:  # still alerting at the latest decision time
            started[(last["source_run"], last["element_id"])] = min(d["signal_start_ts"] for d in grp)
    now = scored[scored["decision_ts"] == t_last]
    rows = []
    for case_id, g in now.groupby("case_id"):
        g = g.sort_values("score", ascending=False)
        top = g.iloc[0]
        key = (top["source_run"], top["element_id"])
        if top["score"] < threshold or key not in started:
            continue
        det = started[key]
        iid = hashlib.sha1(f"{key[0]}|{key[1]}|{det.isoformat()}".encode()).hexdigest()[:16]
        r = {"incident_id": f"RCA-{iid}", "source_run": top["source_run"], "region_code": top["region_code"],
             "case_id": case_id, "detected_ts": det, "last_scored_ts": t_last, "status": "open",
             "n_impacted_cells": int(g.loc[g["level"] == 5, "n_impacted_cells"].sum()),
             "n_candidates": len(g), "model_version": str(model_version)}
        for k in range(3):
            s = g.iloc[k] if k < len(g) else None
            r[f"suspect_{k + 1}_id"] = None if s is None else s["element_id"]
            r[f"suspect_{k + 1}_type"] = None if s is None else s["element_type"]
            r[f"suspect_{k + 1}_score"] = None if s is None else round(float(s["score"]), 4)
        rows.append(r)
    out = pd.DataFrame(rows, columns=OPEN_INCIDENT_COLUMNS)
    # one open incident per suspect element (two cases can share a top-1 root, e.g. a link split in two)
    return out.sort_values("suspect_1_score", ascending=False).drop_duplicates("suspect_1_id").reset_index(drop=True)


def element_status(topology: pd.DataFrame, scored: pd.DataFrame, incidents: pd.DataFrame) -> pd.DataFrame:
    """One row per topology element at the latest decision time."""
    t_last = scored["decision_ts"].max() if not scored.empty else pd.NaT
    now = scored[scored["decision_ts"] == t_last]
    agg = now.groupby("element_id").agg(
        n_desc_cells=("log_n_desc_cells", lambda x: float(np.expm1(x.max()))),
        n_impacted_cells=("n_impacted_cells", "max"), impacted_fraction=("impacted_fraction", "max"),
        silent_fraction=("silent_fraction", "max"), n_alarms=("n_alarms", "max"),
        n_service_down_alarms=("n_service_down_alarms", "max"), rca_score=("score", "max"))
    out = topology[["element_id", "element_type", "parent_id", "region_code"]].merge(
        agg.reset_index(), on="element_id", how="left")
    for c in ("n_impacted_cells", "impacted_fraction", "silent_fraction", "n_alarms", "n_service_down_alarms"):
        out[c] = out[c].fillna(0.0)
    out["state"] = np.select(
        [(out["silent_fraction"] >= 0.8) | (out["n_service_down_alarms"] > 0), out["impacted_fraction"] >= 0.5,
         out["n_impacted_cells"] > 0, out["n_alarms"] > 0], ["down", "degraded", "impacted", "alarm"], "ok")
    suspects = {}
    if not incidents.empty:
        for r in incidents.itertuples(index=False):
            for k in (1, 2, 3):
                e = getattr(r, f"suspect_{k}_id")
                if e is not None and (e not in suspects or k < suspects[e][1]):
                    suspects[e] = (r.incident_id, k)
    out["open_incident_id"] = out["element_id"].map(lambda e: suspects.get(e, (None, None))[0])
    out["suspect_rank"] = out["element_id"].map(lambda e: suspects.get(e, (None, None))[1])
    out["last_updated_ts"] = t_last
    return out


def conform(df: pd.DataFrame, ddl: str) -> pd.DataFrame:
    """Columns of `ddl`, in order, with pandas dtypes Spark's createDataFrame(df, schema=ddl) accepts."""
    out = pd.DataFrame(index=df.index)
    for part in ddl.split(","):
        name, typ = part.strip().split(" ", 1)
        x = df[name] if name in df else pd.Series([None] * len(df), index=df.index, dtype=object)
        if typ == "DOUBLE":
            out[name] = pd.to_numeric(x, errors="coerce").astype("float64")
        elif typ == "BIGINT":
            out[name] = pd.to_numeric(x, errors="coerce").astype("Int64")
        elif typ == "TIMESTAMP":
            out[name] = pd.to_datetime(x, utc=True)
        else:
            out[name] = x.astype(object).where(x.notna(), None).map(lambda v: v if v is None else str(v))
    return out
