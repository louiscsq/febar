"""Silver data-quality rules, kept as data so they render to Spark SQL expectations and can also be
checked in plain Python against generator output (tests/test_pipeline_rules.py).

Policy (see docs/pipeline.md):
- `DROP` rules quarantine the row: it is removed from the silver table by `expect_all_or_drop` and
  appended to `silver_quarantine` with the names of the rules it failed. Covers the generator's
  malformed, null and out-of-range defects.
- `WARN` rules keep the row and are only counted in the event log. Covers late arrivals, which are
  valid data that arrived late: they stay in silver, flagged `is_late`.
- `FAIL` rules stop the update. Only used on reference data (topology), where a broken inventory
  would silently corrupt every downstream join.
- Duplicates are not an expectation: silver drops them with `dropDuplicatesWithinWatermark` on
  `record_id` (see `DEDUPE_WATERMARK`).

Rules are evaluated on the typed silver view, where `<ts>` is the parsed TIMESTAMP and `<ts>_raw` the
original string.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# A record is late when it reaches the collector this long after its period / session ended. Normal
# collection lag is < 4 min for 15-min KPIs and < 2 min for everything else; DQ late arrivals are 30 min+.
LATE_THRESHOLD_S = 20 * 60
# Duplicates are re-delivered 1-600 s after the original (data_model.md), so a 15-minute watermark on
# the delivery time (`emitted_ts`) catches every one without holding much state.
DEDUPE_WATERMARK = "15 minutes"
# Alarm clock skew: an alarm cannot be raised after it was delivered, or days before.
ALARM_MAX_AGE_S = 3 * 24 * 3600
ALARM_MAX_FUTURE_S = 15 * 60

TS_FORMAT = "yyyy-MM-dd'T'HH:mm:ssX"


def _parse_ts(v) -> datetime | None:
    """Python mirror of `try_to_timestamp(v, TS_FORMAT)` for ISO-8601 UTC strings."""
    if not isinstance(v, str) or len(v) != 20 or not v.endswith("Z"):
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


@dataclass(frozen=True)
class NotNull:
    column: str

    @property
    def name(self) -> str:
        return f"{self.column}_not_null"

    @property
    def sql(self) -> str:
        return f"{self.column} IS NOT NULL"

    def check(self, r: dict) -> bool:
        return r.get(self.column) is not None


@dataclass(frozen=True)
class ValidTimestamp:
    """The raw string is present and parses as an ISO-8601 UTC timestamp."""

    column: str

    @property
    def name(self) -> str:
        return f"{self.column}_valid"

    @property
    def sql(self) -> str:
        return f"{self.column} IS NOT NULL"

    def check(self, r: dict) -> bool:
        return _parse_ts(r.get(self.column)) is not None


@dataclass(frozen=True)
class Range:
    """lo <= column <= hi (either bound optional). Nulls pass: they are the NotNull rules' job."""

    column: str
    lo: float | None = None
    hi: float | None = None

    @property
    def name(self) -> str:
        return f"{self.column}_in_range"

    @property
    def sql(self) -> str:
        parts = []
        if self.lo is not None:
            parts.append(f"{self.column} >= {self.lo}")
        if self.hi is not None:
            parts.append(f"{self.column} <= {self.hi}")
        return f"{self.column} IS NULL OR ({' AND '.join(parts)})"

    def check(self, r: dict) -> bool:
        v = r.get(self.column)
        if v is None or not isinstance(v, int | float) or isinstance(v, bool):
            return True  # null, or a type mismatch (caught by RescuedData)
        return (self.lo is None or v >= self.lo) and (self.hi is None or v <= self.hi)


@dataclass(frozen=True)
class RescuedData:
    """No value failed to cast to its declared type (Auto Loader put nothing in `_rescued_data`)."""

    numeric: tuple[str, ...]
    name: str = "no_rescued_data"
    sql: str = "_rescued_data IS NULL"

    def check(self, r: dict) -> bool:
        return all(r.get(c) is None or (isinstance(r[c], int | float) and not isinstance(r[c], bool))
                   for c in self.numeric)


@dataclass(frozen=True)
class Parseable:
    """The line was valid JSON (Auto Loader put nothing in `_corrupt_record`)."""

    name: str = "parseable_record"
    sql: str = "_corrupt_record IS NULL"

    def check(self, r: dict) -> bool:
        return not r.get("__corrupt__", False)


@dataclass(frozen=True)
class AlarmClock:
    """Alarm event time is plausible relative to its delivery time (catches 1970 / 2099 clock skew)."""

    name: str = "event_ts_plausible"
    sql: str = (f"event_ts IS NULL OR (event_ts >= emitted_ts - INTERVAL {ALARM_MAX_AGE_S} SECONDS "
                f"AND event_ts <= emitted_ts + INTERVAL {ALARM_MAX_FUTURE_S} SECONDS)")

    def check(self, r: dict) -> bool:
        ev, em = _parse_ts(r.get("event_ts")), _parse_ts(r.get("emitted_ts"))
        if ev is None or em is None:
            return True
        return em - timedelta(seconds=ALARM_MAX_AGE_S) <= ev <= em + timedelta(seconds=ALARM_MAX_FUTURE_S)


