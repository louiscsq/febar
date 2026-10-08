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
from functools import cached_property

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
class Hub:
    name: str
    lat: float
    lon: float
    weight: float  # share of the region's urban/suburban/rural sites clustered on this town


@dataclass(frozen=True)
class Region:
    code: str
    name: str
    state: str
    timezone: str  # IANA zone; KPI/session seasonality and busy-hour fault windows follow local time
    population_m: float  # residents (millions); drives the regional subscriber share
    weight: float  # share of national sites (remote areas carry more sites per head for coverage)
    mix: tuple[float, float, float, float]  # urban, suburban, rural, remote share of sites
    city_km: float  # spread of urban sites around each hub (suburban = 2.5x)
    rural_km: float  # spread of rural sites around each hub; remote sites scatter across the polygon
    ran_vendor: str
    hubs: tuple[Hub, ...]  # population centres, first = region centre
    land: tuple[tuple[float, float], ...]  # service-area polygon (lat, lon), drawn inside the coastline
    water: tuple[tuple[tuple[float, float], ...], ...] = ()  # bays inside `land` where no site may sit
    core: tuple[float, float] | None = None  # core data-centre location if not in the region (long-haul)
    tropical: bool = False  # tropical north: cyclone / monsoon flood exposure

    @property
    def lat(self) -> float:
        return self.hubs[0].lat

    @property
    def lon(self) -> float:
        return self.hubs[0].lon

    @property
    def core_latlon(self) -> tuple[float, float]:
        return self.core or (self.lat, self.lon)


PERTH = (-31.9505, 115.8605)
BRISBANE = (-27.4698, 153.0251)
MELBOURNE = (-37.8136, 144.9631)

