"""Australian fault types: seasonality, geographic clusters, local-time windows, 30-day presence."""

import numpy as np
import pandas as pd
import pytest

from netmon_datagen.config import FaultConfig, get_preset, rng_for
from netmon_datagen.faults import (
    CLUSTER_TYPES,
    FAULT_SPECS,
    _season_factor,
    in_season,
    incidents_frame,
    root_pool,
    schedule_incidents,
)
from netmon_datagen.kpis import local_clock
from netmon_datagen.topology import ANCESTOR_COL, LONG_HAUL_KM, REGION_BY_CODE, build_topology, km_between

AU_TYPES = ["BUSHFIRE_GRID_OUTAGE", "CYCLONE_BACKHAUL_CUT", "LONG_HAUL_FIBRE_CUT"]


@pytest.fixture(scope="module")
def small():
    return build_topology(get_preset("small"), seed=42)


@pytest.fixture(scope="module")
def month(small):
    """A default-settings 30-day schedule on the small preset (September: off-season for both weather types)."""
    ws = np.datetime64("2026-09-01T00:00:00")
    return schedule_incidents(small, ws, ws + np.timedelta64(30, "D"), FaultConfig(), rng_for(42, "faults"))


@pytest.fixture(scope="module")
def summer(small):
    """Stressed January schedule: in season for bushfires and cyclones."""
    ws = np.datetime64("2027-01-10T00:00:00")
    return schedule_incidents(small, ws, ws + np.timedelta64(5, "D"), FaultConfig(rate_multiplier=20),
                              rng_for(7, "faults"))


def test_every_type_appears_in_a_default_30_day_run(month):
    scheduled = {t for t, s in FAULT_SPECS.items() if s.root_rates}
    assert {i.fault_type for i in month} == scheduled


def test_seasonal_rates():
    bush, cyc = FAULT_SPECS["BUSHFIRE_GRID_OUTAGE"], FAULT_SPECS["CYCLONE_BACKHAUL_CUT"]
    jan = (np.datetime64("2027-01-01T00:00:00"), np.datetime64("2027-02-01T00:00:00"))
    jul = (np.datetime64("2026-07-01T00:00:00"), np.datetime64("2026-08-01T00:00:00"))
    assert _season_factor(bush, *jan) == pytest.approx(3.0) and _season_factor(bush, *jul) == pytest.approx(0.3)
    assert _season_factor(cyc, *jan) == pytest.approx(2.0) and _season_factor(cyc, *jul) == pytest.approx(0.2)
    assert _season_factor(FAULT_SPECS["CELL_OUTAGE"], *jan) == 1.0
    # A window straddling the end of the cyclone season averages its days.
    apr_may = (np.datetime64("2026-04-21T00:00:00"), np.datetime64("2026-05-11T00:00:00"))
    assert _season_factor(cyc, *apr_may) == pytest.approx((10 * 2.0 + 10 * 0.2) / 20)
    assert in_season(bush, np.datetime64("2026-12-25T00:00:00")) and not in_season(bush, jul[0])


def test_descriptions_follow_the_season(month, summer):
    for incs, fire_word, cyc_word in ((month, "storm", "thunderstorm"), (summer, "Bushfire", "cyclone")):
        df = incidents_frame(incs, build_topology(get_preset("small"), seed=42))
        assert df[df.fault_type == "BUSHFIRE_GRID_OUTAGE"].description.str.contains(fire_word, case=False).all()
        assert df[df.fault_type == "CYCLONE_BACKHAUL_CUT"].description.str.contains(cyc_word, case=False).all()


def test_root_pools(small):
    n = small.nodes
    bush = root_pool(small, "BUSHFIRE_GRID_OUTAGE", "SITE")
    assert len(bush) and set(n.loc[bush, "urbanity"]) <= {"rural", "remote"}
    cyc = root_pool(small, "CYCLONE_BACKHAUL_CUT", "BACKHAUL_LINK")
    assert len(cyc) and all(REGION_BY_CODE[c].tropical for c in n.loc[cyc, "region_code"])
    lh = root_pool(small, "LONG_HAUL_FIBRE_CUT", "AGG_ROUTER")
    assert len(lh) and (n.loc[lh, "uplink_km"] >= LONG_HAUL_KM).all()
    assert set(n.loc[lh, "region_code"]) == {"NQL"}  # the only small-preset region homed on a distant core


