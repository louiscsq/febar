# Gold: per-cell health windows with baseline deviation, customer-impact detections, the topology
# rollup of impact (root-cause candidate features) and per-cell session outcomes.
#
# Latency budget (docs/pipeline.md): detections are stateless per KPI record / alarm, so they are emitted
# as soon as the record is ingested, without waiting for a window to close. The 1-minute and 5-minute
# health windows are append-mode aggregates behind a 2-minute event-time watermark, used for trends,
# the topology rollup and ML features.

import sys

sys.path.insert(0, spark.conf.get("netmon.src_path"))

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from netmon_pipeline import detection, hierarchy, rules
from netmon_pipeline.settings import Settings

S = Settings.from_conf(spark.conf.get)
HEALTH_WATERMARK = "2 minutes"
METRICS = ["availability_pct", "active_users", "prb_util_pct", "rrc_setup_success_pct", "attach_success_pct",
           "session_drop_rate_pct", "dl_throughput_mbps", "ul_throughput_mbps", "latency_ms", "packet_loss_pct"]
BASE = detection.BASELINE_METRICS
BASE_COLS = [f"b_{m}_{s}" for m in BASE for s in ("mean", "std")]
ANCESTOR_COLS = ["site_id", "backhaul_id", "router_id", "upf_id", "amf_id"]


# ---------------------------------------------------------------------------------------------------
# (a) Baseline: same cell, same local hour and day type, trailing 14 days strictly before the day it is
# used on. Each row is valid for exactly one UTC date, so scoring a record never sees its own day or the
# future (no leakage, also when the whole history is backfilled at once).
# ---------------------------------------------------------------------------------------------------

def _baseline_sql() -> str:
    moments = ",\n".join(f"count({m}) AS n_{m}, sum({m}) AS s_{m}, sum({m} * {m}) AS ss_{m}" for m in BASE)
    stats = ",\n".join(
        f"sum(s_{m}) / sum(n_{m}) AS b_{m}_mean,\n"
        f"sqrt(greatest(sum(ss_{m}) - sum(s_{m}) * sum(s_{m}) / sum(n_{m}), 0) / nullif(sum(n_{m}) - 1, 0)) AS b_{m}_std"
        for m in BASE)
    return f"""
    WITH daily AS (
      SELECT cell_id, local_hour, day_type, event_date, count(*) AS n, {moments}
      FROM {S.silver}.silver_kpis
      -- outage periods would drag the baseline down; hard-rule failures are excluded from it
      WHERE availability_pct >= 99 AND attach_success_pct >= 95 AND rrc_setup_success_pct >= 80
      GROUP BY cell_id, local_hour, day_type, event_date
    ),
    dates AS (
      SELECT explode(sequence(date_add(min(event_date), 1), date_add(max(event_date), 1))) AS valid_date FROM daily
    )
    SELECT d.valid_date, x.cell_id, x.local_hour, x.day_type, sum(x.n) AS n_samples, count(*) AS n_days,
           {stats}
    FROM dates d
    JOIN daily x ON x.event_date BETWEEN date_sub(d.valid_date, {detection.BASELINE_LOOKBACK_DAYS})
                                     AND date_sub(d.valid_date, 1)
    GROUP BY d.valid_date, x.cell_id, x.local_hour, x.day_type
    """


@dp.materialized_view(
    name=f"{S.gold}.gold_cell_baseline",
    comment="Per cell x local hour x day type (weekday/weekend) KPI mean and std over the 14 days strictly "
            "before valid_date. Join on (cell_id, local_hour, day_type, valid_date = UTC event date).",
    cluster_by=["valid_date", "cell_id"],
)
def gold_cell_baseline():
    return spark.sql(_baseline_sql())


@dp.temporary_view(name="kpis_scored")
def kpis_scored():
    """Silver KPI stream joined to its baseline, with z-scores and the detection rules that fire."""
    base = spark.read.table(f"{S.gold}.gold_cell_baseline").withColumnRenamed("valid_date", "event_date") \
        .select("cell_id", "local_hour", "day_type", "event_date", "n_days", *BASE_COLS)
    df = spark.readStream.table(f"{S.silver}.silver_kpis").join(
        F.broadcast(base), ["cell_id", "local_hour", "day_type", "event_date"], "left")
    for m in BASE:
        df = df.withColumn(f"{m}_z", F.expr(detection.zscore_sql(m)))
    return df.withColumn("flags", F.expr(detection.flags_sql()))


