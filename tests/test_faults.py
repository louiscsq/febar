"""Fault propagation, verified against a no-fault counterfactual run with the same seed.

Baseline KPI noise uses its own RNG stream, so any difference between the two runs is caused by an
injected incident.
"""

import numpy as np
import pandas as pd
import pytest

from conftest import read_table
from netmon_datagen.faults import FAULT_SPECS
from netmon_datagen.topology import ANCESTOR_COL

SIGNAL = ["availability_pct", "active_users", "latency_ms", "dl_throughput_mbps", "attach_success_pct",
          "prb_util_pct", "session_drop_rate_pct"]


@pytest.fixture(scope="module")
def data(counterfactual_pair):
    with_f, without_f = counterfactual_pair
    kf, kb = read_table(with_f, "kpis"), read_table(without_f, "kpis")
    m = kb.merge(kf, on=["record_id", "cell_id", "event_ts"], how="left", suffixes=("_base", "_fault"))
    m["t"] = pd.to_datetime(m["event_ts"])
    m["missing"] = m["availability_pct_fault"].isna()
    m["changed"] = m["missing"] | np.logical_or.reduce(
        [~np.isclose(m[f"{c}_base"].astype(float), m[f"{c}_fault"].astype(float)) for c in SIGNAL])
    inc = read_table(with_f, "ground_truth/incidents")
    for c in ["start_ts", "end_ts", "impact_start_ts", "impact_end_ts"]:
        inc[c] = pd.to_datetime(inc[c])
    topo = read_table(with_f, "topology_nodes").set_index("element_id")
    return m, inc, topo


def _window(m, cells, t0, t1):
    return m[m.cell_id.isin(cells) & (m.t >= t0) & (m.t < t1)]


def test_only_incident_cells_ever_change(data):
    m, inc, _ = data
    impacted = set().union(*inc.loc[inc.is_customer_impacting, "affected_cell_ids"].map(set))
    assert m["changed"].any()
    assert not m.loc[~m.cell_id.isin(impacted), "changed"].any()


def test_changes_happen_only_inside_incident_windows(data):
    m, inc, _ = data
    ch = m[m.changed]
    covered = np.zeros(len(ch), dtype=bool)
    for _, r in inc[inc.is_customer_impacting].iterrows():
        lo = r.impact_start_ts - pd.Timedelta(minutes=15)  # period containing the onset
        covered |= ch.cell_id.isin(r.affected_cell_ids).to_numpy() & (ch.t >= lo).to_numpy() & (
            ch.t < r.impact_end_ts).to_numpy()
    assert covered.all()


def test_router_failure_degrades_all_descendants_and_nothing_else(data):
    m, inc, topo = data
    rf = inc[inc.fault_type == "AGG_ROUTER_FAILURE"]
    r = rf.loc[(rf.end_ts - rf.impact_start_ts).idxmax()]  # longest one: needs whole periods inside the outage
    desc_cells = topo.index[(topo.router_id == r.root_element_id) & (topo.element_type == "CELL")]
    assert set(r.affected_cell_ids) == set(desc_cells)
    t0 = (r.impact_start_ts + pd.Timedelta(minutes=3)).ceil("15min")  # every cell's onset is within 1-3 min
    t1 = r.end_ts.floor("15min")
    assert t1 > t0
    inside = _window(m, desc_cells, t0, t1)
    assert len(inside) and inside.changed.all()
    assert inside.availability_pct_fault.max() < 20
    assert inside.active_users_fault.mean() < 0.1 * inside.active_users_base.mean()
    # Non-descendants not involved in any other incident at that time are untouched.
    others_busy = set()
    for _, o in inc[inc.is_customer_impacting & (inc.incident_id != r.incident_id)].iterrows():
        if o.impact_start_ts < t1 and o.impact_end_ts > t0:
            others_busy |= set(o.affected_cell_ids)
    outside = m[~m.cell_id.isin(set(desc_cells) | others_busy) & (m.t >= t0) & (m.t < t1)]
    assert len(outside) and not outside.changed.any()


