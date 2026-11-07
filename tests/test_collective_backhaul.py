"""Step 6: the offline collective (backhaul-link) degradation detector.

`detection.CollectiveRule` (SQL + Python mirror), `windows.parent_health(_sql)` (the active_users-weighted parent-minute
statistic over on-time cell windows) and the experiment's scoring (`collective_eval`). The frozen thresholds on generator
output are tested in test_collective_backhaul_frozen.py.
"""

from __future__ import annotations

import ast
import inspect
import random
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from netmon_pipeline import collective_eval as ce
from netmon_pipeline import detection, scoring, windows

ROOT = Path(__file__).resolve().parents[1]
T0 = 1_791_590_400  # 2026-10-10T00:00:00Z
WM = windows.COLLECTIVE_WATERMARK_S
RULE = detection.CollectiveRule("test", 2.0, (("latency_ms", 6.0), ("packet_loss_pct", 0.26),
                                              ("session_drop_rate_pct", 0.13)), 0.4, 0.8, 2)
BASE = {"latency_ms": (30.0, 3.0), "packet_loss_pct": (0.2, 0.02), "session_drop_rate_pct": (1.0, 0.1)}


def cw(cell, minute, link="BH-1", run="r1", lat=0.0, loss=0.0, drop=0.0, users=20.0, delay=20.0, flags=(),
       maint=False, late=0):
    """One on-time 1-minute cell window; lat / loss / drop are offsets from the baseline mean."""
    ws = T0 + 60 * minute
    r = {"source_run": run, "cell_id": cell, "backhaul_id": link, "window_start_s": ws, "window_end_s": ws + 60,
         "evidence_s": ws + 60 + delay, "flags": list(flags), "in_maintenance": maint, "active_users": users,
         "prb_util_pct": 40.0, "n_late_reports": late}
    for m, off in (("latency_ms", lat), ("packet_loss_pct", loss), ("session_drop_rate_pct", drop)):
        mean, std = BASE[m]
        r.update({m: mean + off, f"b_{m}_mean": mean, f"b_{m}_std": std})
    return r


def link(n, minute, **kw):
    return [cw(f"C{i}", minute, **kw) for i in range(n)]


def stats(rows, n_desc=None):
    n_desc = n_desc or {r["backhaul_id"]: len({x["cell_id"] for x in rows if x["backhaul_id"] == r["backhaul_id"]})
                        for r in rows}
    return windows.parent_health(rows, n_desc)


# --- rule and mirror -------------------------------------------------------------------------------------------------

def test_rule_sql_covers_every_metric_share_and_guard():
    sql = RULE.sql
    for m in detection.COLLECTIVE_METRICS:
        assert f"wz_{m} > 2.0" in sql and f"wdelta_{m} > {RULE.floor(m)}" in sql and f"frac_z1_{m} >= 0.4" in sql
    assert "reporting_share >= 0.8" in sql
    det = detection.collective_detections_sql(RULE, "SELECT 1")
    assert "RANGE BETWEEN 1 PRECEDING AND CURRENT ROW" in det and "n_qualified_in_frame >= 2" in det


def test_vectorised_mirror_equals_scalar_mirror():
    rng = random.Random(3)
    rows = []
    for link_id in ("A", "B", "C"):
        for minute in range(200):
            if rng.random() < 0.05:
                continue  # a missing minute breaks persistence
            r = {"source_run": "r1", "parent_id": link_id, "window_start_s": T0 + 60 * minute,
                 "reporting_share": rng.choice([0.5, 0.79, 0.8, 1.0, None])}
            for m in detection.COLLECTIVE_METRICS:
                r[f"wz_{m}"] = rng.choice([None, rng.uniform(0, 4)])
                r[f"wdelta_{m}"] = rng.uniform(0, 2 * RULE.floor(m))
                r[f"frac_z1_{m}"] = rng.uniform(0, 1)
            rows.append(r)
    df = pd.DataFrame(rows)
    assert list(RULE.qualifies_frame(df)) == [RULE.qualifies(r) for r in rows]
    fired = {(r["parent_id"], r["window_start_s"]) for r in RULE.fires(rows)}
    vec = {(p, w) for p, w, f in zip(df.parent_id, df.window_start_s, RULE.fires_frame(df), strict=True) if f}
    assert fired == vec and 0 < len(fired) < sum(RULE.qualifies(r) for r in rows)


