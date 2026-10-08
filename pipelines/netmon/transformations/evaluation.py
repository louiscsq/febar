# Evaluation (netmon_eval schema): detections and DQ handling scored against the generator's ground truth.
#
# Kept apart from the feature tables on purpose: nothing in bronze/silver/gold reads this schema, and
# the ground-truth incident columns are only ever joined here. Definitions mirror netmon_pipeline.scoring.

import sys

sys.path.insert(0, spark.conf.get("netmon.src_path"))

from pyspark import pipelines as dp

from netmon_pipeline import rules, scoring
from netmon_pipeline.settings import Settings

S = Settings.from_conf(spark.conf.get)
TS = rules.TS_FORMAT


@dp.materialized_view(
    name=f"{S.eval}.eval_gt_incidents",
    comment="GROUND TRUTH incidents, typed (UTC), one row per (source_run, incident_id). Labels only.",
)
@dp.expect_or_drop("incident_id_not_null", "incident_id IS NOT NULL")
def eval_gt_incidents():
    return spark.sql(f"""
        SELECT * EXCEPT (rn) FROM (
          SELECT _source_run AS source_run, incident_id, event_class, fault_type, root_element_id, root_element_type,
                 root_element_ids, region_code,
                 try_to_timestamp(start_ts, "{TS}") AS start_ts, try_to_timestamp(end_ts, "{TS}") AS end_ts,
                 try_to_timestamp(impact_start_ts, "{TS}") AS impact_start_ts,
                 try_to_timestamp(impact_end_ts, "{TS}") AS impact_end_ts,
                 is_customer_impacting, is_censored, severity, affected_element_ids, affected_cell_ids,
                 n_affected_cells, estimated_impacted_subscribers, n_alarms, description,
                 row_number() OVER (PARTITION BY _source_run, incident_id
                                    ORDER BY _file_modification_time DESC) AS rn
          FROM {S.eval}.bronze_gt_incidents WHERE _corrupt_record IS NULL)
        WHERE rn = 1""")


@dp.table(
    name=f"{S.eval}.eval_detection_log",
    comment="Unfiltered copy of the impact detections for offline scoring (gold_impact_detections is row-filtered "
            "for NOC users). Same rows, same detected_ts semantics.",
    cluster_by=["source_run", "element_id"],
)
def eval_detection_log():
    return spark.readStream.table("impact_signals")


def _incident_detection_sql() -> str:
    return f"""
    WITH inc AS (
      SELECT * FROM {S.eval}.eval_gt_incidents
      WHERE is_customer_impacting AND NOT is_censored AND impact_start_ts IS NOT NULL
    ),
    elems AS (
      SELECT incident_id, source_run, explode(array_distinct(concat(
               array(root_element_id), coalesce(root_element_ids, array()), coalesce(affected_element_ids, array()),
               coalesce(affected_cell_ids, array())))) AS element_id
      FROM inc
    ),
    det AS (
      SELECT *,
             -- availability to the NOC: evidence time plus the measured pipeline latency for live files
             timestampadd(MILLISECOND, CAST(CASE WHEN landed_ts IS NOT NULL THEN pipeline_latency_s ELSE 0 END
                                            * 1000 AS BIGINT), evidence_ts) AS available_ts
      FROM {S.eval}.eval_detection_log
    ),
    m AS (
      SELECT e.incident_id, e.source_run, d.* EXCEPT (source_run)
      FROM elems e
      JOIN inc i ON i.incident_id = e.incident_id AND i.source_run = e.source_run
      JOIN det d ON d.element_id = e.element_id AND d.source_run = e.source_run
       AND d.signal_end_ts > i.impact_start_ts
       AND d.signal_start_ts < coalesce(i.impact_end_ts, i.end_ts) + INTERVAL {scoring.MATCH_SLACK_S} SECONDS
    ),
    first_det AS (
      SELECT incident_id, source_run, min(available_ts) AS first_available_ts,
             min_by(signal_source, available_ts) AS first_signal_source,
             min_by(element_id, available_ts) AS first_element_id,
             min_by(element_type, available_ts) AS first_element_type,
             min_by(flags, available_ts) AS first_flags,
             min_by(evidence_ts, available_ts) AS first_evidence_ts,
             min_by(CASE WHEN landed_ts IS NOT NULL THEN pipeline_latency_s END, available_ts) AS first_pipeline_latency_s,
             min_by(detected_ts, available_ts) AS first_detected_ts,
             count(*) AS n_matched_detections, count(DISTINCT element_id) AS n_detected_elements,
             max(CAST(array_contains(coalesce(i_roots, array()), element_id) AS INT)) = 1 AS root_detected
      FROM (SELECT m.*, i.root_element_ids AS i_roots FROM m JOIN inc i USING (incident_id, source_run))
      GROUP BY incident_id, source_run
    )
    SELECT i.source_run, i.incident_id, i.event_class, i.fault_type, i.severity, i.region_code, i.root_element_id,
           i.root_element_type, i.root_element_ids, i.impact_start_ts, i.impact_end_ts, i.n_affected_cells,
           i.estimated_impacted_subscribers,
           f.first_available_ts, f.first_signal_source, f.first_element_id, f.first_element_type, f.first_flags,
           f.first_evidence_ts, f.first_pipeline_latency_s, f.first_detected_ts, f.n_matched_detections,
           f.n_detected_elements, coalesce(f.root_detected, false) AS root_detected,
           f.first_available_ts IS NOT NULL AS is_detected,
           greatest(unix_timestamp(f.first_evidence_ts) - unix_timestamp(i.impact_start_ts), 0) AS evidence_lag_s,
           greatest((unix_millis(f.first_available_ts) - unix_millis(i.impact_start_ts)) / 1000.0, 0) AS ttd_s,
           coalesce((unix_millis(f.first_available_ts) - unix_millis(i.impact_start_ts)) / 1000.0
                    <= {scoring.SLA_S}, false) AS detected_within_sla
    FROM inc i LEFT JOIN first_det f ON f.incident_id = i.incident_id AND f.source_run = i.source_run
    """