def test_router_impact_is_delayed_after_root_failure(data):
    _, inc, _ = data
    r = inc[inc.fault_type == "AGG_ROUTER_FAILURE"].iloc[0]
    assert r.impact_start_ts > r.start_ts


@pytest.mark.parametrize("ftype,col,direction", [
    ("CELL_OUTAGE", "availability_pct", -1),
    ("BACKHAUL_DEGRADATION", "latency_ms", +1),
    ("CORE_CONGESTION", "latency_ms", +1),
    ("AMF_OVERLOAD", "attach_success_pct", -1),
    ("PLANNED_MAINTENANCE", "availability_pct", -1),
    ("TRAFFIC_SURGE", "prb_util_pct", +1),
])
def test_fault_signatures(data, ftype, col, direction):
    m, inc, _ = data
    r = inc[inc.fault_type == ftype].iloc[0]
    w = _window(m, r.affected_cell_ids, r.impact_start_ts, r.impact_end_ts).dropna(subset=[f"{col}_fault"])
    assert len(w)
    delta = (w[f"{col}_fault"] - w[f"{col}_base"]).mean()
    assert direction * delta > 0, (ftype, col, delta)


def test_site_power_outage_cells_go_silent_after_battery(data):
    m, inc, _ = data
    r = inc[(inc.fault_type == "SITE_POWER_OUTAGE") & inc.is_customer_impacting].iloc[0]
    assert r.impact_start_ts >= r.start_ts  # battery hold-up delays the impact
    t0 = r.impact_start_ts.ceil("15min")
    t1 = r.end_ts.floor("15min")
    w = _window(m, r.affected_cell_ids, t0, t1)
    assert len(w) and w.missing.all()


def test_alarm_storm_has_alarms_but_no_customer_impact(counterfactual_pair):
    with_f, _ = counterfactual_pair
    inc = read_table(with_f, "ground_truth/incidents")
    alarms = read_table(with_f, "alarms")
    storm = inc[inc.fault_type == "ALARM_STORM"].iloc[0]
    assert not storm.is_customer_impacting and storm.n_affected_cells == 0
    t = pd.to_datetime(alarms.event_ts)
    on_root = alarms[(alarms.element_id == storm.root_element_id) & (alarms.event_type == "RAISE")
                     & (t >= pd.Timestamp(storm.start_ts)) & (t <= pd.Timestamp(storm.end_ts))]
    assert len(on_root) >= 50


@pytest.mark.parametrize("ftype", ["BUSHFIRE_GRID_OUTAGE", "CYCLONE_BACKHAUL_CUT", "LONG_HAUL_FIBRE_CUT"])
def test_au_faults_change_only_cells_under_their_roots(data, ftype):
    m, inc, topo = data
    r = inc[inc.fault_type == ftype].iloc[0]
    col = ANCESTOR_COL[r.root_element_type]
    under = set(topo.index[(topo.element_type == "CELL") & topo[col].isin(r.root_element_ids)])
    assert r.is_customer_impacting and set(r.affected_cell_ids) == under
    lo, hi = r.impact_start_ts.floor("15min"), r.impact_end_ts
    others = set()
    for _, o in inc[inc.is_customer_impacting & (inc.incident_id != r.incident_id)].iterrows():
        if o.impact_start_ts < hi and o.impact_end_ts > lo:
            others |= set(o.affected_cell_ids)
    w = m[(m.t >= lo) & (m.t < hi) & m.changed]
    assert w.cell_id.isin(under).any()
    assert set(w.cell_id) - others <= under
    if FAULT_SPECS[ftype].silent:  # dark sites: missing KPI rows, not zeros
        assert w[w.cell_id.isin(under)].missing.any()
    else:
        mine = _window(m, under, lo, hi).dropna(subset=["availability_pct_fault"])
        assert (mine.availability_pct_fault - mine.availability_pct_base).mean() < 0
