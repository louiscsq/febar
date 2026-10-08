# Silver: typed, deduplicated, topology-enriched streaming tables with expectations and a quarantine.
#
# Per feed, a streaming temporary view `<feed>_typed` parses timestamps (UTC), drops redelivered
# duplicates on `record_id` within a watermark on delivery time, and joins the topology. Two flows read
# it: the silver table (`expect_all_or_drop` + warn-only late flag) and an append flow into
# `silver_quarantine` that keeps every dropped row with the names of the rules it failed. Unparseable
# JSON lines never reach the typed view; a separate flow sends them straight from bronze to quarantine.
# The rules themselves live in netmon_pipeline.rules (unit-tested against the generator).

import sys

sys.path.insert(0, spark.conf.get("netmon.src_path"))

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from netmon_pipeline import paths, rules
from netmon_pipeline.detection import DAY_TYPE_SQL, LOCAL_TS_SQL, alarm_signal_sql
from netmon_pipeline.settings import Settings

S = Settings.from_conf(spark.conf.get)
LATE = rules.LATE_THRESHOLD_S
RECORD_ID_RE = '"record_id":"([^"]+)"'
PII_REDACT = r"regexp_replace(regexp_replace({c}, '00101[0-9]{{10}}', '00101**********'), '[+]999[0-9]{{9}}', '+999*********')"


def ts(col: str):
    return F.expr(f'try_to_timestamp({col}, "{rules.TS_FORMAT}")')


def typed(feed: str, ts_cols: list[str], dedupe: bool = True):
    """Bronze stream minus corrupt lines, timestamps parsed, duplicates dropped on record_id."""
    df = spark.readStream.table(f"{S.bronze}.bronze_{feed}").where("_corrupt_record IS NULL")
    for c in ts_cols:
        df = df.withColumnRenamed(c, f"{c}_raw").withColumn(c, ts(f"{c}_raw"))
    if dedupe:
        df = (
            df.withColumn("_dedupe_key", F.expr("coalesce(record_id, sha2(to_json(struct(*)), 256))"))
            # Watermark on the ingestion time, which only moves forward: no row is ever late for the
            # deduper, whatever its event / delivery time or however late its file is discovered. Event and
            # delivery times are used for lateness metrics only (is_late). See netmon_pipeline.dedupe.
            .withWatermark(rules.DEDUPE_WATERMARK_COLUMN, rules.DEDUPE_WATERMARK)
            .dropDuplicatesWithinWatermark(["_dedupe_key"])
        )
    return (
        df.withColumn("source_run", F.col("_source_run"))
        # When the record's micro-batch file landed (simulated clock; NULL for batch history files), and
        # when its evidence became available to the NOC: the landing time, else the delivery time.
        .withColumn("landed_ts", F.expr(paths.landed_at_sql("_source_file", S.stream_step_seconds)))
        .withColumn("evidence_ts", F.coalesce("landed_ts", "emitted_ts"))
    )


def dim_cells():
    return (spark.read.table(f"{S.silver}.silver_topology_nodes").where("element_type = 'CELL'")
            .select(F.col("element_id").alias("cell_id"), "site_id", "backhaul_id", "router_id", "upf_id", "amf_id",
                    "region_code", "timezone"))


def dim_elements():
    return spark.read.table(f"{S.silver}.silver_topology_nodes").select(
        "element_id", "region_code", "timezone", "site_id", "backhaul_id", "router_id", "upf_id", "amf_id")


# ---------------------------------------------------------------------------------------------------
# Reference data (materialized views; a broken inventory fails the update)
# ---------------------------------------------------------------------------------------------------

@dp.materialized_view(
    name=f"{S.silver}.silver_topology_nodes",
    comment="Network inventory (one row per element, latest snapshot). Ancestor columns (amf_id .. site_id) "
            "include the element itself, so 'everything under X' is one equality filter.",
    cluster_by=["element_type", "region_code"],
)
@dp.expect_all_or_fail(rules.TOPOLOGY_FAIL)
def silver_topology_nodes():
    return spark.sql(f"""
        SELECT * EXCEPT (rn, _rescued_data, _corrupt_record, _ingested_at)
        FROM (SELECT *, row_number() OVER (PARTITION BY element_id
                                           ORDER BY _file_modification_time DESC, _source_file DESC) AS rn
              FROM {S.bronze}.bronze_topology_nodes WHERE _corrupt_record IS NULL)
        WHERE rn = 1""")


