"""Customer-impact detection rules and the baseline-deviation maths behind them.

Detection is stateless per KPI record, so latency is bounded by collection lag plus one pipeline
micro-batch, not by a window plus watermark (docs/pipeline.md, "latency budget"). A record is flagged
when any rule fires:

- hard rules (no baseline needed): the cell is out of service, or setup / attach success has
  collapsed. Healthy cells report `availability_pct = 100` and attach success above 98 %, even when
  congested, so these thresholds have no organic false positives.
- deviation rules: the KPI is far from the same cell's baseline for that local hour and day type
  (weekday / weekend), learned only from earlier days (no future leakage). "Far" means both a z-score
  above `Z` *and* an absolute change above a floor, so a very stable cell cannot fire on noise.

Dark cells send no KPI rows at all, so element-down alarms are a second signal (`ALARM_SIGNALS`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

Z = 4.0  # deviation threshold in baseline standard deviations
MIN_STD = {  # floor on the baseline std, so z-scores stay meaningful for very stable cells
    "latency_ms": 2.0, "packet_loss_pct": 0.05, "dl_throughput_mbps": 1.0, "rrc_setup_success_pct": 0.2,
    "session_drop_rate_pct": 0.1,
}


@dataclass(frozen=True)
class HardRule:
    name: str
    column: str
    below: float

    @property
    def sql(self) -> str:
        return f"{self.column} < {self.below}"

    def fires(self, r: dict, _b: dict | None = None) -> bool:
        v = r.get(self.column)
        return v is not None and v < self.below


@dataclass(frozen=True)
class DeviationRule:
    """Fires when (value - mean) * direction > max(Z * std, floor, rel_floor * |mean|)."""

    name: str
    column: str
    direction: int  # +1: higher is worse, -1: lower is worse
    floor: float  # minimum absolute change
    rel_floor: float = 0.0  # minimum change relative to the baseline mean

    @property
    def sql(self) -> str:
        c, s = self.column, f"greatest(coalesce(b_{self.column}_std, 0), {MIN_STD[self.column]})"
        delta = f"({c} - b_{c}_mean)" if self.direction > 0 else f"(b_{c}_mean - {c})"
        return (f"(b_{c}_mean IS NOT NULL AND {delta} > "
                f"greatest({Z} * {s}, {self.floor}, {self.rel_floor} * abs(b_{c}_mean)))")

    def fires(self, r: dict, b: dict | None) -> bool:
        v = r.get(self.column)
        if v is None or not b or b.get(f"b_{self.column}_mean") is None:
            return False
        mean = b[f"b_{self.column}_mean"]
        std = max(b.get(f"b_{self.column}_std") or 0.0, MIN_STD[self.column])
        return (v - mean) * self.direction > max(Z * std, self.floor, self.rel_floor * abs(mean))


HARD_RULES = [
    HardRule("cell_unavailable", "availability_pct", 95.0),
    HardRule("attach_failure", "attach_success_pct", 95.0),
    HardRule("rrc_collapse", "rrc_setup_success_pct", 80.0),
]
DEVIATION_RULES = [
    DeviationRule("latency_degradation", "latency_ms", +1, 40.0),
    DeviationRule("packet_loss", "packet_loss_pct", +1, 1.5),
    # Organic load swings move throughput a lot; the faults that matter cut it by 60-65 %.
    DeviationRule("throughput_collapse", "dl_throughput_mbps", -1, 0.0, rel_floor=0.5),
    DeviationRule("rrc_degradation", "rrc_setup_success_pct", -1, 3.0),
    DeviationRule("drop_rate_spike", "session_drop_rate_pct", +1, 2.0),
]
RULES = HARD_RULES + DEVIATION_RULES
BASELINE_METRICS = [r.column for r in DEVIATION_RULES]
BASELINE_LOOKBACK_DAYS = 14

# Element-down alarms that mean customers have lost service (dark sites cannot report KPIs). Chosen to
# avoid the generator's background noise and flapping codes: background backhaul noise includes `LOS`,
# and flapping elements raise MAJOR `LINK_DOWN` / `S1_NG_LINK_FAILURE` / `SYNC_LOSS`.
ALARM_SIGNALS = [
    # (element_type, alarm_code, severities or None for any)
    ("CELL", "CELL_OUT_OF_SERVICE", None),
    ("SITE", "NE_UNREACHABLE", None),
    ("SITE", "S1_NG_LINK_FAILURE", ("CRITICAL",)),
    ("BACKHAUL_LINK", "LINK_DOWN", ("CRITICAL",)),
    ("AGG_ROUTER", "NODE_DOWN", None),
    ("AGG_ROUTER", "NE_UNREACHABLE", None),
]


def flags_sql() -> str:
    """SQL array<string> of the rules a KPI row (joined with its baseline) fires."""
    items = ", ".join(f"CASE WHEN {r.sql} THEN '{r.name}' END" for r in RULES)
    return f"filter(array({items}), x -> x IS NOT NULL)"


def alarm_signal_sql() -> str:
    parts = []
    for et, code, sev in ALARM_SIGNALS:
        cond = f"(element_type = '{et}' AND alarm_code = '{code}'"
        if sev:
            cond += " AND severity IN (" + ", ".join(f"'{s}'" for s in sev) + ")"
        parts.append(cond + ")")
    return "event_type = 'RAISE' AND (" + " OR ".join(parts) + ")"


def flags_py(record: dict, baseline: dict | None) -> list[str]:
    return [r.name for r in RULES if r.fires(record, baseline)]


def mean_std(values: list[float]) -> tuple[float | None, float | None]:
    """Mean and sample standard deviation (as Spark's avg / stddev_samp)."""
    vals = [v for v in values if v is not None]
    if not vals:
        return None, None
    m = sum(vals) / len(vals)
    if len(vals) < 2:
        return m, None
    return m, math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))


