"""Candidate generation and detection-time features for the root-cause ranker.

A **case** is one impact cluster the NOC sees at decision time `t`: impacted cells (degraded in a recent
real-time window, or silent) grouped under their highest ancestor of which at least half the cells are
impacted (no ground truth involved), so two independent faults in one region become two cases. The
**candidates** of a case are every ancestor of its impacted cells (cell, site, backhaul link, aggregation
router, UPF, AMF) plus alarmed elements nearby: elements with an active alarm under one of the case's
routers, alarmed elements above router level in the region, and elements with an active service-down alarm
(which form a case of their own when no impacted cell is near them, e.g. a dark site).

Only what the NOC could see at `t` is used:

- KPI windows come from `gold_cell_health_1m` (real-time, on-time records only). A window is visible at
  `t` only if its `evidence_ts <= t`. The current window is the latest one most cells had delivered by `t`.
- Alarms (`silver_alarms`) count only if their RAISE had arrived by `t` (`evidence_ts`), was raised in
  the last hour, and no CLEAR had arrived by `t`.
- The change calendar (`silver_maintenance_windows`) is operational data the NOC has in advance.
- No ground-truth column is an input (`FEATURE_COLUMNS` is checked against `LABEL_COLUMNS` in the tests),
  and every row carries `feature_evidence_ts`, the latest arrival among the records it was built from,
  which is never later than `decision_ts`.

The topology has no link counters, so a link's (or any element's) "utilisation and latency trend" is the
trend of its descendant cells' PRB utilisation and latency deviation.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from netmon_pipeline.hierarchy import ANCESTORS, LEVEL

LOOKBACK_SLOTS = 15  # 1-minute windows used for "now" and the trend features
RECENT_SLOTS = 3  # a cell degraded in any of the last 3 visible windows counts as impacted now
ANOMALY_LOOKBACK_SLOTS = 60  # horizon for "time since first anomaly"
ALARM_LOOKBACK_MIN = 60  # alarms raised more than an hour ago are ignored (stale alarms never clear)
SLOT_S = 60
CLUSTER_DENSITY = 0.5  # an ancestor at least this impacted joins its impacted cells into one case

Z_METRICS = {  # short name -> gold_cell_health_1m column (baseline deviation of the window mean)
    "lat": "latency_ms_z", "loss": "packet_loss_pct_z", "thr": "dl_throughput_mbps_z",
    "rrc": "rrc_setup_success_pct_z", "drop": "session_drop_rate_pct_z",
}
RAW_METRICS = {"attach": "attach_success_pct", "avail": "min_availability_pct", "prb": "prb_util_pct"}
HEALTH_COLUMNS = ["source_run", "cell_id", "window_start", "evidence_ts", "is_degraded", "granularity_s",
                  *Z_METRICS.values(), *RAW_METRICS.values()]
ALARM_COLUMNS = ["alarm_id", "event_type", "element_id", "alarm_code", "severity", "event_ts", "evidence_ts",
                 "is_service_down"]

ALARM_CATEGORIES = {
    "link": {"LINK_DOWN", "LOS", "HIGH_BER", "RSL_LOW", "LINK_DEGRADED"},
    "power": {"MAINS_FAILURE", "BATTERY_LOW", "TEMPERATURE_HIGH"},
    "unreach": {"NE_UNREACHABLE", "NODE_DOWN", "CELL_OUT_OF_SERVICE", "S1_NG_LINK_FAILURE"},
    "core": {"GTPU_PATH_FAILURE", "USER_PLANE_CONGESTION", "SIGNALLING_OVERLOAD", "CORE_CPU_OVERLOAD",
             "PACKET_DROP_HIGH"},
}

ID_COLUMNS = ["source_run", "decision_ts", "region_code", "case_id", "element_id", "element_type",
              "feature_evidence_ts"]
FEATURE_COLUMNS = [
    "level", "log_n_desc_cells", "n_children",
    "n_impacted_cells", "impacted_fraction", "degraded_fraction", "silent_fraction", "coverage",
    "child_max_coverage", "impacted_children_fraction", "parent_impacted_fraction", "parent_coverage",
    *[f"{m}_{k}" for m in Z_METRICS for k in ("now", "slope5", "slope15", "vs_parent")],
    "attach_now", "attach_vs_parent", "avail_now", "prb_now", "prb_slope15", "impacted_fraction_slope15",
    "minutes_since_first_anomaly",
    "n_alarms", "n_critical_alarms", "n_major_alarms", "n_service_down_alarms",
    *[f"n_alarms_{c}" for c in ALARM_CATEGORIES], "alarm_age_min",
    "n_subtree_alarms", "n_subtree_service_down_alarms", "alarmed_children_fraction", "parent_n_alarms",
    "in_maintenance", "log_case_impacted_cells", "n_case_candidates",
]
# Ground-truth / label columns. None of these may ever be a model input.
LABEL_COLUMNS = ["incident_id", "event_class", "fault_type", "root_element_id", "root_element_type",
                 "root_element_ids", "affected_element_ids", "affected_cell_ids", "is_customer_impacting",
                 "is_censored", "impact_start_ts", "impact_end_ts", "start_ts", "end_ts", "severity",
                 "estimated_impacted_subscribers", "n_affected_cells", "label", "is_root", "case_label"]


class Topology:
    """Index over `silver_topology_nodes`: ancestor chains, descendant cells and children per element."""

    def __init__(self, nodes: pd.DataFrame):
        nodes = nodes.drop_duplicates("element_id").reset_index(drop=True)
        self.ids = nodes["element_id"].to_numpy(dtype=object)
        self.types = nodes["element_type"].to_numpy(dtype=object)
        self.level = nodes["element_type"].map(LEVEL).to_numpy(dtype=np.int64)
        self.region = nodes["region_code"].to_numpy(dtype=object)
        self.idx = {e: i for i, e in enumerate(self.ids)}
        parent = nodes["parent_id"].map(self.idx)
        self.parent = parent.fillna(-1).astype(np.int64).to_numpy()
        n = len(self.ids)
        self.chain: list[list[int]] = []  # self first, then each ancestor up to the AMF
        for i in range(n):
            ch, j = [i], self.parent[i]
            while j >= 0:
                ch.append(int(j))
                j = self.parent[j]
            self.chain.append(ch)
        self.children: list[list[int]] = [[] for _ in range(n)]
        for i in range(n):
            if self.parent[i] >= 0:
                self.children[self.parent[i]].append(i)
        self.cells = np.flatnonzero(self.types == "CELL")
        self.cell_pos = {int(e): k for k, e in enumerate(self.cells)}
        desc: list[list[int]] = [[] for _ in range(n)]
        for k, e in enumerate(self.cells):
            for a in self.chain[e]:
                desc[a].append(k)
        self.desc_cells = [np.asarray(d, dtype=np.int64) for d in desc]
        self.router_of = np.array([next((a for a in self.chain[i] if self.level[a] == LEVEL["AGG_ROUTER"]), -1)
                                   for i in range(n)], dtype=np.int64)
        self.regions = sorted({r for r in self.region if r is not None})
        self.region_cells = {r: np.flatnonzero(self.region[self.cells] == r) for r in self.regions}
        # cell chains as a dense [n_cells, 6] array (cell, site, backhaul, router, upf, amf)
        self.cell_chain = np.array([self.chain[e] for e in self.cells], dtype=np.int64)
        assert self.cell_chain.shape[1] == len(ANCESTORS) + 1


@dataclass
class _Alarms:
    elem: np.ndarray
    code: np.ndarray
    severity: np.ndarray
    service_down: np.ndarray
    raise_min: np.ndarray  # event time, minutes since t0
    raise_avail: np.ndarray  # first decision minute at which the RAISE had arrived
    clear_avail: np.ndarray  # first decision minute at which a CLEAR had arrived (inf if never)
    evidence_s: np.ndarray  # RAISE arrival, seconds since t0
    region: np.ndarray


def _minutes(ts: pd.Series, t0: pd.Timestamp) -> np.ndarray:
    return ((pd.to_datetime(ts, utc=True) - t0).dt.total_seconds() / SLOT_S).to_numpy(dtype=np.float64)


class RunState:
    """Dense per-minute arrays of one generator run (one `source_run`), built from the gold / silver tables.

    Decision time `t` is an integer minute since `t0`; a record is visible at `t` iff its evidence (arrival)
    time is `<= t0 + t minutes`."""

    def __init__(self, topo: Topology, health: pd.DataFrame, alarms: pd.DataFrame,
                 maintenance: pd.DataFrame | None = None, source_run: str | None = None):
        self.topo = topo
        if source_run is None:
            runs = health["source_run"].unique() if "source_run" in health else [None]
            if len(runs) > 1:
                raise ValueError(f"one RunState per source_run, got {list(runs)}")
            source_run = runs[0]
        self.source_run = source_run
        if "granularity_s" in health and (health["granularity_s"] > SLOT_S).any():
            raise ValueError("the RCA features need 1-minute KPI windows (granularity_s = 60)")
        ws = pd.to_datetime(health["window_start"], utc=True)
        self.t0 = ws.min().floor("min")
        slot = np.round(_minutes(ws, self.t0)).astype(np.int64)
        self.n_slots = int(slot.max()) + 1
        cell = health["cell_id"].map({topo.ids[e]: k for k, e in enumerate(topo.cells)})
        ok = cell.notna().to_numpy()
        slot, cell = slot[ok], cell[ok].astype(np.int64).to_numpy()
        h = health.loc[ok]
        shape = (self.n_slots, len(topo.cells))
        self.vals: dict[str, np.ndarray] = {}
        for name, col in {**Z_METRICS, **RAW_METRICS}.items():
            a = np.full(shape, np.nan, dtype=np.float32)
            a[slot, cell] = h[col].to_numpy(dtype=np.float32)
            self.vals[name] = a
        self.degraded = np.zeros(shape, dtype=bool)
        self.degraded[slot, cell] = h["is_degraded"].fillna(False).to_numpy(dtype=bool)
        ev_s = _minutes(h["evidence_ts"], self.t0) * SLOT_S
        self.evidence_s = np.full(shape, np.inf, dtype=np.float64)
        self.evidence_s[slot, cell] = ev_s
        self.avail = np.full(shape, np.iinfo(np.int32).max, dtype=np.int64)
        self.avail[slot, cell] = np.ceil(ev_s / SLOT_S - 1e-9).astype(np.int64)
        # Current window at decision time t: the latest slot that most of its reporting cells had delivered.
        med = np.full(self.n_slots, np.inf)
        df = pd.DataFrame({"slot": slot, "avail": self.avail[slot, cell]})
        m = df.groupby("slot")["avail"].median()
        med[m.index.to_numpy()] = m.to_numpy()
        med = np.where(np.isfinite(med), med, np.nan)
        med = pd.Series(med).ffill().fillna(np.inf).to_numpy()
        self._slot_ready = np.maximum.accumulate(med)
        self._alarms = self._index_alarms(alarms)
        self._maint = self._index_maintenance(maintenance)

    # -- indexing ------------------------------------------------------------------------------------

    def _index_alarms(self, alarms: pd.DataFrame) -> _Alarms:
        a = alarms[alarms["element_id"].isin(self.topo.idx)].copy()
        a["avail"] = np.ceil(_minutes(a["evidence_ts"], self.t0) - 1e-9)
        a["ev_s"] = _minutes(a["evidence_ts"], self.t0) * SLOT_S
        a["ev_min"] = _minutes(a["event_ts"], self.t0)
        r = a[a["event_type"] == "RAISE"].sort_values("avail").drop_duplicates("alarm_id")
        c = a[a["event_type"] == "CLEAR"].groupby("alarm_id")["avail"].min()
        elem = r["element_id"].map(self.topo.idx).to_numpy(dtype=np.int64)
        return _Alarms(
            elem=elem, code=r["alarm_code"].to_numpy(dtype=object), severity=r["severity"].to_numpy(dtype=object),
            service_down=r["is_service_down"].fillna(False).to_numpy(dtype=bool),
            raise_min=r["ev_min"].to_numpy(), raise_avail=r["avail"].to_numpy(),
            clear_avail=r["alarm_id"].map(c).fillna(np.inf).to_numpy(), evidence_s=r["ev_s"].to_numpy(),
            region=self.topo.region[elem])

    def _index_maintenance(self, m: pd.DataFrame | None) -> list[tuple[int, float, float]]:
        if m is None or m.empty:
            return []
        m = m[m["element_id"].isin(self.topo.idx)]
        return list(zip(m["element_id"].map(self.topo.idx), _minutes(m["planned_start_ts"], self.t0),
                        _minutes(m["planned_end_ts"], self.t0), strict=True))

    # -- time ------------------------------------------------------------------------------------------

    def ts(self, t: float) -> pd.Timestamp:
        return self.t0 + pd.Timedelta(minutes=float(t))

    def minute_of(self, ts) -> float:
        return (pd.Timestamp(ts).tz_convert("UTC") - self.t0).total_seconds() / SLOT_S

    def current_slot(self, t: int) -> int:
        """Latest window most cells had delivered by decision time t (-1 if none yet)."""
        return int(np.searchsorted(self._slot_ready, t, side="right")) - 1

    def decision_times(self, step: int = 1) -> np.ndarray:
        first = ANOMALY_LOOKBACK_SLOTS + 2
        return np.arange(first, self.n_slots + 2, step)

    # -- one case ----------------------------------------------------------------------------------------

    def case_features(self, t: int, region: str) -> pd.DataFrame | None:
        """Candidate rows with features for every case at decision time t in one region (None if nothing
        is impacted). A case is one impact cluster: impacted cells grouped under their highest ancestor whose
        descendant cells are at least `CLUSTER_DENSITY` impacted (GT-free), so concurrent independent faults in
        one region are ranked separately."""
        topo = self.topo
        cur = self.current_slot(t)
        if cur < ANOMALY_LOOKBACK_SLOTS:
            return None
        cells_r = topo.region_cells[region]
        lo = cur - ANOMALY_LOOKBACK_SLOTS + 1
        vis = self.avail[lo:cur + 1, cells_r] <= t  # [A, n_r] visible windows
        deg = self.degraded[lo:cur + 1, cells_r] & vis
        missing = ~vis
        silent_slot = np.zeros_like(missing)
        silent_slot[1:] = missing[1:] & missing[:-1]  # no window for two consecutive minutes: dark
        imp_slot = deg | silent_slot
        silent_now = silent_slot[-1]
        deg_now = deg[-RECENT_SLOTS:].any(axis=0)
        imp_now = deg_now | silent_now

        al = self._alarms
        a_sel = np.flatnonzero((al.region == region) & (al.raise_avail <= t) & (al.clear_avail > t)
                               & (al.raise_min >= t - ALARM_LOOKBACK_MIN))
        if not imp_now.any() and not al.service_down[a_sel].any():
            return None

        local = np.full(len(topo.cells), -1, dtype=np.int64)
        local[cells_r] = np.arange(len(cells_r))
        imp_cells = np.flatnonzero(imp_now)  # local indices
        chains = topo.cell_chain[cells_r[imp_cells]]  # [n_imp, 6] cell .. amf

        # -- clusters ---------------------------------------------------------------------------------
        chain_elems = np.unique(chains) if len(imp_cells) else np.array([], dtype=np.int64)
        frac = {int(e): float(imp_now[local[topo.desc_cells[e]]].mean()) for e in chain_elems}
        clusters: dict[int, list[int]] = {}  # head element -> impacted local cell indices
        for k, ch in zip(imp_cells, chains, strict=True):
            head = next(int(e) for e in ch[::-1] if frac[int(e)] >= CLUSTER_DENSITY)
            clusters.setdefault(head, []).append(int(k))
        cl_cands: dict[int, set[int]] = {h: set(np.unique(topo.cell_chain[cells_r[c]]).tolist())
                                         for h, c in clusters.items()}
        cl_routers = {h: {int(x) for x in topo.cell_chain[cells_r[c], 3]} for h, c in clusters.items()}
        for i in a_sel:  # alarmed elements nearby: same router, or above router level, or service-down
            e = int(al.elem[i])
            attached = False
            for h in clusters:
                if topo.level[e] < LEVEL["AGG_ROUTER"] or topo.router_of[e] in cl_routers[h] or e in cl_cands[h]:
                    cl_cands[h].add(e)
                    attached = True
            if al.service_down[i] and not attached:
                clusters.setdefault(e, [])
                cl_cands.setdefault(e, set()).update(topo.chain[e])
                cl_routers[e] = {int(topo.router_of[e])}

        cand_all = sorted(set().union(*cl_cands.values()))
        parents = sorted({int(topo.parent[e]) for e in cand_all if topo.parent[e] >= 0} - set(cand_all))
        units = cand_all + parents
        col = {e: j for j, e in enumerate(units)}
        nu = len(units)

        memb = np.zeros((len(cells_r), nu), dtype=np.float32)
        for j, e in enumerate(units):
            memb[local[topo.desc_cells[e]], j] = 1.0
        n_desc = memb.sum(axis=0)
        n_desc_safe = np.maximum(n_desc, 1.0)
        n_imp = imp_now.astype(np.float32) @ memb
        n_deg = deg_now.astype(np.float32) @ memb
        n_sil = silent_now.astype(np.float32) @ memb
        imp_frac = n_imp / n_desc_safe
        imp_series = (imp_slot.astype(np.float32) @ memb) / n_desc_safe  # [A, U]

        L = LOOKBACK_SLOTS
        vis_l = self.avail[cur - L + 1:cur + 1, cells_r] <= t
        series: dict[str, np.ndarray] = {}
        for name, arr in self.vals.items():
            v = np.where(vis_l, arr[cur - L + 1:cur + 1, cells_r], np.nan)
            ok = ~np.isnan(v)
            s = np.nan_to_num(v) @ memb
            c = ok.astype(np.float32) @ memb
            with np.errstate(invalid="ignore", divide="ignore"):
                series[name] = np.where(c > 0, s / np.maximum(c, 1), np.nan)  # [L, U] mean over desc cells

        def now(x):
            with _quiet():
                return np.nanmean(x[-RECENT_SLOTS:], axis=0)

        par = np.array([col.get(int(topo.parent[e]), -1) if topo.parent[e] >= 0 else -1 for e in units])

        def parent_of(x):
            return np.where(par >= 0, x[np.maximum(par, 0)], np.nan)

        f: dict[str, np.ndarray] = {}  # element-intrinsic features, one value per unit
        for m in Z_METRICS:
            x = series[m]
            f[f"{m}_now"] = now(x)
            f[f"{m}_slope5"] = _slope(x[-5:])
            f[f"{m}_slope15"] = _slope(x)
            f[f"{m}_vs_parent"] = f[f"{m}_now"] - parent_of(f[f"{m}_now"])
        f["attach_now"] = now(series["attach"])
        f["attach_vs_parent"] = f["attach_now"] - parent_of(f["attach_now"])
        f["avail_now"] = now(series["avail"])
        f["prb_now"] = now(series["prb"])
        f["prb_slope15"] = _slope(series["prb"])
        f["impacted_fraction_slope15"] = _slope(imp_series[-L:])
        # time since first anomaly: first slot in the last hour with at least half the current impact
        thr = np.maximum(0.5 * imp_frac, 1e-9)
        above = (imp_series >= thr[None, :]) & (imp_series > 0)
        first = np.where(above.any(axis=0), above.argmax(axis=0), above.shape[0])
        f["minutes_since_first_anomaly"] = np.where(n_imp > 0, (above.shape[0] - 1 - first).astype(np.float32), 0.0)
        f["level"] = topo.level[units].astype(np.float32)
        f["log_n_desc_cells"] = np.log1p(n_desc)
        f["n_children"] = np.array([len(topo.children[e]) for e in units], dtype=np.float32)
        f["n_impacted_cells"] = n_imp
        f["impacted_fraction"] = imp_frac
        f["degraded_fraction"] = n_deg / n_desc_safe
        f["silent_fraction"] = n_sil / n_desc_safe
        f["parent_impacted_fraction"] = parent_of(imp_frac)
        child_cols = [[col[c] for c in topo.children[e] if c in col] for e in units]
        f["impacted_children_fraction"] = np.array(
            [sum(n_imp[c] > 0 for c in cc) / len(topo.children[e]) if topo.children[e] else 0.0
             for cc, e in zip(child_cols, units, strict=True)], dtype=np.float32)

        cnt = {k: np.zeros(nu, dtype=np.float32) for k in (
            "n_alarms", "n_critical_alarms", "n_major_alarms", "n_service_down_alarms",
            *[f"n_alarms_{c}" for c in ALARM_CATEGORIES], "n_subtree_alarms", "n_subtree_service_down_alarms")}
        oldest = np.full(nu, np.nan, dtype=np.float32)
        alarmed_elems = set()
        for i in a_sel:
            e = int(al.elem[i])
            alarmed_elems.add(e)
            for a in topo.chain[e]:
                j = col.get(a)
                if j is not None:
                    cnt["n_subtree_alarms"][j] += 1
                    cnt["n_subtree_service_down_alarms"][j] += al.service_down[i]
            j = col.get(e)
            if j is not None:
                cnt["n_alarms"][j] += 1
                cnt["n_critical_alarms"][j] += al.severity[i] == "CRITICAL"
                cnt["n_major_alarms"][j] += al.severity[i] == "MAJOR"
                cnt["n_service_down_alarms"][j] += al.service_down[i]
                for c, codes in ALARM_CATEGORIES.items():
                    cnt[f"n_alarms_{c}"][j] += al.code[i] in codes
                age = t - al.raise_min[i]
                oldest[j] = age if np.isnan(oldest[j]) else max(oldest[j], age)
        f.update(cnt)
        f["alarm_age_min"] = np.nan_to_num(oldest, nan=0.0)
        f["parent_n_alarms"] = np.nan_to_num(parent_of(cnt["n_alarms"]), nan=0.0)
        f["alarmed_children_fraction"] = np.array(
            [sum(c in alarmed_elems for c in topo.children[e]) / len(topo.children[e]) if topo.children[e] else 0.0
             for e in units], dtype=np.float32)
        f["in_maintenance"] = np.array([float(any(m_e in topo.chain[e] and s <= t < en
                                                  for m_e, s, en in self._maint)) for e in units],
                                       dtype=np.float32)

        # -- one block of rows per cluster: case-relative features ---------------------------------------
        ev = self.evidence_s[lo:cur + 1, cells_r]
        ev_cells = np.where(vis, ev, -np.inf).max(axis=0)  # latest arrival used, per cell
        dts = self.ts(t)
        blocks = []
        for head, cl_cells in clusters.items():
            cand = sorted(cl_cands[head])
            idx = np.array([col[e] for e in cand], dtype=np.int64)
            size = len(cl_cells)
            in_cl = np.zeros(len(cells_r), dtype=np.float32)
            in_cl[cl_cells] = 1.0
            cov_u = (in_cl @ memb) / max(size, 1)  # share of the cluster's impacted cells under each unit
            row = {c: f[c][idx] for c in f}
            row["coverage"] = cov_u[idx]
            row["parent_coverage"] = np.where(par[idx] >= 0, cov_u[np.maximum(par[idx], 0)], np.nan)
            row["child_max_coverage"] = np.array([max((cov_u[c] for c in child_cols[j]), default=0.0) for j in idx],
                                                 dtype=np.float32)
            row["log_case_impacted_cells"] = np.full(len(idx), math.log1p(size), dtype=np.float32)
            row["n_case_candidates"] = np.full(len(idx), float(len(idx)), dtype=np.float32)
            out = pd.DataFrame({c: np.asarray(row[c], dtype=np.float32) for c in FEATURE_COLUMNS})
            # latest arrival among every record this case was built from (must be <= decision_ts)
            used = [ev_cells[local[topo.desc_cells[e]]].max() for e in cand if len(topo.desc_cells[e])]
            ev_used = max(used) if used else -np.inf
            if len(a_sel):
                ev_used = max(ev_used, float(al.evidence_s[a_sel].max()))
            out.insert(0, "feature_evidence_ts", self.t0 + pd.Timedelta(seconds=float(ev_used))
                       if np.isfinite(ev_used) else pd.NaT)
            out.insert(0, "element_type", topo.types[cand])
            out.insert(0, "element_id", topo.ids[cand])
            out.insert(0, "case_id", f"{self.source_run}|{region}|{dts:%Y%m%dT%H%M}|{topo.ids[head]}")
            out.insert(0, "region_code", region)
            out.insert(0, "decision_ts", dts)
            out.insert(0, "source_run", self.source_run)
            blocks.append(out)
        return pd.concat(blocks, ignore_index=True) if blocks else None

    def features(self, times: Iterable[int] | None = None, regions: Iterable[str] | None = None) -> pd.DataFrame:
        """Candidate feature rows for every (decision time, region) case that has something impacted."""
        times = self.decision_times() if times is None else times
        regions = list(regions or self.topo.regions)
        parts = [x for t in times for r in regions if (x := self.case_features(int(t), r)) is not None]
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=ID_COLUMNS + FEATURE_COLUMNS)


class _quiet:
    def __enter__(self):
        import warnings

        self._w = warnings.catch_warnings()
        self._w.__enter__()
        warnings.simplefilter("ignore", category=RuntimeWarning)

    def __exit__(self, *exc):
        self._w.__exit__(*exc)


def _slope(y: np.ndarray) -> np.ndarray:
    """Least-squares slope per column (per minute) over the rows that are not NaN; NaN if < 3 points."""
    x = np.arange(y.shape[0], dtype=np.float64)[:, None]
    w = ~np.isnan(y)
    n = w.sum(axis=0)
    yz = np.where(w, y, 0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        xm = (w * x).sum(axis=0) / n
        ym = yz.sum(axis=0) / n
        num = (w * (x - xm) * (yz - ym)).sum(axis=0)
        den = (w * (x - xm) ** 2).sum(axis=0)
        s = num / den
    return np.where(n >= 3, s, np.nan).astype(np.float32)
