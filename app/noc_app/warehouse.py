"""Unity Catalog reads through the SQL warehouse, AS THE SIGNED-IN USER (Databricks Apps on-behalf-of-user auth).

The Apps proxy forwards the user's downscoped token (`x-forwarded-access-token`, scope `sql`). Queries run as that
user, so the `netmon_noc` views' regional row filter and the user's grants decide what comes back: a regional NOC
user gets only their region's topology and incidents. Nothing here reads the ground-truth schema.

Used for reference data and analytics, not the hot path: the region scope of the user, the network inventory of a
region (cached: it changes with network builds, not by the minute), operational detection timing per incident and
the KPI scorecard.
"""

from __future__ import annotations

import time
from typing import Protocol

REGION_SCOPE_SQL = "SELECT DISTINCT region_code FROM {noc}.silver_topology_nodes WHERE element_type = 'AMF_MME' ORDER BY 1"

TOPOLOGY_SQL = """
SELECT element_id, element_type, name, parent_id, region_code, region, timezone, lat, lon, urbanity,
       transport_medium, technology, vendor
FROM {noc}.silver_topology_nodes
WHERE region_code = :region"""

DETECTION_TIMES_SQL = """
SELECT incident_id, suspect_1_id, first_impact_signal_ts, first_detection_ts, incident_detected_ts,
       time_to_detect_s, time_to_localise_s, detected_within_5min, n_detection_rows
FROM {noc}.incident_detection_times
WHERE incident_id = :incident_id"""

KPI_SQL = """
SELECT region_code, count(*) AS n_open_incidents, round(avg(time_to_detect_s), 1) AS mttd_s,
       round(100 * avg(CASE WHEN detected_within_5min THEN 1 ELSE 0 END), 1) AS pct_detected_within_5min
FROM {noc}.incident_detection_times GROUP BY region_code ORDER BY region_code"""


class Warehouse(Protocol):
    def query(self, user_token: str | None, sql: str, params: dict | None = None) -> list[dict]: ...


def _coerce(v: str | None, type_name: str):
    if v is None:
        return None
    t = (type_name or "").upper()
    if t in ("INT", "LONG", "SHORT", "BYTE", "BIGINT"):
        return int(v)
    if t in ("DOUBLE", "FLOAT", "DECIMAL"):
        return float(v)
    if t == "BOOLEAN":
        return v.lower() == "true"
    return v


class SqlWarehouse:
    """Statement Execution API with the forwarded user token (falls back to the app identity only for local dev)."""

    def __init__(self, settings):
        self.s = settings

    def _client(self, user_token: str | None):
        from databricks.sdk import WorkspaceClient
        if user_token:
            return WorkspaceClient(host=self.s.host, token=user_token, auth_type="pat")
        return WorkspaceClient()

    def query(self, user_token: str | None, sql: str, params: dict | None = None) -> list[dict]:
        from databricks.sdk.service.sql import StatementParameterListItem, StatementState

        w = self._client(user_token)
        stmt = sql.format(noc=self.s.noc)
        p = [StatementParameterListItem(name=k, value=str(v)) for k, v in (params or {}).items()]
        r = w.statement_execution.execute_statement(statement=stmt, warehouse_id=self.s.warehouse_id,
                                                    parameters=p or None, wait_timeout="30s")
        while r.status and r.status.state in (StatementState.PENDING, StatementState.RUNNING):
            time.sleep(1)
            r = w.statement_execution.get_statement(r.statement_id)
        if not r.status or r.status.state != StatementState.SUCCEEDED:
            msg = r.status.error.message if r.status and r.status.error else str(r.status)
            raise PermissionError(msg) if "PERMISSION" in msg.upper() or "INSUFFICIENT" in msg.upper() \
                else RuntimeError(msg)
        cols = [(c.name, c.type_name.value if c.type_name else "") for c in r.manifest.schema.columns]
        rows = []
        chunk = r.result
        while chunk is not None:
            for row in chunk.data_array or []:
                rows.append({n: _coerce(v, t) for (n, t), v in zip(cols, row, strict=True)})
            if chunk.next_chunk_index is None:
                break
            chunk = w.statement_execution.get_statement_result_chunk_n(r.statement_id, chunk.next_chunk_index)
        return rows


class TTLCache:
    def __init__(self, ttl_s: float):
        self.ttl, self.d = ttl_s, {}

    def get(self, key, fn):
        hit = self.d.get(key)
        now = time.monotonic()
        if hit and now - hit[0] < self.ttl:
            return hit[1]
        val = fn()
        self.d[key] = (now, val)
        return val
