"""Detection scoring against ground truth: incident matching, time-to-detect and RCA hits.

These definitions are what `netmon_eval` computes in Spark SQL; the Python versions are used in the
unit tests and to cross-check the evidence summary.

- Scored incidents: `is_customer_impacting AND NOT is_censored` (censored rows were not fully observed).
- A detection matches an incident when its element is one of the incident's elements (the roots in
  `root_element_ids`, `affected_element_ids` or `affected_cell_ids`) and its signal time overlaps the
  impact window, allowing `MATCH_SLACK_S` for alarm and collection lag.
- Time-to-detect = first matching detection's availability time minus `impact_start_ts`, where
  availability = when the evidence reached the pipeline plus the measured pipeline latency.
- RCA hit: the candidate root is in `root_element_ids` (so any site of a bushfire cluster counts).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence

SLA_S = 300  # 5-minute detection SLA
MATCH_SLACK_S = 600


def incident_elements(inc: Mapping) -> set[str]:
    ids = {inc["root_element_id"]}
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
    times = [d["available_s"] for d in dets if matches(d, inc)]
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