@pytest.mark.parametrize("ftype", AU_TYPES)
def test_au_faults_hit_descendants_of_their_roots_only(small, month, summer, ftype):
    incs = [i for i in month + summer if i.fault_type == ftype]
    assert incs
    n, cells = small.nodes, small.cells
    for inc in incs:
        roots = inc.root_element_ids
        assert inc.root_element_id == roots[0] and len(set(roots)) == len(roots)
        assert set(n.loc[roots, "element_type"]) == {inc.root_element_type}
        if ftype not in CLUSTER_TYPES:
            assert len(roots) == 1
        under = np.flatnonzero(cells[ANCESTOR_COL[inc.root_element_type]].isin(roots).to_numpy())
        assert set(inc.cell_idx) == set(under)
        below = set(n.index[n[ANCESTOR_COL[inc.root_element_type]].isin(roots) & ~n.index.isin(roots)])
        assert set(inc.affected_element_ids) == below - {inc.root_element_id}
        assert inc.customer_impacting
        # Alarms only on the roots, their descendants and (long-haul) the parent UPF.
        allowed = set(roots) | below | {n.at[inc.root_element_id, "upf_id"]}
        assert {a["element_id"] for a in inc.alarms} <= allowed


@pytest.mark.parametrize("ftype", CLUSTER_TYPES)
def test_weather_clusters_are_geographic(small, summer, ftype):
    n = small.nodes
    big = [i for i in summer if i.fault_type == ftype]
    assert big and max(len(i.root_element_ids) for i in big) >= 2
    radius = 45 if ftype == "BUSHFIRE_GRID_OUTAGE" else 150
    for inc in big:
        r = n.loc[inc.root_element_ids]
        assert (r.region_code == inc.region_code).all()
        d = km_between(r.lat.iloc[0], r.lon.iloc[0], r.lat.to_numpy(), r.lon.to_numpy())
        assert (d <= radius + 0.5).all() and np.all(np.diff(d) >= -1e-9)  # nearest first


def test_bushfire_timeline(small, summer):
    """Mains loss sweeps out from the epicentre; batteries hold before sites go dark; the 5G layer is shed
    first; restoration is staggered and the epicentre is restored last."""
    cells = small.cells
    seen_5g = False
    for inc in (i for i in summer if i.fault_type == "BUSHFIRE_GRID_OUTAGE"):
        d = inc.detail
        assert inc.spec.silent
        assert (d["hit"] >= inc.start).all() and (d["dark"] >= d["hit"]).all()
        assert d["restore"][0] == d["restore"].max() == inc.end
        site = cells["site_id"].to_numpy()[inc.cell_idx]
        tech = cells["technology"].to_numpy()[inc.cell_idx]
        for i, s in enumerate(d["roots"]):
            on = inc.onset[site == s]
            assert (on >= d["hit"][i]).all()
            g4, g5 = inc.onset[(site == s) & (tech == "4G")], inc.onset[(site == s) & (tech == "5G")]
            assert (g4 == d["dark"][i]).all()
            if len(g5):
                seen_5g = True
                assert g5.max() <= g4.min()
        codes = {a["alarm_code"] for a in inc.alarms}
        assert {"MAINS_FAILURE", "BATTERY_LOW", "NE_UNREACHABLE"} <= codes
    assert seen_5g


def test_long_haul_cut_is_silent_and_alarms_from_core_side(month):
    inc = next(i for i in month if i.fault_type == "LONG_HAUL_FIBRE_CUT")
    assert inc.spec.silent
    by_el = pd.DataFrame(inc.alarms).groupby("element_id").alarm_code.apply(set)
    assert {"LOS", "NE_UNREACHABLE"} <= by_el[inc.root_element_id]
    assert not {"S1_NG_LINK_FAILURE", "LINK_DOWN", "CELL_OUT_OF_SERVICE"} & set().union(*by_el)


def test_busy_hour_and_maintenance_windows_are_local(small, month):
    tz = small.nodes["timezone"]
    checked = set()
    for inc in month:
        spec = inc.spec
        if spec.hours is None:
            continue
        t = inc.planned_window[0] if inc.fault_type == "PLANNED_MAINTENANCE" else inc.start
        h = local_clock(np.array([t]), [tz[inc.root_element_id]])[0][0, 0]
        if inc.fault_type == "PLANNED_MAINTENANCE":
            assert h in (0.0, 0.5, 1.0, 1.5), (inc.incident_id, h)  # window opens on a local half hour
        else:
            assert spec.hours[0] <= h < spec.hours[1], (inc.fault_type, h)
        checked.add(tz[inc.root_element_id])
    assert len(checked) >= 2  # spans more than one time zone
