"""The Python copy of the late-data rule (`windows.realtime_window`, `rules.is_late_py`) checked against the
Spark code the pipeline actually runs (`windows.is_late_sql`, `windows.realtime_records`,
`windows.window_health`, all called by pipelines/netmon/transformations/silver.py and gold.py).

Runs a local SparkSession (pyspark + a Java 17/21 runtime). Skipped only if pyspark is not installed."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from netmon_pipeline import detection, rules, windows

pyspark = pytest.importorskip("pyspark")

ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 10, 10, 0, 0, tzinfo=timezone.utc)
WM = 120
# gold.METRICS (window means), with healthy values
HEALTHY = {"availability_pct": 100.0, "active_users": 20.0, "prb_util_pct": 40.0, "rrc_setup_success_pct": 99.0,
           "attach_success_pct": 99.5, "session_drop_rate_pct": 1.0, "dl_throughput_mbps": 50.0,
           "ul_throughput_mbps": 10.0, "latency_ms": 30.0, "packet_loss_pct": 0.2}
METRICS = list(HEALTHY)
ANC = ["site_id"]


def kpi(event_ts, emitted_ts, availability, cell="CELL-A"):
    return {"source_run": "history_1m", "cell_id": cell, "site_id": "SITE-A", "region_code": "NSW",
            "timezone": "Australia/Sydney", "granularity_s": 60, "event_ts": event_ts,
            "event_end_ts": event_ts + timedelta(seconds=60), "emitted_ts": emitted_ts,
            "evidence_ts": emitted_ts, **HEALTHY, "availability_pct": float(availability),
            # baseline equal to the healthy values: only the hard availability rule can fire
            **{f"b_{m}_mean": HEALTHY[m] for m in detection.BASELINE_METRICS},
            **{f"b_{m}_std": 1.0 for m in detection.BASELINE_METRICS}}


def run_pipeline_code(spark, records):
    """silver's is_late, then gold's real-time record filter and window aggregate, on a static frame."""
    from pyspark.sql import functions as F

    df = spark.createDataFrame(records)
    df = df.withColumn("lag_s", F.expr("unix_timestamp(emitted_ts) - unix_timestamp(event_end_ts)")) \
        .withColumn("is_late", F.expr(windows.is_late_sql("lag_s"))) \
        .withColumn("flags", F.expr(detection.flags_sql()))
    late = {(_utc(r["event_ts"]), _utc(r["emitted_ts"])): r["is_late"]
            for r in df.select("event_ts", "emitted_ts", "is_late").collect()}
    out = windows.window_health(windows.realtime_records(df), "1 minute", METRICS, ANC).collect()
    return late, {_utc(r["window_start"]): r for r in out}


def _utc(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def as_py(rec):
    return {"event_ts": rec["event_ts"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "emitted_ts": rec["emitted_ts"].strftime("%Y-%m-%dT%H:%M:%SZ"), "granularity_s": 60}


CASES = {
    # window start -> records (event_ts, delivery delay after the period end in s, availability)
    "late degraded row would qualify": [(0, 20, 100), (0, 36 * 3600, 0)],
    "on-time degraded row qualifies": [(1, 15, 100), (1, 290, 0)],
    "only late rows": [(2, 3 * 3600, 0)],
    "exactly at the threshold": [(3, rules.LATE_THRESHOLD_S, 0)],
    "one second past the threshold": [(4, rules.LATE_THRESHOLD_S + 1, 0)],
}


def test_python_late_rule_and_realtime_window_match_the_spark_transform(spark):
    records, expect = [], {}
    for rows in CASES.values():
        py_rows = []
        for m, delay, avail in rows:
            ev = T0 + timedelta(minutes=m)
            emitted = ev + timedelta(seconds=60 + delay)
            rec = kpi(ev, emitted, avail)
            records.append(rec)
            py_late = rules.is_late_py("kpis", as_py(rec))
            py_rows.append({"is_late": py_late, "degraded": avail < 95,
                            "evidence_s": (emitted - T0).total_seconds(), "_rec": rec})
        start = T0 + timedelta(minutes=rows[0][0])
        expect[start] = (windows.realtime_window(py_rows, (start - T0).total_seconds() + 60, WM), py_rows)

    late, spark_windows = run_pipeline_code(spark, records)
    for start, (py, py_rows) in expect.items():
        for r in py_rows:  # (1) per-record lateness: rules.is_late_py == silver's is_late SQL
            key = (r["_rec"]["event_ts"], r["_rec"]["emitted_ts"])
            assert late[key] == r["is_late"], start
        w = spark_windows.get(start)  # (2) the window gold actually emits
        if py["silent"]:
            assert w is None, start  # no on-time record: no real-time window row, i.e. the cell is silent
            continue
        assert w["n_reports"] == py["n_reports"], start
        assert bool(w["is_degraded"]) == py["degraded"], start
        ev_s = (_utc(w["evidence_ts"]) - T0).total_seconds()
        assert max(ev_s, (start - T0).total_seconds() + 60 + WM) == py["available_s"], start
        assert w["n_late_reports"] == 0


def test_pipeline_sources_call_the_shared_functions():
    """gold.py / silver.py must use the shared functions, not a private copy of the rule."""
    gold = (ROOT / "pipelines/netmon/transformations/gold.py").read_text()
    silver = (ROOT / "pipelines/netmon/transformations/silver.py").read_text()
    assert "windows.realtime_records(" in gold and "windows.window_health(" in gold
    assert gold.count("windows.score_against_baseline(") == 2  # real-time stream and the retrospective MV
    assert silver.count("windows.is_late_sql(") == 3  # kpis, alarms, sessions
    for src in (gold, silver):
        tree = ast.parse(src)
        consts = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        assert not any("NOT is_late" in c for c in consts)
        assert not any("lag_s >" in c for c in consts)