@dp.materialized_view(name=f"{S.silver}.silver_topology_edges", comment="Directed topology edges, upstream -> downstream.")
@dp.expect_or_fail("edge_endpoints_not_null", "parent_id IS NOT NULL AND child_id IS NOT NULL")
def silver_topology_edges():
    return spark.sql(f"""
        SELECT DISTINCT parent_id, child_id, edge_type, parent_type, child_type
        FROM {S.bronze}.bronze_topology_edges WHERE _corrupt_record IS NULL""")


@dp.materialized_view(name=f"{S.silver}.silver_maintenance_windows",
                      comment="Approved change windows (UTC). Operational data the NOC uses to suppress planned work.")
@dp.expect_or_drop("valid_window", "planned_start_ts IS NOT NULL AND planned_end_ts > planned_start_ts")
def silver_maintenance_windows():
    return spark.sql(f"""
        SELECT DISTINCT _source_run AS source_run, change_id, element_id, element_type,
               try_to_timestamp(planned_start_ts, "{rules.TS_FORMAT}") AS planned_start_ts,
               try_to_timestamp(planned_end_ts, "{rules.TS_FORMAT}") AS planned_end_ts,
               change_type, status
        FROM {S.bronze}.bronze_maintenance_windows WHERE _corrupt_record IS NULL""")


# ---------------------------------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------------------------------

KPI_METRICS = ["availability_pct", "active_users", "prb_util_pct", "rrc_setup_success_pct", "attach_success_pct",
               "session_drop_rate_pct", "dl_throughput_mbps", "ul_throughput_mbps", "latency_ms", "packet_loss_pct"]


@dp.temporary_view(name="kpis_typed")
def kpis_typed():
    return (
        typed("kpis", ["event_ts", "emitted_ts"])
        .join(F.broadcast(dim_cells()), "cell_id", "left")
        .withColumn("event_end_ts", F.expr("timestampadd(SECOND, granularity_s, event_ts)"))
        .withColumn("lag_s", F.expr("unix_timestamp(emitted_ts) - unix_timestamp(event_end_ts)"))
        .withColumn("is_late", F.expr(f"coalesce(lag_s > {LATE}, false)"))
        .withColumn("event_ts_local", F.expr(LOCAL_TS_SQL.format(ts="event_ts")))
        .withColumn("local_date", F.expr("to_date(event_ts_local)"))  # baseline day (local calendar)
        .withColumn("local_hour", F.expr("hour(event_ts_local)"))
        .withColumn("day_type", F.expr(DAY_TYPE_SQL.format(ts="event_ts_local")))
        .withColumn("event_date", F.expr("to_date(event_ts)"))  # UTC date, for clustering only
    )


@dp.table(
    name=f"{S.silver}.silver_kpis",
    comment="Validated per-cell KPI records: typed, UTC timestamps plus local time / local date from the cell's IANA zone, "
            "deduplicated on record_id, enriched with the cell's ancestors. Late arrivals kept (is_late).",
    cluster_by=["event_date", "cell_id"],
    table_properties={"quality": "silver"},
)
@dp.expect_all_or_drop(rules.drop_expectations("kpis"))
@dp.expect_all(rules.warn_expectations("kpis"))
def silver_kpis():
    return spark.readStream.table("kpis_typed").select(
        "record_id", "cell_id", "site_id", "backhaul_id", "router_id", "upf_id", "amf_id", "region_code", "timezone",
        "event_ts", "event_end_ts", "emitted_ts", "event_ts_local", "local_date", "local_hour", "day_type",
        "event_date",
        "granularity_s", *KPI_METRICS, "lag_s", "is_late", "landed_ts", "evidence_ts", "source_run",
        "_rescued_data", "_source_file", "_file_modification_time", "_ingested_at")


# ---------------------------------------------------------------------------------------------------
# Alarms
# ---------------------------------------------------------------------------------------------------