def test_persistence_needs_consecutive_qualified_minutes():
    shifted = [r for m in (0, 1, 3) for r in link(10, m, lat=8.0)]  # minute 2 missing
    rows = stats(shifted)
    fired = sorted((r["window_start_s"] - T0) // 60 for r in RULE.fires(rows))
    assert fired == [1]  # minute 0 has no predecessor, minute 3's predecessor is missing


def test_weighted_by_active_users():
    rows = [cw("C0", 0, lat=30.0, users=900.0)] + [cw(f"C{i}", 0, users=1.0) for i in range(1, 10)]
    s = stats(rows)[0]
    assert s["wdelta_latency_ms"] == pytest.approx(30.0 * 900 / 909)
    assert s["frac_z1_latency_ms"] == pytest.approx(0.1)


def test_consistency_guard_stops_one_cell_carrying_the_mean():
    # one cell +60 ms (z = 20), nine flat: weighted mean z = 2.0x, mean delta 6.x ms, but only 10 % of cells agree
    rows = [cw("C0", m, lat=65.0) for m in range(3)] + [r for m in range(3) for r in link(10, m)[1:]]
    s = stats(rows)
    assert all(x["wz_latency_ms"] > RULE.z and x["wdelta_latency_ms"] > RULE.floor("latency_ms") for x in s)
    assert not any(RULE.qualifies(x) for x in s)
    no_guard = detection.CollectiveRule("no_guard", RULE.z, RULE.floors, 0.0, RULE.min_reporting_share, RULE.persist)
    assert all(no_guard.qualifies(x) for x in s)  # the guard, nothing else, holds it back
    # the same mean shift carried by every cell qualifies
    assert all(RULE.qualifies(x) for x in stats([r for m in range(3) for r in link(10, m, lat=7.0)]))


def test_hard_rule_maintenance_and_no_baseline_cells_are_excluded():
    rows = link(10, 0, lat=8.0)
    rows[0]["flags"] = ["cell_unavailable", "latency_degradation"]
    rows[1]["in_maintenance"] = True
    rows[2]["b_latency_ms_mean"] = None
    s = stats(rows)[0]
    assert s["n_reporting_cells"] == 7 and s["reporting_share"] == pytest.approx(0.7)
    assert s["n_hard_rule_cells"] == 1 and s["in_maintenance"]
    assert not RULE.qualifies(s)  # below the 80 % reporting share


def test_silent_cells_lower_the_reporting_share():
    s = stats(link(7, 0, lat=8.0), n_desc={"BH-1": 10})[0]
    assert s["n_reporting_cells"] == 7 and not RULE.qualifies(s)


# --- the late-data rule ----------------------------------------------------------------------------------------------

def test_late_record_never_qualifies_a_window():
    on_time = [r for m in range(2) for r in link(10, m)]
    # the shift is carried only by a late copy of the windows (late record, or arriving after the parent closes)
    for late_kw in ({"late": 1}, {"delay": WM + 1}):
        rows = [r for m in range(2) for r in link(10, m, lat=8.0, **late_kw)]
        s = stats(rows, n_desc={"BH-1": 10})
        assert all(x["n_reporting_cells"] == 0 for x in s) and RULE.fires(s) == []
        assert RULE.fires(stats(on_time)) == []
    # the record-level rule upstream: a late record never enters an on-time cell window at all
    w = windows.realtime_window([{"is_late": True, "degraded": True, "evidence_s": T0 + 90}], T0 + 60, WM)
    assert w["silent"] and not w["degraded"]


def test_window_is_never_stamped_before_close_or_its_latest_used_record():
    rng = random.Random(5)
    rows = [cw(f"C{i}", m, lat=8.0, delay=rng.uniform(1, WM)) for m in range(5) for i in range(10)]
    rows += [cw("C9", 2, lat=8.0, delay=WM + 30)]  # a too-late copy: not used, so it cannot time the window either
    for s in stats(rows):
        used_ev = [r["evidence_s"] for r in rows if r["window_start_s"] == s["window_start_s"]
                   and windows.cell_window_used(r)]
        assert s["available_s"] >= s["window_end_s"] + WM and s["available_s"] >= max(used_ev)
        assert s["available_s"] == max(s["window_end_s"] + WM, max(used_ev))
    for d in RULE.fires(stats(rows)):
        assert d["available_s"] >= d["window_end_s"] + WM


# --- detection ids, ground truth -------------------------------------------------------------------------------------

def test_detection_ids_unique_per_run():
    ids = [detection.collective_detection_id(run, lk, datetime.fromtimestamp(T0 + 60 * m, timezone.utc)
                                             .strftime("%Y-%m-%dT%H:%M:%SZ"))
           for run in ("history_1m", "holdout_1m", "stream") for lk in ("BH-1", "BH-2") for m in range(50)]
    assert len(set(ids)) == len(ids)
    sql = detection.collective_detections_sql(RULE, "SELECT 1")
    assert "concat('collective|', source_run, '|', parent_id, '|'" in sql


FORBIDDEN = ("netmon_eval", "eval_gt", "gt_incidents", "incident", "is_root", "root_element", "affected_cell",
             "is_censored", "event_class", "fault_type")


def test_ground_truth_is_never_an_input_to_detections():
    sql = detection.collective_detections_sql(
        RULE, windows.parent_health_sql("h", "t", "m", "source_run = 'x'"))
    for code in (sql, inspect.getsource(windows.parent_health), inspect.getsource(windows.cell_window_used),
                 inspect.getsource(detection.CollectiveRule), inspect.getsource(detection.collective_detections_sql)):
        assert not any(f in code for f in FORBIDDEN), [f for f in FORBIDDEN if f in code]
    # the experiment computes and writes the detections before it reads any ground truth
    src = (ROOT / "scripts/collective_backhaul_experiment.py").read_text()
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "score")
    body = ast.get_source_segment(src, fn)
    assert body.index("wh.execute(insert)") < body.index("Context(wh, reading)")
    assert "GT" not in ast.get_source_segment(src, next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                                                       and n.name == "stats_sql"))


