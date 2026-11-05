"""Real-time windows: qualification and timing come from the same (on-time) record set."""

from __future__ import annotations

from netmon_pipeline import rules, scoring, windows

WM = 120  # gold HEALTH_WATERMARK, 2 minutes
INC = {"incident_id": "INC-1", "root_element_id": "CELL-A", "root_element_ids": ["CELL-A"],
       "affected_element_ids": [], "affected_cell_ids": ["CELL-A"], "impact_start_s": 1000, "impact_end_s": 4000,
       "is_customer_impacting": True, "is_censored": False, "source_run": "history"}


def row(late, degraded, evidence_s):
    return {"is_late": late, "degraded": degraded, "evidence_s": evidence_s}


def test_late_row_that_would_qualify_the_window_is_excluded():
    # Window [1000, 1300): the only degraded record arrives 36 h late; an on-time healthy one at 1310.
    w = windows.realtime_window([row(False, False, 1310), row(True, True, 1300 + 36 * 3600)], 1300, WM)
    assert w["degraded"] is False and w["n_reports"] == 1
    # So no rollup localisation can be produced from this window, at any time.
    roll = [{"element_id": "CELL-A", "available_s": w["available_s"], "qualifies": w["degraded"],
             "source_run": "history"}]
    assert scoring.localisation_time(INC, [], roll) is None


def test_window_is_timed_by_the_rows_that_made_it_qualify():
    # An early healthy row at 1305 and the degrading on-time row arriving at 1590: available no earlier
    # than 1590, never at 1305 (the old behaviour timed by unrelated earlier evidence).
    w = windows.realtime_window([row(False, False, 1305), row(False, True, 1590)], 1300, WM)
    assert w["degraded"] and w["available_s"] >= 1590
    roll = [{"element_id": "CELL-A", "available_s": w["available_s"], "qualifies": w["degraded"]}]
    assert scoring.localisation_time(INC, [], roll) >= 1590 - INC["impact_start_s"]


def test_window_with_only_late_rows_is_silent_and_timed_at_close():
    # In real time the cell had not reported: silent, observable once the window closed behind the watermark.
    w = windows.realtime_window([row(True, True, 99_999)], 1300, WM)
    assert w["silent"] and not w["degraded"] and w["available_s"] == 1300 + WM


def test_late_record_detection_is_timed_at_its_own_arrival():
    # Per-record detections from a late record are kept but can only make TTD later, never earlier.
    late_arrival = 1000 + 36 * 3600
    det = {"element_id": "CELL-A", "signal_start_s": 1000, "signal_end_s": 1900, "available_s": late_arrival}
    assert scoring.time_to_detect(INC, [det]) == late_arrival - INC["impact_start_s"]


def test_filter_matches_the_late_rule():
    assert windows.REALTIME_FILTER_SQL == "NOT is_late"
    assert rules.LATE_THRESHOLD_S == 20 * 60