# Fictional operator footprint ("Banksia Mobile") over real Australian geography. Vendors are fictional;
# each region is single-vendor RAN, as is typical for large operators that split the country between
# suppliers. Polygons are coarse service areas kept just inside the coastline so no site lands at sea.
REGIONS = [
    Region("NSW", "Sydney & NSW", "NSW", "Australia/Sydney", 8.4, 0.29, (0.45, 0.30, 0.20, 0.05), 14, 70, "Arcturus",
           (Hub("Sydney", -33.8688, 151.2093, 0.75), Hub("Newcastle", -32.93, 151.70, 0.12),
            Hub("Wollongong", -34.42, 150.86, 0.08), Hub("Bathurst", -33.4193, 149.5775, 0.05)),
           ((-32.60, 151.60), (-32.95, 151.72), (-33.40, 151.40), (-33.62, 151.28), (-33.80, 151.26),
            (-33.90, 151.25), (-34.05, 151.12), (-34.40, 150.87), (-34.80, 150.70), (-34.80, 149.70),
            (-33.30, 149.50), (-32.60, 150.30))),
    Region("VIC", "Melbourne & Victoria", "VIC", "Australia/Melbourne", 6.9, 0.24, (0.45, 0.30, 0.20, 0.05), 13, 60,
           "Borealis",
           (Hub("Melbourne", -37.8136, 144.9631, 0.80), Hub("Geelong", -38.1499, 144.3617, 0.10),
            Hub("Ballarat", -37.5622, 143.8503, 0.05), Hub("Bendigo", -36.7570, 144.2794, 0.05)),
           ((-36.45, 143.90), (-36.45, 145.70), (-37.00, 146.30), (-37.90, 146.60), (-38.30, 146.40),
            (-38.62, 145.80), (-38.52, 145.45), (-38.46, 145.05), (-38.38, 144.80), (-38.30, 144.60),
            (-38.30, 144.35), (-38.40, 144.15), (-38.35, 143.60), (-37.60, 143.40)),
           water=(((-37.86, 144.84), (-37.87, 144.98), (-38.00, 145.06), (-38.14, 145.10), (-38.28, 145.00),
                   (-38.35, 144.88), (-38.33, 144.72), (-38.27, 144.66), (-38.12, 144.63), (-38.10, 144.42),
                   (-37.98, 144.66), (-37.89, 144.78)),  # Port Phillip
                  ((-38.22, 145.20), (-38.28, 145.55), (-38.45, 145.50), (-38.42, 145.15)))),  # Western Port
    Region("QLD", "Brisbane & South East QLD", "QLD", "Australia/Brisbane", 4.0, 0.16, (0.45, 0.32, 0.20, 0.03), 12,
           50, "Arcturus",
           (Hub("Brisbane", *BRISBANE, 0.70), Hub("Gold Coast", -28.0167, 153.38, 0.17),
            Hub("Sunshine Coast", -26.65, 153.05, 0.08), Hub("Toowoomba", -27.5598, 151.9507, 0.05)),
           ((-26.30, 152.60), (-26.40, 153.05), (-26.80, 153.10), (-27.10, 153.05), (-27.30, 153.06),
            (-27.42, 153.12), (-27.60, 153.24), (-27.85, 153.36), (-28.17, 153.50), (-28.35, 153.30),
            (-28.35, 151.90), (-27.50, 151.70), (-26.50, 151.90))),
    Region("WA", "Perth & South West WA", "WA", "Australia/Perth", 2.3, 0.09, (0.50, 0.30, 0.17, 0.03), 12, 50,
           "Borealis",
           (Hub("Perth", *PERTH, 0.85), Hub("Mandurah", -32.53, 115.78, 0.10), Hub("Northam", -31.65, 116.67, 0.05)),
           ((-31.30, 115.60), (-31.80, 115.78), (-32.05, 115.78), (-32.30, 115.78), (-32.55, 115.75),
            (-33.30, 115.70), (-33.40, 116.20), (-32.00, 117.00), (-31.30, 116.60))),
    Region("SA", "Adelaide & SA", "SA", "Australia/Adelaide", 1.5, 0.065, (0.45, 0.30, 0.20, 0.05), 9, 45, "Arcturus",
           (Hub("Adelaide", -34.9285, 138.6007, 0.90), Hub("Murray Bridge", -35.12, 139.27, 0.05),
            Hub("Victor Harbor", -35.50, 138.65, 0.05)),
           ((-33.80, 138.60), (-34.10, 138.25), (-34.60, 138.48), (-34.85, 138.54), (-35.15, 138.52),
            (-35.40, 138.47), (-35.55, 138.70), (-35.40, 139.40), (-34.30, 139.30))),
    Region("TAS", "Tasmania", "TAS", "Australia/Hobart", 0.58, 0.03, (0.25, 0.30, 0.35, 0.10), 6, 60, "Borealis",
           (Hub("Hobart", -42.8821, 147.3272, 0.55), Hub("Launceston", -41.4332, 147.1441, 0.35),
            Hub("Devonport", -41.28, 146.35, 0.10)),
           ((-41.15, 145.90), (-41.25, 146.40), (-41.15, 146.85), (-41.05, 147.70), (-41.10, 148.20),
            (-41.40, 148.20), (-41.90, 148.20), (-42.20, 147.95), (-42.60, 147.80), (-42.82, 147.45),
            (-43.00, 147.30), (-43.15, 147.00), (-42.70, 146.60), (-42.10, 145.50), (-41.40, 145.50)),
           core=MELBOURNE),  # cores in Melbourne, reached over Bass Strait submarine fibre
    Region("ACT", "Canberra", "ACT", "Australia/Sydney", 0.47, 0.02, (0.60, 0.30, 0.10, 0.0), 7, 20, "Arcturus",
           (Hub("Canberra", -35.2809, 149.1300, 1.0),),
           ((-35.12, 148.95), (-35.12, 149.25), (-35.35, 149.40), (-35.60, 149.20), (-35.92, 149.05),
            (-35.60, 148.80), (-35.30, 148.80))),
    Region("NT", "Darwin & Top End", "NT", "Australia/Darwin", 0.25, 0.015, (0.30, 0.20, 0.20, 0.30), 6, 60,
           "Borealis",
           (Hub("Darwin", -12.42, 130.88, 0.60), Hub("Palmerston", -12.48, 130.98, 0.25),
            Hub("Katherine", -14.4652, 132.2635, 0.15)),
           ((-12.40, 130.84), (-12.36, 130.90), (-12.40, 131.10), (-12.30, 131.40), (-12.60, 132.50),
            (-14.50, 132.60), (-14.60, 131.00), (-13.20, 130.50), (-12.62, 130.75), (-12.47, 130.82)),
           tropical=True),
    Region("NQL", "North Queensland", "QLD", "Australia/Brisbane", 0.75, 0.05, (0.30, 0.25, 0.30, 0.15), 8, 80,
           "Arcturus",
           (Hub("Townsville", -19.30, 146.75, 0.45), Hub("Cairns", -16.93, 145.74, 0.35),
            Hub("Mackay", -21.17, 149.05, 0.20)),
           ((-16.40, 145.40), (-16.90, 145.76), (-17.50, 145.98), (-18.30, 145.98), (-18.70, 146.20),
            (-19.20, 146.80), (-19.45, 147.20), (-19.95, 148.10), (-20.40, 148.55), (-21.10, 149.15),
            (-21.60, 148.60), (-21.00, 144.00), (-19.00, 143.50), (-17.00, 144.50)),
           core=BRISBANE, tropical=True),  # cores in Brisbane, ~1,100-1,400 km of long-haul fibre away
    Region("PIL", "Pilbara (Regional WA)", "WA", "Australia/Perth", 0.06, 0.02, (0.15, 0.10, 0.25, 0.50), 5, 60,
           "Borealis",
           (Hub("Karratha", -20.76, 116.85, 0.40), Hub("South Hedland", -20.40, 118.62, 0.35),
            Hub("Newman", -23.3594, 119.7319, 0.15), Hub("Tom Price", -22.69, 117.79, 0.10)),
           ((-21.70, 115.20), (-20.75, 116.65), (-20.72, 116.90), (-20.80, 117.20), (-20.40, 118.40),
            (-20.35, 118.70), (-20.10, 119.50), (-23.80, 120.50), (-23.80, 116.50), (-22.30, 115.20)),
           core=PERTH, tropical=True),  # cores in Perth, ~1,300-1,600 km south
]
REGION_BY_CODE = {r.code: r for r in REGIONS}
CORE_VENDOR = "Eridani Core"
TRANSPORT_VENDOR = "Cygnus Networks"

