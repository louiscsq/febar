"""Fault taxonomy, incident scheduling, downstream propagation and ground truth.

An incident has a root element. Its impact propagates to every cell below the root in the topology,
with a per-cell onset delay (hop-dependent), an optional ramp (gradual degradations), a per-cell
severity, and a staggered recovery. `compute_effects` turns active incidents into (time, cell)
effect arrays that the KPI generator applies on top of organic behaviour.

Red herrings (alarm storms, planned maintenance, traffic surges, flapping elements) go through the
same machinery so the ground-truth table describes everything a NOC analyst would see.

Weather-driven Australian faults (bushfire grid outages, cyclone backhaul cuts) hit a *geographic*
cluster of elements that need not share a topology ancestor: they have several roots
(`root_element_ids`) and impact the descendants of each. Their rates are seasonal. Busy-hour and
maintenance start windows are in the root element's local time.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from netmon_datagen.config import FaultConfig
from netmon_datagen.kpis import expected_users, local_clock, to_iso
from netmon_datagen.topology import ANCESTOR_COL, LONG_HAUL_KM, REGION_BY_CODE, Topology, km_between

S = np.timedelta64(1, "s")
MIN = np.timedelta64(60, "s")


@dataclass(frozen=True)
class FaultSpec:
    fault_type: str
    event_class: str  # fault | planned | red_herring
    root_rates: dict[str, float]  # root element type -> incidents per element per day
    duration_min: tuple[float, float]
    hours: tuple[float, float] | None  # allowed start-hour window (root's LOCAL time), None = any time
    coefs: dict[str, float] = field(default_factory=dict)  # effect at full intensity
    silent: bool = False  # affected cells stop reporting KPIs entirely
    description: str = ""
    # (months, in-season multiplier, off-season multiplier) applied to the base rate; None = aseasonal.
    season: tuple[tuple[int, ...], float, float] | None = None
    off_season_description: str = ""


FAULT_SPECS: dict[str, FaultSpec] = {s.fault_type: s for s in [
    FaultSpec("AMF_OVERLOAD", "fault", {"AMF_MME": 0.015}, (15, 60), (17.0, 21.0),
              dict(attach=40, rrc=6, users=0.2),
              description="Control-plane signalling overload: attach/registration failures region-wide"),
    FaultSpec("CORE_CONGESTION", "fault", {"UPF_SGW": 0.01}, (30, 120), (17.0, 21.0),
              dict(thr=0.6, lat=80, loss=3, drop=1.5, rrc=1),
              description="User-plane congestion at busy hour: latency/throughput degrade under the UPF"),
    FaultSpec("AGG_ROUTER_FAILURE", "fault", {"AGG_ROUTER": 0.005}, (15, 120), None,
              dict(avail=0.97, users=0.97, thr=0.98, rrc=90, attach=90, drop=20),
              description="Aggregation router down: every downstream site loses S1/NG transport"),
    FaultSpec("PLANNED_MAINTENANCE", "planned", {"AGG_ROUTER": 0.0025, "SITE": 0.00015}, (10, 45), (0.0, 1.5),
              dict(avail=1, users=1, thr=1, rrc=100, attach=100),
              description="Change-managed night-time outage inside an approved maintenance window"),
    FaultSpec("BACKHAUL_DEGRADATION", "fault", {"BACKHAUL_LINK": 0.001}, (30, 240), None,
              dict(thr=0.65, lat=140, loss=6, drop=3, rrc=4, users=0.1),
              description="Rising BER / microwave fading: latency, loss and drops on chained sites"),
    FaultSpec("SITE_POWER_OUTAGE", "fault", {"SITE": 0.0003}, (60, 360), None,
              dict(avail=1, users=1, thr=1, rrc=100, attach=100), silent=True,
              description="Mains failure; site runs on battery, then goes dark (cells stop reporting)"),
    FaultSpec("TRAFFIC_SURGE", "red_herring", {"SITE": 0.00008}, (120, 240), (17.0, 20.0),
              description="Stadium/concert crowd: organic congestion with no faulty element"),
    FaultSpec("CELL_OUTAGE", "fault", {"CELL": 0.0003}, (20, 180), None,
              dict(avail=1, users=1, thr=1, rrc=100, attach=100),
              description="Single cell out of service (RRU / software fault)"),
    FaultSpec("BUSHFIRE_GRID_OUTAGE", "fault", {"SITE": 2e-5}, (300, 960), None,
              dict(avail=1, users=1, thr=1, rrc=100, attach=100), silent=True,
              description="Bushfire: grid power lost across a cluster of regional sites; batteries hold for "
                          "1-4 h, 5G layers shed first, then sites go dark; staggered, partial restoration",
              season=((12, 1, 2), 3.0, 0.3),
              off_season_description="Severe storm: grid power lost across a cluster of regional sites; "
                                     "batteries hold for 1-4 h, then sites go dark; staggered restoration"),
    FaultSpec("CYCLONE_BACKHAUL_CUT", "fault", {"BACKHAUL_LINK": 4e-4}, (240, 1200), None,
              dict(avail=0.97, users=0.95, thr=0.98, rrc=90, attach=90, drop=20, lat=120, loss=8),
              description="Tropical cyclone: microwave hops misaligned and fibre washed out along the track; "
                          "chained sites lose or degrade backhaul until crews can reach them",
              season=((11, 12, 1, 2, 3, 4), 2.0, 0.2),
              off_season_description="Severe thunderstorm and flash flooding: fibre washouts and microwave "
                                     "rain fade cut backhaul to a cluster of northern sites"),
    FaultSpec("LONG_HAUL_FIBRE_CUT", "fault", {"AGG_ROUTER": 0.003}, (180, 600), None,
              dict(avail=1, users=1, thr=1, rrc=100, attach=100), silent=True,
              description="Long-haul fibre cut (roadworks / washout) isolates a remote aggregation area from "
                          "its capital-city core: every site behind it goes dark to the NOC"),
    FaultSpec("ALARM_STORM", "red_herring", {"AGG_ROUTER": 0.003, "SITE": 0.00014}, (5, 20), None,
              description="Burst of environmental/equipment alarms with no customer impact"),
    # Not scheduled per window: a fixed set of chronically noisy elements (see alarms.select_flapping).
    FaultSpec("FLAPPING_ELEMENT", "red_herring", {}, (0, 0), None,
              description="Chronically flapping element: repeated RAISE/CLEAR with no customer impact"),
]}
CUSTOMER_IMPACT_TYPES = [t for t, s in FAULT_SPECS.items() if s.coefs or t == "TRAFFIC_SURGE"]
EFFECT_FIELDS = ["avail", "users", "thr", "lat", "loss", "drop", "rrc", "attach"]
CLUSTER_TYPES = ("BUSHFIRE_GRID_OUTAGE", "CYCLONE_BACKHAUL_CUT")
MAJOR_INCIDENT_TYPES = ("AGG_ROUTER_FAILURE", "AMF_OVERLOAD", "CORE_CONGESTION", "LONG_HAUL_FIBRE_CUT",
                        *CLUSTER_TYPES)


@dataclass
class Incident:
    incident_id: str
    fault_type: str
    event_class: str
    root_element_id: str
    root_element_type: str
    region_code: str
    start: np.datetime64
    end: np.datetime64
    cell_idx: np.ndarray  # affected cell indices (topology.cells positions)
    onset: np.ndarray  # per-cell impact start (datetime64[s])
    cell_end: np.ndarray  # per-cell impact end
    severity: np.ndarray  # per-cell peak intensity 0..1
    ramp_s: float = 0.0
    load_boost: float = 0.0  # TRAFFIC_SURGE: peak extra load multiplier minus 1
    alarms: list[dict] = field(default_factory=list)
    affected_element_ids: list[str] = field(default_factory=list)
    planned_window: tuple[np.datetime64, np.datetime64] | None = None
    estimated_impacted_subscribers: int = 0
    # Censored = not fully observed (streaming stopped mid-incident); times are clipped to `observed_until`.
    is_censored: bool = False
    observed_until: np.datetime64 | None = None
    root_element_ids: list[str] = field(default_factory=list)  # all roots (clusters); default [root]
    detail: dict = field(default_factory=dict)  # type-specific timing used by the alarm cascade
    description: str | None = None  # overrides the spec description (e.g. off-season variant)
    # Streaming: latest emission time of any associated KPI/alarm record seen so far.
    last_emit: np.datetime64 | None = None

    def __post_init__(self) -> None:
        if not self.root_element_ids:
            self.root_element_ids = [self.root_element_id]

    @property
    def spec(self) -> FaultSpec:
        return FAULT_SPECS[self.fault_type]

    @property
    def impact_start(self) -> np.datetime64 | None:
        return self.onset.min() if len(self.onset) else None

    @property
    def impact_end(self) -> np.datetime64 | None:
        return self.cell_end.max() if len(self.cell_end) else None

    @property
    def customer_impacting(self) -> bool:
        return len(self.cell_idx) > 0 and bool((self.cell_end > self.onset).any())

    def extent(self) -> tuple[np.datetime64, np.datetime64]:
        """Earliest and latest instant the incident touches anything: root start/end, per-cell onset and
        recovery, and every alarm RAISE/CLEAR it generates."""
        lo = [self.start] + ([self.onset.min()] if len(self.onset) else [])
        hi = [self.end] + ([self.cell_end.max()] if len(self.cell_end) else [])
        for a in self.alarms:
            lo.append(a["raise_ts"])
            hi.append(a["clear_ts"] if a["clear_ts"] is not None else a["raise_ts"])
        return min(lo), max(hi)


@dataclass
class Effects:
    avail: np.ndarray
    users: np.ndarray
    thr: np.ndarray
    lat: np.ndarray
    loss: np.ndarray
    drop: np.ndarray
    rrc: np.ndarray
    attach: np.ndarray
    load_mult: np.ndarray
    silent: np.ndarray

    @classmethod
    def zeros(cls, n_t: int, n_c: int) -> Effects:
        z = {f: np.zeros((n_t, n_c)) for f in EFFECT_FIELDS}
        return cls(**z, load_mult=np.ones((n_t, n_c)), silent=np.zeros((n_t, n_c), dtype=bool))


def compute_effects(incidents: list[Incident], n_cells: int, ts: np.ndarray, step_s: float) -> Effects:
    """Aggregate active incidents into (time, cell) effect arrays for KPI periods starting at `ts`."""
    eff = Effects.zeros(len(ts), n_cells)
    t0 = ts.astype("datetime64[s]").astype(np.int64)[:, None].astype(float)
    t1 = t0 + step_s
    for inc in incidents:
        if not len(inc.cell_idx):
            continue
        on = inc.onset.astype(np.int64)[None, :].astype(float)
        en = inc.cell_end.astype(np.int64)[None, :].astype(float)
        if en.max() <= t0[0, 0] or on.min() >= t1[-1, 0]:
            continue
        ov0, ov1 = np.maximum(t0, on), np.minimum(t1, en)
        frac = np.clip(ov1 - ov0, 0, None) / step_s
        ramp = np.clip(((ov0 + ov1) / 2 - on) / inc.ramp_s, 0, 1) if inc.ramp_s > 0 else 1.0
        inten = frac * ramp * inc.severity[None, :]
        idx = inc.cell_idx
        for f, coef in inc.spec.coefs.items():
            arr = getattr(eff, f)
            arr[:, idx] = np.maximum(arr[:, idx], inten * coef)
        if inc.spec.silent:
            eff.silent[:, idx] |= frac >= 0.5
        if inc.load_boost:
            eff.load_mult[:, idx] = np.maximum(eff.load_mult[:, idx], 1 + inten * inc.load_boost)
    return eff


# --------------------------------------------------------------------------------------------------
# Scheduling
# --------------------------------------------------------------------------------------------------

def opaque_id(prefix: str, *parts: object) -> str:
    h = hashlib.blake2b("|".join(map(str, parts)).encode(), digest_size=8).hexdigest()
    return f"{prefix}-{h}"


def _allowed_fraction(ws: np.datetime64, we: np.datetime64, hours: tuple[float, float] | None, tz: str) -> float:
    if hours is None:
        return 1.0
    grid = np.arange(ws, we, np.timedelta64(5, "m")).astype("datetime64[s]")
    if not len(grid):
        return 0.0
    hod = local_clock(grid, [tz])[0][0]
    return float(((hod >= hours[0]) & (hod < hours[1])).mean())


def _sample_start(rng, ws, we, hours, tz: str) -> np.datetime64 | None:
    """Uniform start in [ws, we) whose local hour (in `tz`) lies inside `hours`."""
    span = max(int((we - ws) / S), 1)
    if hours is None:
        return ws + np.timedelta64(int(rng.integers(0, span)), "s")
    cand = ws + rng.integers(0, span, 200).astype("timedelta64[s]")
    h = local_clock(cand, [tz])[0][0]
    ok = np.flatnonzero((h >= hours[0]) & (h < hours[1]))
    return cand[ok[0]] if len(ok) else None


def _season_factor(spec: FaultSpec, ws: np.datetime64, we: np.datetime64) -> float:
    if spec.season is None:
        return 1.0
    months, m_in, m_out = spec.season
    days = np.arange(ws.astype("datetime64[D]"), (we - S).astype("datetime64[D]") + 1)
    month = days.astype("datetime64[M]").astype(np.int64) % 12 + 1
    return float(np.where(np.isin(month, months), m_in, m_out).mean())


def in_season(spec: FaultSpec, t: np.datetime64) -> bool:
    return spec.season is None or int(t.astype("datetime64[M]").astype(np.int64) % 12 + 1) in spec.season[0]


def root_pool(topo: Topology, ftype: str, rtype: str) -> np.ndarray:
    """Elements of `rtype` eligible as roots (and, for clusters, as cluster members) of `ftype`."""
    pool = topo.ids_of_type(rtype)
    n = topo.nodes.loc[pool]
    if ftype == "TRAFFIC_SURGE":
        keep = n["urbanity"] == "urban"
    elif ftype == "BUSHFIRE_GRID_OUTAGE":
        keep = n["urbanity"].isin(["rural", "remote"])
    elif ftype == "CYCLONE_BACKHAUL_CUT":
        keep = n["region_code"].map(lambda c: REGION_BY_CODE[c].tropical)
    elif ftype == "LONG_HAUL_FIBRE_CUT":
        keep = n["uplink_km"] >= LONG_HAUL_KM
    else:
        return pool
    return pool[keep.to_numpy(dtype=bool)]


def _cluster(topo: Topology, root: str, pool: np.ndarray, radius_km: float, cap: int):
    """Pool members in the root's region within `radius_km` of it, nearest first (root first)."""
    n = topo.nodes
    same = pool[(n.loc[pool, "region_code"] == n.at[root, "region_code"]).to_numpy()]
    same = np.concatenate([[root], same[same != root]])
    d = km_between(n.at[root, "lat"], n.at[root, "lon"], n.loc[same, "lat"].to_numpy(), n.loc[same, "lon"].to_numpy())
    d[0] = 0.0
    order = np.argsort(d, kind="stable")
    order = order[d[order] <= radius_km][:cap]
    return same[order].astype(str), d[order]


