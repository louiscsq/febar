"""Scoring of the offline collective-backhaul experiment against ground truth.

Ground truth enters ONLY here, after detections exist: `detection.CollectiveRule` and
`windows.parent_health(_sql)` never take an incident, label or `netmon_eval` table as input (tested). The
definitions follow `netmon_pipeline.scoring` (the step-2 contract), so "before" and "after" are measured the
same way:

- an incident is scored when customer-impacting and not censored; TTD = first matching detection's
  availability minus `impact_start`, clipped at 0; a detection matches when its element is in the incident's
  footprint and its signal overlaps the impact window (+ `MATCH_SLACK_S`);
- detections form alerts per (run, element) with the `ALERT_GAP_S` rule; an alert takes the highest-priority
  label of its rows (fault, censored, planned, red herring, else unexplained) and is suppressed when its
  first row is in a change window.

All times are epoch seconds (UTC).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence

from netmon_pipeline import scoring

BUSY_PRB_PCT = 70.0  # the generator's congestion knee (netmon_datagen.kpis): organic busy-hour degradation
LABEL_OVERLAP_PRE_S = 300  # a detection up to 5 min before an incident's start still overlaps it (_labelled_sql)
SMALL_LINK_MAX_CELLS = 6


def incident_window(inc: Mapping) -> tuple[float, float]:
    """The interval over which detections are labelled by `inc` (eval `_labelled_sql`)."""
    start = inc.get("start_s") if inc.get("start_s") is not None else inc["impact_start_s"]
    end = inc.get("end_s") if inc.get("end_s") is not None else inc.get("impact_end_s")
    return start - LABEL_OVERLAP_PRE_S, (math.inf if end is None else end + scoring.MATCH_SLACK_S)


class IncidentIndex:
    """Incidents indexed by footprint element, so labelling hundreds of thousands of rows stays cheap."""

    def __init__(self, incidents: Iterable[Mapping]):
        self.incidents = list(incidents)
        self.by_element: dict[str, list[int]] = {}
        for k, inc in enumerate(self.incidents):
            for e in scoring.incident_elements(inc):
                self.by_element.setdefault(e, []).append(k)
        self.windows = [incident_window(i) for i in self.incidents]

    def overlapping(self, det: Mapping, elements: Iterable[str] | None = None) -> list[Mapping]:
        """Incidents of the same run whose footprint holds one of `elements` (default: the detection's
        `label_element_id`, else its element) and whose labelling window overlaps the detection's signal."""
        els = elements if elements is not None else [det.get("label_element_id") or det["element_id"]]
        ks = sorted({k for e in els for k in self.by_element.get(e, ())})
        out = []
        for k in ks:
            inc = self.incidents[k]
            lo, hi = self.windows[k]
            if scoring.same_run(det, inc) and det["signal_end_s"] > lo and det["signal_start_s"] < hi:
                out.append(inc)
        return out


def _index(incidents) -> IncidentIndex:
    return incidents if isinstance(incidents, IncidentIndex) else IncidentIndex(incidents)


def score_incidents(incidents: Sequence[Mapping], collective: Sequence[Mapping],
                    before_available_s: Mapping[tuple[str, str], float | None],
                    n_desc_cells: Mapping[str, int]) -> list[dict]:
    """Per scored incident: per-cell first availability (`before`, the published step-2 metric (a)),
    collective first availability, and the combined detector (whichever is first), each as a TTD."""
    out = []
    for inc in incidents:
        if not scoring.is_scored(inc):
            continue
        t0 = inc["impact_start_s"]
        b = before_available_s.get((inc["source_run"], inc["incident_id"]))
        c = scoring.time_to_detect(inc, collective)
        c_av = None if c is None else min(d["available_s"] for d in collective
                                          if scoring.same_run(d, inc) and scoring.matches(d, inc))
        both = [x for x in (b, c_av) if x is not None]
        link = inc["root_element_id"]
        out.append({
            "source_run": inc["source_run"], "incident_id": inc["incident_id"], "fault_type": inc["fault_type"],
            "root_element_id": link, "n_desc_cells": n_desc_cells.get(link),
            "before_ttd_s": None if b is None else max(0.0, b - t0), "collective_ttd_s": c,
            "combined_ttd_s": max(0.0, min(both) - t0) if both else None,
        })
    return out


def summary(rows: Sequence[Mapping], key: str, sla_s: float = scoring.SLA_S) -> dict:
    return scoring.summarise([r[key] for r in rows], sla_s)