URBANITY = np.array(["urban", "suburban", "rural", "remote"])
P_5G = {"urban": 0.8, "suburban": 0.5, "rural": 0.15, "remote": 0.05}
# Per-cell radio/transport characteristics by (technology, urbanity).
CAPACITY_USERS = {("4G", "urban"): 300, ("4G", "suburban"): 220, ("4G", "rural"): 150, ("4G", "remote"): 120,
                  ("5G", "urban"): 450, ("5G", "suburban"): 330, ("5G", "rural"): 220, ("5G", "remote"): 180}
PEAK_DL_MBPS = {"4G": 90.0, "5G": 480.0}
BASE_LATENCY_MS = {"4G": 28.0, "5G": 12.0}
BASE_LOAD = {"urban": 0.65, "suburban": 0.52, "rural": 0.38, "remote": 0.30}
URB_LATENCY_MS = {"urban": 0.0, "suburban": 3.0, "rural": 8.0, "remote": 14.0}
URB_RRC_PENALTY = {"urban": 0.0, "suburban": 0.1, "rural": 0.35, "remote": 0.5}
URB_DROP_PENALTY = {"urban": 0.0, "suburban": 0.1, "rural": 0.35, "remote": 0.5}
COVERAGE_KM = {"urban": (0.4, 1.5), "suburban": (1.5, 4.0), "rural": (5.0, 15.0), "remote": (15.0, 40.0)}
# Backhaul medium mix by the most rural site on the link: fibre, microwave, satellite.
MEDIUM_P = {"urban": (0.85, 0.15, 0.0), "suburban": (0.60, 0.40, 0.0), "rural": (0.27, 0.70, 0.03),
            "remote": (0.15, 0.50, 0.35)}
