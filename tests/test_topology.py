import pandas as pd
import pytest

from netmon_datagen.config import get_preset
from netmon_datagen.topology import ANCESTOR_COL, LEVEL_OF, LEVELS, build_topology


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
    assert set(cells["urbanity"]) <= {"urban", "suburban", "rural"}
    assert cells["lat"].between(49.5, 61).all() and cells["lon"].between(-8.5, 2.5).all()
    assert topo.nodes["vendor"].notna().all()
    assert topo.nodes["region"].notna().all()
    assert set(topo.nodes["level"]) == set(LEVEL_OF.values())
    assert set(topo.nodes.loc[topo.nodes.element_type == "BACKHAUL_LINK", "transport_medium"]) <= {"fibre", "microwave"}


def test_deterministic_and_seed_sensitive():
    a = build_topology(get_preset("tiny"), seed=7).public_nodes()
    b = build_topology(get_preset("tiny"), seed=7).public_nodes()
    c = build_topology(get_preset("tiny"), seed=8).public_nodes()
    pd.testing.assert_frame_equal(a, b)
    assert not a[["lat", "lon"]].equals(c[["lat", "lon"]])


def test_large_preset_is_operator_scale():
    t = build_topology(get_preset("large"), seed=42)
    counts = t.nodes["element_type"].value_counts()
    assert counts["SITE"] == pytest.approx(5000, rel=0.02)
    assert 18_000 < counts["CELL"] < 28_000
    assert counts["AGG_ROUTER"] == 100
