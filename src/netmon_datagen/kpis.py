"""Traffic load model (diurnal + weekly seasonality in each cell's local time) and per-cell KPI generation.

Load drives everything else: PRB utilisation follows load, and once PRB utilisation passes ~70 %
a congestion term pushes latency, packet loss and drop rate up and success rates / throughput down.
Fault effects (see `faults.Effects`) are applied on top of the organic behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from netmon_datagen.topology import Topology

# Normalised hourly traffic profiles (peak = 1.0) by urbanity, weekday vs weekend.
# Urban: commuter/business double peak; suburban/rural: residential evening peak, busier weekends.
# Remote (mining towns, FIFO camps, communities): shift-change peaks around 05-06h and 18-19h, and the
# same pattern on weekends because rosters ignore the calendar.
_PROFILES = {
    ("urban", False): [.20, .13, .09, .07, .07, .10, .22, .48, .78, .85, .82, .84,
                       .88, .85, .82, .83, .88, .95, 1.0, .98, .92, .80, .58, .35],
    ("urban", True): [.30, .20, .13, .09, .08, .08, .12, .22, .38, .55, .68, .76,
                      .80, .80, .78, .78, .80, .84, .88, .90, .86, .76, .60, .42],
    ("suburban", False): [.22, .14, .10, .08, .08, .11, .25, .50, .62, .55, .52, .55,
                          .58, .56, .55, .60, .70, .85, .95, 1.0, .98, .88, .65, .40],
    ("suburban", True): [.28, .18, .12, .09, .08, .09, .15, .30, .50, .65, .72, .75,
                         .76, .74, .72, .74, .78, .85, .92, .96, .94, .85, .66, .45],
    ("rural", False): [.18, .11, .08, .06, .06, .10, .25, .45, .55, .55, .55, .57,
                       .60, .58, .57, .60, .68, .80, .90, .92, .88, .75, .52, .32],
    ("rural", True): [.22, .14, .10, .07, .06, .08, .16, .32, .52, .62, .66, .68,
                      .68, .66, .65, .67, .72, .82, .92, .95, .90, .78, .56, .36],
    ("remote", False): [.25, .18, .14, .14, .30, .62, .70, .52, .42, .40, .40, .45,
                        .50, .45, .42, .45, .55, .78, .96, 1.0, .90, .72, .52, .36],
    ("remote", True): [.27, .19, .15, .14, .28, .58, .66, .52, .44, .42, .42, .47,
                       .52, .47, .44, .47, .56, .78, .95, 1.0, .91, .74, .54, .38],
}
_URB = ["urban", "suburban", "rural", "remote"]
_PROFILE_ARR = np.array([[_PROFILES[(u, we)] for we in (False, True)] for u in _URB])  # (4, 2, 24)
GROWTH_PER_DAY = 0.0005  # ~1.5 % traffic growth per month, relative to the reference date below
_GROWTH_REF = np.datetime64("2026-06-01", "D")

KPI_COLUMNS = ["availability_pct", "active_users", "prb_util_pct", "rrc_setup_success_pct",
               "attach_success_pct", "session_drop_rate_pct", "dl_throughput_mbps", "ul_throughput_mbps",
               "latency_ms", "packet_loss_pct"]


def to_iso(ts: np.ndarray) -> np.ndarray:
    return np.char.add(np.datetime_as_string(ts.astype("datetime64[s]"), unit="s"), "Z")


def urbanity_codes(topo: Topology) -> np.ndarray:
    return topo.cells["urbanity"].map({u: i for i, u in enumerate(_URB)}).to_numpy()


def local_clock(ts: np.ndarray, timezones: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Local wall-clock hour (float) and weekend flag, each shape (n_zones, nT), for UTC instants `ts`.

    Vectorised per zone through pandas' tz database (DST transitions included), so the cost is one
    conversion per distinct zone regardless of cell count."""
    idx = pd.DatetimeIndex(ts.astype("datetime64[s]")).tz_localize("UTC")
    hours, weekend = [], []
    for z in timezones:
        loc = idx.tz_convert(z)
        hours.append(loc.hour.to_numpy() + loc.minute.to_numpy() / 60.0 + loc.second.to_numpy() / 3600.0)
        weekend.append(loc.dayofweek.to_numpy() >= 5)
    return np.array(hours).reshape(len(timezones), len(ts)), np.array(weekend).reshape(len(timezones), len(ts))