def mean_std_from_moments(n: int, s: float, ss: float) -> tuple[float | None, float | None]:
    """Mean and sample std from count, sum and sum of squares: how the baseline MV combines daily
    partial aggregates over its trailing window without re-reading raw rows."""
    if n <= 0:
        return None, None
    m = s / n
    if n < 2:
        return m, None
    var = max(ss - n * m * m, 0.0) / (n - 1)
    return m, math.sqrt(var)


def zscore(value: float | None, mean: float | None, std: float | None, floor: float) -> float | None:
    if value is None or mean is None:
        return None
    return (value - mean) / max(std or 0.0, floor)


def zscore_sql(column: str) -> str:
    return (f"({column} - b_{column}_mean) / greatest(coalesce(b_{column}_std, 0), {MIN_STD[column]})")


# Local calendar keys of a UTC timestamp in the element's IANA zone (DST-aware in Spark and in Python).
# The baseline aggregates, looks back and joins on the *local* date, so a record just after local midnight
# belongs to the new local day even though its UTC date is the previous one.
LOCAL_TS_SQL = "from_utc_timestamp({ts}, timezone)"
LOCAL_DATE_SQL = "to_date(from_utc_timestamp({ts}, timezone))"


def local_keys(ts_utc: datetime, tz: str) -> tuple[date, int, str]:
    """(local_date, local_hour, day_type) of an aware UTC datetime: Python mirror of the silver columns."""
    loc = ts_utc.astimezone(ZoneInfo(tz))
    return loc.date(), loc.hour, day_type(loc.isoweekday() % 7 + 1)


def day_type(local_dow: int) -> str:
    """Spark `dayofweek` numbering (1 = Sunday .. 7 = Saturday) -> 'weekend' / 'weekday'."""
    return "weekend" if local_dow in (1, 7) else "weekday"


DAY_TYPE_SQL = "CASE WHEN dayofweek({ts}) IN (1, 7) THEN 'weekend' ELSE 'weekday' END"


def baseline_window(valid_date_ordinal: int) -> tuple[int, int]:
    """Inclusive range of local-date ordinals feeding the baseline used on local date `valid_date`:
    strictly earlier local days."""
    return valid_date_ordinal - BASELINE_LOOKBACK_DAYS, valid_date_ordinal - 1


