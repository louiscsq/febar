"""Detection scoring against ground truth. These definitions are what `netmon_eval` computes in Spark SQL;
the Python versions are unit-tested and document the contract.

Scored incidents: `is_customer_impacting AND NOT is_censored` (censored rows were not fully observed).

Two separate metrics, because step-2 detection is per cell by design and naming the root is step 3's job:

(a) **Customer-impact detection** (`impact_*`): the first detection on any element of the incident's
    footprint (its roots, `affected_element_ids`, `affected_cell_ids`) whose signal overlaps the impact
    window (+ `MATCH_SLACK_S`). TTD = that detection's availability (evidence time + measured pipeline
    latency for live files) minus `impact_start_ts`. This is the 5-minute SLA metric.
(b) **Root-element localisation** (`root_localised`, `localisation_*`): a detection, or the topology
    rollup, lands on an element of `root_element_ids` (falling back to `root_element_id`). For cluster
    faults any one of the roots counts.

Detection precision labels each detection by the ground truth it overlaps, in priority order: uncensored
fault (TP), censored incident (excluded), planned work (suppressed when `in_maintenance`, else FP), red
herring (FP), nothing (FP).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence

SLA_S = 300  # 5-minute detection SLA
ALERT_GAP_S = 600  # a detection starting > 10 min after the element's previous signal ended is a new alert
MATCH_SLACK_S = 600


def roots(inc: Mapping) -> set[str]:
    return set(inc.get("root_element_ids") or ()) or {inc["root_element_id"]}


def incident_elements(inc: Mapping) -> set[str]:
    """The impact footprint: roots plus every affected element and cell."""
    ids = roots(inc)
    for key in ("root_element_ids", "affected_element_ids", "affected_cell_ids"):
        ids.update(inc.get(key) or ())
    return ids


def is_scored(inc: Mapping) -> bool:
    return bool(inc.get("is_customer_impacting")) and not inc.get("is_censored") and inc.get(
        "impact_start_s") is not None


def matches(det: Mapping, inc: Mapping) -> bool:
    """`det`: element_id, signal_start_s, signal_end_s. `inc`: ids plus impact_start_s / impact_end_s."""
    if det["element_id"] not in incident_elements(inc):
        return False
    end = inc.get("impact_end_s") if inc.get("impact_end_s") is not None else math.inf
    return det["signal_end_s"] > inc["impact_start_s"] and det["signal_start_s"] < end + MATCH_SLACK_S


def time_to_detect(inc: Mapping, dets: Iterable[Mapping]) -> float | None:
    """Seconds from impact start to the first matching detection's availability (`available_s`)."""
    times = [d["available_s"] for d in dets if same_run(d, inc) and matches(d, inc)]
    return max(0.0, min(times) - inc["impact_start_s"]) if times else None


