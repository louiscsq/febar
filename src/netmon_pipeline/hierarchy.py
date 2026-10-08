"""Topology hierarchy helpers for the root-cause rollup (cell -> site -> backhaul -> router -> UPF -> AMF).

`topology_nodes` carries denormalised ancestor columns, so rolling a cell-level signal up the tree is a
`stack()` of those columns rather than a recursive join. The same mapping is used in Python for tests.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping

# Ancestor column on a CELL row for every level above it, nearest first, with the element type.
ANCESTORS: list[tuple[str, str, int]] = [
    ("site_id", "SITE", 4),
    ("backhaul_id", "BACKHAUL_LINK", 3),
    ("router_id", "AGG_ROUTER", 2),
    ("upf_id", "UPF_SGW", 1),
    ("amf_id", "AMF_MME", 0),
]
LEVEL = {"CELL": 5, **{t: lvl for _c, t, lvl in ANCESTORS}}


def stack_sql(cell_id_col: str = "cell_id") -> str:
    """SQL generator expression: one (element_id, element_type, level) row per ancestor, plus the cell."""
    items = [f"{cell_id_col}, 'CELL', 5"] + [f"{c}, '{t}', {lvl}" for c, t, lvl in ANCESTORS]
    return f"stack({len(items)}, {', '.join(items)}) AS (element_id, element_type, level)"


def ancestors(cell: Mapping[str, str]) -> list[tuple[str, str, int]]:
    """(element_id, element_type, level) for the cell itself and each of its ancestors."""
    return [(cell["element_id"], "CELL", 5)] + [(cell[c], t, lvl) for c, t, lvl in ANCESTORS]


def descendant_cell_counts(cells: Iterable[Mapping[str, str]]) -> Counter:
    """Number of cells below (or equal to) every element."""
    n: Counter = Counter()
    for cell in cells:
        for eid, _t, _lvl in ancestors(cell):
            n[eid] += 1
    return n


def rollup(cells: Iterable[Mapping[str, str]], impacted: set[str]) -> dict[str, dict]:
    """Per element: descendant cells, impacted descendant cells and their fraction, and the number of
    direct children with at least one impacted cell. Python mirror of `gold_element_impact_5m`."""
    cells = list(cells)
    total = descendant_cell_counts(cells)
    hit: Counter = Counter()
    children: dict[str, set[str]] = defaultdict(set)
    hit_children: dict[str, set[str]] = defaultdict(set)
    for cell in cells:
        chain = ancestors(cell)  # nearest first: cell, site, backhaul, router, upf, amf
        for (child, _ct, _cl), (parent, _pt, _pl) in zip(chain, chain[1:], strict=False):
            children[parent].add(child)
            if cell["element_id"] in impacted:
                hit_children[parent].add(child)
        if cell["element_id"] in impacted:
            for eid, _t, _lvl in chain:
                hit[eid] += 1
    return {eid: {"n_desc_cells": n, "n_impacted_cells": hit[eid], "impacted_fraction": hit[eid] / n,
                  "n_children": len(children.get(eid, ())), "n_impacted_children": len(hit_children.get(eid, ()))}
            for eid, n in total.items()}


def lowest_common_ancestor(cells: Iterable[Mapping[str, str]]) -> tuple[str, str] | None:
    """Deepest element whose subtree contains every given cell (a topology-only RCA guess)."""
    cells = list(cells)
    if not cells:
        return None
    chains = [ancestors(c) for c in cells]
    common = set(chains[0])
    for ch in chains[1:]:
        common &= set(ch)
    if not common:
        return None
    eid, etype, _lvl = max(common, key=lambda x: x[2])
    return eid, etype