def health(width: str):
    agg = (
        spark.readStream.table("kpis_scored")
        .withWatermark("event_ts", HEALTH_WATERMARK)
        .groupBy(F.window("event_ts", width).alias("w"), "cell_id", *ANCESTOR_COLS, "region_code", "timezone")
        .agg(
            F.count("*").alias("n_reports"),
            F.max("granularity_s").alias("granularity_s"),
            F.min("availability_pct").alias("min_availability_pct"),
            *[F.avg(m).alias(m) for m in METRICS],
            *[F.avg(c).alias(c) for c in BASE_COLS],
            F.sum(F.when(F.size("flags") > 0, 1).otherwise(0)).alias("n_flagged_reports"),
            F.sum(F.col("is_late").cast("int")).alias("n_late_reports"),
            F.max("evidence_ts").alias("evidence_ts"),
        )
    )
    out = (
        agg.withColumn("window_start", F.col("w.start")).withColumn("window_end", F.col("w.end")).drop("w")
        .withColumn("window_start_local", F.expr("from_utc_timestamp(window_start, timezone)"))
    )
    for m in BASE:
        out = out.withColumn(f"{m}_z", F.expr(detection.zscore_sql(m)))
    return (
        out.withColumn("flags", F.expr(detection.flags_sql()))
        .withColumn("is_degraded", F.size("flags") > 0)
        .withColumn("max_abs_z", F.greatest(*[F.abs(F.col(f"{m}_z")) for m in BASE]))
    )


@dp.table(
    name=f"{S.gold}.gold_cell_health_1m",
    comment="Per-cell 1-minute KPI windows (event time, UTC) with baseline means, z-scores, fired rules and "
            "is_degraded. Append-only behind a 2-minute watermark. 15-min history rows fill one window each.",
    cluster_by=["window_start", "cell_id"],
    table_properties={"quality": "gold"},
)
def gold_cell_health_1m():
    return health("1 minute")


@dp.table(
    name=f"{S.gold}.gold_cell_health_5m",
    comment="Per-cell 5-minute KPI windows with baseline deviation. Feeds the topology rollup and ML features.",
    cluster_by=["window_start", "cell_id"],
    table_properties={"quality": "gold"},
)
def gold_cell_health_5m():
    return health("5 minutes")


# ---------------------------------------------------------------------------------------------------
# (b) Impact detections: one row per degraded KPI record or element-down alarm, as soon as it arrives.
# ---------------------------------------------------------------------------------------------------

SEVERITY = ("CASE WHEN array_contains(flags, 'cell_unavailable') OR signal_source = 'alarm' THEN 3 "
            "WHEN array_contains(flags, 'attach_failure') OR array_contains(flags, 'rrc_collapse') THEN 2 ELSE 1 END")


@dp.temporary_view(name="impact_signals")
def impact_signals():
    kpi = (
        spark.readStream.table("kpis_scored").where(F.size("flags") > 0)
        .selectExpr(
            "sha2(concat('kpi|', record_id), 256) AS detection_id", "'kpi' AS signal_source",
            "cell_id AS element_id", "'CELL' AS element_type", "cell_id", *ANCESTOR_COLS, "region_code",
            "event_ts AS signal_start_ts", "event_end_ts AS signal_end_ts", "flags",
            "availability_pct", "attach_success_pct", "rrc_setup_success_pct", "latency_ms", "packet_loss_pct",
            "dl_throughput_mbps", "latency_ms_z", "dl_throughput_mbps_z",
            "landed_ts", "evidence_ts", "_file_modification_time", "source_run", "record_id")
    )
    alarm = (
        spark.readStream.table(f"{S.silver}.silver_alarms").where("is_service_down")
        .selectExpr(
            "sha2(concat('alarm|', record_id), 256) AS detection_id", "'alarm' AS signal_source",
            "element_id", "element_type", "CASE WHEN element_type = 'CELL' THEN element_id END AS cell_id",
            *ANCESTOR_COLS, "region_code", "event_ts AS signal_start_ts",
            "event_ts + INTERVAL 1 MINUTE AS signal_end_ts", "array(alarm_code) AS flags",
            "landed_ts", "evidence_ts", "_file_modification_time", "source_run", "record_id")
    )
    maint = spark.read.table(f"{S.silver}.silver_maintenance_windows").select(
        F.col("element_id").alias("m_element_id"), "planned_start_ts", "planned_end_ts")
    sig = kpi.unionByName(alarm, allowMissingColumns=True)
    cond = (F.col("m_element_id").isin(F.col("site_id"), F.col("router_id"))
            & (F.col("signal_start_ts") >= F.col("planned_start_ts"))
            & (F.col("signal_start_ts") < F.col("planned_end_ts")))
    return (
        sig.join(F.broadcast(maint), cond, "left")
        .withColumn("in_maintenance", F.col("m_element_id").isNotNull())
        .drop("m_element_id", "planned_start_ts", "planned_end_ts")
        .withColumn("severity_score", F.expr(SEVERITY))
        .withColumn("detected_ts", F.current_timestamp())
        # Wall-clock time from the file landing in the Volume to this row being produced.
        .withColumn("pipeline_latency_s",
                    F.expr("(unix_millis(detected_ts) - unix_millis(_file_modification_time)) / 1000.0"))
        .withColumnRenamed("_file_modification_time", "file_landed_ts")
    )


