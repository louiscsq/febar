"""Data-quality defect injection with a full audit log.

Every injected defect is recorded in `dq_injections` (feed, record_id, defect type, column, value) so
pipeline expectations can be scored against ground truth. Defects are disjoint per record: a record
gets at most one defect, and duplicates are copies of clean records.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from netmon_datagen.config import DQConfig

FEEDS = {
    "kpis": dict(
        ts_col="event_ts",
        null_cols=["cell_id", "event_ts", "availability_pct", "active_users", "rrc_setup_success_pct",
                   "dl_throughput_mbps", "latency_ms", "prb_util_pct"],
        numeric_cols=["availability_pct", "prb_util_pct", "latency_ms", "dl_throughput_mbps"],
        int_cols=["active_users", "granularity_s"],
        oor=[("rrc_setup_success_pct", 100.5, 160.0), ("prb_util_pct", 101.0, 250.0), ("latency_ms", -500.0, -1.0),
             ("active_users", -50, -1), ("availability_pct", 100.5, 200.0), ("dl_throughput_mbps", -100.0, -0.1)],
    ),
    "alarms": dict(
        ts_col="event_ts",
        null_cols=["element_id", "alarm_code", "severity", "event_ts"],
        numeric_cols=[],
        int_cols=[],
        oor=[("event_ts", "future", None), ("event_ts", "epoch", None)],
    ),
    "sessions": dict(
        ts_col="start_ts",
        null_cols=["imsi", "cell_id", "start_ts", "outcome", "bytes_dl"],
        numeric_cols=["bytes_dl", "bytes_ul", "duration_s"],
        int_cols=["bytes_dl", "bytes_ul", "duration_s"],
        oor=[("bytes_dl", -10**9, -1), ("duration_s", -86400, -1)],
    ),
}
BAD_TIMESTAMPS = ["2026-13-45T25:61:00Z", "N/A", "", "31/02/2026 24:00", "0000-00-00T00:00:00Z", "yesterday"]
TYPE_MISMATCH = ["#VALUE!", "NaN%", "ERR", "--"]
LATE_MIN_S, LATE_MAX_S = 30 * 60, 36 * 3600
LOG_COLUMNS = ["feed", "record_id", "defect_type", "defect_subtype", "column", "injected_value"]


def _count(rng, n, rate):
    return int(np.floor(rate * n + rng.random())) if rate > 0 else 0


def inject_defects(df: pd.DataFrame, feed: str, dq: DQConfig, rng: np.random.Generator,
                   fmt: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (defective frame, injection log). `df` must carry `_emitted` (datetime64[s])."""
    spec = FEEDS[feed]
    df = df.reset_index(drop=True).copy()
    for c in spec["int_cols"]:
        df[c] = df[c].astype("Int64")
    df["_truncate"] = False
    n = len(df)
    if n == 0 or dq.total == 0:
        return df, pd.DataFrame(columns=LOG_COLUMNS)

    perm = rng.permutation(n)
    counts = [_count(rng, n, r) for r in
              (dq.malformed_rate, dq.null_rate, dq.out_of_range_rate, dq.late_rate, dq.duplicate_rate)]
    bounds = np.cumsum([0] + counts)
    mal, nul, oor, late, dup = (perm[bounds[i]:bounds[i + 1]] for i in range(5))
    log: list[dict] = []
    rid = df["record_id"].to_numpy()
    edits: dict[str, list[tuple[int, object]]] = {}  # column -> [(row, value)], applied once per column

    def note(i, dtype, sub, col, val):
        log.append(dict(feed=feed, record_id=rid[i], defect_type=dtype, defect_subtype=sub, column=col,
                        injected_value=None if val is None else str(val)))
        if col is not None and dtype != "late_arrival":
            edits.setdefault(col, []).append((i, val))

    # Malformed: unparseable timestamp everywhere; type mismatch and truncated lines only in JSON.
    variants = ["bad_timestamp", "type_mismatch", "truncated_json"] if fmt == "json" else ["bad_timestamp"]
    if fmt == "json" and not spec["numeric_cols"]:
        variants = ["bad_timestamp", "truncated_json"]
    choice = rng.integers(0, len(variants), len(mal))
    truncate = []
    for i, v in zip(mal, choice, strict=True):
        sub = variants[v]
        if sub == "bad_timestamp":
            note(i, "malformed", sub, spec["ts_col"], BAD_TIMESTAMPS[rng.integers(len(BAD_TIMESTAMPS))])
        elif sub == "type_mismatch":
            col = spec["numeric_cols"][rng.integers(len(spec["numeric_cols"]))]
            note(i, "malformed", sub, col, TYPE_MISMATCH[rng.integers(len(TYPE_MISMATCH))])
        else:
            truncate.append(i)
            note(i, "malformed", sub, None, None)

    for i in nul:
        note(i, "null", "missing_value", spec["null_cols"][rng.integers(len(spec["null_cols"]))], None)

    for i in oor:
        col, lo, hi = spec["oor"][rng.integers(len(spec["oor"]))]
        if lo == "future":
            val = "2099-01-01T00:00:00Z"
        elif lo == "epoch":
            val = "1970-01-01T00:00:00Z"
        elif isinstance(lo, int):
            val = int(rng.integers(lo, hi + 1))
        else:
            val = round(float(rng.uniform(lo, hi)), 2)
        note(i, "out_of_range", "clock_skew" if isinstance(val, str) else "impossible_value", col, val)

    for col, items in edits.items():
        rows = np.array([r for r, _ in items])
        vals = [v for _, v in items]
        if any(isinstance(v, str) for v in vals) and col in spec["numeric_cols"] + spec["int_cols"]:
            df[col] = df[col].astype(object)  # type-mismatch strings in a numeric column (JSON only)
        dtype = df[col].dtype
        if pd.api.types.is_object_dtype(dtype):
            arr = pd.array(vals, dtype=object)
        elif pd.api.types.is_float_dtype(dtype):
            arr = np.array([np.nan if v is None else v for v in vals], dtype=float)
        else:  # nullable Int64 or string columns accept None directly
            arr = pd.array(vals, dtype=dtype)
        df.loc[rows, col] = arr
    if truncate:
        df.loc[np.array(truncate), "_truncate"] = True

    if len(late):
        delay = rng.uniform(LATE_MIN_S, LATE_MAX_S, len(late)).astype(np.int64).astype("timedelta64[s]")
        df.loc[late, "_emitted"] = df.loc[late, "_emitted"].to_numpy() + delay
        for i, d in zip(late, delay.astype(np.int64), strict=True):
            note(i, "late_arrival", "delayed_delivery", "emitted_ts", f"+{int(d)}s")

    if len(dup):
        copies = df.loc[dup].copy()
        copies["_emitted"] = copies["_emitted"].to_numpy() + rng.integers(1, 600, len(dup)).astype("timedelta64[s]")
        for i in dup:
            note(i, "duplicate", "redelivery", None, None)
        df = pd.concat([df, copies], ignore_index=True)

    return df, pd.DataFrame(log, columns=LOG_COLUMNS)