def _u(rng, lo, hi, n=None):
    return rng.uniform(lo, hi, n)


def _secs(x) -> np.ndarray:
    return np.asarray(np.round(x), dtype=np.int64).astype("timedelta64[s]")


def _cells_of_roots(topo: Topology, rtype: str, roots) -> tuple[np.ndarray, np.ndarray]:
    """(cell positions under any of `roots`, index into `roots` of each cell's root)."""
    ri = pd.Index(list(roots)).get_indexer(topo.cells[ANCESTOR_COL[rtype]].to_numpy())
    idx = np.flatnonzero(ri >= 0)
    return idx, ri[idx]


def _build_cluster(spec: FaultSpec, root: str, start, end, topo: Topology, pool: np.ndarray, rng) -> dict:
    """Bushfire / cyclone: a geographic cluster of roots hit progressively as the fire front or storm
    track moves outward from the epicentre root, then restored in a staggered, partial way."""
    ftype = spec.fault_type
    span = (end - start) / S
    if ftype == "BUSHFIRE_GRID_OUTAGE":
        roots, dist = _cluster(topo, root, pool, _u(rng, 15, 45), 30)
        speed = _u(rng, 10, 40)  # km/h, fire front / storm cell
    else:
        roots, dist = _cluster(topo, root, pool, _u(rng, 40, 150), 40)
        speed = _u(rng, 12, 30)
    k_r = len(roots)
    hit = start + _secs(np.minimum(dist / speed * 3600, 0.5 * span))
    # Staggered restoration: the epicentre root is restored last, ~25 % of the rest only at the very end.
    frac = np.where(rng.random(k_r) < 0.25, 1.0, _u(rng, 0.35, 1.0, k_r))
    frac[0] = 1.0
    restore = hit + _secs(frac * ((end - hit) / S))
    idx, r_of = _cells_of_roots(topo, next(iter(spec.root_rates)), roots)
    k = len(idx)
    detail = dict(roots=roots, hit=hit, restore=restore)
    if ftype == "BUSHFIRE_GRID_OUTAGE":
        battery = np.where(rng.random(k_r) < 0.1, _u(rng, 0, 5, k_r), _u(rng, 60, 240, k_r)) * 60
        dark = hit + _secs(battery)
        # On battery the site sheds its 5G layer (energy saving) after 5-20 min; 4G lasts until the battery dies.
        is5g = topo.cells["technology"].to_numpy()[idx] == "5G"
        shed = hit[r_of] + _secs(_u(rng, 300, 1200, k))
        onset = np.where(is5g, np.minimum(shed, dark[r_of]), dark[r_of])
        cend = restore[r_of] + _secs(_u(rng, 180, 600, k))  # reboot after mains returns
        cend = np.where(restore[r_of] > onset, cend, onset)  # restored before shedding/dark: no impact
        sev = np.ones(k)
        detail.update(dark=dark)
    else:
        medium = topo.nodes.loc[roots, "transport_medium"].to_numpy()
        p_cut = np.select([medium == "microwave", medium == "fibre"], [0.7, 0.45], 0.2)
        cut = rng.random(k_r) < p_cut
        cut[0] = True
        link_sev = np.where(cut, 1.0, _u(rng, 0.3, 0.7, k_r))
        onset = hit[r_of] + _secs(_u(rng, 30, 300, k))
        cend = restore[r_of] + _secs(_u(rng, 60, 600, k))
        sev = link_sev[r_of] * _u(rng, 0.9, 1.0, k)
        detail.update(cut=cut)
    desc = spec.description if in_season(spec, start) else spec.off_season_description
    return dict(idx=idx, onset=onset, cend=cend, sev=sev, start=start, end=restore.max(), roots=list(roots),
                detail=detail, description=desc)


