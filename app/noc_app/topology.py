"""Topology views for the NOC app: pure functions over the inventory and the live element status (tested).

The network is a tree: AMF_MME (core control plane) > UPF_SGW (core user plane) > AGG_ROUTER > BACKHAUL_LINK >
SITE > CELL. Two views:

- `region_overview`: core, routers and every backhaul link / site that is not healthy, with the healthy children of
  each expanded parent collapsed into one "+N ok" node, so a region of ~800 elements fits on one screen.
- `incident_focus`: the path from the core to each of the incident's top-3 suspects, the children of every element on
  that path, and the suspects highlighted (`pinpoint` = suspect 1, the ranker's most likely root cause).

Both return nodes with a tidy-tree layout (`x` in [0, 1], `depth`) so the browser only draws.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

LEVEL = {"AMF_MME": 0, "UPF_SGW": 1, "AGG_ROUTER": 2, "BACKHAUL_LINK": 3, "SITE": 4, "CELL": 5}
STATE_RANK = {"ok": 0, "alarm": 1, "impacted": 2, "degraded": 3, "down": 4}
TYPE_LABEL = {"AMF_MME": "AMF/MME (core)", "UPF_SGW": "UPF/SGW (core)", "AGG_ROUTER": "aggregation router",
              "BACKHAUL_LINK": "backhaul link", "SITE": "cell site", "CELL": "cell"}


def state_of(status: Mapping[str, Mapping], element_id: str) -> str:
    s = (status.get(element_id) or {}).get("state")
    return s if s in STATE_RANK else "ok"


def worst(states: Iterable[str]) -> str:
    return max(states, key=lambda s: STATE_RANK.get(s, 0), default="ok")


class Inventory:
    """Index over topology nodes: parent / children and ancestor chains."""

    def __init__(self, nodes: Iterable[Mapping]):
        self.nodes: dict[str, dict] = {n["element_id"]: dict(n) for n in nodes}
        self.children: dict[str, list[str]] = defaultdict(list)
        for eid, n in sorted(self.nodes.items()):
            p = n.get("parent_id")
            if p and p in self.nodes:
                self.children[p].append(eid)

    def ancestors(self, element_id: str) -> list[str]:
        """Chain from the root down to (and including) element_id."""
        chain, seen, cur = [], set(), element_id
        while cur and cur in self.nodes and cur not in seen:
            chain.append(cur)
            seen.add(cur)
            cur = self.nodes[cur].get("parent_id")
        return chain[::-1]

    def roots(self) -> list[str]:
        return sorted(e for e, n in self.nodes.items() if not n.get("parent_id") or n["parent_id"] not in self.nodes)


def _graph(inv: Inventory, status: Mapping[str, Mapping], keep: set[str], expand: list[str],
           highlight: Mapping[str, str], suspect_info: Mapping[str, Mapping], max_ok: int) -> dict:
    included: set[str] = set()
    for e in keep:
        included.update(inv.ancestors(e))
    summaries: dict[str, dict] = {}
    for p in expand:
        if p not in inv.nodes:
            continue
        healthy = []
        for c in inv.children.get(p, []):
            if c in included or state_of(status, c) != "ok":
                included.add(c)
            else:
                healthy.append(c)
        for c in healthy[:max_ok]:
            included.add(c)
        rest = healthy[max_ok:]
        if rest:
            sid = f"{p}::ok"
            summaries[sid] = {"id": sid, "kind": "collapsed", "parent_id": p, "count": len(rest),
                              "element_type": inv.nodes[rest[0]]["element_type"], "state": "ok",
                              "name": f"+{len(rest)} healthy {TYPE_LABEL.get(inv.nodes[rest[0]]['element_type'], '')}"}

    # children lists restricted to what is shown (+ the collapsed node last)
    kids: dict[str, list[str]] = defaultdict(list)
    for e in sorted(included):
        p = inv.nodes[e].get("parent_id")
        if p in included:
            kids[p].append(e)
    for sid, s in summaries.items():
        kids[s["parent_id"]].append(sid)
    for p in kids:  # unhealthy first, then by id, collapsed last
        kids[p].sort(key=lambda c: (c in summaries, -STATE_RANK.get(state_of(status, c), 0), c))

    # tidy tree layout: leaves in DFS order, parents centred over their children
    xs: dict[str, float] = {}
    depth: dict[str, int] = {}
    leaf = 0

    def place(n: str, d: int) -> float:
        nonlocal leaf
        depth[n] = d
        if not kids.get(n):
            xs[n] = float(leaf)
            leaf += 1
        else:
            cx = [place(c, d + 1) for c in kids[n]]
            xs[n] = (min(cx) + max(cx)) / 2
        return xs[n]

    roots = [e for e in sorted(included) if inv.nodes[e].get("parent_id") not in included]
    for r in roots:
        place(r, 0)
    span = max(leaf - 1, 1)

    out_nodes = []
    for e in sorted(included, key=lambda e: (depth.get(e, 0), xs.get(e, 0))):
        n, st = inv.nodes[e], status.get(e) or {}
        si = suspect_info.get(e, {})
        out_nodes.append({
            "id": e, "kind": "element", "element_type": n["element_type"], "name": n.get("name") or e,
            "parent_id": n.get("parent_id"), "level": LEVEL.get(n["element_type"]), "state": state_of(status, e),
            "rca_score": st.get("rca_score"), "n_impacted_cells": st.get("n_impacted_cells"),
            "n_desc_cells": st.get("n_desc_cells"), "open_incident_id": st.get("open_incident_id"),
            "highlight": highlight.get(e), "suspect_rank": si.get("rank"), "suspect_score": si.get("score"),
            "lat": n.get("lat"), "lon": n.get("lon"), "depth": depth.get(e, 0), "x": round(xs.get(e, 0) / span, 4),
        })
    for sid, s in summaries.items():
        out_nodes.append({**s, "level": LEVEL.get(s["element_type"]), "highlight": None,
                          "depth": depth.get(sid, 0), "x": round(xs.get(sid, 0) / span, 4)})
    edges = [{"source": p, "target": c} for p, cs in sorted(kids.items()) for c in cs]
    return {"nodes": out_nodes, "edges": edges, "max_depth": max(depth.values(), default=0)}


def region_overview(nodes: Iterable[Mapping], status: Mapping[str, Mapping], max_ok: int = 3) -> dict:
    inv = Inventory(nodes)
    core_and_routers = [e for e, n in inv.nodes.items() if LEVEL.get(n["element_type"], 9) <= 2]
    unhealthy = [e for e, n in inv.nodes.items()
                 if n["element_type"] in ("BACKHAUL_LINK", "SITE") and state_of(status, e) != "ok"]
    expand = sorted(core_and_routers) + sorted(e for e in unhealthy if inv.nodes[e]["element_type"] == "BACKHAUL_LINK")
    g = _graph(inv, status, set(core_and_routers) | set(unhealthy), expand, {}, {}, max_ok)
    g["view"] = "region"
    return g


def incident_focus(nodes: Iterable[Mapping], status: Mapping[str, Mapping], suspects: list[Mapping],
                   max_ok: int = 3) -> dict:
    """suspects: [{"element_id", "rank", "score"}] (rank 1 = the ranker's most likely root cause)."""
    inv = Inventory(nodes)
    sus = sorted((s for s in suspects if s.get("element_id") in inv.nodes), key=lambda s: s["rank"])
    pinpoint = sus[0]["element_id"] if sus else None
    path = inv.ancestors(pinpoint) if pinpoint else []
    highlight = {e: "path" for e in path}
    for s in sus:
        highlight[s["element_id"]] = "pinpoint" if s["element_id"] == pinpoint else "suspect"
    chains = {e for s in sus for e in inv.ancestors(s["element_id"])}
    expand = sorted(chains, key=lambda e: (LEVEL.get(inv.nodes[e]["element_type"], 9), e))
    info = {s["element_id"]: {"rank": s["rank"], "score": s.get("score")} for s in sus}
    g = _graph(inv, status, chains, expand, highlight, info, max_ok)
    g.update(view="incident", pinpoint=pinpoint, path=path,
             missing_suspects=[s.get("element_id") for s in suspects if s.get("element_id") not in inv.nodes])
    return g


def map_points(nodes: Iterable[Mapping], status: Mapping[str, Mapping], suspects: list[Mapping] | None = None) -> list[dict]:
    """Geographic points (core, routers, backhaul links, sites; cells share their site's coordinates).

    A site's state is the worst of its own and its cells' states, so a dark cell shows on the map."""
    inv = Inventory(nodes)
    rank = {s["element_id"]: s["rank"] for s in suspects or []}
    cell_parent = {e: n.get("parent_id") for e, n in inv.nodes.items() if n["element_type"] == "CELL"}
    pts = []
    for e, n in sorted(inv.nodes.items()):
        if n["element_type"] == "CELL" or n.get("lat") is None or n.get("lon") is None:
            continue
        st = state_of(status, e)
        if n["element_type"] == "SITE":
            st = worst([st, *(state_of(status, c) for c in inv.children.get(e, []))])
        r = rank.get(e)
        if r is None:  # a suspected cell is shown on its site
            r = min((rank[c] for c, p in cell_parent.items() if p == e and c in rank), default=None)
        pts.append({"id": e, "element_type": n["element_type"], "name": n.get("name") or e, "lat": n["lat"],
                    "lon": n["lon"], "state": st, "suspect_rank": r, "parent_id": n.get("parent_id")})
    return pts
