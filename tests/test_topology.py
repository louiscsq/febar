from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from netmon_datagen.config import PRESETS, get_preset
from netmon_datagen.topology import (
    ANCESTOR_COL,
    LEVEL_OF,
    LEVELS,
    REGION_BY_CODE,
    REGIONS,
    build_topology,
    km_between,
    on_land,
)

AU_LAT, AU_LON = (-44.0, -10.0), (112.0, 154.0)  # mainland Australia + Tasmania bounding box
AU_ZONES = {"Australia/Sydney", "Australia/Melbourne", "Australia/Brisbane", "Australia/Perth",
            "Australia/Adelaide", "Australia/Hobart", "Australia/Darwin"}


@pytest.fixture(scope="module")
def topo():
    return build_topology(get_preset("tiny"), seed=42)


def test_forest_structure(topo):
    nodes, edges = topo.nodes, topo.edges
    roots = nodes[nodes["parent_id"].isna()]
    assert set(roots["element_type"]) == {"AMF_MME"}
    assert len(edges) == len(nodes) - len(roots)
    # Every non-root node has exactly one parent, and the parent exists.
    assert edges["child_id"].is_unique
    assert set(edges["child_id"]) == set(nodes.index[nodes["parent_id"].notna()])
    assert set(edges["parent_id"]) <= set(nodes.index)
    # Levels strictly increase by one along every edge -> acyclic.
    lvl = nodes["level"]
    assert ((lvl.loc[edges["child_id"]].to_numpy() - lvl.loc[edges["parent_id"]].to_numpy()) == 1).all()


def test_no_orphans_every_node_reaches_a_root(topo):
    parent = topo.nodes["parent_id"].to_dict()
    for eid in topo.nodes.index:
        seen = 0
        while parent[eid] is not None and not pd.isna(parent[eid]):
            eid = parent[eid]
            seen += 1
            assert seen <= len(LEVELS)
        assert topo.nodes.at[eid, "element_type"] == "AMF_MME"


def test_every_non_leaf_level_has_children(topo):
    has_child = set(topo.edges["parent_id"])
    for etype in LEVELS[:-1]:
        ids = set(topo.ids_of_type(etype))
        assert ids <= has_child, f"{etype} without children: {sorted(ids - has_child)[:5]}"


def test_ancestor_columns_match_parent_chain(topo):
    nodes = topo.nodes
    for eid, row in nodes[nodes["element_type"] == "CELL"].iterrows():
        cur = eid
        while not pd.isna(nodes.at[cur, "parent_id"]):
            cur = nodes.at[cur, "parent_id"]
            assert row[ANCESTOR_COL[nodes.at[cur, "element_type"]]] == cur


def test_attributes(topo):
    cells = topo.cells
    assert set(cells["technology"]) <= {"4G", "5G"}
    assert set(cells["urbanity"]) <= {"urban", "suburban", "rural", "remote"}
    assert cells["lat"].between(*AU_LAT).all() and cells["lon"].between(*AU_LON).all()
    assert topo.nodes["vendor"].notna().all()
    assert topo.nodes["region"].notna().all()
    assert set(topo.nodes["level"]) == set(LEVEL_OF.values())
    assert set(topo.nodes.loc[topo.nodes.element_type == "BACKHAUL_LINK", "transport_medium"]) <= {"fibre", "microwave", "satellite"}


def test_deterministic_and_seed_sensitive():
    a = build_topology(get_preset("tiny"), seed=7).public_nodes()
    b = build_topology(get_preset("tiny"), seed=7).public_nodes()
    c = build_topology(get_preset("tiny"), seed=8).public_nodes()
    pd.testing.assert_frame_equal(a, b)
    assert not a[["lat", "lon"]].equals(c[["lat", "lon"]])


def test_large_preset_is_operator_scale(large):
    t = large
    counts = t.nodes["element_type"].value_counts()
    assert counts["SITE"] == pytest.approx(5000, rel=0.02)
    assert 18_000 < counts["CELL"] < 28_000
    assert counts["AGG_ROUTER"] == 100


