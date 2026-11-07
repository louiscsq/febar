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


# ---------------------------------------------------------------------------------------------------
# Parent-level (collective) health: per source_run x minute x parent element (default: backhaul link), an
# active_users-weighted aggregate of the on-time 1-minute cell windows below it. Used only by the offline
# collective-backhaul experiment (scripts/collective_backhaul_experiment.py); no pipeline table reads it.
#
# A cell window is USED in its parent's minute only if it is on time (no late record; the real-time health
# tables already hold on-time records only), its evidence arrived by the parent window's close
# (window_end + watermark: a streaming aggregate would have dropped it otherwise), no hard rule fired (an
# outage is not a soft degradation and is already detected per cell), it is not inside a change window
# (site, link or router), and it has a baseline. Silent cells have no window, so they are simply not
# reporting. The parent minute is available at max(window_end + watermark, latest evidence of the used
# cell windows): the same rule as `realtime_window`.
# ---------------------------------------------------------------------------------------------------

COLLECTIVE_WATERMARK_S = 120  # = the gold_cell_health_1m watermark the experiment reads (gold.HEALTH_WATERMARK)
PARENT_LEVELS = {"site_id": "SITE", "backhaul_id": "BACKHAUL_LINK", "router_id": "AGG_ROUTER"}


def _cell_weight(active_users) -> float:
    return max(float(active_users or 0.0), 1.0)


def cell_window_used(w: Mapping, watermark_s: float = COLLECTIVE_WATERMARK_S) -> bool:
    """Python mirror of the `used` condition of `parent_health_sql` for one cell window."""
    from netmon_pipeline import detection

    if w.get("is_late") or (w.get("n_late_reports") or 0) > 0:
        return False
    if w["evidence_s"] > w["window_end_s"] + watermark_s:
        return False
    if set(w.get("flags") or ()) & set(detection.HARD_RULE_NAMES) or w.get("in_maintenance"):
        return False
    return all(w.get(m) is not None and w.get(f"b_{m}_mean") is not None for m in detection.COLLECTIVE_METRICS)


def parent_health(cell_windows: Iterable[Mapping], n_desc_cells: Mapping[str, int],
                  watermark_s: float = COLLECTIVE_WATERMARK_S, parent_col: str = "backhaul_id") -> list[dict]:
    """Python mirror of `parent_health_sql`. `cell_windows`: source_run, cell_id, `parent_col`, window_start_s,
    window_end_s, evidence_s, flags, in_maintenance, active_users, prb_util_pct, n_late_reports (or is_late),
    and per collective metric m: m, b_m_mean, b_m_std."""
    from netmon_pipeline import detection

    groups: dict[tuple, list[Mapping]] = {}
    for w in cell_windows:
        groups.setdefault((w["source_run"], w[parent_col], w["window_start_s"]), []).append(w)
    out = []
    for (run, parent, ws), rows in sorted(groups.items()):
        we = rows[0]["window_end_s"]
        used = [w for w in rows if cell_window_used(w, watermark_s)]
        n_desc = n_desc_cells[parent]
        row = {"source_run": run, "parent_id": parent, "parent_type": PARENT_LEVELS[parent_col],
               "window_start_s": ws, "window_end_s": we, "n_desc_cells": n_desc, "n_cell_windows": len(rows),
               "n_reporting_cells": len(used), "reporting_share": len(used) / n_desc,
               "n_hard_rule_cells": sum(bool(set(w.get("flags") or ()) & set(detection.HARD_RULE_NAMES))
                                        for w in rows),
               "n_maintenance_cells": sum(bool(w.get("in_maintenance")) for w in rows),
               "in_maintenance": any(w.get("in_maintenance") for w in rows)}
        wsum = sum(_cell_weight(w.get("active_users")) for w in used)
        for m in detection.COLLECTIVE_METRICS:
            if not used:
                row[f"wz_{m}"] = row[f"wdelta_{m}"] = row[f"frac_z1_{m}"] = None
                continue
            zs = [detection.zscore(w[m], w[f"b_{m}_mean"], w.get(f"b_{m}_std"), detection.MIN_STD[m]) for w in used]
            ds = [w[m] - w[f"b_{m}_mean"] for w in used]
            ws_ = [_cell_weight(w.get("active_users")) for w in used]
            row[f"wz_{m}"] = sum(a * b for a, b in zip(ws_, zs, strict=True)) / wsum
            row[f"wdelta_{m}"] = sum(a * b for a, b in zip(ws_, ds, strict=True)) / wsum
            row[f"frac_z1_{m}"] = sum(z > detection.CONSISTENCY_Z for z in zs) / len(used)
        prb = [(w.get("prb_util_pct"), _cell_weight(w.get("active_users"))) for w in used
               if w.get("prb_util_pct") is not None]
        row["w_prb_util_pct"] = sum(p * a for p, a in prb) / sum(a for _p, a in prb) if prb else None
        row["max_used_evidence_s"] = max((w["evidence_s"] for w in used), default=None)
        row["available_s"] = max(we + watermark_s, row["max_used_evidence_s"] or we + watermark_s)
        out.append(row)
    return out