@dp.table(
    name=f"{S.gold}.gold_impact_detections",
    comment="Customer-impact detections per cell (KPI rules vs baseline) or element (element-down alarms), "
            "with detected_ts (wall clock), evidence_ts and pipeline_latency_s. Row-filtered by regional NOC group.",
    row_filter=f"ROW FILTER {S.gov}.region_filter ON (region_code)",
    cluster_by=["region_code", "signal_start_ts"],
    table_properties={"quality": "gold"},
)
def gold_impact_detections():
    return spark.readStream.table("impact_signals")


# ---------------------------------------------------------------------------------------------------
# Session outcomes per cell (customer-experience features; no PII)
# ---------------------------------------------------------------------------------------------------

@dp.table(
    name=f"{S.gold}.gold_cell_sessions_5m",
    comment="Per-cell 5-minute session outcomes by session end time: setup failures, drops, no-service and "
            "approximate distinct subscribers (pseudonymous key). No IMSI/MSISDN.",
    cluster_by=["window_start", "cell_id"],
    table_properties={"quality": "gold"},
)
def gold_cell_sessions_5m():
    ok = rules.all_pass_sql(rules.drop_expectations("sessions"))
    return (
        spark.readStream.table("sessions_typed").where(ok)
        .withWatermark("end_ts", "5 minutes")
        .groupBy(F.window("end_ts", "5 minutes").alias("w"), "cell_id", "site_id", "region_code")
        .agg(
            F.count("*").alias("n_sessions"),
            F.sum(F.expr("CAST(outcome = 'SETUP_FAILED' AS INT)")).alias("n_setup_failed"),
            F.sum(F.expr("CAST(outcome = 'DROPPED' AS INT)")).alias("n_dropped"),
            F.sum(F.expr("CAST(cause_code = 'NO_SERVICE' AS INT)")).alias("n_no_service"),
            F.approx_count_distinct("subscriber_key").alias("n_subscribers_approx"),
            F.sum("bytes_dl").alias("bytes_dl"),
        )
        .selectExpr("w.start AS window_start", "w.end AS window_end", "* EXCEPT (w)")
        .withColumn("failure_rate", F.expr("(n_setup_failed + n_dropped) / n_sessions"))
    )


# ---------------------------------------------------------------------------------------------------
# (c) Topology rollup: impact per element per 5-minute window, counted over descendant cells, with
# alarms on the element and its subtree. Candidate root-cause features; no ground truth is read.
# ---------------------------------------------------------------------------------------------------

