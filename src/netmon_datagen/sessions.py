"""Subscriber session records (xDR sample) with clearly synthetic identifiers.

IMSI uses MCC 001 / MNC 01, the ITU-T test network code that is never allocated to a real operator.
MSISDN uses E.164 country code +999, which is unassigned. Both are PII-shaped columns that the
governance layer masks later.

Session outcomes are drawn from the serving cell's KPIs in the same period, so faults surface as
setup failures and drops in the session feed (the customer-impact signal).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from netmon_datagen.kpis import KpiResult, to_iso
from netmon_datagen.topology import REGION_BY_CODE, Topology

IMSI_PREFIX = "00101"  # MCC 001 + MNC 01 (ITU test network)
MSISDN_PREFIX = "+999"  # unassigned E.164 country code
SESSIONS_PER_USER_HOUR = 3.0
ROAM_P = 0.1  # share of sessions by a subscriber away from their home cell

SERVICES = np.array(["data", "video", "volte", "iot"])
SERVICE_P = [0.62, 0.18, 0.14, 0.06]
# (median duration s, lognormal sigma, nominal DL Mbps, UL/DL byte ratio, DNN)
SERVICE_PARAMS = {
    "data": (180, 1.0, 4.0, 0.10, "internet"),
    "video": (720, 0.8, 6.0, 0.03, "internet"),
    "volte": (150, 0.9, 0.05, 1.0, "ims"),
    "iot": (20, 0.6, 0.01, 2.0, "iot.m2m"),
}
SESSION_COLUMNS = ["record_id", "imsi", "msisdn", "cell_id", "start_ts", "end_ts", "emitted_ts", "duration_s",
                   "service_type", "dnn", "bytes_dl", "bytes_ul", "outcome", "cause_code"]


@dataclass
class SubscriberBase:
    pool_lo: np.ndarray  # per-cell start of the home-subscriber index range
    pool_size: np.ndarray
    n: int

    @classmethod
    def build(cls, topo: Topology, n_subscribers: int) -> SubscriberBase:
        # Within a region subscribers follow cell demand; across regions they follow resident population
        # (remote areas carry many sites per head for coverage, not for subscribers).
        cells = topo.cells
        w = cells["capacity_users"].to_numpy(dtype=float) * cells["base_load"].to_numpy()
        pop = cells["region_code"].map(lambda c: REGION_BY_CODE[c].population_m).to_numpy(dtype=float)
        region_w = pd.Series(w).groupby(cells["region_code"].to_numpy()).transform("sum").to_numpy()
        w = w / region_w * pop
        size = np.maximum(1, np.round(n_subscribers * w / w.sum())).astype(np.int64)
        lo = np.concatenate([[0], np.cumsum(size)[:-1]])
        return cls(lo, size, int(size.sum()))


def imsi_of(idx: np.ndarray) -> np.ndarray:
    msin = (idx.astype(np.int64) * 7919 + 1_234_567) % 10**10  # bijective scramble (gcd(7919, 10^10) = 1)
    return np.char.add(IMSI_PREFIX, np.char.zfill(msin.astype(str), 10))


def msisdn_of(idx: np.ndarray) -> np.ndarray:
    num = (idx.astype(np.int64) * 104_729 + 55_555) % 10**9
    return np.char.add(MSISDN_PREFIX, np.char.zfill(num.astype(str), 9))


def generate_sessions(topo: Topology, ts: np.ndarray, step_minutes: float, kpi: KpiResult, subs: SubscriberBase,
                      sample_rate: float, rng: np.random.Generator) -> pd.DataFrame:
    step_s = step_minutes * 60
    # Attempts follow *expected* demand: subscribers keep trying even when the cell is down.
    lam = kpi.expected_users * SESSIONS_PER_USER_HOUR * (step_s / 3600) * sample_rate
    counts = rng.poisson(lam)
    t_i, c_i = np.nonzero(counts)
    reps = counts[t_i, c_i]
    t_i, c_i = np.repeat(t_i, reps), np.repeat(c_i, reps)
    n = len(t_i)
    if n == 0:
        return pd.DataFrame(columns=SESSION_COLUMNS[:6] + SESSION_COLUMNS[7:] + ["_event_time", "_emit_delay_s"])

    start = ts.astype("datetime64[s]")[t_i] + rng.uniform(0, step_s, n).astype("timedelta64[s]")
    svc_i = rng.choice(len(SERVICES), size=n, p=SERVICE_P)
    svc = SERVICES[svc_i]
    med, sig, rate, ulr = (np.array([SERVICE_PARAMS[s][k] for s in SERVICES])[svc_i] for k in range(4))
    dnn = np.array([SERVICE_PARAMS[s][4] for s in SERVICES])[svc_i]
    dur = med * rng.lognormal(0, 1, n) ** sig

    sel = (t_i, c_i)
    silent = kpi.silent[sel]
    avail, rrc, attach, drop = kpi.avail[sel], kpi.rrc[sel], kpi.attach[sel], kpi.drop[sel]
    p_fail = np.where(silent, 0.97, 1 - (rrc / 100) * (attach / 100) * (avail / 100))
    p_drop = np.minimum(0.95, drop / 100 * (1 + dur / 300))
    u1, u2 = rng.random(n), rng.random(n)
    failed = u1 < p_fail
    dropped = ~failed & (u2 < p_drop)
    dur = np.where(failed, 0.0, np.where(dropped, dur * rng.uniform(0.05, 0.9, n), dur))

    peak = topo.cells["peak_dl_mbps"].to_numpy()[c_i]
    radio = np.clip(kpi.dl[sel] / (0.5 * peak), 0.05, 1.0)
    bytes_dl = np.round(dur * rate * radio * 1e6 / 8 * rng.lognormal(0, 0.4, n)).astype(np.int64)
    bytes_ul = np.round(bytes_dl * ulr * rng.lognormal(0, 0.3, n)).astype(np.int64)

    no_service = silent | (avail < 50)
    attach_dominant = (100 - attach) > (100 - rrc)
    cause = np.select(
        [failed & no_service, failed & attach_dominant, failed, dropped & (radio < 0.5), dropped],
        ["NO_SERVICE", "ATTACH_REJECT_CONGESTION", "RRC_SETUP_FAILURE", "TRANSPORT_TIMEOUT", "RADIO_LINK_FAILURE"],
        default="NORMAL_RELEASE")
    outcome = np.select([failed, dropped], ["SETUP_FAILED", "DROPPED"], default="COMPLETED")

    roam = rng.random(n) < ROAM_P
    home = subs.pool_lo[c_i] + (rng.random(n) * subs.pool_size[c_i]).astype(np.int64)
    sub = np.where(roam, rng.integers(0, subs.n, n), home)
    end = start + np.round(dur).astype("timedelta64[s]")
    stamp = np.datetime_as_string(ts[0].astype("datetime64[m]"), unit="m").replace("-", "").replace(":", "")
    df = pd.DataFrame({
        "record_id": np.char.add(f"S-{stamp}-", np.char.zfill(np.arange(n).astype(str), 7)),
        "imsi": imsi_of(sub),
        "msisdn": msisdn_of(sub),
        "cell_id": topo.cells["element_id"].to_numpy()[c_i],
        "start_ts": to_iso(start),
        "end_ts": to_iso(end),
        "duration_s": np.round(dur).astype(np.int64),
        "service_type": svc,
        "dnn": dnn,
        "bytes_dl": bytes_dl,
        "bytes_ul": bytes_ul,
        "outcome": outcome,
        "cause_code": cause,
    })
    # xDRs are emitted when the session closes.
    df["_event_time"] = start
    df["_emit_delay_s"] = (end - start).astype(np.int64) + rng.uniform(5, 90, n)
    return df
