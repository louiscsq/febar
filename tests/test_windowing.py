"""Ground truth never describes impact outside the telemetry that was generated.

Stress runs use a high fault rate so many incidents land near the window edges.
"""

import numpy as np
import pandas as pd
import pytest

from conftest import read_table, tiny_cfg
from netmon_datagen.batch import generate_history
from netmon_datagen.config import DQConfig, FaultConfig, get_preset, rng_for
from netmon_datagen.faults import schedule_incidents
from netmon_datagen.stream import run_stream
from netmon_datagen.topology import build_topology

START, DAYS = "2026-09-05", 1
# With the window check disabled, this seed schedules a backhaul degradation and a cell outage whose
# impact runs past window_end (verified when the fix was written), so the batch tests below would fail.
EDGE_SEED = 51
WS, WE = pd.Timestamp(START, tz="UTC"), pd.Timestamp(START, tz="UTC") + pd.Timedelta(days=DAYS)
KPIS = ["availability_pct", "active_users", "prb_util_pct", "latency_ms", "dl_throughput_mbps",
        "attach_success_pct", "rrc_setup_success_pct", "session_drop_rate_pct"]


def _changed(with_f, without_f) -> pd.DataFrame:
    kf, kb = read_table(with_f, "kpis"), read_table(without_f, "kpis")
    m = kb.merge(kf, on=["record_id", "cell_id", "event_ts"], how="left", suffixes=("_b", "_f"))
    m["t"] = pd.to_datetime(m["event_ts"])
    m["changed"] = m["availability_pct_f"].isna() | np.logical_or.reduce(
        [~np.isclose(m[f"{c}_b"].astype(float), m[f"{c}_f"].astype(float)) for c in KPIS])
    return m


def _times(inc: pd.DataFrame) -> pd.DataFrame:
    for c in ["start_ts", "end_ts", "impact_start_ts", "impact_end_ts"]:
        inc[c] = pd.to_datetime(inc[c])
    return inc


@pytest.fixture(scope="module")
def stressed(tmp_path_factory):
    with_f, without_f = tmp_path_factory.mktemp("edge_f"), tmp_path_factory.mktemp("edge_b")
    common = dict(days=DAYS, start=START, seed=EDGE_SEED, dq=DQConfig.none())
    generate_history(tiny_cfg(**common, faults=FaultConfig(rate_multiplier=40)), with_f, log=lambda *a: None)
    generate_history(tiny_cfg(**common, faults=FaultConfig(enabled=False)), without_f, log=lambda *a: None)
    return _times(read_table(with_f, "ground_truth/incidents")), _changed(with_f, without_f), with_f


def test_scheduler_keeps_full_extent_inside_bounds():
    topo = build_topology(get_preset("tiny"), seed=3)
    ws, we = np.datetime64("2026-09-05T00:00:00"), np.datetime64("2026-09-05T06:00:00")
    incs = schedule_incidents(topo, ws, we, FaultConfig(rate_multiplier=200), rng_for(3, "t"))
    assert len(incs) > 5
    for inc in incs:
        lo, hi = inc.extent()  # includes propagation delay, recovery and every alarm raise/clear
        assert ws <= lo and hi <= we, (inc.fault_type, lo, hi)


def test_batch_incidents_lie_inside_window(stressed):
    inc, _, out = stressed
    assert len(inc) >= 10 and not inc.is_censored.any()
    assert (inc.start_ts >= WS).all() and (inc.end_ts <= WE).all()
    imp = inc[inc.is_customer_impacting]
    assert (imp.impact_end_ts > WE - pd.Timedelta(hours=4)).any()  # the window edge is actually exercised
    assert (imp.impact_start_ts >= WS).all() and (imp.impact_end_ts <= WE).all()
    mw = read_table(out, "maintenance_windows")
    assert (pd.to_datetime(mw.planned_end_ts) <= WE).all()


def test_batch_incident_alarms_lie_inside_window(stressed):
    inc, _, out = stressed
    alarms = read_table(out, "alarms")
    alarms["t"] = pd.to_datetime(alarms.event_ts)
    roots = set(inc.loc[inc.fault_type.isin(["AGG_ROUTER_FAILURE", "ALARM_STORM", "SITE_POWER_OUTAGE"]),
                        "root_element_id"])
    # Background alarms may clear after the window; none may precede it.
    assert (alarms.t >= WS).all()
    assert len(alarms[alarms.element_id.isin(roots)])


def test_every_uncensored_impacting_incident_has_matching_degraded_telemetry(stressed):
    inc, m, _ = stressed
    imp = inc[inc.is_customer_impacting & ~inc.is_censored]
    assert len(imp) >= 8
    for _, r in imp.iterrows():
        lo = r.impact_start_ts.floor("15min")
        w = m[m.cell_id.isin(r.affected_cell_ids) & (m.t >= lo) & (m.t < r.impact_end_ts)]
        assert len(w) and w.changed.any(), (r.incident_id, r.fault_type)
        # Telemetry covers the whole labelled impact: the last degraded period reaches impact_end.
        assert w.loc[w.changed, "t"].max() >= r.impact_end_ts - pd.Timedelta(minutes=15), r.incident_id


def test_stream_censors_in_flight_incidents_at_stop(tmp_path):
    t0 = pd.Timestamp("2026-10-08T18:20:00", tz="UTC")
    n = 40
    common = dict(interval_seconds=0, max_batches=n, start="2026-10-08T18:20:00", on_batch=lambda i, s: None,
                  log=lambda *x: None)
    res = run_stream(tiny_cfg(dq=DQConfig.none(), faults=FaultConfig(rate_multiplier=300)), tmp_path / "f", **common)
    run_stream(tiny_cfg(dq=DQConfig.none(), faults=FaultConfig(enabled=False)), tmp_path / "b", **common)
    t_end = t0 + pd.Timedelta(minutes=n)
    inc = _times(read_table(tmp_path / "f", "ground_truth/incidents"))
    real = inc[inc.fault_type != "FLAPPING_ELEMENT"]
    assert res["censored_incidents"] >= 1 and real.is_censored.sum() == res["censored_incidents"]
    assert (real.start_ts >= t0).all()  # nothing is scheduled before the stream starts
    assert (real.end_ts <= t_end).all()  # censored rows are clipped to the observed end
    done = real[~real.is_censored]
    assert (done.end_ts < t_end).all()
    flap = inc[inc.fault_type == "FLAPPING_ELEMENT"]
    assert flap.is_censored.all() and flap.end_ts.isna().all()  # chronic, open-ended
    m = _changed(tmp_path / "f", tmp_path / "b")
    for _, r in real[real.is_customer_impacting].iterrows():
        assert r.impact_end_ts <= t_end
        w = m[m.cell_id.isin(r.affected_cell_ids) & (m.t >= r.impact_start_ts.floor("min"))
              & (m.t < r.impact_end_ts)]
        assert w.changed.any(), (r.incident_id, r.fault_type, r.is_censored)
