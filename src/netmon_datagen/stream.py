"""Streaming mode: emit JSON micro-batch files to a landing directory (local path or /Volumes/...).

Each micro-batch advances simulated time by `step_seconds` (KPIs at that granularity, default 1 min)
and sleeps so that batches land every `interval_seconds` of wall-clock time (0 = as fast as possible).
Faults are scheduled live, one simulated hour at a time, and propagate exactly as in batch mode.

Emission-ordering guarantees (a micro-batch "lands" at its simulated end time `t + step`):
- A record lands in the first micro-batch whose end is after its emission time (`emitted_ts`).
- Ground truth for an incident is written once it has fully played out (impact, recovery, alarms) *and*
  every associated record has landed: all its alarm RAISE/CLEAR events and every KPI record of its
  affected cells for a period overlapping the impact window, including DQ late arrivals and
  redeliveries. Within a micro-batch, feeds are written before ground truth.
- A DQ-log row is written in the micro-batch where the record it describes lands (first delivery for
  duplicates), never earlier, so every logged `record_id` exists in an emitted feed.
- When a bounded run stops (`max_batches`), the spool is flushed of every record whose event time was
  observed, together with its DQ-log rows; records (and log rows) for unobserved event times are
  dropped. Then incidents that finished but were still waiting for late records are written as
  normal, and incidents still in flight are written with `is_censored = true` and times clipped to
  the end of the observed window. Chronic flapping elements are written at start as open-ended
  (`end_ts` null, censored).

Files are written atomically (dot-prefixed temp file + rename), so Auto Loader never sees partial files.
"""

from __future__ import annotations

import dataclasses
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from netmon_datagen.alarms import background_alarms, flapping_incidents
from netmon_datagen.config import GeneratorConfig, rng_for
from netmon_datagen.engine import DQ_LOG, FEEDS, Engine, config_dict, stamp
from netmon_datagen.faults import Incident, incidents_frame, maintenance_frame, schedule_incidents
from netmon_datagen.io import write_frame, write_json_manifest, write_partitioned

HOUR = np.timedelta64(1, "h")


def _now_minute() -> np.datetime64:
    return np.datetime64(datetime.now(timezone.utc).replace(tzinfo=None, second=0, microsecond=0), "s")


def run_stream(cfg: GeneratorConfig, out_dir: str | Path, *, step_seconds: int = 60, interval_seconds: float = 60.0,
               max_batches: int | None = None, start: str | None = None,
               on_batch: Callable[[int, dict], None] | None = None, log=print) -> dict:
    # Faults are drawn per simulated hour, so a per-window minimum would mean one of each type every hour.
    cfg = cfg.with_(fmt="json", faults=dataclasses.replace(cfg.faults, min_per_type=0))
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
    flaps = flapping_incidents(eng.flappers, topo, t0, t0, prefix="FLAP")
    for f in flaps:  # chronic, open-ended condition: no end time yet
        f.is_censored = True
    if flaps:
        write_frame(incidents_frame(flaps, topo),
                    out / "ground_truth" / "incidents" / f"date={str(t0)[:10]}" / "flapping.json", "json")

    active: list[Incident] = []
    tracker = _EmissionTracker(step)
    eng.observer = tracker.observe
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
            # Nothing may start (or alarm) before the stream does; there is no upper bound while running.
            new = schedule_incidents(topo, max(h, t0), h + HOUR, cfg.faults,
                                     rng_for(cfg.seed, "stream-faults", str(h)), existing=active,
                                     id_prefix=f"INC-{stamp(h)[:11].replace('T', '')}", bounds=(t0, None))
            active += new
            tracker.add(new)
            mw = maintenance_frame(new)
            if len(mw):
                write_frame(mw, out / "maintenance_windows" / f"{name}.json", "json")
            rows = background_alarms(topo, h, cfg.seed, eng.flappers) + [a for inc in new for a in inc.alarms]
            logs += eng.alarms(rows, key=str(h), not_before=t0)

        logs += eng.period(np.array([t], dtype="datetime64[s]"), step_seconds / 60, active, key=str(t))
        for lg in logs:  # DQ-log rows wait in the spool for the record they describe
            eng.spool.push(DQ_LOG, lg)

        stats = {}
        for feed in FEEDS:
            df = eng.spool.release(feed, bend)
            totals[feed] += len(df)
            stats[feed] = len(df)
            write_partitioned(df, out, feed, "json", stem=name)
        finished = tracker.pop_due(bend)
        if finished:
            _write_truth(finished, topo, out, t, name)
        _write_dq(eng.spool.release(DQ_LOG, bend), out, t, name)
        active = [inc for inc in active if inc.end + 2 * HOUR > t]
        stats.update(sim_time=str(t) + "Z", active_incidents=sum(1 for x in active if x.start <= t < x.end))
        if on_batch:
            on_batch(i, stats)
        else:
            log(f"  batch {i} {stats}")
        i += 1
        if max_batches is None or i < max_batches:
            time.sleep(max(0.0, interval_seconds - (time.time() - wall)))

    # Bounded run finished: flush records (and their DQ-log rows) for observed event times, then write the
    # remaining ground truth: complete incidents as normal, in-flight ones censored.
    t_end = t0 + i * step
    final = f"batch-{stamp(t_end)}-final"
    for feed in FEEDS:
        df = eng.spool.release(feed, None)
        df = df[df["_event_time"].to_numpy() < t_end] if len(df) else df
        totals[feed] += len(df)
        write_partitioned(df, out, feed, "json", stem=final)
    complete = tracker.pop_complete(t_end)
    started = [inc for inc in tracker.pending if inc.extent()[0] < t_end]
    for inc in started:
        inc.is_censored, inc.observed_until = True, t_end
    if complete or started:
        _write_truth(complete + started, topo, out, t_end, final)
    dq = eng.spool.release(DQ_LOG, None)
    _write_dq(dq[dq["_event_time"].to_numpy() < t_end] if len(dq) else dq, out, t_end, final)
    return {"batches": i, "written": totals, "censored_incidents": len(started)}


