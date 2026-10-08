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
      SELECT *, CASE WHEN size(coalesce(root_element_ids, array())) > 0 THEN root_element_ids
                     ELSE array(root_element_id) END AS roots
      FROM {S.eval}.eval_gt_incidents
      WHERE is_customer_impacting AND NOT is_censored AND impact_start_ts IS NOT NULL
    ),
    -- (a) impact footprint: every element the incident touches (affected cells / elements and its roots)
    footprint AS (
      SELECT incident_id, source_run, explode(array_distinct(concat(roots, coalesce(affected_element_ids, array()),
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
      SELECT e.incident_id, e.source_run, array_contains(i.roots, d.element_id) AS on_root, d.* EXCEPT (source_run)
      FROM footprint e
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
             count(*) AS n_matched_detections, count(DISTINCT element_id) AS n_detected_elements,
             min(CASE WHEN on_root THEN available_ts END) AS root_detection_ts,
             min_by(element_id, CASE WHEN on_root THEN available_ts END) AS root_detection_element
      FROM m GROUP BY incident_id, source_run
    ),
    -- (b) localisation via the topology rollup: a root element itself shows the impact (>= 80 % of its
    -- descendant cells degraded or silent, or a service-down alarm on it). Earliest availability is a lower
    -- bound: evidence available, the 5-min window closed and the 2-min health watermark passed (MV refresh
    -- latency is not included).
    rollup AS (
      SELECT incident_id, source_run, first.ts AS rollup_ts, first.element_id AS rollup_element
      FROM (
        -- one min(struct(...)) so the reported element is the one of the earliest localisation
        SELECT i.incident_id, i.source_run,
               min(struct(greatest(f.window_end + INTERVAL 2 MINUTES, coalesce(f.evidence_ts, f.window_end)) AS ts,
                          f.element_id AS element_id)) AS first
        FROM inc i JOIN {S.gold}.gold_element_impact_5m f
          ON f.source_run = i.source_run AND array_contains(i.roots, f.element_id)
         AND f.window_end > i.impact_start_ts AND f.window_start < coalesce(i.impact_end_ts, i.end_ts)
        WHERE f.impacted_fraction >= 0.8 OR f.n_service_down_alarms > 0
        GROUP BY i.incident_id, i.source_run)
    ),
    joined AS (
      SELECT i.*, f.* EXCEPT (incident_id, source_run), r.rollup_ts, r.rollup_element,
             least(f.root_detection_ts, r.rollup_ts) AS localised_ts
      FROM inc i
      LEFT JOIN first_det f ON f.incident_id = i.incident_id AND f.source_run = i.source_run
      LEFT JOIN rollup r ON r.incident_id = i.incident_id AND r.source_run = i.source_run
    )
    SELECT source_run, incident_id, event_class, fault_type, severity, region_code, root_element_id,
           root_element_type, roots AS root_element_ids, impact_start_ts, impact_end_ts, n_affected_cells,
           estimated_impacted_subscribers,
           -- (a) customer-impact detection: any detection on the incident's footprint
           first_available_ts IS NOT NULL AS impact_detected,
           first_signal_source, first_element_id, first_element_type, first_flags, first_evidence_ts,
           first_pipeline_latency_s, n_matched_detections, n_detected_elements,
           greatest(unix_timestamp(first_evidence_ts) - unix_timestamp(impact_start_ts), 0) AS evidence_lag_s,
           greatest((unix_millis(first_available_ts) - unix_millis(impact_start_ts)) / 1000.0, 0) AS impact_ttd_s,
           coalesce((unix_millis(first_available_ts) - unix_millis(impact_start_ts)) / 1000.0 <= {scoring.SLA_S},
                    false) AS impact_within_sla,
           -- (b) root-element localisation: a detection, or the rollup, on an element of root_element_ids
           localised_ts IS NOT NULL AS root_localised,
           CASE WHEN localised_ts IS NULL THEN NULL
                WHEN root_detection_ts IS NOT NULL AND root_detection_ts <= coalesce(rollup_ts, root_detection_ts)
                  THEN 'detection' ELSE 'rollup' END AS localisation_source,
           coalesce(CASE WHEN root_detection_ts <= coalesce(rollup_ts, root_detection_ts) THEN root_detection_element END,
                    rollup_element) AS localised_element,
           greatest((unix_millis(localised_ts) - unix_millis(impact_start_ts)) / 1000.0, 0) AS localisation_ttd_s,
           coalesce((unix_millis(localised_ts) - unix_millis(impact_start_ts)) / 1000.0 <= {scoring.SLA_S},
                    false) AS localised_within_sla
    FROM joined
    """


@dp.materialized_view(
    name=f"{S.eval}.eval_incident_detection",
    comment="Per scored incident (customer-impacting, not censored), two separate metrics. (a) impact detection: "
            "first detection on any element of the incident's footprint (affected cells / elements or roots), "
            "impact_ttd_s and impact_within_sla. (b) root localisation: a detection or the topology rollup on an "
            "element of root_element_ids (any one counts for cluster faults), localisation_ttd_s.",
)
def eval_incident_detection():
    return spark.sql(_incident_detection_sql())


@dp.materialized_view(
    name=f"{S.eval}.eval_ttd_summary",
    comment="Per source run (history = 15-min ROP backfill, stream = 1-min live feed), per event class "
            "(fault first) and fault type: impact-detection rate / median / p90 TTD / % within 5 min, and the "
            "root-localisation rate / median TTD / % within 5 min.",
)
def eval_ttd_summary():
    return spark.sql(f"""
        SELECT source_run, coalesce(event_class, 'ALL') AS event_class, coalesce(fault_type, 'ALL') AS fault_type,
               count(*) AS n_incidents,
               count_if(impact_detected) AS n_impact_detected,
               round(100.0 * count_if(impact_detected) / count(*), 1) AS impact_detected_pct,
               round(percentile(impact_ttd_s, 0.5), 1) AS impact_median_ttd_s,
               round(percentile(impact_ttd_s, 0.9), 1) AS impact_p90_ttd_s,
               round(100.0 * count_if(impact_within_sla) / count(*), 1) AS impact_within_5min_pct,
               count_if(root_localised) AS n_root_localised,
               round(100.0 * count_if(root_localised) / count(*), 1) AS root_localised_pct,
               round(percentile(localisation_ttd_s, 0.5), 1) AS localisation_median_ttd_s,
               round(100.0 * count_if(localised_within_sla) / count(*), 1) AS localised_within_5min_pct,
               round(percentile(evidence_lag_s, 0.5), 1) AS median_evidence_lag_s,
               round(percentile(first_pipeline_latency_s, 0.5), 1) AS median_pipeline_latency_s
        FROM {S.eval}.eval_incident_detection
        GROUP BY GROUPING SETS ((source_run), (source_run, event_class), (source_run, event_class, fault_type))""")


def _labelled_sql() -> str:
    """CTEs ending in `labelled`: every detection row with its ground-truth label, in priority order
    (netmon_pipeline.scoring.label_detection)."""
    return f"""
        elems AS (
          SELECT source_run, incident_id, event_class, is_censored, start_ts, coalesce(end_ts, impact_end_ts) AS end_ts,
                 explode(array_distinct(concat(array(root_element_id), coalesce(root_element_ids, array()),
                         coalesce(affected_element_ids, array()), coalesce(affected_cell_ids, array())))) AS element_id
          FROM {S.eval}.eval_gt_incidents
        ),
        matched AS (
          SELECT d.source_run, d.detection_id,
                 max(CAST(e.event_class = 'fault' AND NOT e.is_censored AS INT)) AS m_fault,
                 max(CAST(e.is_censored AS INT)) AS m_censored,
                 max(CAST(e.event_class = 'planned' AND NOT e.is_censored AS INT)) AS m_planned,
                 max(CAST(e.event_class = 'red_herring' AND NOT e.is_censored AS INT)) AS m_red_herring
          FROM {S.eval}.eval_detection_log d
          JOIN elems e ON e.element_id = d.element_id AND e.source_run = d.source_run
           AND d.signal_end_ts > e.start_ts - INTERVAL 5 MINUTES
           AND (e.end_ts IS NULL OR d.signal_start_ts < e.end_ts + INTERVAL {scoring.MATCH_SLACK_S} SECONDS)
          GROUP BY d.source_run, d.detection_id
        ),
        labelled AS (
          SELECT d.source_run, d.detection_id, d.signal_source, d.element_id, d.signal_start_ts, d.in_maintenance,
                 CASE WHEN m.m_fault = 1 THEN 'fault'
                      WHEN m.m_censored = 1 THEN 'censored'
                      WHEN m.m_planned = 1 THEN 'planned'
                      WHEN m.m_red_herring = 1 THEN 'red_herring'
                      ELSE 'unexplained' END AS label
          FROM {S.eval}.eval_detection_log d
          LEFT JOIN matched m ON m.source_run = d.source_run AND m.detection_id = d.detection_id
        )"""


def _precision_select(unit: str, src: str) -> str:
    return f"""
        SELECT source_run, coalesce(signal_source, 'ALL') AS signal_source, count(*) AS n_{unit}s,
               count_if(label = 'fault') AS n_fault_tp,
               count_if(label = 'censored') AS n_censored_excluded,
               count_if(label = 'planned') AS n_planned,
               count_if(label = 'planned' AND in_maintenance) AS n_planned_suppressed,
               count_if(label = 'planned' AND NOT in_maintenance) AS n_planned_unsuppressed_fp,
               count_if(label = 'red_herring') AS n_red_herring_fp,
               count_if(label = 'unexplained') AS n_unexplained_fp,
               round(100.0 * count_if(label = 'fault') / nullif(count_if(label = 'fault')
                     + count_if(label = 'planned' AND NOT in_maintenance) + count_if(label = 'red_herring')
                     + count_if(label = 'unexplained'), 0), 1) AS {unit}_fault_precision_pct,
               round(100.0 * count_if(label = 'planned' AND in_maintenance) / nullif(count_if(label = 'planned'), 0), 1)
                 AS maintenance_suppression_pct
        FROM {src}
        GROUP BY GROUPING SETS ((source_run), (source_run, signal_source))"""


@dp.materialized_view(
    name=f"{S.eval}.eval_detection_precision",
    comment="Detection-ROW fault precision per source run and signal source (one row per detection, i.e. per "
            "degraded cell-minute or alarm). Labels in priority order: uncensored fault (TP), censored incident "
            "(excluded), planned work (suppressed if in_maintenance, else FP), red herring (FP), nothing (FP). "
            "row_fault_precision_pct = TP / (TP + FP). See eval_alert_precision for the alert-level figure.",
)
def eval_detection_precision():
    return spark.sql(f"WITH {_labelled_sql()}\n{_precision_select('row', 'labelled')}")


@dp.materialized_view(
    name=f"{S.eval}.eval_alert_precision",
    comment=f"Alert-level fault precision: detections grouped per (source_run, element_id) into episodes "
            f"(a gap of more than {scoring.ALERT_GAP_S // 60} min starts a new alert, i.e. a new page). An alert "
            "takes the highest-priority label of its detections and is suppressed when its first detection is in "
            "a change window. alert_fault_precision_pct = TP alerts / (TP + FP alerts).",
)
def eval_alert_precision():
    return spark.sql(f"""
        WITH {_labelled_sql()},
        ep AS (
          SELECT *, sum(new_alert) OVER (PARTITION BY source_run, element_id ORDER BY signal_start_ts, detection_id)
                    AS alert_seq
          FROM (SELECT *, CASE WHEN unix_timestamp(signal_start_ts) - unix_timestamp(lag(signal_start_ts) OVER (
                                      PARTITION BY source_run, element_id ORDER BY signal_start_ts, detection_id))
                                    <= {scoring.ALERT_GAP_S} THEN 0 ELSE 1 END AS new_alert
                FROM labelled)
        ),
        alerts AS (
          SELECT source_run, element_id, alert_seq,
                 min_by(signal_source, signal_start_ts) AS signal_source,
                 min_by(in_maintenance, signal_start_ts) AS in_maintenance,
                 CASE WHEN array_contains(collect_set(label), 'fault') THEN 'fault'
                      WHEN array_contains(collect_set(label), 'censored') THEN 'censored'
                      WHEN array_contains(collect_set(label), 'planned') THEN 'planned'
                      WHEN array_contains(collect_set(label), 'red_herring') THEN 'red_herring'
                      ELSE 'unexplained' END AS label,
                 count(*) AS n_rows
          FROM ep GROUP BY source_run, element_id, alert_seq
        )
        {_precision_select('alert', 'alerts')}""")


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
            ON f.source_run = i.source_run AND f.region_code = i.region_code
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