# ---------------------------------------------------------------------------------------------------
# Collective (parent-level) degradation: an OFFLINE experiment detector, not wired into the pipeline.
#
# The per-cell rules need +40 ms / +1.5 pp, which a slow backhaul ramp reaches only ~8-9 min after impact
# start. Averaging the cells behind one parent (a backhaul link) shrinks the noise by about sqrt(N), so a
# much smaller shift is significant when it is shared by the link's cells. The statistic per
# source_run x minute x parent comes from `windows.parent_health_sql` / `windows.parent_health` (on-time
# cell windows only, active_users-weighted, hard-rule / maintenance / no-baseline cells excluded).
# See docs/pipeline.md, "Collective backhaul detector (offline experiment)".
# ---------------------------------------------------------------------------------------------------

COLLECTIVE_METRICS = ("latency_ms", "packet_loss_pct", "session_drop_rate_pct")  # all "higher is worse"
CONSISTENCY_Z = 1.0  # a reporting cell "agrees" with the shift when its own z exceeds this
HARD_RULE_NAMES = tuple(r.name for r in HARD_RULES)


@dataclass(frozen=True)
class CollectiveRule:
    """A parent-minute qualifies when, for at least one metric m in `COLLECTIVE_METRICS`:
    weighted mean z_m > `z` AND weighted mean delta_m > floor_m AND the fraction of reporting cells with
    z_m > `CONSISTENCY_Z` >= `min_consistency`; and reporting cells / descendant cells >= `min_reporting_share`.
    It fires (one detection row) on a minute that qualifies together with the `persist - 1` minutes before it
    (consecutive window_start minutes, all present). No ground truth is an input."""

    name: str
    z: float
    floors: tuple[tuple[str, float], ...]  # (metric, minimum weighted-mean delta vs baseline), per metric
    min_consistency: float
    min_reporting_share: float
    persist: int

    def floor(self, metric: str) -> float:
        return dict(self.floors)[metric]

    def metric_sql(self, m: str) -> str:
        return (f"(coalesce(wz_{m} > {self.z}, false) AND coalesce(wdelta_{m} > {self.floor(m)}, false) "
                f"AND coalesce(frac_z1_{m} >= {self.min_consistency}, false))")

    @property
    def sql(self) -> str:
        """SQL predicate on one parent-minute row of `windows.parent_health_sql` (per-minute qualification)."""
        any_metric = " OR ".join(self.metric_sql(m) for m in COLLECTIVE_METRICS)
        return f"(coalesce(reporting_share >= {self.min_reporting_share}, false) AND ({any_metric}))"

    def metrics_sql(self) -> str:
        """SQL array<string> of the metrics that qualify on the row."""
        items = ", ".join(f"CASE WHEN {self.metric_sql(m)} THEN '{m}' END" for m in COLLECTIVE_METRICS)
        return f"filter(array({items}), x -> x IS NOT NULL)"

    # --- Python mirror -------------------------------------------------------------------------------
    def qualifying_metrics(self, row: dict) -> list[str]:
        share = row.get("reporting_share")
        if share is None or share < self.min_reporting_share:
            return []
        out = []
        for m in COLLECTIVE_METRICS:
            z, dl, fr = row.get(f"wz_{m}"), row.get(f"wdelta_{m}"), row.get(f"frac_z1_{m}")
            if None not in (z, dl, fr) and z > self.z and dl > self.floor(m) and fr >= self.min_consistency:
                out.append(m)
        return out

    def qualifies(self, row: dict) -> bool:
        return bool(self.qualifying_metrics(row))

    def fires(self, rows: list[dict]) -> list[dict]:
        """Python mirror of `collective_detections_sql`: the rows (parent-minutes) on which the rule fires.
        `rows`: parent_health rows with source_run, parent_id, window_start_s."""
        q = {(r["source_run"], r["parent_id"], r["window_start_s"]) for r in rows if self.qualifies(r)}
        out = []
        for r in rows:
            k = (r["source_run"], r["parent_id"], r["window_start_s"])
            if k in q and all((k[0], k[1], k[2] - 60 * i) in q for i in range(1, self.persist)):
                out.append(r)
        return out

    def qualifies_frame(self, df):
        """Vectorised `qualifies` over a pandas frame of parent-minute rows (the calibration sweep)."""
        import numpy as np

        ok = np.zeros(len(df), dtype=bool)
        for m in COLLECTIVE_METRICS:
            ok |= ((df[f"wz_{m}"] > self.z) & (df[f"wdelta_{m}"] > self.floor(m))
                   & (df[f"frac_z1_{m}"] >= self.min_consistency)).fillna(False).to_numpy(dtype=bool)
        return ok & (df["reporting_share"] >= self.min_reporting_share).fillna(False).to_numpy(dtype=bool)

    def fires_frame(self, df):
        """Vectorised `fires`: boolean mask over `df` (source_run, parent_id, window_start_s, ...)."""
        import pandas as pd

        q = pd.Series(self.qualifies_frame(df), index=df.index)
        keys = pd.MultiIndex.from_arrays([df["source_run"], df["parent_id"], df["window_start_s"]])
        qset = pd.Series(q.to_numpy(), index=keys)
        qset = qset[qset]
        out = q.copy()
        for i in range(1, self.persist):
            prev = pd.MultiIndex.from_arrays([df["source_run"], df["parent_id"], df["window_start_s"] - 60 * i])
            out &= prev.isin(qset.index)
        return out.to_numpy(dtype=bool)


