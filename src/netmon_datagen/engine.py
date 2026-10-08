"""Shared generation engine used by both batch history and streaming modes."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from netmon_datagen.alarms import ALARM_COLUMNS, expand_events, select_flapping
from netmon_datagen.config import GeneratorConfig, rng_for
from netmon_datagen.dq import inject_defects
from netmon_datagen.faults import Incident, compute_effects
from netmon_datagen.io import Spool, ordered, write_frame
from netmon_datagen.kpis import generate_kpis
from netmon_datagen.sessions import SESSION_COLUMNS, SubscriberBase, generate_sessions
from netmon_datagen.topology import build_topology

KPI_COLUMNS_OUT = ["record_id", "event_ts", "emitted_ts", "cell_id", "granularity_s", "availability_pct",
                   "active_users", "prb_util_pct", "rrc_setup_success_pct", "attach_success_pct",
                   "session_drop_rate_pct", "dl_throughput_mbps", "ul_throughput_mbps", "latency_ms",
                   "packet_loss_pct"]
COLUMNS = {"kpis": KPI_COLUMNS_OUT, "alarms": ALARM_COLUMNS, "sessions": SESSION_COLUMNS}
FEEDS = list(COLUMNS)
DQ_LOG = "dq_injections"  # spool key for DQ-log rows awaiting their record's emission (streaming)


def stamp(t: np.datetime64) -> str:
    return np.datetime_as_string(np.datetime64(t, "s"), unit="s").replace("-", "").replace(":", "")


def config_dict(cfg: GeneratorConfig) -> dict:
    return dataclasses.asdict(cfg)


class Engine:
    def __init__(self, cfg: GeneratorConfig):
        self.cfg = cfg
        self.topo = build_topology(cfg.scale, cfg.seed)
        self.subs = SubscriberBase.build(self.topo, cfg.scale.subscribers)
        self.flappers = select_flapping(self.topo, cfg.faults, cfg.seed)
        self.spool = Spool()
        self.generated = dict.fromkeys(FEEDS, 0)
        # Streaming bookkeeping: an observer called with (feed, post-DQ frame) for every generated batch of
        # records, and private emission/event times on DQ-log rows so they can be spooled with their records.
        self.observer: Callable[[str, pd.DataFrame], None] | None = None
        self.dq_log_times = False

    # -- reference data ---------------------------------------------------------------------------
    def write_topology(self, out: Path, fmt: str) -> None:
        nodes = self.topo.public_nodes()
        write_frame(nodes, out / "topology_nodes" / f"part-00000.{fmt}", fmt)
        write_frame(self.topo.edges, out / "topology_edges" / f"part-00000.{fmt}", fmt)

    # -- event generation -------------------------------------------------------------------------
    def _finish(self, df: pd.DataFrame, feed: str, key: str) -> pd.DataFrame:
        """Assign emission time, inject DQ defects, push to the spool. Returns the DQ log."""
        if df.empty:
            return pd.DataFrame()
        self.generated[feed] += len(df)
        df = ordered(df, [c for c in COLUMNS[feed] if c != "emitted_ts"])
        df["_emitted"] = df["_event_time"].to_numpy() + np.round(df["_emit_delay_s"].to_numpy()).astype(
            "timedelta64[s]")
        df, log = inject_defects(df, feed, self.cfg.dq, rng_for(self.cfg.seed, "dq", feed, key), self.cfg.fmt)
        if len(log) and self.dq_log_times:
            # Private emission/event time of the logged record (first delivery for duplicates), so the log
            # can be spooled and released together with the record it describes.
            first = df.groupby("record_id", sort=False).agg(_emitted=("_emitted", "min"),
                                                            _event_time=("_event_time", "first"))
            log = log.join(first, on="record_id")
        if self.observer is not None:
            self.observer(feed, df)
        self.spool.push(feed, df)
        return log

    def period(self, ts: np.ndarray, step_minutes: float, incidents: list[Incident], key: str) -> list[pd.DataFrame]:
        ts = ts.astype("datetime64[s]")
        step_s = step_minutes * 60
        t_lo, t_hi = ts[0], ts[-1] + np.timedelta64(int(step_s), "s")
        active = [i for i in incidents if len(i.cell_idx) and i.onset.min() < t_hi and i.cell_end.max() > t_lo]
        eff = compute_effects(active, self.topo.n_cells, ts, step_s)
        kpi = generate_kpis(self.topo, ts, step_minutes, eff, rng_for(self.cfg.seed, "kpi", key))
        sess = generate_sessions(self.topo, ts, step_minutes, kpi, self.subs, self.cfg.scale.session_sample_rate,
                                 rng_for(self.cfg.seed, "sessions", key))
        return [self._finish(kpi.frame, "kpis", key), self._finish(sess, "sessions", key)]

    def alarms(self, rows: list[dict], key: str, not_before: np.datetime64 | None = None) -> list[pd.DataFrame]:
        ev = expand_events(rows, self.topo, rng_for(self.cfg.seed, "alarm-events", key))
        if not_before is not None and len(ev):
            ev = ev[ev["_event_time"].to_numpy() >= np.datetime64(not_before, "s")]
        return [self._finish(ev, "alarms", key)]