class _EmissionTracker:
    """Incidents awaiting ground truth, with the latest emission time of their associated records.

    Associated records: the incident's alarm events (by alarm_id) and KPI records of its cells for any
    period overlapping the impact window. Every such record is generated before the incident's extent
    ends (KPI periods are generated in real time, alarms when the incident is scheduled), so once the
    extent has passed, `last_emit` is final."""

    def __init__(self, step: np.timedelta64) -> None:
        self.step = step
        self.pending: list[Incident] = []
        self._alarm_owner: dict[str, Incident] = {}

    def add(self, incs: list[Incident]) -> None:
        self.pending += incs
        for inc in incs:
            for a in inc.alarms:
                self._alarm_owner[a["alarm_id"]] = inc

    def observe(self, feed: str, df: pd.DataFrame) -> None:
        if df.empty or not self.pending:
            return
        emitted = df["_emitted"].to_numpy()
        if feed == "alarms":
            owner = df["alarm_id"].map(self._alarm_owner)
            hit = owner.notna().to_numpy()
            if hit.any():
                last = pd.Series(emitted[hit]).groupby(owner[hit].map(id).to_numpy()).max()
                for inc in {id(x): x for x in owner[hit]}.values():
                    self._bump(inc, last[id(inc)])
        elif feed == "kpis":
            ev, cell = df["_event_time"].to_numpy(), df["_cell"].to_numpy()
            for inc in self.pending:
                if not inc.customer_impacting:
                    continue
                m = (ev < inc.impact_end) & (ev + self.step > inc.impact_start) & np.isin(cell, inc.cell_idx)
                if m.any():
                    self._bump(inc, emitted[m].max())

    @staticmethod
    def _bump(inc: Incident, t) -> None:
        t = np.datetime64(t, "s")
        inc.last_emit = t if inc.last_emit is None else max(inc.last_emit, t)

    def _pop(self, keep) -> list[Incident]:
        out = [inc for inc in self.pending if not keep(inc)]
        self.pending = [inc for inc in self.pending if keep(inc)]
        for inc in out:
            for a in inc.alarms:
                self._alarm_owner.pop(a["alarm_id"], None)
        return out

    def pop_due(self, bend: np.datetime64) -> list[Incident]:
        """Incidents fully played out whose every associated record lands by `bend`."""
        return self._pop(lambda inc: not (inc.extent()[1] < bend and (inc.last_emit is None or inc.last_emit < bend)))

    def pop_complete(self, t_end: np.datetime64) -> list[Incident]:
        """At a bounded stop: incidents that played out before `t_end` (their records were just flushed)."""
        return self._pop(lambda inc: not inc.extent()[1] < t_end)


def _write_dq(df: pd.DataFrame, out: Path, t: np.datetime64, name: str) -> None:
    if len(df):
        write_frame(df, out / "ground_truth" / "dq_injections" / f"date={str(t)[:10]}" / f"{name}.json", "json")


def _write_truth(incs: list[Incident], topo, out: Path, t: np.datetime64, name: str) -> None:
    write_frame(incidents_frame(incs, topo), out / "ground_truth" / "incidents" / f"date={str(t)[:10]}" / f"{name}.json",
                "json")