def _rollup_sql() -> str:
    t, h, a, m = (f"{S.silver}.silver_topology_nodes", f"{S.gold}.gold_cell_health_5m",
                  f"{S.silver}.silver_alarms", f"{S.silver}.silver_maintenance_windows")
    return f"""
    WITH windows AS (SELECT DISTINCT window_start, window_end FROM {h}),
    cells AS (SELECT element_id AS cell_id, {", ".join(ANCESTOR_COLS)}, region_code FROM {t} WHERE element_type = 'CELL'),
    -- every cell in every window: a cell with no KPI row while others reported is silent (dark)
    status AS (
      SELECT w.window_start, w.window_end, c.*, hc.cell_id IS NULL AS is_silent,
             coalesce(hc.is_degraded, false) AS is_degraded, hc.latency_ms_z, hc.dl_throughput_mbps_z
      FROM windows w CROSS JOIN cells c
      LEFT JOIN {h} hc ON hc.window_start = w.window_start AND hc.cell_id = c.cell_id
    ),
    rolled AS (
      SELECT window_start, window_end, region_code, cell_id, is_silent, is_degraded, latency_ms_z,
             dl_throughput_mbps_z, {hierarchy.stack_sql("cell_id")}
      FROM status
    ),
    agg AS (
      SELECT window_start, window_end, element_id, element_type, level, first(region_code) AS region_code,
             count(*) AS n_desc_cells,
             sum(CAST(is_silent AS INT)) AS n_silent_cells,
             sum(CAST(is_degraded AS INT)) AS n_degraded_cells,
             sum(CAST(is_silent OR is_degraded AS INT)) AS n_impacted_cells,
             avg(latency_ms_z) AS avg_latency_z, avg(dl_throughput_mbps_z) AS avg_dl_throughput_z
      FROM rolled GROUP BY window_start, window_end, element_id, element_type, level
    ),
    children AS (
      SELECT g.window_start, n.parent_id AS element_id, count(*) AS n_children,
             sum(CAST(g.n_impacted_cells > 0 AS INT)) AS n_impacted_children
      FROM agg g JOIN {t} n ON n.element_id = g.element_id
      WHERE n.parent_id IS NOT NULL GROUP BY g.window_start, n.parent_id
    ),
    alarms_raised AS (
      SELECT window(event_ts, '5 minutes').start AS window_start, element_id, upf_id, router_id, backhaul_id,
             site_id, amf_id, alarm_code, severity, is_service_down
      FROM {a} WHERE event_type = 'RAISE'
    ),
    own_alarms AS (
      SELECT window_start, element_id, count(*) AS n_alarms,
             sum(CAST(severity = 'CRITICAL' AS INT)) AS n_critical_alarms,
             sum(CAST(is_service_down AS INT)) AS n_service_down_alarms,
             array_sort(collect_set(alarm_code)) AS alarm_codes
      FROM alarms_raised GROUP BY window_start, element_id
    ),
    -- ancestor columns include the element itself, so this counts alarms anywhere in each subtree
    subtree_alarms AS (
      SELECT window_start, anc AS element_id, count(*) AS n_subtree_alarms,
             sum(CAST(is_service_down AS INT)) AS n_subtree_service_down_alarms
      FROM (SELECT window_start, element_id, is_service_down,
                   explode(array_distinct(filter(array(element_id, site_id, backhaul_id, router_id, upf_id, amf_id),
                                                 x -> x IS NOT NULL))) AS anc
            FROM alarms_raised)
      GROUP BY window_start, anc
    ),
    maint AS (
      SELECT DISTINCT w.window_start, mw.element_id
      FROM windows w JOIN {m} mw ON mw.planned_start_ts < w.window_end AND mw.planned_end_ts > w.window_start
    )
    SELECT g.window_start, g.window_end, g.element_id, g.element_type, g.level, g.region_code, n.parent_id,
           g.n_desc_cells, g.n_silent_cells, g.n_degraded_cells, g.n_impacted_cells,
           g.n_impacted_cells / g.n_desc_cells AS impacted_fraction,
           coalesce(c.n_children, 0) AS n_children, coalesce(c.n_impacted_children, 0) AS n_impacted_children,
           coalesce(c.n_impacted_children / c.n_children, 0) AS impacted_children_fraction,
           p.n_impacted_cells / p.n_desc_cells AS parent_impacted_fraction,
           g.avg_latency_z, g.avg_dl_throughput_z,
           coalesce(o.n_alarms, 0) AS n_alarms, coalesce(o.n_critical_alarms, 0) AS n_critical_alarms,
           coalesce(o.n_service_down_alarms, 0) AS n_service_down_alarms, o.alarm_codes,
           coalesce(s.n_subtree_alarms, 0) AS n_subtree_alarms,
           coalesce(s.n_subtree_service_down_alarms, 0) AS n_subtree_service_down_alarms,
           mt.element_id IS NOT NULL AS in_maintenance_window
    FROM agg g
    JOIN {t} n ON n.element_id = g.element_id
    LEFT JOIN children c ON c.window_start = g.window_start AND c.element_id = g.element_id
    LEFT JOIN agg p ON p.window_start = g.window_start AND p.element_id = n.parent_id
    LEFT JOIN own_alarms o ON o.window_start = g.window_start AND o.element_id = g.element_id
    LEFT JOIN subtree_alarms s ON s.window_start = g.window_start AND s.element_id = g.element_id
    LEFT JOIN maint mt ON mt.window_start = g.window_start AND mt.element_id = g.element_id
    WHERE g.n_impacted_cells > 0 OR o.n_alarms > 0
    """


@dp.materialized_view(
    name=f"{S.gold}.gold_element_impact_5m",
    comment="Topology rollup per element per 5-min window: impacted (degraded or silent) descendant cells, "
            "impacted children, parent impact, alarms on the element and in its subtree, maintenance flag. "
            "Root-cause candidate features for the RCA model. Only elements with impact or alarms are kept.",
    cluster_by=["window_start", "element_id"],
)
def gold_element_impact_5m():
    return spark.sql(_rollup_sql())