@dp.materialized_view(
    name=f"{S.eval}.eval_incident_detection",
    comment="Per scored incident (customer-impacting, not censored): first matching detection, time-to-detect "
            "(ttd_s, from impact_start_ts) and whether it met the 5-minute SLA. Cluster faults: root_detected "
            "checks detections against every element of root_element_ids.",
)
def eval_incident_detection():
    return spark.sql(_incident_detection_sql())


@dp.materialized_view(
    name=f"{S.eval}.eval_ttd_summary",
    comment="Time-to-detect summary per source run (history = 15-min ROP backfill, stream = 1-min live feed), "
            "overall and per fault type: detected share, median / p90 TTD and share detected within 5 minutes.",
)
def eval_ttd_summary():
    return spark.sql(f"""
        SELECT source_run, coalesce(fault_type, 'ALL') AS fault_type, count(*) AS n_incidents,
               count_if(is_detected) AS n_detected,
               round(100.0 * count_if(is_detected) / count(*), 1) AS detected_pct,
               round(percentile(ttd_s, 0.5), 1) AS median_ttd_s, round(percentile(ttd_s, 0.9), 1) AS p90_ttd_s,
               round(100.0 * count_if(detected_within_sla) / count(*), 1) AS within_5min_pct,
               round(percentile(evidence_lag_s, 0.5), 1) AS median_evidence_lag_s,
               round(percentile(first_pipeline_latency_s, 0.5), 1) AS median_pipeline_latency_s
        FROM {S.eval}.eval_incident_detection
        GROUP BY GROUPING SETS ((source_run), (source_run, fault_type))""")


@dp.materialized_view(
    name=f"{S.eval}.eval_detection_precision",
    comment="Share of detections explained by any ground-truth event (incl. red herrings, planned work and "
            "censored incidents), per source run and signal source. Unexplained = false-positive candidates.",
)
def eval_detection_precision():
    return spark.sql(f"""
        WITH elems AS (
          SELECT source_run, incident_id, event_class, start_ts, coalesce(end_ts, impact_end_ts) AS end_ts,
                 explode(array_distinct(concat(array(root_element_id), coalesce(root_element_ids, array()),
                         coalesce(affected_element_ids, array()), coalesce(affected_cell_ids, array())))) AS element_id
          FROM {S.eval}.eval_gt_incidents
        ),
        matched AS (
          SELECT d.detection_id, max_by(e.event_class, e.start_ts) AS event_class
          FROM {S.eval}.eval_detection_log d
          JOIN elems e ON e.element_id = d.element_id AND e.source_run = d.source_run
           AND d.signal_end_ts > e.start_ts - INTERVAL 5 MINUTES
           AND (e.end_ts IS NULL OR d.signal_start_ts < e.end_ts + INTERVAL {scoring.MATCH_SLACK_S} SECONDS)
          GROUP BY d.detection_id
        )
        SELECT d.source_run, d.signal_source, count(*) AS n_detections,
               count(m.detection_id) AS n_explained,
               count_if(m.event_class = 'fault') AS n_fault, count_if(m.event_class = 'planned') AS n_planned,
               count_if(m.event_class = 'red_herring') AS n_red_herring,
               round(100.0 * count(m.detection_id) / count(*), 1) AS explained_pct,
               count_if(d.in_maintenance) AS n_in_maintenance_window
        FROM {S.eval}.eval_detection_log d LEFT JOIN matched m ON m.detection_id = d.detection_id
        GROUP BY d.source_run, d.signal_source""")