def parent_health_sql(health: str, topology: str, maintenance: str, where: str = "true",
                      watermark_s: int = COLLECTIVE_WATERMARK_S, parent_col: str = "backhaul_id") -> str:
    """SQL of the parent-minute statistic over a 1-minute on-time cell-window table shaped like
    `gold_cell_health_1m` (`health`, filtered by `where`), the topology nodes (descendant-cell counts) and
    the change calendar (`maintenance`, joined on the same source_run). Reads no ground truth."""
    from netmon_pipeline import detection

    ms = detection.COLLECTIVE_METRICS
    hard = ", ".join(f"'{n}'" for n in detection.HARD_RULE_NAMES)
    wm = f"INTERVAL {int(watermark_s)} SECONDS"
    per_cell = ",\n".join(f"{detection.zscore_sql(m)} AS z_{m}, ({m} - b_{m}_mean) AS d_{m}" for m in ms)
    have = " AND ".join(f"z_{m} IS NOT NULL AND d_{m} IS NOT NULL" for m in ms)
    stats = ",\n".join(
        f"sum(CASE WHEN used THEN w * z_{m} END) / sum(CASE WHEN used THEN w END) AS wz_{m},\n"
        f"sum(CASE WHEN used THEN w * d_{m} END) / sum(CASE WHEN used THEN w END) AS wdelta_{m},\n"
        f"count_if(used AND z_{m} > {detection.CONSISTENCY_Z}) / nullif(count_if(used), 0) AS frac_z1_{m}"
        for m in ms)
    return f"""
    WITH topo AS (
      SELECT {parent_col} AS parent_id, count(DISTINCT element_id) AS n_desc_cells
      FROM {topology} WHERE element_type = 'CELL' GROUP BY {parent_col}
    ),
    h AS (SELECT * FROM {health} WHERE {where}),
    -- a cell is in a change window when its site, link or router is (deduplicated: one flag per cell window)
    hm AS (
      SELECT h.source_run, h.window_start, h.cell_id, true AS in_maint
      FROM h JOIN {maintenance} mw ON mw.source_run = h.source_run
       AND mw.element_id IN (h.site_id, h.backhaul_id, h.router_id)
       AND mw.planned_start_ts < h.window_end AND mw.planned_end_ts > h.window_start
      GROUP BY h.source_run, h.window_start, h.cell_id
    ),
    c AS (
      SELECT h.source_run, h.window_start, h.window_end, h.cell_id, h.{parent_col} AS parent_id,
             greatest(coalesce(CAST(h.active_users AS DOUBLE), 0D), 1D) AS w, h.prb_util_pct, h.evidence_ts,
             arrays_overlap(coalesce(h.flags, array()), array({hard})) AS hard,
             coalesce(hm.in_maint, false) AS in_maint, coalesce(h.n_late_reports, 0) AS n_late,
             {per_cell}
      FROM h LEFT JOIN hm ON hm.source_run = h.source_run AND hm.window_start = h.window_start
                         AND hm.cell_id = h.cell_id
    ),
    u AS (
      SELECT *, (n_late = 0 AND evidence_ts <= window_end + {wm} AND NOT hard AND NOT in_maint AND {have}) AS used
      FROM c
    )
    SELECT u.source_run, u.window_start, u.window_end, u.parent_id, '{PARENT_LEVELS[parent_col]}' AS parent_type,
           t.n_desc_cells, count(*) AS n_cell_windows, count_if(used) AS n_reporting_cells,
           count_if(used) / t.n_desc_cells AS reporting_share,
           count_if(hard) AS n_hard_rule_cells, count_if(in_maint) AS n_maintenance_cells,
           bool_or(in_maint) AS in_maintenance,
           {stats},
           sum(CASE WHEN used THEN w * prb_util_pct END) / sum(CASE WHEN used AND prb_util_pct IS NOT NULL THEN w END)
             AS w_prb_util_pct,
           max(CASE WHEN used THEN evidence_ts END) AS max_used_evidence_ts,
           greatest(u.window_end + {wm}, coalesce(max(CASE WHEN used THEN evidence_ts END), u.window_end + {wm}))
             AS available_ts
    FROM u JOIN topo t ON t.parent_id = u.parent_id
    GROUP BY u.source_run, u.window_start, u.window_end, u.parent_id, t.n_desc_cells"""