def test_scoring_matches_the_step2_contract():
    inc = {"source_run": "r1", "incident_id": "I1", "fault_type": "BACKHAUL_DEGRADATION", "event_class": "fault",
           "root_element_id": "BH-1", "root_element_ids": ["BH-1"], "affected_element_ids": ["SITE-1"],
           "affected_cell_ids": ["C0"], "is_customer_impacting": True, "is_censored": False,
           "impact_start_s": T0, "impact_end_s": T0 + 3600, "start_s": T0, "end_s": T0 + 3600}
    coll = [{"source_run": "r1", "element_id": "BH-1", "signal_start_s": T0 + 240, "signal_end_s": T0 + 300,
             "available_s": T0 + 420},
            {"source_run": "r2", "element_id": "BH-1", "signal_start_s": T0, "signal_end_s": T0 + 60,
             "available_s": T0 + 180}]  # another run never credits it
    rows = ce.score_incidents([inc], coll, {("r1", "I1"): T0 + 600.0}, {"BH-1": 9})
    assert rows[0]["before_ttd_s"] == 600 and rows[0]["collective_ttd_s"] == 420 and rows[0]["combined_ttd_s"] == 420
    far = [{"source_run": "r1", "element_id": "BH-1", "signal_start_s": T0 + 90000, "signal_end_s": T0 + 90060,
            "available_s": T0 + 90180, "in_maintenance": False, "w_prb_util_pct": 75.0}]
    alerts = ce.alert_table(coll[:1] + far, [inc], {"BH-1": {"C0", "SITE-1"}})
    labels = sorted((a["label"], a["busy_hour"]) for a in alerts)
    assert labels == [("fault", False), ("unexplained", True)]
    days = ce.healthy_link_days(["BH-1"], {"BH-1": {"C0"}}, [inc], "r1", T0 - 86400, T0 + 86400)
    lo, hi = ce.incident_window(inc)
    assert days == pytest.approx((2 * 86400 - (hi - lo)) / 86400)
    fa = ce.false_alarm_summary(alerts, days)
    assert fa["n_false_alarms"] == 1 and fa["unexplained_busy_hour"] == 1


# --- Spark: the SQL the experiment runs equals the Python mirror -----------------------------------------------------

