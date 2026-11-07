"""Step 6: the FROZEN collective-backhaul thresholds (`detection.COLLECTIVE_BACKHAUL`) on the repo's own generator output:
no firing on healthy links, and earlier than the per-cell rules on injected BACKHAUL_DEGRADATION ramps drawn with the
generator's onset / ramp / severity parameters (real `small` links, baseline from earlier days, out-of-sample days)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from netmon_pipeline import detection, windows

# -----------------------------------------------------------------------

def _simulate(n_links=24, base_days=8, seed=11):
    """Healthy days and one injected BACKHAUL_DEGRADATION per link (the generator's onset / ramp / severity draws), on
    real `small` links. Returns cell-window builders for a healthy day and the ramp day, plus the injected starts."""
    from netmon_datagen.config import get_preset
    from netmon_datagen.faults import FAULT_SPECS, Effects
    from netmon_datagen.kpis import generate_kpis, local_clock
    from netmon_datagen.topology import Topology, build_topology

    full = build_topology(get_preset("small"), 42)
    rng = np.random.default_rng(seed)
    pick = rng.choice(sorted(full.cells["backhaul_id"].unique()), n_links, replace=False)
    cells = full.cells[full.cells["backhaul_id"].isin(pick)].reset_index(drop=True)
    topo = Topology(nodes=full.nodes, edges=full.edges, cells=cells)
    n_c, ms = len(cells), detection.COLLECTIVE_METRICS
    t0 = np.datetime64("2026-10-01T00:00:00")

    def day(d, eff=None):
        ts = t0 + np.arange(d * 1440, (d + 1) * 1440).astype("timedelta64[m]")
        k = generate_kpis(topo, ts, 1, eff or Effects.zeros(1440, n_c), np.random.default_rng(1000 + d)).frame
        return {c: k[c].to_numpy(float).reshape(1440, n_c) for c in (*ms, "active_users", "prb_util_pct",
                                                                     "availability_pct")}

    days = base_days + 2
    hours, wkend = local_clock(t0 + np.arange(days * 1440).astype("timedelta64[m]"), topo.timezones)
    key = (np.arange(n_c)[None, :] * 48 + wkend[topo.cell_tz_idx].T.astype(int) * 24
           + np.floor(hours[topo.cell_tz_idx]).astype(int).T)
    hist = [day(d) for d in range(base_days)]
    base = {}
    for m in ms:
        v = np.concatenate([h[m] for h in hist]).ravel()
        kk = key[:base_days * 1440].ravel()
        n = np.bincount(kk, None, n_c * 48)
        s, ss = np.bincount(kk, v, n_c * 48), np.bincount(kk, v * v, n_c * 48)
        mean = s / np.maximum(n, 1)
        base[m] = (mean, np.sqrt(np.maximum(ss - n * mean * mean, 0) / np.maximum(n - 1, 1)))

    tsec = np.arange(1440) * 60.0
    eff = Effects.zeros(1440, n_c)
    starts = {}
    links = cells["backhaul_id"].to_numpy()
    spec = FAULT_SPECS["BACKHAUL_DEGRADATION"]
    for lk in pick:
        idx = np.flatnonzero(links == lk)
        start = rng.uniform(60, 1300) * 60.0
        onset = start + rng.uniform(0, 120, len(idx))
        ramp = rng.uniform(600, 1800)
        sev = rng.uniform(0.4, 1.0) * rng.uniform(0.85, 1.0, len(idx))
        ov0, ov1 = np.maximum(tsec[:, None], onset[None, :]), tsec[:, None] + 60
        inten = np.clip(ov1 - ov0, 0, None) / 60 * np.clip(((ov0 + ov1) / 2 - onset[None, :]) / ramp, 0, 1) * sev
        for f, coef in spec.coefs.items():
            getattr(eff, f)[:, idx] = np.maximum(getattr(eff, f)[:, idx], inten * coef)
        starts[lk] = start

    def windows_of(d, x):
        sl = slice(d * 1440, (d + 1) * 1440)
        kk = key[sl]
        out = []
        for t in range(1440):
            ws = int((t0 - np.datetime64("1970-01-01T00:00:00")).astype(int)) + (d * 1440 + t) * 60
            for c in range(n_c):
                r = {"source_run": "sim", "cell_id": cells.element_id[c], "backhaul_id": links[c],
                     "window_start_s": ws, "window_end_s": ws + 60, "evidence_s": ws + 60 + 20, "n_late_reports": 0,
                     "in_maintenance": False, "active_users": x["active_users"][t, c],
                     "prb_util_pct": x["prb_util_pct"][t, c], "flags": []}
                b = {}
                for m in ms:
                    r[m] = x[m][t, c]
                    b[f"b_{m}_mean"], b[f"b_{m}_std"] = base[m][0][kk[t, c]], base[m][1][kk[t, c]]
                r.update(b)
                r["flags"] = detection.flags_py({"availability_pct": x["availability_pct"][t, c],
                                                 **{m: x[m][t, c] for m in ms}}, b)
                out.append(r)
        return out

    healthy = windows_of(base_days, day(base_days))
    ramp_day = windows_of(base_days + 1, day(base_days + 1, eff))
    day0 = int((t0 - np.datetime64("1970-01-01T00:00:00")).astype(int)) + (base_days + 1) * 86400
    n_desc = pd.Series(links).value_counts().to_dict()
    return healthy, ramp_day, {lk: day0 + s for lk, s in starts.items()}, n_desc


@pytest.fixture(scope="module")
def sim():
    return _simulate()


def test_frozen_rule_never_fires_on_healthy_generator_output(sim):
    healthy, _ramp, _starts, n_desc = sim
    rows = windows.parent_health(healthy, n_desc)
    assert len(rows) == 1440 * len(n_desc)
    assert detection.COLLECTIVE_BACKHAUL.fires(rows) == []


def test_frozen_rule_fires_earlier_than_per_cell_on_an_injected_ramp(sim):
    _healthy, ramp, starts, n_desc = sim
    fired = detection.COLLECTIVE_BACKHAUL.fires(windows.parent_health(ramp, n_desc))
    gains, misses = [], 0
    for lk, start in starts.items():
        # per cell: a deviation rule fires on one of the link's cells (record-level timing: evidence 20 s after the
        # period); collective: windowed timing, window_end + watermark
        cell = [r["evidence_s"] for r in ramp if r["backhaul_id"] == lk and r["window_end_s"] > start
                and set(r["flags"]) - set(detection.HARD_RULE_NAMES)]
        coll = [d["available_s"] for d in fired if d["parent_id"] == lk and d["window_end_s"] > start]
        if not coll:
            misses += 1
            continue
        if cell:
            gains.append(min(cell) - min(coll))
    assert misses <= len(starts) // 10
    assert np.median(gains) > 120 and np.mean(np.array(gains) > 0) > 0.8