def _build_impact(spec: FaultSpec, root: str, start: np.datetime64, dur_min: float, topo: Topology, rng,
                  pool: np.ndarray) -> dict:
    """Impact of one incident: cells, per-cell onset/end/severity, ramp, surge boost, (possibly moved)
    start/end, planned window, roots and type-specific detail."""
    ftype = spec.fault_type
    end = start + _secs(dur_min * 60)
    planned = None
    out = dict(ramp_s=0.0, boost=0.0, planned=None, roots=[root], detail={}, description=None)
    if ftype == "ALARM_STORM":
        e = np.array([], dtype="datetime64[s]")
        return {**out, "idx": np.array([], dtype=int), "onset": e, "cend": e, "sev": np.array([]),
                "start": start, "end": end}
    if ftype in CLUSTER_TYPES:
        return {**out, **_build_cluster(spec, root, start, end, topo, pool, rng)}
    if ftype == "TRAFFIC_SURGE":
        # The venue site plus its two nearest neighbours.
        sites = topo.nodes[topo.nodes["element_type"] == "SITE"]
        r = topo.nodes.loc[root]
        d = (sites["lat"] - r["lat"]) ** 2 + ((sites["lon"] - r["lon"]) * np.cos(np.radians(r["lat"]))) ** 2
        near = d.nsmallest(3).index
        idx = np.flatnonzero(topo.cells["site_id"].isin(near).to_numpy())
    else:
        idx = topo.cell_indices_under(root)
    k = len(idx)
    ramp_s, boost = 0.0, 0.0
    sev = np.ones(k)
    onset = np.full(k, start)
    cend = np.full(k, end)
    if ftype == "CELL_OUTAGE":
        pass
    elif ftype == "SITE_POWER_OUTAGE":
        battery = _u(rng, 0, 2) if rng.random() < 0.1 else _u(rng, 20, 90)
        onset = onset + _secs(battery * 60)
        cend = cend + _secs(_u(rng, 180, 480, k))  # reboot after mains restore
    elif ftype == "BACKHAUL_DEGRADATION":
        onset = onset + _secs(_u(rng, 0, 120, k))
        ramp_s = _u(rng, 600, 1800)
        sev = _u(rng, 0.4, 1.0) * _u(rng, 0.85, 1.0, k)
        cend = cend + _secs(_u(rng, 0, 60, k))
    elif ftype == "AGG_ROUTER_FAILURE":
        onset = onset + _secs(_u(rng, 60, 180, k))
        cend = cend + _secs(_u(rng, 60, 300, k))
    elif ftype == "CORE_CONGESTION":
        onset = onset + _secs(_u(rng, 0, 60, k))
        ramp_s = _u(rng, 600, 1200)
        bl = topo.cells["base_load"].to_numpy()[idx]
        sev = _u(rng, 0.4, 0.9) * np.clip(0.5 + 0.5 * bl / bl.max(), 0, 1) * _u(rng, 0.8, 1.0, k)
    elif ftype == "AMF_OVERLOAD":
        onset = onset + _secs(_u(rng, 0, 30, k))
        ramp_s = 300.0
        sev = _u(rng, 0.5, 1.0) * _u(rng, 0.8, 1.0, k)
    elif ftype == "PLANNED_MAINTENANCE":
        # Window opens on the half hour (aligned to local time in every AU zone, incl. UTC+9:30/+10:30).
        win0 = start - (start - start.astype("datetime64[D]").astype("datetime64[s]")) % np.timedelta64(30, "m")
        planned = (win0, win0 + np.timedelta64(4, "h"))
        start = win0 + _secs(_u(rng, 10, 90) * 60)
        end = start + _secs(dur_min * 60)
        onset = np.full(k, start) + _secs(_u(rng, 0, 60, k))
        cend = np.full(k, end) + _secs(_u(rng, 60, 300, k))
    elif ftype == "LONG_HAUL_FIBRE_CUT":
        onset = onset + _secs(_u(rng, 0, 30, k))  # instantaneous loss of the only path to the core
        cend = cend + _secs(_u(rng, 60, 300, k))  # sites re-register once the splice is done
    elif ftype == "TRAFFIC_SURGE":
        ramp_s = _u(rng, 1800, 2700)
        boost = _u(rng, 1.0, 2.0)
    return {**out, "idx": idx, "onset": onset, "cend": cend, "sev": sev, "ramp_s": ramp_s, "boost": boost,
            "start": start, "end": end, "planned": planned}