@dp.temporary_view(name="alarms_typed")
def alarms_typed():
    return (
        typed("alarms", ["event_ts", "emitted_ts"])
        .join(F.broadcast(dim_elements()), "element_id", "left")
        .withColumn("lag_s", F.expr("unix_timestamp(emitted_ts) - unix_timestamp(event_ts)"))
        .withColumn("is_late", F.expr(f"coalesce(lag_s > {LATE}, false)"))
        .withColumn("event_ts_local", F.expr("from_utc_timestamp(event_ts, timezone)"))
        .withColumn("is_service_down", F.expr(f"coalesce({alarm_signal_sql()}, false)"))
    )


@dp.table(
    name=f"{S.silver}.silver_alarms",
    comment="Validated alarm RAISE/CLEAR events with the element's region and ancestors. is_service_down marks "
            "element-down alarms that imply lost customer service (dark sites send no KPIs).",
    cluster_by=["element_id"],
    table_properties={"quality": "silver"},
)
@dp.expect_all_or_drop(rules.drop_expectations("alarms"))
@dp.expect_all(rules.warn_expectations("alarms"))
def silver_alarms():
    return spark.readStream.table("alarms_typed").select(
        "record_id", "alarm_id", "event_type", "element_id", "element_type", "alarm_code", "severity",
        "event_ts", "emitted_ts", "event_ts_local", "vendor", "additional_text", "source_system",
        "region_code", "site_id", "backhaul_id", "router_id", "upf_id", "amf_id", "is_service_down",
        "lag_s", "is_late", "landed_ts", "evidence_ts", "source_run", "_source_file", "_file_modification_time",
        "_ingested_at")


# ---------------------------------------------------------------------------------------------------
# Sessions (PII: IMSI / MSISDN column masks and a regional row filter, both declared here and backed by
# the UC functions in governance/sql/01_functions.sql)
# ---------------------------------------------------------------------------------------------------

def _sessions(dedupe: bool):
    return (
        typed("sessions", ["start_ts", "end_ts", "emitted_ts"], dedupe=dedupe)
        .join(F.broadcast(dim_cells().select("cell_id", "site_id", "region_code", "timezone")), "cell_id", "left")
        # Pseudonymous subscriber key for downstream counts (not reversible from the gold tables alone).
        .withColumn("subscriber_key", F.expr("sha2(concat('banksia-netmon:', imsi), 256)"))
        .withColumn("lag_s", F.expr("unix_timestamp(emitted_ts) - unix_timestamp(end_ts)"))
        .withColumn("is_late", F.expr(f"coalesce(lag_s > {LATE}, false)"))
        .withColumn("start_ts_local", F.expr("from_utc_timestamp(start_ts, timezone)"))
    )


@dp.temporary_view(name="sessions_typed")
def sessions_typed():
    return _sessions(dedupe=True)


@dp.temporary_view(name="sessions_events")
def sessions_events():
    """Typed sessions without a watermark, for gold windows that need their own event-time watermark."""
    return _sessions(dedupe=False)


SESSIONS_SCHEMA = f"""
  record_id STRING COMMENT 'xDR session id (dedupe key)',
  imsi STRING MASK {S.gov}.mask_imsi COMMENT 'PII: subscriber IMSI (masked unless pii_privileged)',
  msisdn STRING MASK {S.gov}.mask_msisdn COMMENT 'PII: subscriber MSISDN (masked unless pii_privileged)',
  subscriber_key STRING COMMENT 'Pseudonymous SHA-256 subscriber key for distinct counts',
  cell_id STRING, site_id STRING,
  region_code STRING COMMENT 'Region of the serving cell (row-filter key)',
  start_ts TIMESTAMP COMMENT 'UTC', end_ts TIMESTAMP COMMENT 'UTC', emitted_ts TIMESTAMP COMMENT 'UTC',
  start_ts_local TIMESTAMP COMMENT 'Session start in the cell local time zone',
  duration_s BIGINT, service_type STRING, dnn STRING, bytes_dl BIGINT, bytes_ul BIGINT,
  outcome STRING, cause_code STRING, lag_s BIGINT, is_late BOOLEAN, evidence_ts TIMESTAMP, source_run STRING,
  _rescued_data STRING, _source_file STRING, _ingested_at TIMESTAMP
"""
SESSION_COLS = ["record_id", "imsi", "msisdn", "subscriber_key", "cell_id", "site_id", "region_code", "start_ts",
                "end_ts", "emitted_ts", "start_ts_local", "duration_s", "service_type", "dnn", "bytes_dl", "bytes_ul",
                "outcome", "cause_code", "lag_s", "is_late", "evidence_ts", "source_run", "_rescued_data",
                "_source_file", "_ingested_at"]