def percentile(values: Sequence[float], q: float) -> float | None:
    """Linear-interpolated percentile (as Spark's `percentile`, not `percentile_approx`)."""
    v = sorted(values)
    if not v:
        return None
    pos = (len(v) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def summarise(ttds: Sequence[float | None], sla_s: float = SLA_S) -> dict:
    """Undetected incidents (None) count against the within-SLA share but not the TTD percentiles."""
    det = [t for t in ttds if t is not None]
    n = len(ttds)
    return {
        "n_incidents": n,
        "n_detected": len(det),
        "detected_pct": round(100.0 * len(det) / n, 1) if n else None,
        "median_ttd_s": percentile(det, 0.5),
        "p90_ttd_s": percentile(det, 0.9),
        "within_sla_pct": round(100.0 * sum(t <= sla_s for t in det) / n, 1) if n else None,
    }


def rca_hit(candidates: Sequence[str], root_element_ids: Sequence[str], k: int = 1) -> bool:
    """Is any of the top-k ranked candidates a true root? Cluster faults list every root site/link."""
    roots = set(root_element_ids)
    return any(c in roots for c in candidates[:k])


def localisation_time(inc: Mapping, dets: Iterable[Mapping], rollup: Iterable[Mapping] = ()) -> float | None:
    """Seconds from impact start until a detection, or a rollup row (`element_id`, `available_s`,
    `qualifies`), lands on a root element. None if the root is never localised."""
    first = first_localisation(inc, dets, rollup)
    return max(0.0, first[0] - inc["impact_start_s"]) if first else None


def same_run(x: Mapping, inc: Mapping) -> bool:
    """Evidence only counts for an incident of the same generator run (`source_run`, when given)."""
    return x.get("source_run", inc.get("source_run")) == inc.get("source_run")


def first_localisation(inc: Mapping, dets: Iterable[Mapping], rollup: Iterable[Mapping] = ()) -> tuple | None:
    """(available_s, element_id) of the earliest detection or qualifying rollup row on a root element of
    the same run: the time and the element always come from the same row (SQL: min(struct(ts, element)))."""
    r = roots(inc)
    cands = [(d["available_s"], d["element_id"]) for d in dets
             if d["element_id"] in r and same_run(d, inc) and matches(d, inc)]
    cands += [(x["available_s"], x["element_id"]) for x in rollup
              if x["element_id"] in r and x.get("qualifies", True) and same_run(x, inc)]
    return min(cands) if cands else None


LABEL_PRIORITY = ("fault", "censored", "planned", "red_herring")


def label_detection(matched: Iterable[Mapping]) -> str:
    """Label of a detection given the incidents it overlaps (`event_class`, `is_censored`)."""
    found = set()
    for inc in matched:
        found.add("censored" if inc.get("is_censored") else inc["event_class"])
    return next((x for x in LABEL_PRIORITY if x in found), "unexplained")


def fault_precision(labelled: Iterable[tuple[str, bool]]) -> dict:
    """`labelled`: (label, in_maintenance) per detection."""
    n = {"fault": 0, "censored": 0, "planned_suppressed": 0, "planned_fp": 0, "red_herring": 0, "unexplained": 0}
    for label, in_maint in labelled:
        key = ("planned_suppressed" if in_maint else "planned_fp") if label == "planned" else label
        n[key] += 1
    fp = n["planned_fp"] + n["red_herring"] + n["unexplained"]
    planned = n["planned_suppressed"] + n["planned_fp"]
    return {**n, "fault_precision_pct": round(100.0 * n["fault"] / (n["fault"] + fp), 1) if n["fault"] + fp else None,
            "maintenance_suppression_pct": round(100.0 * n["planned_suppressed"] / planned, 1) if planned else None}


def alerts(dets: Iterable[Mapping], gap_s: float = ALERT_GAP_S) -> list[list[Mapping]]:
    """Group detection rows into alerts: per (source_run, element_id), a detection belongs to the current
    alert (one page to the NOC) unless it starts more than `gap_s` after the previous signal ended. Measuring
    from the previous end keeps back-to-back 15-minute history periods in one alert."""
    by_key: dict[tuple, list[Mapping]] = {}
    for d in dets:
        by_key.setdefault((d.get("source_run"), d["element_id"]), []).append(d)
    out = []
    for rows in by_key.values():
        rows = sorted(rows, key=lambda d: d["signal_start_s"])
        cur = [rows[0]]
        for prev, d in zip(rows, rows[1:], strict=False):
            if d["signal_start_s"] - prev.get("signal_end_s", prev["signal_start_s"]) > gap_s:
                out.append(cur)
                cur = []
            cur.append(d)
        out.append(cur)
    return out


def alert_label(alert: Sequence[Mapping]) -> tuple[str, bool]:
    """An alert takes the highest-priority label of its detections; it is suppressed (maintenance) when
    its first detection, the one that would page, is in a change window."""
    labels = {d["label"] for d in alert}
    label = next((x for x in (*LABEL_PRIORITY, "unexplained") if x in labels), "unexplained")
    first = min(alert, key=lambda d: d["signal_start_s"])
    return label, bool(first.get("in_maintenance"))