def seasonal_profile(ts: np.ndarray, urb_codes: np.ndarray, tz_idx: np.ndarray, timezones: list[str]) -> np.ndarray:
    """(nT, nC) normalised seasonal factor at each cell's local time, interpolated between hourly anchors.

    `tz_idx` gives each cell's position in `timezones`. Timestamps stay UTC; only the profile lookup
    uses local hour and local day of week."""
    ts = ts.astype("datetime64[s]")
    days = ts.astype("datetime64[D]")
    hours_z, weekend_z = local_clock(ts, timezones)
    hour = hours_z[tz_idx].T  # (nT, nC)
    we = weekend_z[tz_idx].T.astype(int)
    h0 = np.floor(hour).astype(int) % 24
    h1 = (h0 + 1) % 24
    w = hour - np.floor(hour)
    u = np.broadcast_to(urb_codes[None, :], hour.shape)
    p0 = _PROFILE_ARR[u, we, h0]
    p1 = _PROFILE_ARR[u, we, h1]
    growth = 1.0 + GROWTH_PER_DAY * np.clip((days - _GROWTH_REF).astype(np.int64), -365, 365)
    return (p0 * (1 - w) + p1 * w) * growth[:, None]


def baseline_load(topo: Topology, ts: np.ndarray) -> np.ndarray:
    """Noise-free expected load (fraction of cell capacity) per (time, cell)."""
    prof = seasonal_profile(ts, urbanity_codes(topo), topo.cell_tz_idx, topo.timezones)
    return prof * topo.cells["base_load"].to_numpy()[None, :]


def expected_users(topo: Topology, ts: np.ndarray) -> np.ndarray:
    cap = topo.cells["capacity_users"].to_numpy(dtype=float)
    return np.minimum(baseline_load(topo, ts), 1.5) * 0.9 * cap[None, :]


@dataclass
class KpiResult:
    frame: pd.DataFrame  # one row per reporting (time, cell); silent cells omitted
    # Ground-truth (pre-DQ) arrays reused by the session generator, all shape (nT, nC).
    rrc: np.ndarray
    attach: np.ndarray
    drop: np.ndarray
    avail: np.ndarray
    dl: np.ndarray
    expected_users: np.ndarray
    silent: np.ndarray