def collective_detection_id(source_run: str, parent_id: str, window_start_iso: str) -> str:
    """Python mirror of the SQL `detection_id` (sha2 of 'collective|run|parent|window_start')."""
    import hashlib

    return hashlib.sha256(f"collective|{source_run}|{parent_id}|{window_start_iso}".encode()).hexdigest()


def collective_detections_sql(rule: CollectiveRule, stats_sql: str) -> str:
    """Detections over the parent-minute statistic `stats_sql` (a SELECT from `windows.parent_health_sql`).
    Persistence: the minute and the `persist - 1` minutes before it all qualify (a RANGE frame over minute
    indices, so a missing minute breaks the run). Timing: a detection is available when its own minute's
    aggregate is (`available_ts`), never earlier than the earlier minutes it needs."""
    p = rule.persist
    return f"""
    WITH s AS ({stats_sql}),
    q AS (SELECT *, {rule.sql} AS qualifies, {rule.metrics_sql()} AS qualifying_metrics,
                 CAST(unix_timestamp(window_start) / 60 AS BIGINT) AS minute_idx FROM s),
    r AS (SELECT *,
                 sum(CAST(qualifies AS INT)) OVER w AS n_qualified_in_frame,
                 max(available_ts) OVER w AS frame_available_ts
          FROM q
          WINDOW w AS (PARTITION BY source_run, parent_id ORDER BY minute_idx
                       RANGE BETWEEN {p - 1} PRECEDING AND CURRENT ROW))
    SELECT sha2(concat('collective|', source_run, '|', parent_id, '|',
                       date_format(window_start, "yyyy-MM-dd'T'HH:mm:ss'Z'")), 256) AS detection_id,
           'collective' AS signal_source, '{rule.name}' AS rule_name, source_run, parent_id AS element_id,
           parent_type AS element_type, window_start AS signal_start_ts, window_end AS signal_end_ts,
           qualifying_metrics, n_desc_cells, n_reporting_cells, reporting_share, n_hard_rule_cells,
           n_maintenance_cells, in_maintenance,
           {", ".join(f"wz_{m}, wdelta_{m}, frac_z1_{m}" for m in COLLECTIVE_METRICS)},
           w_prb_util_pct, max_used_evidence_ts, frame_available_ts AS available_ts
    FROM r WHERE qualifies AND n_qualified_in_frame >= {p}"""


# FROZEN: chosen on the history_1m DEV days only (2026-10-14 .. 10-15, the RCA dev split) by the declared selection rule
# in scripts/collective_backhaul_experiment.py (evidence/step6/01_calibration.md), and committed before any holdout_1m
# or stream reading. Do not retune on a run it has been scored on. The 3 ms latency floor is the bottom of the grid,
# so the z threshold is what binds; loss / drop floors scale with it by the fault's own ratio (6/140, 3/140).
COLLECTIVE_BACKHAUL = CollectiveRule(
    name="collective_backhaul_v1", z=2.5,
    floors=(("latency_ms", 3.0), ("packet_loss_pct", 0.1286), ("session_drop_rate_pct", 0.0643)),
    min_consistency=0.6, min_reporting_share=0.8, persist=2,
)