@pytest.fixture(scope="module")
def large():
    return build_topology(get_preset("large"), seed=42)


def test_region_catalogue_is_australian():
    assert len(REGIONS) == 10 and len(REGION_BY_CODE) == 10
    for r in REGIONS:
        assert r.timezone in AU_ZONES, r.code
        ZoneInfo(r.timezone)  # valid IANA zone
        assert abs(sum(r.mix) - 1) < 1e-9, r.code
        for lat, lon in [(h.lat, h.lon) for h in r.hubs] + list(r.land):
            assert AU_LAT[0] <= lat <= AU_LAT[1] and AU_LON[0] <= lon <= AU_LON[1], r.code
        assert on_land(r, np.array([h.lat for h in r.hubs]), np.array([h.lon for h in r.hubs])).all(), r.code
    assert {r.timezone for r in REGIONS} == AU_ZONES
    for p in PRESETS.values():
        codes = p.region_codes or [r.code for r in REGIONS[: p.regions]]
        assert len(codes) == p.regions and set(codes) <= set(REGION_BY_CODE)


def test_sites_on_land_inside_their_region(large):
    nodes = large.public_nodes()
    assert nodes["timezone"].notna().all() and set(nodes["timezone"]) == AU_ZONES
    assert nodes["lat"].between(*AU_LAT).all() and nodes["lon"].between(*AU_LON).all()
    sites = nodes[nodes.element_type == "SITE"]
    for rc, g in sites.groupby("region_code"):
        assert on_land(REGION_BY_CODE[rc], g["lat"].to_numpy(), g["lon"].to_numpy()).all(), rc
        assert (g["timezone"] == REGION_BY_CODE[rc].timezone).all()
    # Coastal spot checks: nothing in the Tasman off Sydney, the Indian Ocean off Perth, or Port Phillip.
    syd = sites[(sites.region_code == "NSW") & sites.lat.between(-34.1, -33.7)]
    assert len(syd) and (syd.lon < 151.30).all()
    per = sites[(sites.region_code == "WA") & sites.lat.between(-32.1, -31.8)]
    assert len(per) and (per.lon > 115.73).all()
    bay = sites[(sites.region_code == "VIC") & sites.lat.between(-38.1, -37.9) & sites.lon.between(144.8, 144.95)]
    assert bay.empty


def test_remote_areas_are_sparse_slow_and_long_haul(large):
    nodes = large.nodes
    sites = nodes[nodes.element_type == "SITE"]
    cells = large.cells
    by_urb = cells.groupby("urbanity")
    assert by_urb["coverage_radius_km"].median()["remote"] > 5 * by_urb["coverage_radius_km"].median()["urban"]
    assert by_urb["base_latency_ms"].mean()["remote"] > by_urb["base_latency_ms"].mean()["urban"] + 15
    links = nodes[nodes.element_type == "BACKHAUL_LINK"]
    assert "satellite" in set(links.transport_medium)
    sat_regions = set(links.loc[links.transport_medium == "satellite", "region_code"])
    assert sat_regions & {"PIL", "NT", "NQL"}
    rtr = nodes[nodes.element_type == "AGG_ROUTER"].groupby("region_code")["uplink_km"].median()
    assert rtr["PIL"] > 1000 and rtr["NQL"] > 1000 and rtr["NSW"] < 150

    def nn_km(g):  # median nearest-neighbour site spacing
        d = km_between(g.lat.to_numpy()[:, None], g.lon.to_numpy()[:, None], g.lat.to_numpy()[None], g.lon.to_numpy()[None])
        np.fill_diagonal(d, np.inf)
        return np.median(d.min(axis=1))

    assert nn_km(sites[sites.region_code == "PIL"]) > 5 * nn_km(sites[sites.region_code == "NSW"])
    # Site share follows the weights; Sydney & NSW is the biggest region.
    share = sites.region_code.value_counts(normalize=True)
    assert share.idxmax() == "NSW" and share["PIL"] < 0.03
