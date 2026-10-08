"""Detection rules and baseline maths (netmon_pipeline.detection)."""

from __future__ import annotations

import math
import random
from datetime import datetime

import pandas as pd
import pytest
from conftest import read_table

from netmon_pipeline import detection as d


def test_moments_match_direct_mean_std():
    rng = random.Random(7)
    vals = [rng.gauss(30, 4) for _ in range(200)]
    m, s = d.mean_std(vals)
    # Combine per-day partial aggregates, as the baseline MV does.
    days = [vals[i:i + 25] for i in range(0, 200, 25)]
    n, sm, ss = sum(len(x) for x in days), sum(sum(x) for x in days), sum(sum(v * v for v in x) for x in days)
    m2, s2 = d.mean_std_from_moments(n, sm, ss)
    assert m == pytest.approx(m2) and s == pytest.approx(s2)
    assert d.mean_std([]) == (None, None) and d.mean_std([1.0])[1] is None
    assert d.mean_std_from_moments(0, 0, 0) == (None, None)


def test_zscore_uses_std_floor():
    assert d.zscore(130, 30, 0.0, 2.0) == pytest.approx(50.0)
    assert d.zscore(130, 30, 10.0, 2.0) == pytest.approx(10.0)
    assert d.zscore(None, 30, 1, 1) is None and d.zscore(1, None, 1, 1) is None
    assert d.zscore_sql("latency_ms").startswith("(latency_ms - b_latency_ms_mean)")


def test_deviation_rule_needs_z_and_absolute_floor():
    lat = next(r for r in d.DEVIATION_RULES if r.column == "latency_ms")
    b = {"b_latency_ms_mean": 30.0, "b_latency_ms_std": 1.0}
    assert not lat.fires({"latency_ms": 60.0}, b)  # z = 15 but only +30 ms (< 40 ms floor)
    assert lat.fires({"latency_ms": 75.0}, b)
    assert not lat.fires({"latency_ms": 75.0}, {"b_latency_ms_mean": 30.0, "b_latency_ms_std": 15.0})  # z = 3
    assert not lat.fires({"latency_ms": 500.0}, None)  # no baseline: deviation rules stay silent
    thr = next(r for r in d.DEVIATION_RULES if r.column == "dl_throughput_mbps")
    bt = {"b_dl_throughput_mbps_mean": 100.0, "b_dl_throughput_mbps_std": 8.0}
    assert thr.fires({"dl_throughput_mbps": 50.0}, bt) and not thr.fires({"dl_throughput_mbps": 80.0}, bt)
    assert "b_latency_ms_mean IS NOT NULL" in lat.sql


def test_flags_sql_lists_every_rule():
    sql = d.flags_sql()
    assert all(f"'{r.name}'" in sql for r in d.RULES)
    assert d.flags_py({"availability_pct": 0.0, "attach_success_pct": 0.0}, None) == [
        "cell_unavailable", "attach_failure"]


def test_alarm_signal_sql_excludes_noise_codes():
    sql = d.alarm_signal_sql()
    assert sql.startswith("event_type = 'RAISE'")
    assert "'LOS'" not in sql and "'SYNC_LOSS'" not in sql
    assert "(element_type = 'BACKHAUL_LINK' AND alarm_code = 'LINK_DOWN' AND severity IN ('CRITICAL'))" in sql


def test_day_type_matches_spark_dayofweek():
    # Spark dayofweek: 1 = Sunday, 7 = Saturday.
    assert [d.day_type(i) for i in range(1, 8)] == ["weekend"] + ["weekday"] * 5 + ["weekend"]


def test_baseline_window_is_strictly_before_the_day():
    lo, hi = d.baseline_window(1000)
    assert hi == 999 and lo == 1000 - d.BASELINE_LOOKBACK_DAYS


def _ts(s):
    return pd.Timestamp(s).tz_localize(None) if s else None


@pytest.fixture(scope="module")
def kpis_and_incidents(history_json):
    root, _ = history_json
    k = read_table(root, "kpis")
    k = k[pd.to_numeric(k["availability_pct"], errors="coerce").notna()].copy()
    k["t"] = pd.to_datetime(k["event_ts"], errors="coerce", utc=True).dt.tz_localize(None)
    for c in ["availability_pct", "attach_success_pct", "rrc_setup_success_pct"]:
        k[c] = pd.to_numeric(k[c], errors="coerce")
    inc = read_table(root, "ground_truth/incidents")
    return k.dropna(subset=["t"]), inc


def test_hard_rules_fire_on_outages_and_never_on_healthy_cells(kpis_and_incidents):
    k, inc = kpis_and_incidents
    impacted = set()  # (cell, period start) overlapping any customer impact
    full_outage = set()  # periods entirely inside a cell / router outage
    for r in inc[inc.is_customer_impacting].itertuples():
        s, e = _ts(r.impact_start_ts), _ts(r.impact_end_ts)
        cells = set(r.affected_cell_ids)
        sel = k[k.cell_id.isin(cells) & (k.t + pd.Timedelta(minutes=15) > s - pd.Timedelta(minutes=30))
                & (k.t < e + pd.Timedelta(minutes=30))]
        impacted |= set(zip(sel.cell_id, sel.t, strict=True))
        if r.fault_type in ("CELL_OUTAGE", "AGG_ROUTER_FAILURE"):
            # onset is staggered per cell, so require the period to start 5 min after the impact start
            full = sel[(sel.t >= s + pd.Timedelta(minutes=5)) & (sel.t + pd.Timedelta(minutes=15) <= e)]
            full_outage |= set(zip(full.cell_id, full.t, strict=True))
    hard = [r for r in d.HARD_RULES]
    fired = k.apply(lambda x: any(h.fires(x) for h in hard), axis=1)
    keys = list(zip(k.cell_id, k.t, strict=True))
    healthy_fp = [kk for kk, f in zip(keys, fired, strict=True) if f and kk not in impacted]
    assert healthy_fp == []
    outage_hits = [f for kk, f in zip(keys, fired, strict=True) if kk in full_outage]
    if outage_hits:  # tiny 3-day window always contains a cell outage (min_per_type), but be safe
        assert sum(outage_hits) / len(outage_hits) > 0.9


def test_iso_parse_helper():
    assert _ts("2026-09-04T00:00:00Z") == datetime(2026, 9, 4)
    assert math.isclose(d.Z, 4.0)
