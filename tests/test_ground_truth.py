import pandas as pd
import pytest

from conftest import read_table
from netmon_datagen.faults import FAULT_SPECS
from netmon_datagen.topology import ANCESTOR_COL

ROOT_ALARM_TYPES = ["CELL_OUTAGE", "SITE_POWER_OUTAGE", "BACKHAUL_DEGRADATION", "AGG_ROUTER_FAILURE",
                    "CORE_CONGESTION", "AMF_OVERLOAD", "PLANNED_MAINTENANCE", "ALARM_STORM"]


@pytest.fixture(scope="module")
def gt(history_json):
    out, manifest = history_json
    inc = read_table(out, "ground_truth/incidents")
    for c in ["start_ts", "end_ts", "impact_start_ts", "impact_end_ts"]:
        inc[c] = pd.to_datetime(inc[c])
    topo = read_table(out, "topology_nodes").set_index("element_id")
    alarms = read_table(out, "alarms")
    alarms["t"] = pd.to_datetime(alarms["event_ts"], errors="coerce", format="ISO8601")
    mw = read_table(out, "maintenance_windows")
    return inc, topo, alarms, mw


def test_every_fault_type_present_with_unique_ids(gt):
    inc, *_ = gt
    assert set(FAULT_SPECS) == set(inc.fault_type)
    assert inc.incident_id.is_unique
    assert (inc.end_ts > inc.start_ts).all()


def test_impact_fields_consistent(gt):
    inc, *_ = gt
    imp = inc[inc.is_customer_impacting]
    assert (imp.impact_start_ts >= imp.start_ts - pd.Timedelta(seconds=1)).all()
    assert (imp.impact_end_ts > imp.impact_start_ts).all()
    assert (imp.estimated_impacted_subscribers > 0).all()
    assert (imp.n_affected_cells == imp.affected_cell_ids.map(len)).all()
    quiet = inc[~inc.is_customer_impacting]
    assert (quiet.estimated_impacted_subscribers == 0).all()
    assert set(inc[inc.event_class == "fault"].fault_type) <= set(imp.fault_type) | {"SITE_POWER_OUTAGE"}


def test_affected_elements_are_descendants_of_root(gt):
    inc, topo, *_ = gt
    for _, r in inc.iterrows():
        assert r.root_element_id in topo.index
        assert set(r.affected_element_ids) <= set(topo.index)
        if r.fault_type in ("TRAFFIC_SURGE", "ALARM_STORM", "FLAPPING_ELEMENT"):
            continue
        if r.root_element_type == "CELL":
            desc = set()
        else:
            col = ANCESTOR_COL[r.root_element_type]
            desc = set(topo.index[(topo[col] == r.root_element_id) & (topo.index != r.root_element_id)])
        assert set(r.affected_element_ids) == desc
        assert set(r.affected_cell_ids) <= desc | {r.root_element_id}


def test_customer_impacting_incidents_do_not_overlap(gt):
    inc, *_ = gt
    imp = inc[inc.is_customer_impacting].reset_index(drop=True)
    for i in range(len(imp)):
        for j in range(i + 1, len(imp)):
            a, b = imp.loc[i], imp.loc[j]
            if a.impact_start_ts < b.impact_end_ts and b.impact_start_ts < a.impact_end_ts:
                assert not set(a.affected_cell_ids) & set(b.affected_cell_ids), (a.incident_id, b.incident_id)


@pytest.mark.parametrize("ftype", ROOT_ALARM_TYPES)
def test_root_element_raises_alarms_during_incident(gt, ftype):
    inc, _, alarms, _ = gt
    r = inc[inc.fault_type == ftype].iloc[0]
    lo, hi = r.start_ts - pd.Timedelta(minutes=10), r.end_ts + pd.Timedelta(minutes=10)
    hit = alarms[(alarms.element_id == r.root_element_id) & (alarms.t >= lo) & (alarms.t <= hi)]
    assert len(hit), ftype


def test_router_failure_symptom_flood_exceeds_root_alarms(gt):
    inc, _, alarms, _ = gt
    r = inc[inc.fault_type == "AGG_ROUTER_FAILURE"].iloc[0]
    w = alarms[(alarms.t >= r.start_ts) & (alarms.t <= r.end_ts) & (alarms.event_type == "RAISE")]
    downstream = w[w.element_id.isin(r.affected_element_ids)]
    root = w[w.element_id == r.root_element_id]
    assert len(root) >= 1 and len(downstream) > 3 * len(root)


def test_maintenance_calendar_matches_planned_incidents(gt):
    inc, _, _, mw = gt
    planned = inc[inc.fault_type == "PLANNED_MAINTENANCE"]
    assert len(mw) == len(planned)
    for _, r in planned.iterrows():
        w = mw[mw.element_id == r.root_element_id].iloc[0]
        assert pd.Timestamp(w.planned_start_ts) <= r.impact_start_ts
        assert r.impact_end_ts <= pd.Timestamp(w.planned_end_ts)


def test_flapping_element_flaps(history_json):
    out, _ = history_json
    inc = read_table(out, "ground_truth/incidents")
    alarms = read_table(out, "alarms")
    flap = inc[inc.fault_type == "FLAPPING_ELEMENT"].iloc[0]
    ev = alarms[alarms.element_id == flap.root_element_id]
    assert (ev.event_type == "RAISE").sum() >= 5 and (ev.event_type == "CLEAR").sum() >= 5
