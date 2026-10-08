"""Streaming mode: emit JSON micro-batch files to a landing directory (local path or /Volumes/...).

Each micro-batch advances simulated time by `step_seconds` (KPIs at that granularity, default 1 min)
and sleeps so that batches land every `interval_seconds` of wall-clock time (0 = as fast as possible).
Faults are scheduled live, one simulated hour at a time, and propagate exactly as in batch mode.
Ground truth for each incident is written when the incident starts, under ground_truth/.

Files are written atomically (dot-prefixed temp file + rename), so Auto Loader never sees partial files.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from netmon_datagen.alarms import background_alarms, flapping_incidents
from netmon_datagen.config import GeneratorConfig, rng_for
from netmon_datagen.engine import FEEDS, Engine, config_dict, stamp
from netmon_datagen.faults import Incident, incidents_frame, maintenance_frame, schedule_incidents
from netmon_datagen.io import write_frame, write_json_manifest, write_partitioned

HOUR = np.timedelta64(1, "h")


def _now_minute() -> np.datetime64:
    return np.datetime64(datetime.now(timezone.utc).replace(tzinfo=None, second=0, microsecond=0), "s")


def run_stream(cfg: GeneratorConfig, out_dir: str | Path, *, step_seconds: int = 60, interval_seconds: float = 60.0,
               max_batches: int | None = None, start: str | None = None,
               on_batch: Callable[[int, dict], None] | None = None, log=print) -> dict:
    cfg = cfg.with_(fmt="json")
    out = Path(out_dir)
    eng = Engine(cfg)
    topo = eng.topo
    t0 = np.datetime64(start.replace("Z", ""), "s") if start else _now_minute()
    step = np.timedelta64(int(step_seconds), "s")
    log(f"[netmon-datagen] streaming scale={cfg.scale.name} cells={topo.n_cells} start={t0}Z "
        f"step={step_seconds}s interval={interval_seconds}s -> {out}")

    eng.write_topology(out, "json")
    write_json_manifest(out / "_manifest.json", {"generator": "netmon-datagen", "mode": "stream",
                                                 "config": config_dict(cfg), "start": str(t0) + "Z",
                                                 "step_seconds": step_seconds})
    flaps = flapping_incidents(eng.flappers, topo, t0, t0 + np.timedelta64(3650, "D"), prefix="FLAP")
    if flaps:
        write_frame(incidents_frame(flaps, topo), out / "ground_truth" / "incidents" / "flapping.json", "json")

    active: list[Incident] = []
    pending_truth: list[Incident] = []
    hour = None
    totals = dict.fromkeys(FEEDS, 0)
    i = 0
    while max_batches is None or i < max_batches:
        wall = time.time()
        t = t0 + i * step
        bend = t + step
        name = f"batch-{stamp(t)}-{i:06d}"
        logs: list[pd.DataFrame] = []
        h = t.astype("datetime64[h]").astype("datetime64[s]")
        if hour is None or h != hour:
            hour = h
            new = schedule_incidents(topo, h, h + HOUR, cfg.faults, rng_for(cfg.seed, "stream-faults", str(h)),
                                     existing=active, id_prefix=f"INC-{stamp(h)[:10]}")
            active += new
            pending_truth += new
            mw = maintenance_frame(new)
            if len(mw):
                write_frame(mw, out / "maintenance_windows" / f"{name}.json", "json")
            rows = background_alarms(topo, h, cfg.seed, eng.flappers) + [a for inc in new for a in inc.alarms]
            logs += eng.alarms(rows, key=str(h), not_before=t0)

        logs += eng.period(np.array([t], dtype="datetime64[s]"), step_seconds / 60, active, key=str(t))

        due = [inc for inc in pending_truth if inc.start < bend]
        if due:
            pending_truth = [inc for inc in pending_truth if inc.start >= bend]
            day = str(t)[:10]
            write_frame(incidents_frame(due, topo), out / "ground_truth" / "incidents" / f"date={day}" / f"{name}.json",
                        "json")
        stats = {}
        for feed in FEEDS:
            df = eng.spool.release(feed, bend)
            totals[feed] += len(df)
            stats[feed] = len(df)
            write_partitioned(df, out, feed, "json", stem=name)
        logs = [x for x in logs if len(x)]
        if logs:
            write_frame(pd.concat(logs, ignore_index=True),
                        out / "ground_truth" / "dq_injections" / f"date={str(t)[:10]}" / f"{name}.json", "json")
        active = [inc for inc in active if inc.end + 2 * HOUR > t]
        stats.update(sim_time=str(t) + "Z", active_incidents=sum(1 for x in active if x.start <= t < x.end))
        if on_batch:
            on_batch(i, stats)
        else:
            log(f"  batch {i} {stats}")
        i += 1
        if max_batches is None or i < max_batches:
            time.sleep(max(0.0, interval_seconds - (time.time() - wall)))
    return {"batches": i, "written": totals}