def label_rows(dets: Sequence[Mapping], incidents) -> list[dict]:
    """Each detection with its step-2 label and the fault types of the uncensored faults it overlaps. A row
    may carry `label_element_id` (the cell a per-cell detection is on) when `element_id` is its link."""
    idx = _index(incidents)
    out = []
    for d in dets:
        hit = idx.overlapping(d)
        out.append({**d, "label": scoring.label_detection(hit),
                    "fault_types": sorted({i["fault_type"] for i in hit
                                           if i["event_class"] == "fault" and not i.get("is_censored")})})
    return out


def alert_table(dets: Sequence[Mapping], incidents, members: Mapping[str, set[str]] | None = None) -> list[dict]:
    """Alerts from detection rows (per run x element, `scoring.alerts`), labelled. For an unexplained alert,
    `nearby` lists the incidents (class / fault type) that touch one of the element's members (its cells or
    sites) while the alert runs, and `busy_hour` says the first row's weighted PRB was past the knee."""
    idx = _index(incidents)
    out = []
    for a in scoring.alerts(label_rows(dets, idx)):
        label, suppressed = scoring.alert_label(a)
        first = min(a, key=lambda d: d["signal_start_s"])
        span = {"source_run": first.get("source_run"), "element_id": first["element_id"],
                "signal_start_s": first["signal_start_s"], "signal_end_s": max(d["signal_end_s"] for d in a)}
        near = []
        if label == "unexplained" and members is not None:
            near = sorted({f"{i['event_class']}:{i['fault_type']}"
                           for i in idx.overlapping(span, members.get(first["element_id"], ()))})
        prb = first.get("w_prb_util_pct")
        out.append({**span, "n_rows": len(a), "label": label, "suppressed": suppressed,
                    "fault_types": sorted({f for d in a for f in d["fault_types"]}), "nearby": near,
                    "busy_hour": prb is not None and prb >= BUSY_PRB_PCT, "first_available_s": first.get("available_s")})
    return out


def is_false_alarm(a: Mapping) -> bool:
    """A page the NOC should not have received: unexplained, red herring, or planned work not suppressed."""
    return a["label"] in ("unexplained", "red_herring") or (a["label"] == "planned" and not a["suppressed"])


def _union_length(intervals: list[tuple[float, float]], lo: float, hi: float) -> float:
    total, cur_lo, cur_hi = 0.0, None, None
    for a, b in sorted((max(a, lo), min(b, hi)) for a, b in intervals):
        if b <= a:
            continue
        if cur_hi is None or a > cur_hi:
            if cur_hi is not None:
                total += cur_hi - cur_lo
            cur_lo, cur_hi = a, b
        else:
            cur_hi = max(cur_hi, b)
    if cur_hi is not None:
        total += cur_hi - cur_lo
    return total


def healthy_link_days(links: Iterable[str], members: Mapping[str, set[str]], incidents: Sequence[Mapping],
                      source_run: str, lo_s: float, hi_s: float) -> float:
    """Link-days in [lo_s, hi_s) outside every ground-truth footprint (any class, censored included) that
    touches the link, one of its cells or one of its sites."""
    inc = [i for i in incidents if i["source_run"] == source_run]
    foot = [(scoring.incident_elements(i), incident_window(i)) for i in inc]
    total = 0.0
    for link in links:
        els = {link} | set(members.get(link, ()))
        busy = [w for e, w in foot if e & els]
        total += (hi_s - lo_s) - _union_length(busy, lo_s, hi_s)
    return total / 86400.0


def false_alarm_summary(alerts: Sequence[Mapping], link_days: float) -> dict:
    fa = [a for a in alerts if is_false_alarm(a)]
    unexpl = [a for a in alerts if a["label"] == "unexplained"]
    per100 = (lambda n: round(100.0 * n / link_days, 2)) if link_days else (lambda n: None)
    return {
        "n_alerts": len(alerts), "n_fault_tp": sum(a["label"] == "fault" for a in alerts),
        "n_censored": sum(a["label"] == "censored" for a in alerts),
        "n_planned_suppressed": sum(a["label"] == "planned" and a["suppressed"] for a in alerts),
        "n_false_alarms": len(fa), "n_unexplained": len(unexpl),
        "n_red_herring": sum(a["label"] == "red_herring" for a in alerts),
        "n_planned_unsuppressed": sum(a["label"] == "planned" and not a["suppressed"] for a in alerts),
        "healthy_link_days": round(link_days, 2),
        "false_alarms_per_100_link_days": per100(len(fa)),
        "unexplained_per_100_link_days": per100(len(unexpl)),
        "unexplained_busy_hour": sum(a["busy_hour"] for a in unexpl),
        "unexplained_near_traffic_surge": sum(any("TRAFFIC_SURGE" in x for x in a["nearby"]) for a in unexpl),
        "unexplained_near_other_incident": sum(bool(a["nearby"]) and not any("TRAFFIC_SURGE" in x for x in a["nearby"])
                                               for a in unexpl),
    }