def schedule_incidents(topo: Topology, ws: np.datetime64, we: np.datetime64, cfg: FaultConfig,
                       rng: np.random.Generator, existing: list[Incident] | None = None,
                       id_prefix: str = "INC", bounds: tuple | None = None) -> list[Incident]:
    """Draw incidents starting in [ws, we).

    Every accepted incident's full `extent()` (propagation delays, recovery and all of its alarms) lies
    inside `bounds` = (lo, hi), default (ws, we); `hi=None` means unbounded (streaming). Candidates that
    do not fit are redrawn, so batch ground truth never describes impact outside the telemetry window.
    Customer-impacting incidents never overlap in (cells, time), so every degraded cell-period has
    exactly one ground-truth cause."""
    if not cfg.enabled:
        return []
    ws, we = ws.astype("datetime64[s]"), we.astype("datetime64[s]")
    b_lo, b_hi = bounds if bounds is not None else (ws, we)
    days = (we - ws) / np.timedelta64(1, "D")
    busy: list[tuple[np.ndarray, np.datetime64, np.datetime64]] = [
        (i.cell_idx, i.onset.min() - 30 * MIN, i.cell_end.max() + 30 * MIN)
        for i in (existing or []) if len(i.cell_idx)
    ]
    out: list[Incident] = []
    seq = 0
    for ftype, spec in FAULT_SPECS.items():
        if spec.event_class != "fault" and not cfg.red_herrings:
            continue
        hour_share = 1.0 if spec.hours is None else (spec.hours[1] - spec.hours[0]) / 24.0
        season = _season_factor(spec, ws, we)
        for rtype, rate in spec.root_rates.items():
            pool = root_pool(topo, ftype, rtype)
            if not len(pool):
                continue
            # Start windows are local, so each element's share of the window depends on its time zone.
            tz = topo.nodes.loc[pool, "timezone"].to_numpy()
            frac = {z: _allowed_fraction(ws, we, spec.hours, z) for z in sorted(set(tz))}
            w = np.array([frac[z] for z in tz]) / hour_share
            if w.sum() == 0:
                continue
            lam = rate * days * cfg.rate_multiplier * season * w.sum()
            n = int(rng.poisson(lam))
            if rtype == next(iter(spec.root_rates)):
                n = max(n, cfg.min_per_type)
            p = w / w.sum()
            for _ in range(n):
                for _attempt in range(25):
                    root = str(pool[rng.choice(len(pool), p=p)])
                    start = _sample_start(rng, ws, we, spec.hours, topo.nodes.at[root, "timezone"])
                    if start is None:
                        continue
                    dur = _u(rng, *spec.duration_min)
                    imp = _build_impact(spec, root, start, dur, topo, rng, pool)
                    idx, onset, cend = imp["idx"], imp["onset"], imp["cend"]
                    if len(idx):
                        lo, hi = onset.min() - 30 * MIN, cend.max() + 30 * MIN
                        if any(o_lo < hi and lo < o_hi and np.intersect1d(o_idx, idx, assume_unique=True).size
                               for o_idx, o_lo, o_hi in busy):
                            continue
                    root_row = topo.nodes.loc[root]
                    inc = Incident(
                        incident_id=f"{id_prefix}-{seq + 1:05d}", fault_type=ftype, event_class=spec.event_class,
                        root_element_id=root, root_element_type=rtype, region_code=root_row["region_code"],
                        start=imp["start"], end=imp["end"],
                        cell_idx=idx, onset=onset, cell_end=cend, severity=imp["sev"], ramp_s=imp["ramp_s"],
                        load_boost=imp["boost"], planned_window=imp["planned"], root_element_ids=imp["roots"],
                        detail=imp["detail"], description=imp["description"])
                    _finalise(inc, topo, rng)
                    e_lo, e_hi = inc.extent()
                    if e_lo < b_lo or (b_hi is not None and e_hi > b_hi):
                        continue  # would run past the observed window: redraw
                    if len(idx):
                        busy.append((idx, lo, hi))
                    seq += 1
                    out.append(inc)
                    break
    out.sort(key=lambda i: i.start)
    # Stable, chronological ids.
    for n, inc in enumerate(out, 1):
        inc.incident_id = f"{id_prefix}-{n:05d}"
        for a in inc.alarms:
            a["alarm_id"] = opaque_id("ALM", inc.incident_id, a["_n"])
    return out