@dataclass(frozen=True)
class OnTime:
    """Delivered within LATE_THRESHOLD_S of the end of the measured interval (WARN only)."""

    end_sql: str  # SQL for the end of the interval, on the typed view
    end_py: str  # "kpi" | "alarm" | "session"
    name: str = "on_time"

    @property
    def sql(self) -> str:
        return (f"emitted_ts IS NULL OR {self.end_sql} IS NULL OR "
                f"emitted_ts <= {self.end_sql} + INTERVAL {LATE_THRESHOLD_S} SECONDS")

    def check(self, r: dict) -> bool:
        em = _parse_ts(r.get("emitted_ts"))
        key = {"kpi": "event_ts", "alarm": "event_ts", "session": "end_ts"}[self.end_py]
        end = _parse_ts(r.get(key))
        if em is None or end is None:
            return True
        if self.end_py == "kpi":
            g = r.get("granularity_s")
            end += timedelta(seconds=g if isinstance(g, int) else 0)
        return em <= end + timedelta(seconds=LATE_THRESHOLD_S)


PCT_COLS = ("availability_pct", "prb_util_pct", "rrc_setup_success_pct", "attach_success_pct",
            "session_drop_rate_pct", "packet_loss_pct")
KPI_NUMERIC = ("granularity_s", "availability_pct", "active_users", "prb_util_pct", "rrc_setup_success_pct",
               "attach_success_pct", "session_drop_rate_pct", "dl_throughput_mbps", "ul_throughput_mbps",
               "latency_ms", "packet_loss_pct")
SESSION_NUMERIC = ("duration_s", "bytes_dl", "bytes_ul")

DROP: dict[str, list] = {
    "kpis": [
        Parseable(), RescuedData(KPI_NUMERIC), NotNull("record_id"), NotNull("cell_id"),
        ValidTimestamp("event_ts"),
        *(NotNull(c) for c in ("availability_pct", "active_users", "rrc_setup_success_pct",
                               "dl_throughput_mbps", "latency_ms", "prb_util_pct")),
        *(Range(c, 0, 100) for c in PCT_COLS),
        Range("active_users", 0), Range("dl_throughput_mbps", 0), Range("ul_throughput_mbps", 0),
        Range("latency_ms", 0, 60_000),
    ],
    "alarms": [
        Parseable(), NotNull("record_id"), NotNull("alarm_id"), NotNull("element_id"), NotNull("alarm_code"),
        NotNull("severity"), ValidTimestamp("event_ts"), AlarmClock(),
    ],
    "sessions": [
        Parseable(), RescuedData(SESSION_NUMERIC), NotNull("record_id"), NotNull("imsi"), NotNull("cell_id"),
        ValidTimestamp("start_ts"), NotNull("outcome"), NotNull("bytes_dl"),
        Range("bytes_dl", 0), Range("bytes_ul", 0), Range("duration_s", 0, 7 * 24 * 3600),
    ],
}

# Rows of an unknown element (not in the topology) are quarantined too; checked after the topology join.
KNOWN_ELEMENT = {"kpis": "site_id IS NOT NULL", "alarms": "region_code IS NOT NULL",
                 "sessions": "region_code IS NOT NULL"}

WARN: dict[str, list] = {
    "kpis": [OnTime("event_end_ts", "kpi")],
    "alarms": [OnTime("event_ts", "alarm")],
    "sessions": [OnTime("end_ts", "session")],
}

# Reference data: a broken inventory stops the update.
TOPOLOGY_FAIL = {
    "element_id_not_null": "element_id IS NOT NULL",
    "valid_element_type": "element_type IN ('AMF_MME','UPF_SGW','AGG_ROUTER','BACKHAUL_LINK','SITE','CELL')",
    "valid_level": "level BETWEEN 0 AND 5",
    "has_region_and_timezone": "region_code IS NOT NULL AND timezone IS NOT NULL",
}


def _rule_name(r) -> str:
    return r.name


def drop_expectations(feed: str) -> dict[str, str]:
    """{rule name: SQL predicate} for `@dp.expect_all_or_drop`, including the unknown-element rule.

    `Parseable` is not an expectation: unparseable lines have no columns to test, so silver routes them
    from bronze straight to the quarantine and the typed view only ever sees parseable rows."""
    out = {_rule_name(r): r.sql for r in DROP[feed] if not isinstance(r, Parseable)}
    out["known_element"] = KNOWN_ELEMENT[feed]
    return out


def warn_expectations(feed: str) -> dict[str, str]:
    return {_rule_name(r): r.sql for r in WARN[feed]}


def all_pass_sql(rules: dict[str, str]) -> str:
    """True only if every rule holds (a NULL predicate counts as a failure, as in expectations)."""
    return " AND ".join(f"coalesce(({sql}), false)" for sql in rules.values())


def failed_rules_sql(rules: dict[str, str]) -> str:
    """SQL array<string> of the names of the rules a row fails."""
    items = ", ".join(f"CASE WHEN coalesce(({sql}), false) THEN NULL ELSE '{name}' END"
                      for name, sql in rules.items())
    return f"filter(array({items}), x -> x IS NOT NULL)"


def failed_rules_py(feed: str, record: dict) -> list[str]:
    """Python mirror of the DROP rules (without the topology join) for a raw generator record."""
    return [r.name for r in DROP[feed] if not r.check(record)]


def is_late_py(feed: str, record: dict) -> bool:
    return not all(r.check(record) for r in WARN[feed])


def parse_json_line(line: str) -> dict:
    """How Auto Loader sees one JSON line: a dict, or a corrupt-record marker for an unparseable line."""
    try:
        rec = json.loads(line)
    except json.JSONDecodeError:
        return {"__corrupt__": True}
    if not isinstance(rec, dict):
        return {"__corrupt__": True}
    return {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in rec.items()}