def generate_kpis(topo: Topology, ts: np.ndarray, step_minutes: float, effects, rng: np.random.Generator) -> KpiResult:
    """KPIs for every cell at every period start in `ts` (datetime64 array)."""
    n_t, n_c = len(ts), topo.n_cells
    shape = (n_t, n_c)
    cells = topo.cells
    cap = cells["capacity_users"].to_numpy(dtype=float)[None, :]
    peak = cells["peak_dl_mbps"].to_numpy()[None, :]
    base_lat = cells["base_latency_ms"].to_numpy()[None, :]
    rrc_base = cells["rrc_base_pct"].to_numpy()[None, :]
    drop_base = cells["drop_base_pct"].to_numpy()[None, :]

    # Noise is drawn up-front in a fixed order so it is identical with or without faults.
    z_load = rng.normal(0, 0.08, shape)
    z_prb = rng.normal(0, 2.5, shape)
    z_lat = rng.normal(0, 0.08, shape)
    z_loss = np.abs(rng.normal(0, 0.02, shape))
    z_thr = rng.normal(0, 0.10, shape)
    z_ul = rng.uniform(0.10, 0.16, shape)
    z_drop = np.abs(rng.normal(0, 0.08, shape))
    z_rrc = np.abs(rng.normal(0, 0.15, shape))
    z_att = np.abs(rng.normal(0, 0.05, shape))
    u_users = rng.random(shape)

    exp_users = expected_users(topo, ts)
    load = np.minimum(baseline_load(topo, ts) * effects.load_mult * np.exp(z_load), 1.6)
    # Poisson-ish user count via normal approximation (vectorised, keeps the RNG draw count fixed).
    lam = np.minimum(load, 1.5) * 0.9 * cap
    users = np.maximum(0, np.round(lam + np.sqrt(lam) * _norm_ppf(u_users)))
    users = np.round(users * (1 - effects.users))

    prb = np.clip(100 * (0.06 + 0.88 * load) + z_prb, 0, 100) * (1 - effects.avail)
    util = prb / 100
    cong = np.clip((util - 0.70) / 0.30, 0, 1)  # congestion knee above 70 % PRB
    latency = base_lat * (1 + 0.8 * util + 2.2 * cong**2) * np.exp(z_lat) + effects.lat
    loss = np.clip(0.03 + 0.1 * util + 1.2 * cong**2 + z_loss + effects.loss, 0, 100)
    dl = peak * (1 - 0.72 * util**1.5) * np.exp(z_thr) * (1 - effects.thr)
    ul = dl * z_ul
    drop = np.clip(drop_base + 0.3 * util + 2.0 * cong**3 + z_drop + effects.drop, 0, 100)
    rrc = np.clip(rrc_base - 3.5 * cong**3 - z_rrc, 0, 100) * (1 - effects.rrc / 100)
    attach = np.clip(99.85 - 0.8 * cong**3 - z_att, 0, 100) * (1 - effects.attach / 100)
    avail = 100 * (1 - effects.avail)

    t_idx, c_idx = np.nonzero(~effects.silent)
    ts_iso = to_iso(ts)
    stamp = np.datetime_as_string(ts.astype("datetime64[m]"), unit="m")
    stamp = np.char.replace(np.char.replace(np.char.replace(stamp, "-", ""), "T", ""), ":", "")
    cell_ids = cells["element_id"].to_numpy()
    sel = (t_idx, c_idx)
    frame = pd.DataFrame({
        "record_id": np.char.add(np.char.add("K-", cell_ids[c_idx].astype(str)), np.char.add("-", stamp[t_idx])),
        "event_ts": ts_iso[t_idx],
        "cell_id": cell_ids[c_idx],
        "granularity_s": int(step_minutes * 60),
        "availability_pct": np.round(avail[sel], 2),
        "active_users": users[sel].astype(np.int64),
        "prb_util_pct": np.round(prb[sel], 2),
        "rrc_setup_success_pct": np.round(rrc[sel], 3),
        "attach_success_pct": np.round(attach[sel], 3),
        "session_drop_rate_pct": np.round(drop[sel], 3),
        "dl_throughput_mbps": np.round(dl[sel], 2),
        "ul_throughput_mbps": np.round(ul[sel], 2),
        "latency_ms": np.round(latency[sel], 1),
        "packet_loss_pct": np.round(loss[sel], 3),
    })
    frame["_event_time"] = ts[t_idx].astype("datetime64[s]")
    frame["_cell"] = c_idx  # private: cell position, survives DQ nulling of cell_id
    # Delivered after the period closes; collection lag scales with the period (1-min: 6-30 s, 15-min: 30-240 s).
    step_s = step_minutes * 60
    frame["_emit_delay_s"] = step_s + rng.uniform(min(30, 0.1 * step_s), min(240, 0.5 * step_s), len(frame))
    return KpiResult(frame, rrc, attach, drop, avail, dl, exp_users, effects.silent)


def _norm_ppf(u: np.ndarray) -> np.ndarray:
    """Approximate inverse normal CDF via a logistic with matched variance (fast, good enough for counts)."""
    u = np.clip(u, 1e-6, 1 - 1e-6)
    return np.log(u / (1 - u)) * 0.5513  # sqrt(3) / pi gives unit variance