def _finalise(inc: Incident, topo: Topology, rng) -> None:
    if inc.fault_type == "TRAFFIC_SURGE":
        aff = list(topo.cells["element_id"].to_numpy()[inc.cell_idx])
        aff += sorted(set(topo.cells["site_id"].to_numpy()[inc.cell_idx]))
    elif inc.fault_type == "ALARM_STORM":
        aff = []
    else:
        # Everything strictly below any root (one root except for geographic clusters).
        nodes = topo.nodes
        roots = inc.root_element_ids
        below = nodes[ANCESTOR_COL[inc.root_element_type]].isin(roots) & ~nodes.index.isin(roots)
        aff = list(nodes.index[below])
    inc.affected_element_ids = sorted(set(aff) - {inc.root_element_id})
    inc.alarms = incident_alarms(inc, topo, rng)
    if inc.customer_impacting:
        # Peak concurrent baseline users on affected cells, weighted by severity, over the impact window.
        grid = np.arange(inc.impact_start, inc.impact_end, np.timedelta64(15, "m")).astype("datetime64[s]")
        if len(grid):
            users = expected_users(topo, grid)[:, inc.cell_idx]
            inc.estimated_impacted_subscribers = int(round((users.max(axis=0) * inc.severity).sum()))


# --------------------------------------------------------------------------------------------------
# Alarm cascades
# --------------------------------------------------------------------------------------------------

