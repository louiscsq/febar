"""Which KPI records a real-time health window is built from, and when that window became observable.

One rule for both qualification and timing. The real-time windows (`gold_cell_health_1m` / `_5m`, and so
`gold_element_impact_5m` and rollup localisation) are built **only from on-time records** (`NOT is_late`).
Each window's `evidence_ts` is the latest arrival among exactly those records. So a window can only qualify
(degraded, or a cell silent) on evidence that had arrived by its `evidence_ts`, and never be timed by
records other than the ones that made it qualify.

Late records (delivered more than `rules.LATE_THRESHOLD_S` after their period) stay in silver and in the
separate `gold_cell_health_5m_retrospective` aggregate, which no time-to-detect or localisation metric
reads. Per-record detections from a late record are kept: they are timed at that record's own arrival,
so they can only make a time-to-detect later, never earlier.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

REALTIME_FILTER_SQL = "NOT is_late"


def realtime_window(rows: Iterable[Mapping], window_end_s: float, watermark_s: float) -> dict:
    """Python mirror of one real-time cell window. `rows`: is_late, degraded, evidence_s.

    Returns whether the window qualifies (degraded), whether the cell is silent (no on-time report), and
    the earliest time the window's state was observable: the latest arrival of the rows it is built from,
    and no earlier than the window closing behind the watermark."""
    used = [r for r in rows if not r.get("is_late")]
    closes = window_end_s + watermark_s
    if not used:
        return {"n_reports": 0, "silent": True, "degraded": False, "available_s": closes}
    return {"n_reports": len(used), "silent": False, "degraded": any(r.get("degraded") for r in used),
            "available_s": max(closes, max(r["evidence_s"] for r in used))}


def is_late_sql(lag_col: str = "lag_s") -> str:
    """The late-data rule as the pipeline applies it in silver (`is_late`): delivered more than
    `rules.LATE_THRESHOLD_S` after the measured interval ended. `lag_col` = delivery - interval end."""
    from netmon_pipeline import rules

    return f"coalesce({lag_col} > {rules.LATE_THRESHOLD_S}, false)"


# ---------------------------------------------------------------------------------------------------
# Spark transforms shared by the pipeline (pipelines/netmon/transformations/gold.py) and the tests, so the
# Python mirror above is checked against the code that actually runs. pyspark is imported lazily: the
# rest of this package stays importable without it.
# ---------------------------------------------------------------------------------------------------

BASELINE_KEYS = ["cell_id", "local_hour", "day_type", "local_date"]


def score_against_baseline(kpis, baseline):
    """Per-record baseline comparison, shared by the real-time stream (`kpis_scored`) and the
    after-the-fact retrospective table: join the record's baseline row (same cell, local hour, day type,
    valid for the record's local date), add `<metric>_z` and the fired detection rules (`flags`)."""
    from pyspark.sql import functions as F

    from netmon_pipeline import detection

    base_cols = [f"b_{m}_{s}" for m in detection.BASELINE_METRICS for s in ("mean", "std")]
    base = baseline.withColumnRenamed("valid_date", "local_date").select(*BASELINE_KEYS, "n_days", *base_cols)
    df = kpis.join(F.broadcast(base), BASELINE_KEYS, "left")
    for m in detection.BASELINE_METRICS:
        df = df.withColumn(f"{m}_z", F.expr(detection.zscore_sql(m)))
    return df.withColumn("flags", F.expr(detection.flags_sql()))


def realtime_records(scored):
    """The records a real-time window is built from: on-time only (`REALTIME_FILTER_SQL`)."""
    return scored.where(REALTIME_FILTER_SQL)


def window_health(df, width: str, metrics: list[str], ancestor_cols: list[str]):
    """Per-cell window aggregate, baseline z-scores and fired rules over `df` (stream or batch).
    `evidence_ts` is the latest arrival among exactly the records the window is built from."""
    from pyspark.sql import functions as F

    from netmon_pipeline import detection

    base = detection.BASELINE_METRICS
    base_cols = [f"b_{m}_{s}" for m in base for s in ("mean", "std")]
    agg = (
        # source_run keeps generator runs apart even if their windows ever overlap in time.
        df.groupBy(F.window("event_ts", width).alias("w"), "source_run", "cell_id", *ancestor_cols, "region_code",
                   "timezone")
        .agg(
            F.count("*").alias("n_reports"),
            F.max("granularity_s").alias("granularity_s"),
            F.min("availability_pct").alias("min_availability_pct"),
            *[F.avg(m).alias(m) for m in metrics],
            *[F.avg(c).alias(c) for c in base_cols],
            F.sum(F.when(F.size("flags") > 0, 1).otherwise(0)).alias("n_flagged_reports"),
            F.sum(F.col("is_late").cast("int")).alias("n_late_reports"),
            F.max("evidence_ts").alias("evidence_ts"),
        )
    )
    out = (
        agg.withColumn("window_start", F.col("w.start")).withColumn("window_end", F.col("w.end")).drop("w")
        .withColumn("window_start_local", F.expr("from_utc_timestamp(window_start, timezone)"))
    )
    for m in base:
        out = out.withColumn(f"{m}_z", F.expr(detection.zscore_sql(m)))
    out = (
        out.withColumn("flags", F.expr(detection.flags_sql()))
        .withColumn("is_degraded", F.size("flags") > 0)
        .withColumn("max_abs_z", F.greatest(*[F.abs(F.col(f"{m}_z")) for m in base]))
    )
    # Keys first: Delta collects stats on the leading 32 columns, which liquid clustering needs.
    keys = ["window_start", "window_end", "source_run", "cell_id", "region_code", "is_degraded", "flags"]
    return out.select(*keys, *[c for c in out.columns if c not in keys])
