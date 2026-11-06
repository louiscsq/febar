"""Step 4 grounding: the incident context is built from operational data only. No per-subscriber identifier and
no ground-truth / label column can reach it, and nothing that arrived after the decision time is used."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from test_rca_features import FAULT_FROM, T0, alarms_df, gt_df, health_df, topo_df

from netmon_pipeline.genai import context as C
from netmon_pipeline.genai import guards, sources
from netmon_pipeline.rca import labels
from netmon_pipeline.rca.features import LABEL_COLUMNS, RunState, Topology

AS_OF_MIN = 95
IMSI_RAW = "001010123456789"
MSISDN_RAW = "+999123456789"


def _topo() -> pd.DataFrame:
    t = topo_df().assign(region="Sydney & NSW", timezone="Australia/Sydney", lat=-33.87, lon=151.21)
    t["urbanity"] = np.where(t["element_type"].isin(["CELL", "SITE"]), "urban", None)
    t.loc[t["element_id"] == "BH-1", "transport_medium"] = "microwave"
    return t


def _health() -> pd.DataFrame:
    return health_df().assign(active_users=50.0, availability_pct=100.0)


def _alarms() -> pd.DataFrame:
    a = alarms_df().assign(additional_text=["RSL below threshold", "Equipment alarm"])
    return a


def _sessions() -> pd.DataFrame:
    """Aggregate session windows plus per-subscriber columns that must never be read."""
    rows = []
    for m in range(AS_OF_MIN - 20, AS_OF_MIN, 5):
        for c in ("CELL-1a", "CELL-1b", "CELL-2a", "CELL-2b"):
            rows.append({"cell_id": c, "window_start": T0 + pd.Timedelta(minutes=m),
                         "window_end": T0 + pd.Timedelta(minutes=m + 5), "n_sessions": 4, "n_setup_failed": 1,
                         "n_dropped": 1, "n_no_service": 0, "n_subscribers_approx": 3,
                         "imsi": IMSI_RAW, "msisdn": MSISDN_RAW, "subscriber_key": "sk-42"})
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def scored() -> pd.DataFrame:
    st = RunState(Topology(topo_df()), health_df(), alarms_df())
    f = st.features(times=[AS_OF_MIN])
    return f.assign(score=np.where(f["element_id"] == "BH-1", 0.9, np.where(f["element_id"] == "AGG-1", 0.2, 0.05)))


def _case(scored: pd.DataFrame) -> pd.DataFrame:
    cid = scored.loc[scored["element_id"] == "BH-1", "case_id"].iloc[0]
    return scored[scored["case_id"] == cid]


def _inputs(case: pd.DataFrame, **kw) -> C.ContextInputs:
    ref = sources.ref_from_case("REF-1", case, detected_ts=T0 + pd.Timedelta(minutes=FAULT_FROM + 3),
                                model_version="4", threshold=0.32)
    args = {"incident": ref, "case_rows": case, "topology": _topo(), "alarms": _alarms(), "health": _health(),
            "sessions": _sessions(), "maintenance": pd.DataFrame(), "xdr_sample_rate": 0.01}
    args.update(kw)
    return C.ContextInputs(**args)


def test_context_holds_suspects_neighbourhood_alarms_kpis_and_impact(scored):
    ctx = C.build_context(_inputs(_case(scored)))
    s = ctx["suspects"]
    assert [x["element_id"] for x in s][:2] == ["BH-1", "AGG-1"] and s[0]["ranker_score"] == 0.9
    nb = s[0]["neighbourhood"]
    assert nb["parent"] == {"element_id": "AGG-1", "element_type": "AGG_ROUTER"}
    assert nb["children_by_type"] == {"SITE": 2} and nb["n_impacted_children"] == 2 and nb["n_desc_cells"] == 4
    assert nb["transport_medium"] == "microwave"
    assert s[0]["signals"]["latency_z_now"] > 0 and "impacted_fraction" in s[0]["signals"]
    # the HIGH_BER on BH-1 arrived before as_of; the CPU_HIGH on AGG-1 only arrives 5 h later: not visible
    assert [(a["element_id"], a["alarm_code"]) for a in ctx["alarms"]] == [("BH-1", "HIGH_BER")]
    assert ctx["kpi"]["n_cells"] == 4 and ctx["kpi"]["median_z"]["latency"] > 0
    imp = ctx["impact"]
    assert imp["n_impacted_cells"] == 4 and imp["n_impacted_sites"] == 2
    assert imp["by_region_segment"] == [{"region_code": "NSW", "segment": "urban", "n_cells": 4,
                                         "est_affected_subscribers": 200, "n_cells_without_user_data": 0}]
    assert imp["sessions_last_15min"]["sampled_failed_or_dropped"] == 24
    assert ctx["incident"]["minutes_since_detected"] == AS_OF_MIN - FAULT_FROM - 3
    assert ctx["customer_eta"] is None and ctx["customer_areas"] == ["Sydney"]


def test_no_subscriber_identifier_reaches_the_context(scored):
    a = _alarms()
    a.loc[0, "additional_text"] = f"customer {MSISDN_RAW} imsi {IMSI_RAW} complained"
    ctx = C.build_context(_inputs(_case(scored), alarms=a))
    text = C.to_json(ctx)
    assert IMSI_RAW not in text and MSISDN_RAW not in text and "sk-42" not in text
    assert not ({"imsi", "msisdn", "subscriber_key"} & set(C.all_keys(ctx)))
    assert guards.pii_findings(text) == []
    assert "[imsi redacted]" in ctx["alarms"][0]["text"]
    with pytest.raises(guards.PIIError):
        guards.assert_no_pii(text + IMSI_RAW)


def test_no_ground_truth_or_label_column_reaches_the_context(scored):
    case = _case(scored)
    base = C.build_context(_inputs(case))
    assert not (set(LABEL_COLUMNS) & set(C.all_keys(base)))
    lab = labels.label(case, gt_df())  # adds is_root, case_label, incident_ids, ...
    lab = lab.assign(fault_type="BACKHAUL_DEGRADATION", root_element_ids=[["BH-1"]] * len(lab),
                     estimated_impacted_subscribers=12345)
    rng = np.random.default_rng(0)
    perm = lab.copy()
    for c in ("is_root", "case_label"):
        perm[c] = perm[c].to_numpy()[rng.permutation(len(perm))]
    for variant in (lab, perm):
        assert C.build_context(_inputs(variant)) == base
    text = C.to_json(base)
    assert "INC-1" not in text and "BACKHAUL_DEGRADATION" not in text and "12345" not in text
    with pytest.raises(ValueError):
        C.assert_no_label_keys({**base, "fault_type": "x"})


def test_data_arriving_after_the_decision_time_is_ignored(scored):
    case = _case(scored)
    base = C.build_context(_inputs(case))
    h = _health()
    late = h[h["window_start"] == h["window_start"].max()].assign(
        latency_ms_z=999.0, active_users=1e6, evidence_ts=T0 + pd.Timedelta(hours=10))
    a = pd.concat([_alarms(), pd.DataFrame([{
        "alarm_id": "A9", "event_type": "RAISE", "element_id": "BH-1", "alarm_code": "LINK_DOWN",
        "severity": "CRITICAL", "event_ts": T0 + pd.Timedelta(minutes=AS_OF_MIN - 1),
        "evidence_ts": T0 + pd.Timedelta(minutes=AS_OF_MIN + 3), "is_service_down": True,
        "additional_text": "x"}])], ignore_index=True)
    assert C.build_context(_inputs(case, health=pd.concat([h, late], ignore_index=True), alarms=a)) == base


def test_maintenance_window_is_the_only_eta_source(scored):
    case = _case(scored)
    m = pd.DataFrame([{"element_id": "BH-1", "planned_start_ts": T0, "planned_end_ts": T0 + pd.Timedelta(hours=4)}])
    ctx = C.build_context(_inputs(case, maintenance=m))
    assert ctx["maintenance"]["in_planned_window"] and ctx["customer_eta"] == "2026-10-10T04:00:00Z"


def test_customer_view_has_no_element_ids_or_scores(scored):
    ctx = C.build_context(_inputs(_case(scored)))
    v = C.customer_view(ctx)
    text = json.dumps(v)
    assert not guards.ELEMENT_ID.search(text) and "BH-1" not in text and "score" not in text
    assert v["regions"][0]["region_code"] == "NSW" and v["regions"][0]["est_affected_customers"] == 200
    assert v["service_effect"] and v["eta"] is None


def test_resolve_path_and_known_elements(scored):
    ctx = C.build_context(_inputs(_case(scored)))
    assert C.resolve_path(ctx, "suspects[0].signals.latency_z_now") == ctx["suspects"][0]["signals"]["latency_z_now"]
    with pytest.raises(KeyError):
        C.resolve_path(ctx, "suspects[0].signals.made_up")
    assert {"BH-1", "AGG-1", "SITE-1", "SITE-2"} <= C.known_elements(ctx)
