"""Hierarchical mobile-network topology.

    AMF_MME (control-plane core, one per region)            level 0
      └─ UPF_SGW (user-plane core)                          level 1
           └─ AGG_ROUTER (aggregation / pre-aggregation)    level 2
                └─ BACKHAUL_LINK (fibre or microwave hop)   level 3
                     └─ SITE (gNB/eNB base station)         level 4
                          └─ CELL (4G or 5G sector carrier) level 5

Every non-root node has exactly one parent, so the graph is a forest (one tree per region) and the
set of cells that depend on any element is simply "cells whose <level>_id equals that element".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from netmon_datagen.config import ScalePreset, rng_for

LEVELS = ["AMF_MME", "UPF_SGW", "AGG_ROUTER", "BACKHAUL_LINK", "SITE", "CELL"]
LEVEL_OF = {t: i for i, t in enumerate(LEVELS)}
# Column on the nodes table holding the ancestor id at each level.
ANCESTOR_COL = {
    "AMF_MME": "amf_id", "UPF_SGW": "upf_id", "AGG_ROUTER": "router_id",
    "BACKHAUL_LINK": "backhaul_id", "SITE": "site_id", "CELL": "cell_id",
}
EDGE_TYPE = {
    "UPF_SGW": "control_plane", "AGG_ROUTER": "user_plane", "BACKHAUL_LINK": "transport",
    "SITE": "backhaul", "CELL": "hosts",
}


@dataclass(frozen=True)
class Region:
    code: str
    name: str
    lat: float
    lon: float
    weight: float  # share of national sites
    urban: float  # share of urban sites (rest split suburban/rural below)
    rural: float
    radius_km: float
    ran_vendor: str


# Synthetic operator footprint over real UK geography. Vendors are fictional; each region is
# single-vendor RAN, as is typical for large operators that split the country between suppliers.
REGIONS = [
    Region("LON", "London", 51.5074, -0.1278, 0.20, 0.65, 0.05, 30, "Arcturus"),
    Region("MAN", "North West", 53.4808, -2.2426, 0.12, 0.35, 0.25, 50, "Borealis"),
    Region("BHM", "Midlands", 52.4862, -1.8904, 0.13, 0.35, 0.25, 55, "Arcturus"),
    Region("GLA", "Scotland", 55.8642, -4.2518, 0.10, 0.25, 0.40, 120, "Borealis"),
    Region("LDS", "Yorkshire", 53.8008, -1.5491, 0.09, 0.30, 0.30, 55, "Borealis"),
    Region("BRS", "South West", 51.4545, -2.5879, 0.09, 0.25, 0.40, 90, "Arcturus"),
    Region("NRW", "East of England", 52.6309, 1.2974, 0.08, 0.20, 0.45, 80, "Arcturus"),
    Region("CDF", "Wales", 51.4816, -3.1791, 0.06, 0.25, 0.45, 80, "Borealis"),
    Region("NCL", "North East", 54.9783, -1.6178, 0.05, 0.35, 0.30, 50, "Borealis"),
    Region("BFS", "Northern Ireland", 54.5973, -5.9301, 0.04, 0.30, 0.40, 70, "Arcturus"),
]
CORE_VENDOR = "Eridani Core"
TRANSPORT_VENDOR = "Cygnus Networks"

URBANITY = np.array(["urban", "suburban", "rural"])
P_5G = {"urban": 0.8, "suburban": 0.5, "rural": 0.15}
# Per-cell radio/transport characteristics by (technology, urbanity).
CAPACITY_USERS = {("4G", "urban"): 300, ("4G", "suburban"): 220, ("4G", "rural"): 150,
                  ("5G", "urban"): 450, ("5G", "suburban"): 330, ("5G", "rural"): 220}
PEAK_DL_MBPS = {"4G": 90.0, "5G": 480.0}
BASE_LATENCY_MS = {"4G": 28.0, "5G": 12.0}
BASE_LOAD = {"urban": 0.65, "suburban": 0.52, "rural": 0.38}


@dataclass
class Topology:
    nodes: pd.DataFrame  # one row per element (all levels)
    edges: pd.DataFrame  # parent_id -> child_id
    cells: pd.DataFrame  # CELL rows only, positional index == cell index used in KPI arrays

    @property
    def n_cells(self) -> int:
        return len(self.cells)

    def element(self, element_id: str) -> pd.Series:
        return self.nodes.loc[element_id]

    def cell_indices_under(self, element_id: str) -> np.ndarray:
        etype = self.nodes.at[element_id, "element_type"]
        col = ANCESTOR_COL[etype]
        return np.flatnonzero(self.cells[col].to_numpy() == element_id)

    def descendants(self, element_id: str) -> pd.DataFrame:
        """All elements strictly below `element_id`."""
        etype = self.nodes.at[element_id, "element_type"]
        col = ANCESTOR_COL[etype]
        mask = (self.nodes[col] == element_id) & (self.nodes.index != element_id)
        return self.nodes[mask]

    def ids_of_type(self, etype: str) -> np.ndarray:
        return self.nodes.index[self.nodes["element_type"] == etype].to_numpy()

    def public_nodes(self) -> pd.DataFrame:
        cols = ["element_id", "element_type", "name", "parent_id", "level", "region_code", "region",
                "lat", "lon", "vendor", "technology", "urbanity", "transport_medium", "sector",
                "capacity_users", "amf_id", "upf_id", "router_id", "backhaul_id", "site_id"]
        return self.nodes.reset_index()[cols]


def _jitter_km(rng, lat, lon, sigma_km, n):
    dlat = rng.normal(0, sigma_km, n) / 111.0
    dlon = rng.normal(0, sigma_km, n) / (111.0 * np.cos(np.radians(lat)))
    return lat + dlat, lon + dlon


def build_topology(scale: ScalePreset, seed: int) -> Topology:
    rng = rng_for(seed, "topology")
    regions = REGIONS[: scale.regions]
    weights = np.array([r.weight for r in regions])
    site_counts = np.maximum(scale.routers_per_region, np.round(scale.sites * weights / weights.sum()).astype(int))

    rows: list[dict] = []

    def add(**kw):
        base = dict(parent_id=None, technology=None, urbanity=None, transport_medium=None, sector=None,
                    capacity_users=None, amf_id=None, upf_id=None, router_id=None, backhaul_id=None,
                    site_id=None, base_load=np.nan, peak_dl_mbps=np.nan, base_latency_ms=np.nan,
                    rrc_base_pct=np.nan, drop_base_pct=np.nan)
        base.update(kw)
        base["level"] = LEVEL_OF[base["element_type"]]
        base[ANCESTOR_COL[base["element_type"]]] = base["element_id"]
        rows.append(base)

    for region, n_sites in zip(regions, site_counts, strict=True):
        rc = region.code
        common = dict(region_code=rc, region=region.name)
        amf = f"AMF-{rc}-01"
        add(element_id=amf, element_type="AMF_MME", name=f"{region.name} AMF/MME 1",
            lat=region.lat, lon=region.lon, vendor=CORE_VENDOR, technology="4G/5G", **common)
        upfs = []
        for u in range(scale.upf_per_region):
            upf = f"UPF-{rc}-{u + 1:02d}"
            ulat, ulon = _jitter_km(rng, region.lat, region.lon, 5, 1)
            add(element_id=upf, element_type="UPF_SGW", name=f"{region.name} UPF/SGW {u + 1}",
                parent_id=amf, lat=float(ulat[0]), lon=float(ulon[0]), vendor=CORE_VENDOR,
                technology="4G/5G", amf_id=amf, **common)
            upfs.append(upf)

        # Site geography: urban sites clustered around the city centre, rural ones spread wide.
        urb = rng.choice(3, size=n_sites, p=[region.urban, 1 - region.urban - region.rural, region.rural])
        sigma = np.array([0.12, 0.35, 0.7])[urb] * region.radius_km
        slat = region.lat + rng.normal(0, 1, n_sites) * sigma / 111.0
        slon = region.lon + rng.normal(0, 1, n_sites) * sigma / (111.0 * np.cos(np.radians(region.lat)))

        # Routers sit at distinct site locations; each site homes onto its nearest router, so every
        # router has at least its own site and nothing is orphaned.
        n_rtr = min(scale.routers_per_region, n_sites)
        hubs = rng.choice(n_sites, size=n_rtr, replace=False)
        d2 = (slat[:, None] - slat[hubs][None, :]) ** 2 + (
            (slon[:, None] - slon[hubs][None, :]) * np.cos(np.radians(region.lat))) ** 2
        home = d2.argmin(axis=1)
        home[hubs] = np.arange(n_rtr)

        site_seq = 0
        bh_seq = 0
        for r in range(n_rtr):
            rtr = f"AGG-{rc}-{r + 1:02d}"
            upf = upfs[r % len(upfs)]
            add(element_id=rtr, element_type="AGG_ROUTER", name=f"{region.name} agg router {r + 1}",
                parent_id=upf, lat=float(slat[hubs[r]]), lon=float(slon[hubs[r]]), vendor=TRANSPORT_VENDOR,
                amf_id=amf, upf_id=upf, **common)
            members = np.flatnonzero(home == r)
            # Chain sites into backhaul groups by bearing from the router (ring / microwave-chain style).
            ang = np.arctan2(slat[members] - slat[hubs[r]], slon[members] - slon[hubs[r]])
            members = members[np.argsort(ang)]
            i = 0
            while i < len(members):
                size = int(min(len(members) - i, rng.geometric(1.0 / scale.sites_per_backhaul), 5))
                group = members[i: i + size]
                i += size
                bh_seq += 1
                bh = f"BH-{rc}-{bh_seq:04d}"
                g_urb = URBANITY[urb[group].max()]  # most rural member decides the medium
                p_mw = {"urban": 0.15, "suburban": 0.4, "rural": 0.7}[g_urb]
                medium = "microwave" if rng.random() < p_mw else "fibre"
                add(element_id=bh, element_type="BACKHAUL_LINK", name=f"{medium} backhaul {bh}",
                    parent_id=rtr, lat=float(slat[group].mean()), lon=float(slon[group].mean()),
                    vendor=TRANSPORT_VENDOR, transport_medium=medium, amf_id=amf, upf_id=upf,
                    router_id=rtr, **common)
                for s in group:
                    site_seq += 1
                    site = f"SITE-{rc}-{site_seq:05d}"
                    u_name = URBANITY[urb[s]]
                    techs = ["4G", "5G"] if rng.random() < P_5G[u_name] else ["4G"]
                    anc = dict(amf_id=amf, upf_id=upf, router_id=rtr, backhaul_id=bh)
                    add(element_id=site, element_type="SITE", name=f"{region.name} site {site_seq}",
                        parent_id=bh, lat=float(slat[s]), lon=float(slon[s]), vendor=region.ran_vendor,
                        technology="/".join(techs), urbanity=u_name, **anc, **common)
                    site_load = BASE_LOAD[u_name] * rng.lognormal(0, 0.25)
                    for tech in techs:
                        for sector in (1, 2, 3):
                            cid = f"CELL-{rc}-{site_seq:05d}-{tech}{sector}"
                            add(element_id=cid, element_type="CELL",
                                name=f"{site} {tech} sector {sector}", parent_id=site,
                                lat=float(slat[s]), lon=float(slon[s]), vendor=region.ran_vendor,
                                technology=tech, urbanity=u_name, sector=sector,
                                capacity_users=CAPACITY_USERS[(tech, u_name)], site_id=site, **anc, **common,
                                base_load=site_load * rng.lognormal(0, 0.12) * (0.85 if tech == "5G" else 1.0),
                                peak_dl_mbps=PEAK_DL_MBPS[tech] * rng.uniform(0.8, 1.15),
                                base_latency_ms=BASE_LATENCY_MS[tech] + {"urban": 0, "suburban": 3, "rural": 8}[u_name]
                                + rng.normal(0, 1.5),
                                rrc_base_pct=99.7 - (0.15 if region.ran_vendor == "Borealis" else 0.0)
                                - {"urban": 0.0, "suburban": 0.1, "rural": 0.35}[u_name] - abs(rng.normal(0, 0.1)),
                                drop_base_pct=0.25 + {"urban": 0.0, "suburban": 0.1, "rural": 0.35}[u_name]
                                + abs(rng.normal(0, 0.08)))

    nodes = pd.DataFrame(rows).set_index("element_id", drop=False)
    nodes.index.name = None
    nodes["capacity_users"] = nodes["capacity_users"].astype("Int64")
    nodes["sector"] = nodes["sector"].astype("Int64")
    nodes["lat"] = nodes["lat"].round(5)
    nodes["lon"] = nodes["lon"].round(5)
    child = nodes[nodes["parent_id"].notna()]
    edges = pd.DataFrame({
        "parent_id": child["parent_id"].to_numpy(),
        "child_id": child["element_id"].to_numpy(),
        "edge_type": child["element_type"].map(EDGE_TYPE).to_numpy(),
        "parent_type": nodes.loc[child["parent_id"], "element_type"].to_numpy(),
        "child_type": child["element_type"].to_numpy(),
    })
    cells = nodes[nodes["element_type"] == "CELL"].reset_index(drop=True)
    return Topology(nodes=nodes, edges=edges, cells=cells)