@dp.table(
    name=f"{S.silver}.silver_sessions",
    comment="Validated sampled xDR sessions. IMSI/MSISDN are column-masked and rows are filtered by the reader's "
            "regional NOC group. Gold reads sessions_typed, never this table.",
    schema=SESSIONS_SCHEMA,
    row_filter=f"ROW FILTER {S.gov}.region_filter ON (region_code)",
    cluster_by=["region_code", "cell_id"],
    table_properties={"quality": "silver"},
)
@dp.expect_all_or_drop(rules.drop_expectations("sessions"))
@dp.expect_all(rules.warn_expectations("sessions"))
def silver_sessions():
    return spark.readStream.table("sessions_typed").select(*SESSION_COLS)


# ---------------------------------------------------------------------------------------------------
# Quarantine: every row a DROP rule removed, with the rules it failed (PII redacted)
# ---------------------------------------------------------------------------------------------------

dp.create_streaming_table(
    name=f"{S.silver}.silver_quarantine",
    comment="Rows rejected by silver expectations (malformed, null, out-of-range, unknown element) and "
            "unparseable JSON lines, with failed_rules. IMSI/MSISDN redacted. Not granted to regional groups.",
    cluster_by=["feed"],
    table_properties={"quality": "quarantine"},
)

QUARANTINE_PAYLOAD = {
    "kpis": ["cell_id", "event_ts_raw", "granularity_s", *KPI_METRICS],
    "alarms": ["alarm_id", "event_type", "element_id", "element_type", "alarm_code", "severity", "event_ts_raw"],
    "sessions": ["cell_id", "start_ts_raw", "end_ts_raw", "duration_s", "service_type", "bytes_dl", "bytes_ul",
                 "outcome", "cause_code"],  # no IMSI / MSISDN
}
EVENT_TS_RAW = {"kpis": "event_ts_raw", "alarms": "event_ts_raw", "sessions": "start_ts_raw"}


def quarantine_flows(feed: str) -> None:
    drop = rules.drop_expectations(feed)

    @dp.append_flow(target=f"{S.silver}.silver_quarantine", name=f"quarantine_{feed}")
    def _rejected():
        payload = ", ".join(QUARANTINE_PAYLOAD[feed])
        return spark.readStream.table(f"{feed}_typed").where(f"NOT ({rules.all_pass_sql(drop)})").selectExpr(
            f"'{feed}' AS feed", "record_id", f"{rules.failed_rules_sql(drop)} AS failed_rules",
            f"{EVENT_TS_RAW[feed]} AS event_ts_raw", "emitted_ts_raw", f"to_json(struct({payload})) AS payload",
            f"{PII_REDACT.format(c='_rescued_data')} AS _rescued_data", "CAST(NULL AS STRING) AS _corrupt_record",
            "_source_run", "_source_file", "_ingested_at")

    @dp.append_flow(target=f"{S.silver}.silver_quarantine", name=f"quarantine_{feed}_corrupt")
    def _corrupt():
        return spark.readStream.table(f"{S.bronze}.bronze_{feed}").where("_corrupt_record IS NOT NULL").selectExpr(
            # A truncated line usually still starts with its record_id; keep it so defects can be traced.
            f"'{feed}' AS feed", f"nullif(regexp_extract(_corrupt_record, '{RECORD_ID_RE}', 1), '') AS record_id",
            "array('parseable_record') AS failed_rules",
            "CAST(NULL AS STRING) AS event_ts_raw", "CAST(NULL AS STRING) AS emitted_ts_raw",
            "CAST(NULL AS STRING) AS payload", "CAST(NULL AS STRING) AS _rescued_data",
            f"{PII_REDACT.format(c='_corrupt_record')} AS _corrupt_record",
            "_source_run", "_source_file", "_ingested_at")


for _feed in ("kpis", "alarms", "sessions"):
    quarantine_flows(_feed)
