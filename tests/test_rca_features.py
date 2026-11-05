"""RCA candidate generation, detection-time features, labels, time split and evaluation (step 3)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from netmon_pipeline import scoring
from netmon_pipeline.rca import evaluate, features, labels, model
from netmon_pipeline.rca.features import FEATURE_COLUMNS, LABEL_COLUMNS, RunState, Topology

T0 = pd.Timestamp("2026-10-10T00:00:00Z")
N_MIN = 100
FAULT_FROM = 80  # link BH-1 degrades from minute 80 (all its cells)


def topo_df() -> pd.DataFrame:
    rows = [("AMF-1", "AMF_MME", None), ("UPF-1", "UPF_SGW", "AMF-1"), ("AGG-1", "AGG_ROUTER", "UPF-1"),
            ("BH-1", "BACKHAUL_LINK", "AGG-1"), ("BH-2", "BACKHAUL_LINK", "AGG-1"),
            ("SITE-1", "SITE", "BH-1"), ("SITE-2", "SITE", "BH-1"), ("SITE-3", "SITE", "BH-2")]
    for s in ("1", "2", "3"):
        rows += [(f"CELL-{s}{k}", "CELL", f"SITE-{s}") for k in "ab"]
    return pd.DataFrame(rows, columns=["element_id", "element_type", "parent_id"]).assign(region_code="NSW")


def health_df(late_cell: str | None = None) -> pd.DataFrame:
    cells = [c for c in topo_df()["element_id"] if c.startswith("CELL")]
    rows = []
    for m in range(N_MIN):
        for c in cells:
            bad = m >= FAULT_FROM and c[5] in "12"  # cells of SITE-1 / SITE-2 sit behind BH-1
            ramp = max(0, m - FAULT_FROM + 1) if bad else 0
            ev = T0 + pd.Timedelta(minutes=m + 1, seconds=20)
            if c == late_cell and m == N_MIN - 3:
                ev = T0 + pd.Timedelta(hours=10)  # on-time-flagged but arrives after every decision time used
            rows.append({"source_run": "history_1m", "cell_id": c, "window_start": T0 + pd.Timedelta(minutes=m),
                         "evidence_ts": ev, "is_degraded": bad and ramp >= 3, "granularity_s": 60,
                         "latency_ms_z": 0.5 * ramp, "packet_loss_pct_z": 0.2 * ramp,
                         "dl_throughput_mbps_z": -0.3 * ramp, "rrc_setup_success_pct_z": 0.0,
                         "session_drop_rate_pct_z": 0.1 * ramp, "attach_success_pct": 99.5,
                         "min_availability_pct": 100.0, "prb_util_pct": 40.0 + ramp})
    return pd.DataFrame(rows)


def alarms_df() -> pd.DataFrame:
    t = T0 + pd.Timedelta(minutes=FAULT_FROM + 2)
    return pd.DataFrame([
        {"alarm_id": "A1", "event_type": "RAISE", "element_id": "BH-1", "alarm_code": "HIGH_BER",
         "severity": "MAJOR", "event_ts": t, "evidence_ts": t + pd.Timedelta(seconds=10), "is_service_down": False},
        # an alarm whose RAISE arrives only after the decision times below: must not be counted
        {"alarm_id": "A2", "event_type": "RAISE", "element_id": "AGG-1", "alarm_code": "CPU_HIGH",
         "severity": "CRITICAL", "event_ts": t, "evidence_ts": T0 + pd.Timedelta(hours=5),
         "is_service_down": False},
    ])


def gt_df() -> pd.DataFrame:
    return pd.DataFrame([{
        "source_run": "history_1m", "incident_id": "INC-1", "event_class": "fault",
        "fault_type": "BACKHAUL_DEGRADATION", "root_element_id": "BH-1", "root_element_type": "BACKHAUL_LINK",
        "root_element_ids": ["BH-1"], "region_code": "NSW", "start_ts": T0 + pd.Timedelta(minutes=FAULT_FROM),
        "end_ts": T0 + pd.Timedelta(minutes=N_MIN + 30), "impact_start_ts": T0 + pd.Timedelta(minutes=FAULT_FROM),
        "impact_end_ts": T0 + pd.Timedelta(minutes=N_MIN + 30), "is_customer_impacting": True,
        "is_censored": False, "affected_element_ids": ["SITE-1", "SITE-2", "CELL-1a", "CELL-1b", "CELL-2a",
                                                       "CELL-2b"],
        "affected_cell_ids": ["CELL-1a", "CELL-1b", "CELL-2a", "CELL-2b"]}])


@pytest.fixture(scope="module")
def state() -> RunState:
    return RunState(Topology(topo_df()), health_df(), alarms_df())


def test_feature_set_excludes_every_label_column():
    assert not set(FEATURE_COLUMNS) & set(LABEL_COLUMNS)
    assert not set(features.ID_COLUMNS) & set(LABEL_COLUMNS)
    model.check_features(FEATURE_COLUMNS)
    with pytest.raises(ValueError, match="label columns"):
        model.check_features([*FEATURE_COLUMNS, "is_root"])


def test_feature_rows_never_use_data_after_the_decision_time(state):
    f = state.features(times=range(70, N_MIN + 2))
    assert len(f) and set(f.columns) == set(features.ID_COLUMNS + FEATURE_COLUMNS)
    assert (f["feature_evidence_ts"] <= f["decision_ts"]).all()


def test_records_arriving_after_t_do_not_change_the_features():
    t = N_MIN  # the window starting at N_MIN - 3 is current at t; CELL-1a's copy of it arrives 10 h later
    base = RunState(Topology(topo_df()), health_df(), alarms_df()).case_features(t, "NSW")
    late = RunState(Topology(topo_df()), health_df(late_cell="CELL-1a"), alarms_df()).case_features(t, "NSW")
    # The late copy is invisible at t: CELL-1a simply has one window fewer, so its own "now" mean is
    # built from the other two recent windows. Changing the late value itself changes nothing.
    h = health_df(late_cell="CELL-1a")
    h.loc[(h["cell_id"] == "CELL-1a") & (h["window_start"] == T0 + pd.Timedelta(minutes=N_MIN - 3)),
          "latency_ms_z"] = 999.0
    late2 = RunState(Topology(topo_df()), h, alarms_df()).case_features(t, "NSW")
    pd.testing.assert_frame_equal(late, late2)
    assert (base["feature_evidence_ts"] <= base["decision_ts"]).all()


def test_candidates_are_ancestors_of_impacted_cells_plus_nearby_alarms(state):
    f = state.case_features(FAULT_FROM + 6, "NSW")
    c = set(f["element_id"])
    assert {"BH-1", "AGG-1", "UPF-1", "AMF-1", "SITE-1", "SITE-2", "CELL-1a"} <= c
    assert "BH-2" not in c and "SITE-3" not in c  # healthy and unalarmed
    row = f.set_index("element_id")
    assert row.loc["BH-1", "coverage"] == 1.0 and row.loc["BH-1", "impacted_fraction"] == 1.0
    assert row.loc["AGG-1", "impacted_fraction"] == pytest.approx(4 / 6)
    assert row.loc["BH-1", "n_alarms_link"] == 1  # HIGH_BER arrived at minute 82:10
    assert row.loc["AGG-1", "n_alarms"] == 0  # its CPU_HIGH RAISE had not arrived yet
    assert row.loc["BH-1", "lat_slope5"] > 0 and row.loc["BH-1", "lat_vs_parent"] > 0


def test_slope_handles_missing_points():
    y = np.array([[0, np.nan], [1, np.nan], [2, 1.0], [3, np.nan]], dtype=float)
    s = features._slope(y)
    assert s[0] == pytest.approx(1.0) and np.isnan(s[1])


def test_one_minute_windows_are_required():
    h = health_df().assign(granularity_s=900)
    with pytest.raises(ValueError, match="1-minute"):
        RunState(Topology(topo_df()), h, alarms_df())


def test_labels_mark_the_valid_root_and_skip_unrelated_cases(state):
    f = state.features(times=range(70, N_MIN + 2))
    lab = labels.label(f, gt_df())
    fault = lab[lab["case_label"] == "fault"]
    assert set(fault.loc[fault["is_root"], "element_id"]) == {"BH-1"}
    assert (lab.loc[lab["decision_ts"] < T0 + pd.Timedelta(minutes=FAULT_FROM - 5), "case_label"] != "fault").all()


def test_censored_incidents_are_labelled_censored():
    s = RunState(Topology(topo_df()), health_df(), alarms_df())
    f = s.features(times=range(FAULT_FROM + 4, FAULT_FROM + 8))
    lab = labels.label(f, gt_df().assign(is_censored=True))
    assert set(lab["case_label"]) == {"censored"} and not lab["is_root"].any()


def test_time_split_embargoes_incidents_that_start_later():
    split = model.TimeSplit(val_start=T0 + pd.Timedelta(minutes=90), test_start=T0 + pd.Timedelta(minutes=95))
    inc = labels.prepare_incidents(gt_df().assign(impact_start_ts=T0 + pd.Timedelta(minutes=92)))
    rows = pd.DataFrame({"source_run": "history_1m", "decision_ts": [T0 + pd.Timedelta(minutes=85)] * 2,
                         "incident_ids": [["INC-1"], np.nan]})
    out = split.assign(rows, inc)
    assert len(out) == 1 and out["split"].tolist() == ["train"]


def test_rank_and_early_catch_and_alert_precision_use_step2_definitions(state):
    f = state.features(times=range(70, N_MIN + 2))
    lab = labels.label(f, gt_df())
    lab["score"] = np.where(lab["element_id"] == "BH-1", 0.9, 0.1)
    inc = labels.prepare_incidents(gt_df())
    r = evaluate.rank_incidents(lab, inc)
    assert r["hit_at_1"].all() and r["top_candidates"].iloc[0][0] == "BH-1"
    e = evaluate.early_catch(lab, inc, threshold=0.5)
    assert e["localisation_s"].iloc[0] <= scoring.SLA_S and e["within_5min"].all()
    alerts = evaluate.model_alert_rows(lab, threshold=0.5)
    p = evaluate.alert_precision(alerts, inc)
    assert p["n_alerts"] >= 1 and p["fault"] >= 1


def test_vectorised_detection_labels_match_scoring_label_detection():
    rng = np.random.default_rng(3)
    classes = ["fault", "planned", "red_herring"]
    inc = []
    for i in range(40):
        s = T0 + pd.Timedelta(minutes=int(rng.integers(0, 300)))
        inc.append({"source_run": "r", "incident_id": f"I{i}", "event_class": classes[i % 3],
                    "is_censored": bool(rng.random() < 0.2), "start_ts": s, "end_ts": s + pd.Timedelta(minutes=30),
                    "impact_end_ts": None, "footprint": [f"E{int(x)}" for x in rng.integers(0, 8, 3)]})
    gt = pd.DataFrame(inc)
    starts = [T0 + pd.Timedelta(minutes=int(m)) for m in rng.integers(0, 400, 300)]
    dets = pd.DataFrame({"source_run": "r", "element_id": [f"E{int(x)}" for x in rng.integers(0, 10, 300)],
                         "signal_start_ts": starts, "signal_end_ts": [s + pd.Timedelta(minutes=1) for s in starts]})
    got = evaluate._matched_labels(dets, gt)
    for k, d in dets.iterrows():
        hits = [r for r in inc if d["element_id"] in r["footprint"]
                and d["signal_end_ts"] > r["start_ts"] - pd.Timedelta(minutes=5)
                and d["signal_start_ts"] < r["end_ts"] + pd.Timedelta(seconds=scoring.MATCH_SLACK_S)]
        assert got.iloc[k] == scoring.label_detection(hits)
