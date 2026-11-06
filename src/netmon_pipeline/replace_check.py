"""Post-replacement checks for `notebooks/12_replace_run_feeds.py` (PR #6), shared with the evidence capture.

After a run's alarm / DQ-log / change-calendar files were swapped and the superseded rows deleted, every check
below must return 0 (`violations`). Derived tables of the change calendar are materialized views recomputed from
bronze (`silver_maintenance_windows`, and through it `gold_element_impact_5m` and the eval views), so they cannot keep
superseded rows; the checks prove it. Streaming tables carry the calendar only as the `in_maintenance` flag of a
detection, joined at ingest time: a detection that falls in two overlapping change windows (e.g. its site's and its
router's) is written once per matching window. That fan-out predates the ID fix and is checked separately
(`fanout_unexplained`) so it is not mistaken for a replacement artefact.
"""

from __future__ import annotations

import hashlib


def legacy_change_id(incident_id: str) -> str:
    """The pre-fix change ID (`opaque_id("CHG", incident_id)`), to prove none survives in the replaced runs."""
    return "CHG-" + hashlib.blake2b(incident_id.encode(), digest_size=8).hexdigest()


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def checks(catalog: str, runs: list[str], revision: str, legacy_change_ids: list[str]) -> dict[str, str]:
    """name -> SQL returning one row (run, violations). Every `violations` must be 0."""
    c = f"`{catalog}`"
    b, s, g, e = f"{c}.netmon_bronze", f"{c}.netmon_silver", f"{c}.netmon_gold", f"{c}.netmon_eval"
    rl = ", ".join(_q(r) for r in runs)
    new = f"_source_file RLIKE '-{revision}[.]json$'"
    legacy = ", ".join(_q(x) for x in legacy_change_ids) or "NULL"
    out = {}
    for name, table, run_col in (("bronze_alarms", f"{b}.bronze_alarms", "_source_run"),
                                 ("bronze_gt_dq_injections", f"{e}.bronze_gt_dq_injections", "_source_run"),
                                 ("bronze_maintenance_windows", f"{b}.bronze_maintenance_windows", "_source_run"),
                                 ("silver_alarms", f"{s}.silver_alarms", "source_run")):
        out[f"superseded_rows_{name}"] = (f"SELECT {run_col} AS run, count_if(NOT {new}) AS violations FROM {table} "
                                          f"WHERE {run_col} IN ({rl}) GROUP BY 1")
    out["superseded_rows_silver_quarantine_alarms"] = (
        f"SELECT _source_run AS run, count_if(NOT {new}) AS violations FROM {s}.silver_quarantine "
        f"WHERE feed = 'alarms' AND _source_run IN ({rl}) GROUP BY 1")
    out["legacy_change_ids"] = f"""
        SELECT run, count(*) AS violations FROM (
          SELECT _source_run AS run, change_id FROM {b}.bronze_maintenance_windows WHERE _source_run IN ({rl})
          UNION ALL SELECT source_run, change_id FROM {s}.silver_maintenance_windows WHERE source_run IN ({rl}))
        WHERE change_id IN ({legacy}) GROUP BY 1"""
    out["duplicate_maintenance_windows"] = f"""
        SELECT source_run AS run, coalesce(sum(n - 1), 0) AS violations FROM (
          SELECT source_run, element_id, planned_start_ts, planned_end_ts, count(*) AS n
          FROM {s}.silver_maintenance_windows WHERE source_run IN ({rl}) GROUP BY ALL) GROUP BY 1"""
    out["silver_vs_bronze_maintenance"] = f"""
        SELECT coalesce(x.run, y.run) AS run, abs(coalesce(x.n, 0) - coalesce(y.n, 0)) AS violations
        FROM (SELECT _source_run AS run, count(DISTINCT change_id) AS n FROM {b}.bronze_maintenance_windows
              WHERE _source_run IN ({rl}) AND _corrupt_record IS NULL GROUP BY 1) x
        FULL OUTER JOIN (SELECT source_run AS run, count(*) AS n FROM {s}.silver_maintenance_windows
                         WHERE source_run IN ({rl}) GROUP BY 1) y ON x.run = y.run"""
    out["duplicate_silver_alarm_ids"] = f"""
        SELECT source_run AS run, count(*) - count(DISTINCT record_id) AS violations FROM {s}.silver_alarms
        WHERE source_run IN ({rl}) GROUP BY 1"""
    for name, table in (("gold_impact_detections", f"{g}.gold_impact_detections"),
                        ("eval_detection_log", f"{e}.eval_detection_log")):
        out[f"orphan_alarm_detections_{name}"] = f"""
            SELECT t.source_run AS run, count_if(s.record_id IS NULL) AS violations FROM {table} t
            LEFT JOIN (SELECT DISTINCT source_run, record_id FROM {s}.silver_alarms) s
              ON s.source_run = t.source_run AND s.record_id = t.record_id
            WHERE t.source_run IN ({rl}) AND t.signal_source = 'alarm' GROUP BY 1"""
    # Every repeated detection_id is explained by its number of matching change windows (site or router).
    out["fanout_unexplained_gold_impact_detections"] = f"""
        WITH d AS (SELECT source_run, detection_id, any_value(site_id) AS site, any_value(router_id) AS rtr,
                          any_value(signal_start_ts) AS ts, count(*) AS n
                   FROM {g}.gold_impact_detections WHERE source_run IN ({rl}) GROUP BY 1, 2),
        w AS (SELECT d.source_run, d.detection_id, d.n, count(m.element_id) AS windows FROM d
              LEFT JOIN {s}.silver_maintenance_windows m ON m.source_run = d.source_run
               AND m.element_id IN (d.site, d.rtr) AND d.ts >= m.planned_start_ts AND d.ts < m.planned_end_ts
              GROUP BY 1, 2, 3)
        SELECT source_run AS run, count_if(n <> greatest(windows, 1)) AS violations FROM w GROUP BY 1"""
    return out


def fanout_summary_sql(catalog: str, runs: list[str]) -> str:
    """Repeated detection rows per run and signal: all caused by overlapping change windows (informational)."""
    rl = ", ".join(_q(r) for r in runs)
    return f"""
        SELECT source_run, signal_source, count(*) AS rows, count(DISTINCT detection_id) AS distinct_detections,
               count(*) - count(DISTINCT detection_id) AS repeated_rows
        FROM `{catalog}`.netmon_gold.gold_impact_detections WHERE source_run IN ({rl}) GROUP BY 1, 2 ORDER BY 1, 2"""