def incident_alarms(inc: Incident, topo: Topology, rng) -> list[dict]:
    """Alarms raised by an incident: a few on/near the root, a flood of symptom alarms downstream."""
    rows: list[dict] = []
    nodes = topo.nodes

    def alarm(eid, code, sev, raise_ts, clear_ts, text):
        rows.append(dict(_n=len(rows), element_id=eid, alarm_code=code, severity=sev,
                         raise_ts=np.datetime64(raise_ts, "s"), clear_ts=np.datetime64(clear_ts, "s"),
                         text=text))

    r, t0, t1 = inc.root_element_id, inc.start, inc.end
    desc = topo.descendants(r) if inc.fault_type not in ("ALARM_STORM", "TRAFFIC_SURGE") else nodes.iloc[:0]
    j = lambda lo, hi: _secs(rng.uniform(lo, hi))  # noqa: E731
    ft = inc.fault_type
    if ft == "CELL_OUTAGE":
        if rng.random() < 0.5:
            alarm(r, "RRU_FAILURE", "MAJOR", t0 - j(30, 300), t1, "Radio unit failure detected")
        alarm(r, "CELL_OUT_OF_SERVICE", "CRITICAL", t0 + j(5, 60), t1 + j(5, 60), "Cell disabled")
    elif ft == "SITE_POWER_OUTAGE":
        alarm(r, "MAINS_FAILURE", "MAJOR", t0 + j(1, 20), t1, "AC mains input lost, running on battery")
        on = inc.onset.min()
        if on < t1:
            alarm(r, "BATTERY_LOW", "CRITICAL", max(t0 + j(30, 60), on - j(300, 600)), t1, "Battery below 20 %")
            alarm(r, "NE_UNREACHABLE", "CRITICAL", on + j(60, 180), inc.cell_end.max(), "Management link lost")
    elif ft == "BACKHAUL_DEGRADATION":
        medium = nodes.at[r, "transport_medium"]
        alarm(r, "RSL_LOW" if medium == "microwave" else "HIGH_BER", "MAJOR", t0 + j(60, 600), t1,
              "Receive level below threshold" if medium == "microwave" else "Bit error rate above 1e-6")
        alarm(r, "LINK_DEGRADED", "MINOR", t0 + j(300, 1200), t1 + j(0, 120), "Link capacity degraded")
        for c in desc.index[desc["element_type"] == "CELL"]:
            if rng.random() < 0.3:
                alarm(c, "CELL_DEGRADED", "MINOR", t0 + j(600, 1800), t1 + j(0, 300), "Cell KPI degradation")
    elif ft == "AGG_ROUTER_FAILURE":
        alarm(r, "NODE_DOWN", "CRITICAL", t0 + j(30, 90), t1 + j(30, 120), "Node unreachable (heartbeat lost)")
        alarm(nodes.at[r, "upf_id"], "GTPU_PATH_FAILURE", "MAJOR", t0 + j(20, 90), t1 + j(30, 120),
              f"GTP-U path failure towards {r}")
        for eid, et in desc["element_type"].items():
            if et == "BACKHAUL_LINK":
                alarm(eid, "LINK_DOWN", "CRITICAL", t0 + j(1, 60), t1 + j(10, 120), "Interface operationally down")
            elif et == "SITE":
                alarm(eid, "S1_NG_LINK_FAILURE", "CRITICAL", t0 + j(30, 180), t1 + j(60, 300),
                      "S1/NG interface to core lost")
            elif et == "CELL":
                alarm(eid, "CELL_OUT_OF_SERVICE", "MAJOR", t0 + j(60, 240), t1 + j(60, 360),
                      "Cell barred: no core connectivity")
    elif ft == "CORE_CONGESTION":
        # Alarms lag the customer impact: thresholds trip only once congestion is sustained.
        alarm(r, "USER_PLANE_CONGESTION", "MAJOR", t0 + j(240, 600), t1, "Throughput above 90 % of licence")
        alarm(r, "PACKET_DROP_HIGH", "MINOR", t0 + j(300, 900), t1 + j(0, 300), "Packet drop ratio high")
    elif ft == "AMF_OVERLOAD":
        alarm(r, "SIGNALLING_OVERLOAD", "MAJOR", t0 + j(180, 480), t1, "NAS/NGAP overload control active")
        alarm(r, "CORE_CPU_OVERLOAD", "MINOR", t0 + j(60, 300), t1 + j(0, 300), "CPU above 85 %")
    elif ft == "PLANNED_MAINTENANCE":
        code = "NODE_DOWN" if inc.root_element_type == "AGG_ROUTER" else "NE_UNREACHABLE"
        alarm(r, code, "CRITICAL", inc.start + j(5, 60), inc.end + j(30, 120), "Node unreachable")
        for c in desc.index[desc["element_type"] == "CELL"]:
            alarm(c, "CELL_OUT_OF_SERVICE", "MAJOR", inc.start + j(60, 180), inc.end + j(60, 300), "Cell disabled")
    elif ft == "BUSHFIRE_GRID_OUTAGE":
        d = inc.detail
        site_end = pd.Series(inc.cell_end, index=topo.cells["site_id"].to_numpy()[inc.cell_idx]).groupby(level=0).max()
        fire = in_season(inc.spec, inc.start)
        for i, s in enumerate(d["roots"]):
            hit, dark, rest = d["hit"][i], d["dark"][i], d["restore"][i]
            if fire and rng.random() < 0.3:
                alarm(s, "TEMPERATURE_HIGH", "MAJOR", hit - j(120, 900), hit + j(60, 600), "Shelter temperature high")
            alarm(s, "MAINS_FAILURE", "MAJOR", hit + j(1, 20), rest, "AC mains input lost, running on battery")
            if dark < rest:
                alarm(s, "BATTERY_LOW", "CRITICAL", max(hit + j(30, 60), dark - j(300, 600)), rest, "Battery below 20 %")
                alarm(s, "NE_UNREACHABLE", "CRITICAL", dark + j(60, 180), max(site_end.get(s, rest), dark + j(240, 300)),
                      "Management link lost")
    elif ft == "CYCLONE_BACKHAUL_CUT":
        d = inc.detail
        sites = nodes[(nodes["element_type"] == "SITE") & nodes["backhaul_id"].isin(d["roots"])]
        for i, link in enumerate(d["roots"]):
            hit, rest = d["hit"][i], d["restore"][i]
            medium = nodes.at[link, "transport_medium"]
            if d["cut"][i]:
                code, text = ("LOS", "Loss of signal (fibre washout)") if medium == "fibre" else (
                    "LINK_DOWN", "Radio link down (antenna misalignment / water ingress)")
                alarm(link, code, "CRITICAL", hit + j(10, 120), rest + j(0, 120), text)
                for s in sites.index[sites["backhaul_id"] == link]:
                    alarm(s, "S1_NG_LINK_FAILURE", "CRITICAL", hit + j(30, 180), rest + j(60, 300),
                          "S1/NG interface to core lost")
            else:
                code = "HIGH_BER" if medium == "fibre" else "RSL_LOW"
                alarm(link, code, "MAJOR", hit + j(60, 600), rest + j(0, 120), "Link degraded (rain fade / water ingress)")
    elif ft == "LONG_HAUL_FIBRE_CUT":
        # The far side cannot report: alarms come from the core-side transport and the OSS only.
        alarm(r, "LOS", "CRITICAL", t0 + j(1, 30), t1 + j(10, 60), "Loss of signal on long-haul uplink (core-side DWDM)")
        alarm(r, "NE_UNREACHABLE", "CRITICAL", t0 + j(60, 180), t1 + j(60, 300), "Management link lost")
        alarm(nodes.at[r, "upf_id"], "GTPU_PATH_FAILURE", "MAJOR", t0 + j(20, 90), t1 + j(30, 120),
              f"GTP-U path failure towards {r}")
        for s in desc.index[desc["element_type"] == "SITE"]:
            alarm(s, "NE_UNREACHABLE", "MAJOR", t0 + j(120, 420), t1 + j(120, 420), "Management link lost")
    elif ft == "ALARM_STORM":
        n = int(rng.integers(50, 400))
        codes = ["TEMPERATURE_HIGH", "FAN_FAILURE", "POWER_SUPPLY_FAIL", "NTP_SYNC_LOSS", "DOOR_OPEN",
                 "LICENSE_THRESHOLD"]
        sevs = rng.choice(["WARNING", "MINOR", "MAJOR", "CRITICAL"], size=n, p=[0.3, 0.35, 0.25, 0.1])
        span = int((t1 - t0) / S)
        for k in range(n):
            ts = t0 + np.timedelta64(int(rng.integers(0, max(span, 1))), "s")
            alarm(r, str(rng.choice(codes)), str(sevs[k]), ts, ts + j(5, 120), "Equipment alarm")
    return rows


