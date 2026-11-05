"""SQL for the RCA inputs, one generator run and one region at a time (the jobs run it with `spark.sql`,
local tools on a SQL warehouse). Only real-time tables are read for features: `gold_cell_health_1m`
(on-time records), `silver_alarms` with their arrival time, the topology and the change calendar. Ground
truth (`eval_gt_incidents`) is a separate query used for labels and scoring only."""

from __future__ import annotations

from netmon_pipeline.rca.features import ALARM_COLUMNS, RAW_METRICS, Z_METRICS


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def queries(catalog: str, run: str, region: str | None = None, since: str | None = None) -> dict[str, str]:
    """`since`: optional lower bound on event time (ISO UTC), for live scoring of the latest hours only."""
    s, g, e = f"`{catalog}`.netmon_silver", f"`{catalog}`.netmon_gold", f"`{catalog}`.netmon_eval"
    reg = f" AND region_code = {_q(region)}" if region else ""
    t_h = f" AND window_start >= {_q(since)}" if since else ""
    t_a = f" AND event_ts >= {_q(since)}" if since else ""
    cols = ", ".join(f"CAST({c} AS FLOAT) AS {c}" for c in [*Z_METRICS.values(), *RAW_METRICS.values()])
    return {
        "topology": f"""SELECT element_id, element_type, parent_id, level, region_code
                        FROM {s}.silver_topology_nodes WHERE true{reg}""",
        "health": f"""SELECT source_run, cell_id, window_start, evidence_ts, is_degraded, granularity_s, {cols}
                      FROM {g}.gold_cell_health_1m WHERE source_run = {_q(run)}{reg}{t_h}""",
        "alarms": f"""SELECT {", ".join(ALARM_COLUMNS)} FROM {s}.silver_alarms
                      WHERE source_run = {_q(run)}{reg}{t_a}""",
        "maintenance": f"""SELECT m.element_id, m.planned_start_ts, m.planned_end_ts
                           FROM {s}.silver_maintenance_windows m
                           JOIN {s}.silver_topology_nodes t ON t.element_id = m.element_id
                           WHERE m.source_run = {_q(run)}{reg.replace('region_code', 't.region_code')}""",
        "incidents": f"""SELECT * FROM {e}.eval_gt_incidents WHERE source_run = {_q(run)}""",
        # step-2 results on the same incidents / period (comparison only)
        "baseline": f"""SELECT incident_id, top_candidates, hit_at_1, hit_at_3 FROM {e}.eval_rca_baseline
                        WHERE source_run = {_q(run)}""",
        "step2_localisation": f"""SELECT incident_id, localisation_ttd_s, localised_within_sla, localisation_source
                                  FROM {e}.eval_incident_detection WHERE source_run = {_q(run)}""",
        "step2_detections": f"""SELECT source_run, element_id, signal_start_ts, signal_end_ts, in_maintenance
                                FROM {e}.eval_detection_log WHERE source_run = {_q(run)}{reg}""",
    }
