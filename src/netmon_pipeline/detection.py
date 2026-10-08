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
    """Fires when (value - mean) * direction > max(Z * std, floor)."""

    name: str
    column: str
    direction: int  # +1: higher is worse, -1: lower is worse
    floor: float  # minimum absolute change

    @property
    def sql(self) -> str:
        c, s = self.column, f"greatest(b_{self.column}_std, {MIN_STD[self.column]})"
        delta = f"({c} - b_{c}_mean)" if self.direction > 0 else f"(b_{c}_mean - {c})"
        return f"(b_{c}_mean IS NOT NULL AND {delta} > greatest({Z} * {s}, {self.floor}))"

    def fires(self, r: dict, b: dict | None) -> bool:
        v = r.get(self.column)
        if v is None or not b or b.get(f"b_{self.column}_mean") is None:
            return False
        mean = b[f"b_{self.column}_mean"]
        std = max(b.get(f"b_{self.column}_std") or 0.0, MIN_STD[self.column])
        return (v - mean) * self.direction > max(Z * std, self.floor)


HARD_RULES = [
    HardRule("cell_unavailable", "availability_pct", 95.0),
    HardRule("attach_failure", "attach_success_pct", 95.0),
    HardRule("rrc_collapse", "rrc_setup_success_pct", 80.0),
]
DEVIATION_RULES = [
    DeviationRule("latency_degradation", "latency_ms", +1, 40.0),
    DeviationRule("packet_loss", "packet_loss_pct", +1, 1.5),
    DeviationRule("throughput_collapse", "dl_throughput_mbps", -1, 0.0),
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


def day_type(local_dow: int) -> str:
    """Spark `dayofweek` numbering (1 = Sunday .. 7 = Saturday) -> 'weekend' / 'weekday'."""
    return "weekend" if local_dow in (1, 7) else "weekday"


DAY_TYPE_SQL = "CASE WHEN dayofweek({ts}) IN (1, 7) THEN 'weekend' ELSE 'weekday' END"


def baseline_window(valid_date_ordinal: int) -> tuple[int, int]:
    """Inclusive range of day ordinals feeding the baseline used on `valid_date`: strictly earlier days."""
    return valid_date_ordinal - BASELINE_LOOKBACK_DAYS, valid_date_ordinal - 1