@dp.materialized_view(
    name=f"{S.eval}.eval_dq_capture",
    comment="Data-quality defects injected by the generator (ground truth) vs how the pipeline handled them: "
            "quarantined (malformed/null/out-of-range), flagged late (kept), or deduplicated.",
)
def eval_dq_capture():
    late = rules.LATE_THRESHOLD_S
    return spark.sql(f"""
        WITH inj AS (
          SELECT DISTINCT _source_run AS source_run, feed, record_id, defect_type, defect_subtype
          FROM {S.eval}.bronze_gt_dq_injections WHERE _corrupt_record IS NULL
        ),
        q AS (SELECT DISTINCT _source_run AS source_run, feed, record_id FROM {S.silver}.silver_quarantine
              WHERE record_id IS NOT NULL),
        sk AS (SELECT source_run, 'kpis' AS feed, record_id, count(*) AS n_copies, max(CAST(is_late AS INT)) AS late
               FROM {S.silver}.silver_kpis GROUP BY source_run, record_id
               UNION ALL
               SELECT source_run, 'alarms', record_id, count(*), max(CAST(is_late AS INT))
               FROM {S.silver}.silver_alarms GROUP BY source_run, record_id),
        -- silver_sessions is row-filtered for its readers (this MV included), so sessions are checked against
        -- bronze with the same late rule; their deduplication is the same code as kpis/alarms and not re-scored
        ss AS (SELECT _source_run AS source_run, 'sessions' AS feed, record_id, CAST(NULL AS BIGINT) AS n_copies,
                      max(CAST(unix_timestamp(try_to_timestamp(emitted_ts, "{TS}"))
                               - unix_timestamp(try_to_timestamp(end_ts, "{TS}")) > {late} AS INT)) AS late
               FROM {S.bronze}.bronze_sessions WHERE _corrupt_record IS NULL GROUP BY _source_run, record_id),
        s AS (SELECT * FROM sk UNION ALL SELECT * FROM ss)
        SELECT i.source_run, i.feed, i.defect_type, i.defect_subtype, count(*) AS n_injected,
               count(q.record_id) AS n_quarantined,
               count_if(q.record_id IS NULL AND s.record_id IS NOT NULL) AS n_kept_in_silver,
               count_if(s.late = 1) AS n_flagged_late,
               count_if(s.n_copies = 1) AS n_single_copy_in_silver,
               round(100.0 * CASE
                 WHEN i.defect_type IN ('malformed', 'null', 'out_of_range') THEN count(q.record_id)
                 WHEN i.defect_type = 'late_arrival' THEN count_if(s.late = 1)
                 WHEN i.defect_type = 'duplicate' AND i.feed <> 'sessions' THEN count_if(s.n_copies = 1)
               END / count(*), 1) AS handled_pct
        FROM inj i
        LEFT JOIN q ON q.source_run = i.source_run AND q.feed = i.feed AND q.record_id = i.record_id
        LEFT JOIN s ON s.source_run = i.source_run AND s.feed = i.feed AND s.record_id = i.record_id
        GROUP BY i.source_run, i.feed, i.defect_type, i.defect_subtype""")


@dp.materialized_view(
    name=f"{S.eval}.eval_rca_baseline",
    comment="Topology-heuristic RCA baseline for the later ML model: in the incident's region and first 15 minutes "
            "of impact, rank gold_element_impact_5m elements by impacted descendant cells (then higher in the tree) "
            "and score the top candidates against root_element_ids (hit@1 / hit@3).",
)
def eval_rca_baseline():
    return spark.sql(f"""
        WITH inc AS (
          SELECT * FROM {S.eval}.eval_gt_incidents
          WHERE is_customer_impacting AND NOT is_censored AND impact_start_ts IS NOT NULL
        ),
        cand AS (
          SELECT i.source_run, i.incident_id, f.element_id, f.element_type, f.level,
                 max(f.n_impacted_cells) AS n_impacted_cells, max(f.impacted_fraction) AS impacted_fraction,
                 max(f.n_service_down_alarms) AS n_service_down_alarms
          FROM inc i JOIN {S.gold}.gold_element_impact_5m f
            ON f.region_code = i.region_code
           AND f.window_start >= i.impact_start_ts - INTERVAL 5 MINUTES
           AND f.window_start < i.impact_start_ts + INTERVAL 15 MINUTES
          WHERE f.impacted_fraction >= 0.8 OR f.n_service_down_alarms > 0
          GROUP BY i.source_run, i.incident_id, f.element_id, f.element_type, f.level
        ),
        ranked AS (
          SELECT *, row_number() OVER (PARTITION BY source_run, incident_id
                                       ORDER BY n_impacted_cells DESC, level ASC, element_id) AS rk
          FROM cand
        ),
        top AS (
          SELECT source_run, incident_id, transform(array_sort(collect_list(struct(rk, element_id))), x -> x.element_id)
                 AS top_candidates
          FROM ranked WHERE rk <= 3 GROUP BY source_run, incident_id
        )
        SELECT i.source_run, i.incident_id, i.fault_type, i.root_element_id, i.root_element_type, i.root_element_ids,
               t.top_candidates,
               coalesce(array_contains(i.root_element_ids, element_at(t.top_candidates, 1)), false) AS hit_at_1,
               coalesce(size(array_intersect(i.root_element_ids, t.top_candidates)) > 0, false) AS hit_at_3
        FROM inc i LEFT JOIN top t ON t.source_run = i.source_run AND t.incident_id = i.incident_id""")