def test_parent_health_sql_and_detections_match_the_python_mirror(spark):
    from datetime import timedelta

    from pyspark.sql import Row

    rng = random.Random(9)
    rows = []
    for lk, n in (("BH-1", 10), ("BH-2", 4)):
        for m in range(8):
            for i in range(n):
                shift = 8.0 if m >= 2 else 0.0
                rows.append(cw(f"{lk}-C{i}", m, link=lk, lat=shift + rng.gauss(0, 1), loss=rng.uniform(0, 0.3),
                               users=rng.choice([0.0, 5.0, 40.0]),
                               delay=WM + 5 if rng.random() < 0.04 else rng.choice([10, 30, WM]),
                               flags=["cell_unavailable"] if rng.random() < 0.05 else []))
    rows = [r for r in rows if not (r["backhaul_id"] == "BH-2" and r["window_start_s"] == T0 + 300)]  # a gap
    maint = [("r1", "SITE-BH-1-C3", T0 + 120, T0 + 240)]
    for r in rows:
        r["site_id"], r["router_id"] = "SITE-" + r["cell_id"], "RTR-1"
        r["in_maintenance"] = any(r["site_id"] == e and a < r["window_end_s"] and b > r["window_start_s"]
                                  for _run, e, a, b in maint)

    def ts(s):
        return datetime.fromtimestamp(s, timezone.utc).replace(tzinfo=None)

    ms = detection.COLLECTIVE_METRICS
    spark.createDataFrame([Row(source_run=r["source_run"], cell_id=r["cell_id"], site_id=r["site_id"],
                               backhaul_id=r["backhaul_id"], router_id=r["router_id"],
                               window_start=ts(r["window_start_s"]), window_end=ts(r["window_end_s"]),
                               evidence_ts=ts(r["evidence_s"]), flags=r["flags"], active_users=r["active_users"],
                               prb_util_pct=r["prb_util_pct"], n_late_reports=r["n_late_reports"],
                               **{k: r[k] for m in ms for k in (m, f"b_{m}_mean", f"b_{m}_std")}) for r in rows]
                          ).createOrReplaceTempView("h")
    cells = sorted({(r["cell_id"], r["backhaul_id"]) for r in rows})
    spark.createDataFrame([Row(element_id=c, element_type="CELL", backhaul_id=lk) for c, lk in cells]
                          ).createOrReplaceTempView("t")
    spark.createDataFrame([Row(source_run=a, element_id=e, planned_start_ts=ts(s0), planned_end_ts=ts(s1))
                           for a, e, s0, s1 in maint]).createOrReplaceTempView("m")
    sql = windows.parent_health_sql("h", "t", "m")
    got = {(r.parent_id, int((r.window_start - datetime(1970, 1, 1)).total_seconds())): r.asDict()
           for r in spark.sql(sql).collect()}
    n_desc = {lk: sum(1 for _c, x in cells if x == lk) for lk in ("BH-1", "BH-2")}
    py = windows.parent_health(rows, n_desc)
    assert set(got) == {(p["parent_id"], p["window_start_s"]) for p in py}
    for p in py:
        g = got[(p["parent_id"], p["window_start_s"])]
        for k in ("n_reporting_cells", "n_hard_rule_cells", "n_maintenance_cells", "in_maintenance"):
            assert g[k] == p[k], k
        for k in ["reporting_share", "w_prb_util_pct"] + [f"{x}_{m}" for m in ms for x in ("wz", "wdelta", "frac_z1")]:
            assert (g[k] is None and p[k] is None) or g[k] == pytest.approx(p[k]), k
        av = (g["available_ts"] - datetime(1970, 1, 1)).total_seconds()
        assert av == pytest.approx(p["available_s"])
        assert g["available_ts"] >= g["window_end"] + timedelta(seconds=WM)
    det = spark.sql(detection.collective_detections_sql(RULE, sql)).collect()
    sql_fired = {(r.element_id, int((r.signal_start_ts - datetime(1970, 1, 1)).total_seconds())) for r in det}
    py_fired = {(p["parent_id"], p["window_start_s"]) for p in RULE.fires(py)}
    assert sql_fired == py_fired and sql_fired
    for r in det:
        assert r.detection_id == detection.collective_detection_id(
            "r1", r.element_id, r.signal_start_ts.strftime("%Y-%m-%dT%H:%M:%SZ"))
    assert len({r.detection_id for r in det}) == len(det)
    assert scoring.SLA_S == 300  # the experiment reports against the unchanged step-2 SLA