# --------------------------------------------------------------------------------------------------
# Ground-truth tables
# --------------------------------------------------------------------------------------------------

def _severity_label(inc: Incident) -> str:
    if not inc.customer_impacting:
        return "none"
    n = inc.estimated_impacted_subscribers
    if n >= 2000 or inc.fault_type in MAJOR_INCIDENT_TYPES:
        return "critical"
    return "major" if n >= 200 else "minor"


def incidents_frame(incidents: list[Incident], topo: Topology) -> pd.DataFrame:
    cell_ids = topo.cells["element_id"].to_numpy()
    rows = []
    def iso(t):
        return None if t is None or np.isnat(t) else to_iso(np.array([t]))[0]

    def clip(t):
        return t if not inc.is_censored or inc.observed_until is None else min(t, inc.observed_until)

    for inc in incidents:
        imp = inc.customer_impacting
        if inc.is_censored:  # only what was observed counts
            imp = imp and inc.observed_until is not None and inc.impact_start < inc.observed_until
        end = inc.end if not (inc.is_censored and inc.observed_until is None) else None
        rows.append({
            "incident_id": inc.incident_id,
            "event_class": inc.event_class,
            "fault_type": inc.fault_type,
            "root_element_id": inc.root_element_id,
            "root_element_type": inc.root_element_type,
            "root_element_ids": list(inc.root_element_ids),
            "region_code": inc.region_code,
            "start_ts": iso(inc.start),
            "end_ts": iso(clip(end)) if end is not None else None,
            "impact_start_ts": iso(inc.impact_start) if imp else None,
            "impact_end_ts": (iso(clip(inc.impact_end)) if not (inc.is_censored and inc.observed_until is None)
                              else None) if imp else None,
            "is_customer_impacting": bool(imp),
            "is_censored": bool(inc.is_censored),
            "severity": _severity_label(inc),
            "affected_element_ids": inc.affected_element_ids,
            "affected_cell_ids": sorted(cell_ids[inc.cell_idx].tolist()) if imp else [],
            "n_affected_cells": int(len(inc.cell_idx)) if imp else 0,
            "estimated_impacted_subscribers": int(inc.estimated_impacted_subscribers),
            "n_alarms": len(inc.alarms),
            "description": inc.description or inc.spec.description,
        })
    cols = ["incident_id", "event_class", "fault_type", "root_element_id", "root_element_type", "root_element_ids",
            "region_code",
            "start_ts", "end_ts", "impact_start_ts", "impact_end_ts", "is_customer_impacting", "is_censored", "severity",
            "affected_element_ids", "affected_cell_ids", "n_affected_cells", "estimated_impacted_subscribers",
            "n_alarms", "description"]
    return pd.DataFrame(rows, columns=cols)


def maintenance_frame(incidents: list[Incident]) -> pd.DataFrame:
    """The change-management calendar a NOC would have (operational data, not ground truth)."""
    rows = [{
        "change_id": opaque_id("CHG", inc.incident_id),
        "element_id": inc.root_element_id,
        "element_type": inc.root_element_type,
        "planned_start_ts": to_iso(np.array([inc.planned_window[0]]))[0],
        "planned_end_ts": to_iso(np.array([inc.planned_window[1]]))[0],
        "change_type": "software_upgrade" if inc.root_element_type == "AGG_ROUTER" else "hardware_swap",
        "status": "approved",
    } for inc in incidents if inc.fault_type == "PLANNED_MAINTENANCE"]
    return pd.DataFrame(rows, columns=["change_id", "element_id", "element_type", "planned_start_ts",
                                       "planned_end_ts", "change_type", "status"])
