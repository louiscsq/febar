"""Which KPI records a real-time health window is built from, and when that window became observable.

One rule for both qualification and timing. The real-time windows (`gold_cell_health_1m` / `_5m`, and so
`gold_element_impact_5m` and rollup localisation) are built **only from on-time records** (`NOT is_late`).
Each window's `evidence_ts` is the latest arrival among exactly those records. So a window can only qualify
(degraded, or a cell silent) on evidence that had arrived by its `evidence_ts`, and never be timed by
records other than the ones that made it qualify.

Late records (delivered more than `rules.LATE_THRESHOLD_S` after their period) stay in silver and in the
separate `gold_cell_health_5m_retrospective` aggregate, which no time-to-detect or localisation metric
reads. Per-record detections from a late record are kept: they are timed at that record's own arrival,
so they can only make a time-to-detect later, never earlier.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

REALTIME_FILTER_SQL = "NOT is_late"


def realtime_window(rows: Iterable[Mapping], window_end_s: float, watermark_s: float) -> dict:
    """Python mirror of one real-time cell window. `rows`: is_late, degraded, evidence_s.

    Returns whether the window qualifies (degraded), whether the cell is silent (no on-time report), and
    the earliest time the window's state was observable: the latest arrival of the rows it is built from,
    and no earlier than the window closing behind the watermark."""
    used = [r for r in rows if not r.get("is_late")]
    closes = window_end_s + watermark_s
    if not used:
        return {"n_reports": 0, "silent": True, "degraded": False, "available_s": closes}
    return {"n_reports": len(used), "silent": False, "degraded": any(r.get("degraded") for r in used),
            "available_s": max(closes, max(r["evidence_s"] for r in used))}
