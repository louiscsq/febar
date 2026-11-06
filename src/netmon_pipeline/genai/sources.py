"""SQL for one incident's context inputs (`context.ContextInputs`), run with `spark.sql` in the jobs or on a SQL
warehouse by the on-demand service. Only operational tables are read: the ranker's scored candidates, topology,
alarms, the 1-minute health windows, the 5-minute session aggregates (no per-subscriber rows) and the change
calendar. No ground-truth (`netmon_eval`) table appears here."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from netmon_pipeline.genai import context as C

SqlFn = Callable[[str], pd.DataFrame]
XDR_SAMPLE_RATE = {"small": 0.01}  # session_sample_rate of the generator scale the runs use (collection setting)


def _q(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def _in(values) -> str:
    vals = sorted(set(values))
    return "(" + ", ".join(_q(v) for v in vals) + ")" if vals else "(NULL)"


def _ts(t: pd.Timestamp) -> str:
    return _q(pd.Timestamp(t).tz_convert("UTC").strftime("%Y-%m-%d %H:%M:%S"))


class Queries:
    def __init__(self, catalog: str, rca_schema: str = "netmon_rca"):
        self.s, self.g = f"`{catalog}`.netmon_silver", f"`{catalog}`.netmon_gold"
        self.r = f"`{catalog}`.`{rca_schema}`"

    def open_incident(self, incident_id: str) -> str:
        return f"SELECT * FROM {self.r}.open_incidents WHERE incident_id = {_q(incident_id)}"

    def case_rows(self, table: str, run: str, case_id: str, as_of: pd.Timestamp, model_version: str | None = None
                  ) -> str:
        mv = f" AND model_version = {_q(model_version)}" if model_version else ""
        return (f"SELECT * FROM {self.r}.{table} WHERE source_run = {_q(run)} AND case_id = {_q(case_id)} "
                f"AND decision_ts = {_ts(as_of)}{mv}")

    def topology(self, region: str) -> str:
        return (f"SELECT {', '.join(C.TOPOLOGY_COLUMNS)} FROM {self.s}.silver_topology_nodes "
                f"WHERE region_code = {_q(region)}")

    def alarms(self, run: str, region: str, as_of: pd.Timestamp) -> str:
        lo = as_of - pd.Timedelta(minutes=C.ALARM_LOOKBACK_MIN + 5)
        return (f"SELECT {', '.join(C.ALARM_COLUMNS)} FROM {self.s}.silver_alarms WHERE source_run = {_q(run)} "
                f"AND region_code = {_q(region)} AND event_ts BETWEEN {_ts(lo)} AND {_ts(as_of)}")

    def health(self, run: str, cells, as_of: pd.Timestamp) -> str:
        lo = as_of - pd.Timedelta(minutes=C.USERS_LOOKBACK_MIN + 5)
        return (f"SELECT {', '.join(C.HEALTH_COLUMNS)} FROM {self.g}.gold_cell_health_1m WHERE source_run = {_q(run)} "
                f"AND cell_id IN {_in(cells)} AND window_start BETWEEN {_ts(lo)} AND {_ts(as_of)}")

    def sessions(self, cells, as_of: pd.Timestamp) -> str:
        # gold_cell_sessions_5m has no source_run column; the generator runs cover disjoint dates
        lo = as_of - pd.Timedelta(minutes=20)
        return (f"SELECT {', '.join(C.SESSION_COLUMNS)} FROM {self.g}.gold_cell_sessions_5m "
                f"WHERE cell_id IN {_in(cells)} AND window_start BETWEEN {_ts(lo)} AND {_ts(as_of)}")

    def maintenance(self, run: str, elements) -> str:
        return (f"SELECT element_id, planned_start_ts, planned_end_ts FROM {self.s}.silver_maintenance_windows "
                f"WHERE source_run = {_q(run)} AND element_id IN {_in(elements)}")


def utc(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]) and getattr(df[c].dt, "tz", None) is None:
            df[c] = df[c].dt.tz_localize("UTC")
    return df


def load_inputs(sql: SqlFn, q: Queries, ref: C.IncidentRef, run: str, case_rows: pd.DataFrame,
                xdr_sample_rate: float | None = XDR_SAMPLE_RATE["small"]) -> C.ContextInputs:
    """Context inputs of one incident whose scored case rows are already loaded."""
    topo = utc(sql(q.topology(ref.region_code)))
    cells, _ = C.impacted_cells(case_rows)
    as_of = pd.Timestamp(ref.as_of)
    focus = {s[0] for s in ref.suspects}
    par = dict(zip(topo["element_id"], topo["parent_id"], strict=False))
    focus |= {par.get(e) for e in list(focus)} - {None}
    focus |= set(topo.loc[topo["parent_id"].isin([s[0] for s in ref.suspects]), "element_id"])
    return C.ContextInputs(
        incident=ref, case_rows=case_rows, topology=topo,
        alarms=utc(sql(q.alarms(run, ref.region_code, as_of))),
        health=utc(sql(q.health(run, cells, as_of))) if cells else pd.DataFrame(),
        sessions=utc(sql(q.sessions(cells, as_of))) if cells else pd.DataFrame(),
        maintenance=utc(sql(q.maintenance(run, focus))), xdr_sample_rate=xdr_sample_rate)


def ref_from_open_incident(row: dict, threshold: float | None = None) -> C.IncidentRef:
    sus = [(row[f"suspect_{k}_id"], row[f"suspect_{k}_type"], float(row[f"suspect_{k}_score"]))
           for k in (1, 2, 3) if row.get(f"suspect_{k}_id")]
    return C.IncidentRef(ref=row["incident_id"], region_code=row["region_code"],
                         as_of=pd.Timestamp(row["last_scored_ts"]), detected_ts=pd.Timestamp(row["detected_ts"]),
                         suspects=sus, model_version=str(row.get("model_version") or ""), alert_threshold=threshold)


def ref_from_case(ref: str, case_rows: pd.DataFrame, detected_ts=None, model_version: str = "",
                  threshold: float | None = None, k: int = 3) -> C.IncidentRef:
    """An incident reference for an evaluation case: the case's top-k by score (the ranker's output)."""
    top = case_rows.sort_values(["score", "element_id"], ascending=[False, True]).drop_duplicates("element_id").head(k)
    r0 = case_rows.iloc[0]
    return C.IncidentRef(ref=ref, region_code=r0["region_code"], as_of=pd.Timestamp(r0["decision_ts"]),
                         detected_ts=detected_ts, model_version=model_version, alert_threshold=threshold,
                         suspects=[(r.element_id, r.element_type, float(r.score)) for r in top.itertuples()])
