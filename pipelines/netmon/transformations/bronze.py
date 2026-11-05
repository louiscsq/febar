# Bronze: Auto Loader streaming tables over the landing Volume, one per feed.
#
# Every generator run (`history/`, `stream/`, ...) is a sub-directory of the landing Volume, so one
# Auto Loader stream per feed globs over all of them. Schemas are explicit (netmon_pipeline.schemas):
# values that do not fit their declared type go to `_rescued_data`, unparseable lines to
# `_corrupt_record`, and nothing is dropped here. Ground truth is ingested into the eval schema so it
# can never be mistaken for a feature source.

import sys

sys.path.insert(0, spark.conf.get("netmon.src_path"))  # shared helpers synced with the bundle

from pyspark import pipelines as dp
from pyspark.sql import functions as F

from netmon_pipeline import paths, schemas
from netmon_pipeline.settings import Settings

S = Settings.from_conf(spark.conf.get)


def autoloader(feed: str):
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaEvolutionMode", "rescue")
        .option("rescuedDataColumn", schemas.RESCUE_COLUMN)
        .option("columnNameOfCorruptRecord", schemas.CORRUPT_COLUMN)
        .option("mode", "PERMISSIVE")
        # Ingest a whole history backfill in one micro-batch so downstream event-time watermarks start
        # from the full history (files are written in emission order, see docs/pipeline.md).
        .option("cloudFiles.maxFilesPerTrigger", "20000")
        .schema(schemas.with_corrupt_column(schemas.FEEDS[feed]))
        .load(S.feed_path(feed))
        .select(
            "*",
            F.col("_metadata.file_path").alias("_source_file"),
            F.col("_metadata.file_modification_time").alias("_file_modification_time"),
            F.current_timestamp().alias("_ingested_at"),
        )
        .withColumn("_source_run", F.expr(paths.run_name_sql("_source_file")))
    )


def bronze_table(name: str, feed: str, comment: str, cluster_by=None, target_schema=None):
    @dp.table(
        name=f"{target_schema or S.bronze}.{name}",
        comment=comment,
        cluster_by=cluster_by,
        table_properties={"quality": "bronze"},
    )
    def _t():
        return autoloader(feed)

    return _t


bronze_table("bronze_kpis", "kpis", "Raw per-cell KPI records (15-min history, 1-min streaming) as delivered by the "
             "PM collector. String timestamps; rescued/corrupt columns keep malformed input.", ["cell_id"])
bronze_table("bronze_alarms", "alarms", "Raw OSS fault-management alarm RAISE/CLEAR events.", ["element_id"])
bronze_table("bronze_sessions", "sessions", "Raw sampled xDR session records. Contains unmasked IMSI/MSISDN: "
             "no grants to NOC groups; consumers use silver_sessions (masked, row-filtered).", ["cell_id"])
bronze_table("bronze_topology_nodes", "topology_nodes", "Raw network inventory snapshots (one per generator run).")
bronze_table("bronze_topology_edges", "topology_edges", "Raw network topology edges (one snapshot per run).")
bronze_table("bronze_maintenance_windows", "maintenance_windows", "Raw change-management calendar.")
bronze_table("bronze_gt_incidents", "ground_truth/incidents", "GROUND TRUTH incident labels as written by the "
             "generator. Evaluation only: never a feature source.", target_schema=S.eval)
bronze_table("bronze_gt_dq_injections", "ground_truth/dq_injections", "GROUND TRUTH audit log of every injected "
             "data-quality defect. Evaluation only.", target_schema=S.eval)