MEDIA = np.array(["fibre", "microwave", "satellite"])
SATELLITE_LATENCY_MS = (35.0, 55.0)  # LEO satellite backhaul round-trip penalty
SATELLITE_PEAK_FACTOR = 0.4  # satellite backhaul caps cell throughput
FIBRE_RTT_MS_PER_KM = 0.015  # 2 x route factor 1.5 / (200 km per ms in glass)
LONG_HAUL_KM = 250.0  # router uplinks longer than this are long-haul fibre (single point of failure)


def km_between(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Equirectangular distance in km (accurate to well under 1 % at regional scale)."""
    lat1, lon1, lat2, lon2 = (np.asarray(x, dtype=float) for x in (lat1, lon1, lat2, lon2))
    x = np.radians(lon2 - lon1) * np.cos(np.radians((lat1 + lat2) / 2))
    y = np.radians(lat2 - lat1)
    return 6371.0 * np.hypot(x, y)


def in_polygon(lat: np.ndarray, lon: np.ndarray, poly) -> np.ndarray:
    """Vectorised even-odd ray casting; `poly` is a sequence of (lat, lon) vertices."""
    py, px = np.array(poly, dtype=float).T
    inside = np.zeros(len(lat), dtype=bool)
    j = len(px) - 1
    for i in range(len(px)):
        cross = (py[i] > lat) != (py[j] > lat)
        with np.errstate(divide="ignore", invalid="ignore"):
            x_at = (px[j] - px[i]) * (lat - py[i]) / (py[j] - py[i]) + px[i]
        inside ^= cross & (lon < x_at)
        j = i
    return inside


def on_land(region: Region, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    ok = in_polygon(lat, lon, region.land)
    for w in region.water:
        ok &= ~in_polygon(lat, lon, w)
    return ok


def select_regions(scale: ScalePreset) -> list[Region]:
    if scale.region_codes:
        return [REGION_BY_CODE[c] for c in scale.region_codes]
    return REGIONS[: scale.regions]


def _place_sites(rng, region: Region, urb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Site coordinates: urban/suburban/rural scatter around a hub town, remote sites anywhere in the
    service area. Points off the polygon (sea, bays, outside the region) are redrawn."""
    n = len(urb)
    hub_w = np.array([h.weight for h in region.hubs])
    hub = rng.choice(len(region.hubs), size=n, p=hub_w / hub_w.sum())
    hlat = np.array([h.lat for h in region.hubs])[hub]
    hlon = np.array([h.lon for h in region.hubs])[hub]
    sigma = np.array([region.city_km, 2.5 * region.city_km, region.rural_km, 0.0])[urb]
    py, px = np.array(region.land).T
    lat, lon = hlat.copy(), hlon.copy()
    todo = np.arange(n)
    for _ in range(100):
        if not len(todo):
            break
        k = len(todo)
        remote = urb[todo] == 3
        dlat = rng.normal(0, 1, k) * sigma[todo] / 111.0
        dlon = rng.normal(0, 1, k) * sigma[todo] / (111.0 * np.cos(np.radians(hlat[todo])))
        lat[todo] = np.where(remote, rng.uniform(py.min(), py.max(), k), hlat[todo] + dlat)
        lon[todo] = np.where(remote, rng.uniform(px.min(), px.max(), k), hlon[todo] + dlon)
        todo = todo[~on_land(region, lat[todo], lon[todo])]
    lat[todo], lon[todo] = hlat[todo], hlon[todo]  # (practically unreachable) fall back to the hub itself
    return lat, lon


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
        cols = ["element_id", "element_type", "name", "parent_id", "level", "region_code", "region", "state",
                "timezone", "lat", "lon", "vendor", "technology", "urbanity", "transport_medium", "uplink_km",
                "sector", "capacity_users", "coverage_radius_km", "amf_id", "upf_id", "router_id", "backhaul_id",
                "site_id"]
        return self.nodes.reset_index()[cols]

    @cached_property
    def timezones(self) -> list[str]:
        return sorted(set(self.cells["timezone"]))

    @cached_property
    def cell_tz_idx(self) -> np.ndarray:
        """Per cell, index into `timezones`."""
        return pd.Index(self.timezones).get_indexer(self.cells["timezone"])


def _jitter_km(rng, lat, lon, sigma_km, n):
    dlat = rng.normal(0, sigma_km, n) / 111.0
    dlon = rng.normal(0, sigma_km, n) / (111.0 * np.cos(np.radians(lat)))
    return lat + dlat, lon + dlon


def build_topology(scale: ScalePreset, seed: int) -> Topology:
    rng = rng_for(seed, "topology")
    regions = select_regions(scale)
    weights = np.array([r.weight for r in regions])
    site_counts = np.maximum(scale.routers_per_region, np.round(scale.sites * weights / weights.sum()).astype(int))

    rows: list[dict] = []

    def add(**kw):
        base = dict(parent_id=None, technology=None, urbanity=None, transport_medium=None, uplink_km=np.nan,
                    sector=None, capacity_users=None, coverage_radius_km=np.nan, amf_id=None, upf_id=None,
                    router_id=None, backhaul_id=None, site_id=None, base_load=np.nan, peak_dl_mbps=np.nan,
                    base_latency_ms=np.nan, rrc_base_pct=np.nan, drop_base_pct=np.nan)
        base.update(kw)
        base["level"] = LEVEL_OF[base["element_type"]]
        base[ANCESTOR_COL[base["element_type"]]] = base["element_id"]
        rows.append(base)

    for region, n_sites in zip(regions, site_counts, strict=True):
        rc = region.code
        common = dict(region_code=rc, region=region.name, state=region.state, timezone=region.timezone)
        clat, clon = region.core_latlon
        amf = f"AMF-{rc}-01"
        add(element_id=amf, element_type="AMF_MME", name=f"{region.name} AMF/MME 1",
            lat=clat, lon=clon, vendor=CORE_VENDOR, technology="4G/5G", **common)
        upfs = []
        for u in range(scale.upf_per_region):
            upf = f"UPF-{rc}-{u + 1:02d}"
            ulat, ulon = _jitter_km(rng, clat, clon, 3, 1)
            add(element_id=upf, element_type="UPF_SGW", name=f"{region.name} UPF/SGW {u + 1}",
                parent_id=amf, lat=float(ulat[0]), lon=float(ulon[0]), vendor=CORE_VENDOR,
                technology="4G/5G", amf_id=amf, **common)
            upfs.append(upf)

        urb = rng.choice(4, size=n_sites, p=np.array(region.mix) / sum(region.mix))
        slat, slon = _place_sites(rng, region, urb)

        # Routers sit at distinct site locations, preferring the most urban sites (exchanges are in towns);
        # each site homes onto its nearest router, so every router has at least its own site.
        n_rtr = min(scale.routers_per_region, n_sites)
        prio = rng.random(n_sites) + (3 - urb) * 0.5
        hubs = np.argsort(-prio, kind="stable")[:n_rtr]
        d2 = (slat[:, None] - slat[hubs][None, :]) ** 2 + (
            (slon[:, None] - slon[hubs][None, :]) * np.cos(np.radians(region.lat))) ** 2
        home = d2.argmin(axis=1)
        home[hubs] = np.arange(n_rtr)

        site_seq = 0
        bh_seq = 0
        for r in range(n_rtr):
            rtr = f"AGG-{rc}-{r + 1:02d}"
            upf = upfs[r % len(upfs)]
            rlat, rlon = float(slat[hubs[r]]), float(slon[hubs[r]])
            uplink = float(km_between(rlat, rlon, clat, clon)) * 1.3 + 5  # route factor + core-side tail
            add(element_id=rtr, element_type="AGG_ROUTER", name=f"{region.name} agg router {r + 1}",
                parent_id=upf, lat=rlat, lon=rlon, vendor=TRANSPORT_VENDOR, uplink_km=round(uplink, 1),
                transport_medium="fibre", amf_id=amf, upf_id=upf, **common)
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
                medium = str(MEDIA[rng.choice(3, p=MEDIUM_P[g_urb])])
                blat, blon = float(slat[group].mean()), float(slon[group].mean())
                bh_km = float(km_between(blat, blon, rlat, rlon)) * 1.3
                add(element_id=bh, element_type="BACKHAUL_LINK", name=f"{medium} backhaul {bh}",
                    parent_id=rtr, lat=blat, lon=blon, vendor=TRANSPORT_VENDOR, transport_medium=medium,
                    uplink_km=round(bh_km, 1), amf_id=amf, upf_id=upf, router_id=rtr, **common)
                for s in group:
                    site_seq += 1
                    site = f"SITE-{rc}-{site_seq:05d}"
                    u_name = URBANITY[urb[s]]
                    techs = ["4G", "5G"] if rng.random() < P_5G[u_name] else ["4G"]
                    anc = dict(amf_id=amf, upf_id=upf, router_id=rtr, backhaul_id=bh)
                    # Transport latency: fibre distance site -> router -> core, plus satellite hop if any.
                    path_km = float(km_between(slat[s], slon[s], rlat, rlon)) * 1.3 + uplink
                    transport_ms = path_km * FIBRE_RTT_MS_PER_KM + (
                        rng.uniform(*SATELLITE_LATENCY_MS) if medium == "satellite" else 0.0)
                    peak_factor = SATELLITE_PEAK_FACTOR if medium == "satellite" else 1.0
                    add(element_id=site, element_type="SITE", name=f"{region.name} site {site_seq}",
                        parent_id=bh, lat=float(slat[s]), lon=float(slon[s]), vendor=region.ran_vendor,
                        technology="/".join(techs), urbanity=u_name, **anc, **common)
                    site_load = BASE_LOAD[u_name] * rng.lognormal(0, 0.25)
                    cov = rng.uniform(*COVERAGE_KM[u_name])
                    for tech in techs:
                        for sector in (1, 2, 3):
                            cid = f"CELL-{rc}-{site_seq:05d}-{tech}{sector}"
                            add(element_id=cid, element_type="CELL",
                                name=f"{site} {tech} sector {sector}", parent_id=site,
                                lat=float(slat[s]), lon=float(slon[s]), vendor=region.ran_vendor,
                                technology=tech, urbanity=u_name, sector=sector,
                                capacity_users=CAPACITY_USERS[(tech, u_name)], site_id=site, **anc, **common,
                                coverage_radius_km=round(cov * (0.6 if tech == "5G" else 1.0), 2),
                                base_load=site_load * rng.lognormal(0, 0.12) * (0.85 if tech == "5G" else 1.0),
                                peak_dl_mbps=PEAK_DL_MBPS[tech] * peak_factor * rng.uniform(0.8, 1.15),
                                base_latency_ms=BASE_LATENCY_MS[tech] + URB_LATENCY_MS[u_name] + transport_ms
                                + rng.normal(0, 1.5),
                                rrc_base_pct=99.7 - (0.15 if region.ran_vendor == "Borealis" else 0.0)
                                - URB_RRC_PENALTY[u_name] - abs(rng.normal(0, 0.1)),
                                drop_base_pct=0.25 + URB_DROP_PENALTY[u_name] + abs(rng.normal(0, 0.08)))

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
