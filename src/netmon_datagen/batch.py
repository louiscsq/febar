"""Batch history mode: N days of history written as date-partitioned Parquet or JSON lines.

Layout under `out`:
    topology_nodes/  topology_edges/                      reference (network inventory)
    kpis/date=*/  alarms/date=*/  sessions/date=*/          raw event feeds, partitioned by emitted date
    maintenance_windows/                                   change calendar (operational data)
    ground_truth/incidents/  ground_truth/dq_injections/   labels - never read by the pipeline itself
    _manifest.json
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from netmon_datagen.alarms import background_alarms, flapping_incidents
from netmon_datagen.config import GeneratorConfig, rng_for
from netmon_datagen.engine import FEEDS, Engine, config_dict
from netmon_datagen.faults import incidents_frame, maintenance_frame, schedule_incidents
from netmon_datagen.io import write_frame, write_json_manifest, write_partitioned

CHUNK_HOURS = 6  # KPI arrays are built per 6-hour chunk to bound memory at large scale


def resolve_start(cfg: GeneratorConfig) -> np.datetime64:
    if cfg.start:
        return np.datetime64(cfg.start.replace("Z", ""), "s").astype("datetime64[D]").astype("datetime64[s]")
    today = np.datetime64(datetime.now(timezone.utc).date().isoformat(), "D")
    return (today - np.timedelta64(cfg.days, "D")).astype("datetime64[s]")


def generate_history(cfg: GeneratorConfig, out_dir: str | Path, log=print) -> dict:
    t_wall = time.time()
    out = Path(out_dir)
    fmt = cfg.fmt
    eng = Engine(cfg)
    topo = eng.topo
    ws = resolve_start(cfg)
    we = ws + np.timedelta64(cfg.days, "D")
    log(f"[netmon-datagen] scale={cfg.scale.name} cells={topo.n_cells} sites="
        f"{(topo.nodes.element_type == 'SITE').sum()} window={ws}..{we} fmt={fmt} -> {out}")

    eng.write_topology(out, fmt)
    incidents = schedule_incidents(topo, ws, we, cfg.faults, rng_for(cfg.seed, "faults"), id_prefix="INC")
    incidents += flapping_incidents(eng.flappers, topo, ws, we)
    inc_df = incidents_frame(incidents, topo)
    write_frame(inc_df, out / "ground_truth" / "incidents" / f"part-00000.{fmt}", fmt)
    write_frame(maintenance_frame(incidents), out / "maintenance_windows" / f"part-00000.{fmt}", fmt)

    # Incident alarm lifecycles are bucketed by the day of their RAISE.
    inc_alarms: dict[int, list[dict]] = {}
    for inc in incidents:
        for a in inc.alarms:
            d = int(np.clip((a["raise_ts"] - ws) // np.timedelta64(1, "D"), 0, cfg.days - 1))
            inc_alarms.setdefault(d, []).append(a)

    step = np.timedelta64(cfg.step_minutes, "m")
    written = dict.fromkeys(FEEDS, 0)
    dq_total = 0
    for d in range(cfg.days):
        day0 = ws + np.timedelta64(d, "D")
        day1 = day0 + np.timedelta64(1, "D")
        logs = []
        for c in range(24 // CHUNK_HOURS):
            c0 = day0 + np.timedelta64(c * CHUNK_HOURS, "h")
            ts = np.arange(c0, c0 + np.timedelta64(CHUNK_HOURS, "h"), step).astype("datetime64[s]")
            logs += eng.period(ts, cfg.step_minutes, incidents, key=str(c0))
        rows = [r for h in range(24) for r in
                background_alarms(topo, day0 + np.timedelta64(h, "h"), cfg.seed, eng.flappers)]
        logs += eng.alarms(rows + inc_alarms.get(d, []), key=str(day0))
        for feed in FEEDS:
            df = eng.spool.release(feed, day1)
            written[feed] += len(df)
            write_partitioned(df, out, feed, fmt, stem=f"part-{d:05d}")
        dq_total += _write_dq(logs, out, fmt, str(day0)[:10], f"part-{d:05d}")
        log(f"  day {d + 1}/{cfg.days} {str(day0)[:10]} written ({time.time() - t_wall:.1f}s)")

    for feed in FEEDS:  # late records emitted after the window closes
        df = eng.spool.release(feed, None)
        written[feed] += len(df)
        write_partitioned(df, out, feed, fmt, stem="part-final")

    manifest = {
        "generator": "netmon-datagen", "mode": "batch", "config": config_dict(cfg),
        "window_start": str(ws) + "Z", "window_end": str(we) + "Z",
        "counts": {
            "topology_nodes": len(topo.nodes), "topology_edges": len(topo.edges), "cells": topo.n_cells,
            **{f"{k}_generated": v for k, v in eng.generated.items()},
            **{f"{k}_written": v for k, v in written.items()},
            "incidents": len(inc_df),
            "incidents_by_type": inc_df["fault_type"].value_counts().to_dict(),
            "dq_injections": dq_total,
        },
        "elapsed_s": round(time.time() - t_wall, 1),
    }
    write_json_manifest(out / "_manifest.json", manifest)
    log(f"[netmon-datagen] done in {manifest['elapsed_s']}s: {written}")
    return manifest


def _write_dq(logs: list[pd.DataFrame], out: Path, fmt: str, date: str, stem: str) -> int:
    logs = [x for x in logs if len(x)]
    if not logs:
        return 0
    df = pd.concat(logs, ignore_index=True)
    write_frame(df, out / "ground_truth" / "dq_injections" / f"date={date}" / f"{stem}.{fmt}", fmt)
    return len(df)
