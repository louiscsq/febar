"""Explicit bronze schemas for every landing feed (see docs/data_model.md).

Timestamps stay STRING in bronze: collectors emit strings, and malformed values (`"N/A"`,
`"2026-13-45T25:61:00Z"`) must survive ingestion so silver can parse and quarantine them. Numeric
columns are typed, so a type mismatch (`"#VALUE!"` in a DOUBLE) lands in `_rescued_data` instead of
being silently dropped, and a truncated JSON line lands in `_corrupt_record`.
"""

from __future__ import annotations

RESCUE_COLUMN = "_rescued_data"
CORRUPT_COLUMN = "_corrupt_record"

KPIS = """
record_id STRING, event_ts STRING, emitted_ts STRING, cell_id STRING, granularity_s INT,
availability_pct DOUBLE, active_users BIGINT, prb_util_pct DOUBLE, rrc_setup_success_pct DOUBLE,
attach_success_pct DOUBLE, session_drop_rate_pct DOUBLE, dl_throughput_mbps DOUBLE,
ul_throughput_mbps DOUBLE, latency_ms DOUBLE, packet_loss_pct DOUBLE
"""

ALARMS = """
record_id STRING, alarm_id STRING, event_type STRING, element_id STRING, element_type STRING,
alarm_code STRING, severity STRING, event_ts STRING, emitted_ts STRING, vendor STRING,
additional_text STRING, source_system STRING
"""

SESSIONS = """
record_id STRING, imsi STRING, msisdn STRING, cell_id STRING, start_ts STRING, end_ts STRING,
emitted_ts STRING, duration_s BIGINT, service_type STRING, dnn STRING, bytes_dl BIGINT, bytes_ul BIGINT,
outcome STRING, cause_code STRING
"""

TOPOLOGY_NODES = """
element_id STRING, element_type STRING, name STRING, parent_id STRING, level INT, region_code STRING,
region STRING, state STRING, timezone STRING, lat DOUBLE, lon DOUBLE, vendor STRING, technology STRING,
urbanity STRING, transport_medium STRING, uplink_km DOUBLE, sector INT, capacity_users INT,
coverage_radius_km DOUBLE, amf_id STRING, upf_id STRING, router_id STRING, backhaul_id STRING,
site_id STRING
"""

TOPOLOGY_EDGES = "parent_id STRING, child_id STRING, edge_type STRING, parent_type STRING, child_type STRING"

MAINTENANCE_WINDOWS = """
change_id STRING, element_id STRING, element_type STRING, planned_start_ts STRING, planned_end_ts STRING,
change_type STRING, status STRING
"""

INCIDENTS = """
incident_id STRING, event_class STRING, fault_type STRING, root_element_id STRING,
root_element_type STRING, root_element_ids ARRAY<STRING>, region_code STRING, start_ts STRING,
end_ts STRING, impact_start_ts STRING, impact_end_ts STRING, is_customer_impacting BOOLEAN,
is_censored BOOLEAN, severity STRING, affected_element_ids ARRAY<STRING>, affected_cell_ids ARRAY<STRING>,
n_affected_cells INT, estimated_impacted_subscribers BIGINT, n_alarms INT, description STRING
"""

DQ_INJECTIONS = """
feed STRING, record_id STRING, defect_type STRING, defect_subtype STRING, `column` STRING,
injected_value STRING
"""

# Landing sub-directory (relative to a generator run root) -> schema.
FEEDS: dict[str, str] = {
    "kpis": KPIS,
    "alarms": ALARMS,
    "sessions": SESSIONS,
    "topology_nodes": TOPOLOGY_NODES,
    "topology_edges": TOPOLOGY_EDGES,
    "maintenance_windows": MAINTENANCE_WINDOWS,
    "ground_truth/incidents": INCIDENTS,
    "ground_truth/dq_injections": DQ_INJECTIONS,
}


def columns(ddl: str) -> list[str]:
    """Column names of a simple `name TYPE, ...` DDL string (no nested struct fields)."""
    out, depth, cur = [], 0, ""
    for ch in ddl:
        depth += ch == "<"
        depth -= ch == ">"
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [c.split()[0].strip("`") for c in (x.strip() for x in out) if c]


def with_corrupt_column(ddl: str) -> str:
    """Bronze reader schema: the feed schema plus a column that captures unparseable lines."""
    return " ".join(ddl.split()) + f", {CORRUPT_COLUMN} STRING"
