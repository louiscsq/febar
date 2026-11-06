"""Topology building and highlighting for the NOC app (app/noc_app/topology.py)."""

from __future__ import annotations

from app_fakes import status_rows, topology_nodes
from noc_app import topology


def _status():
    return {r["element_id"]: r for r in status_rows()}


SUSPECTS = [{"element_id": "SITE-NSW-00002", "rank": 1, "score": 0.97},
            {"element_id": "BH-NSW-0001", "rank": 2, "score": 0.02},
            {"element_id": "AGG-NSW-01", "rank": 3, "score": 0.01}]


def test_ancestors_chain_core_to_cell():
    inv = topology.Inventory(topology_nodes())
    assert inv.ancestors("CELL-NSW-00002-4G1") == ["AMF-NSW-01", "UPF-NSW-01", "AGG-NSW-01", "BH-NSW-0001",
                                                     "SITE-NSW-00002", "CELL-NSW-00002-4G1"]
    assert inv.roots() == ["AMF-NSW-01"]


def test_incident_focus_pinpoints_suspect_1_and_highlights_path_and_suspects():
    g = topology.incident_focus(topology_nodes(), _status(), SUSPECTS)
    assert g["view"] == "incident" and g["pinpoint"] == "SITE-NSW-00002"
    assert g["path"] == ["AMF-NSW-01", "UPF-NSW-01", "AGG-NSW-01", "BH-NSW-0001", "SITE-NSW-00002"]
    by = {n["id"]: n for n in g["nodes"]}
    assert by["SITE-NSW-00002"]["highlight"] == "pinpoint" and by["SITE-NSW-00002"]["suspect_rank"] == 1
    assert by["BH-NSW-0001"]["highlight"] == "suspect" and by["AGG-NSW-01"]["highlight"] == "suspect"
    assert by["UPF-NSW-01"]["highlight"] == "path" and by["AMF-NSW-01"]["highlight"] == "path"
    # exactly one pinpoint, never on a non-suspect
    assert [n["id"] for n in g["nodes"] if n.get("highlight") == "pinpoint"] == ["SITE-NSW-00002"]
    # the pinpointed site's dark cells are shown (unhealthy children are never collapsed)
    for c in range(1, 4):
        assert by[f"CELL-NSW-00002-4G{c}"]["state"] == "down"
    assert by["SITE-NSW-00002"]["state"] == "down"


def test_healthy_siblings_are_collapsed_with_a_count():
    g = topology.incident_focus(topology_nodes(n_bh=8), _status(), SUSPECTS, max_ok=2)
    collapsed = {n["parent_id"]: n for n in g["nodes"] if n["kind"] == "collapsed"}
    # AGG-NSW-01 has 8 links: BH-0001 (on the path) + 2 healthy shown + 5 collapsed
    assert collapsed["AGG-NSW-01"]["count"] == 5
    shown_links = [n for n in g["nodes"] if n["kind"] == "element" and n["element_type"] == "BACKHAUL_LINK"]
    assert len(shown_links) == 3
    ids = {n["id"] for n in g["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])


def test_layout_is_a_tidy_tree():
    g = topology.incident_focus(topology_nodes(), _status(), SUSPECTS)
    by = {n["id"]: n for n in g["nodes"]}
    assert all(0.0 <= n["x"] <= 1.0 for n in g["nodes"])
    for e in g["edges"]:
        assert by[e["target"]]["depth"] == by[e["source"]]["depth"] + 1
    kids = [by[e["target"]]["x"] for e in g["edges"] if e["source"] == "BH-NSW-0001"]
    assert min(kids) <= by["BH-NSW-0001"]["x"] <= max(kids)


def test_region_overview_shows_core_routers_and_unhealthy_only():
    g = topology.region_overview(topology_nodes(), _status(), max_ok=1)
    ids = {n["id"] for n in g["nodes"] if n["kind"] == "element"}
    assert {"AMF-NSW-01", "UPF-NSW-01", "AGG-NSW-01", "AGG-NSW-02", "BH-NSW-0001", "SITE-NSW-00002"} <= ids
    assert not any(i.startswith("CELL-") for i in ids)  # cells are counted, not drawn, in the overview
    assert any(n["kind"] == "collapsed" for n in g["nodes"])
    assert all(n.get("highlight") is None for n in g["nodes"])


def test_unknown_suspect_is_reported_not_drawn():
    g = topology.incident_focus(topology_nodes(), _status(),
                                [{"element_id": "SITE-NSW-99999", "rank": 1, "score": 0.9}, *SUSPECTS[1:]])
    assert g["missing_suspects"] == ["SITE-NSW-99999"]
    assert g["pinpoint"] == "BH-NSW-0001"


def test_map_points_roll_cell_state_up_to_the_site_and_flag_suspects():
    status = _status()
    status["CELL-NSW-00003-4G2"] = {**status["CELL-NSW-00003-4G2"], "state": "down"}
    pts = {p["id"]: p for p in topology.map_points(topology_nodes(), status,
                                                     [{"element_id": "CELL-NSW-00004-4G1", "rank": 2}, SUSPECTS[0]])}
    assert not any(i.startswith("CELL-") for i in pts)
    assert pts["SITE-NSW-00003"]["state"] == "down"  # its cell is dark
    assert pts["SITE-NSW-00001"]["state"] == "ok"
    assert pts["SITE-NSW-00002"]["suspect_rank"] == 1
    assert pts["SITE-NSW-00004"]["suspect_rank"] == 2  # a suspected cell shows on its site
