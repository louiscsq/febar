"""Regression guard: ground truth (the netmon_eval schema) never reaches what the Genie space or the app shows.

Ground truth may only be used to verify the build, in the evidence / trace scripts (scripts/trace_end_to_end.py and
the capture scripts). This test scans every Genie data source, instruction, trusted / example SQL, SQL snippet and
benchmark SQL, every SQL the app sends, the app's source and static files, and the live responses of every API path
(served with fakes that refuse any ground-truth query).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app_fakes import FakeGenie, FakeStore, FakeWarehouse, settings
from netmon_pipeline import genie_space
from noc_app import lakebase
from noc_app import warehouse as wh
from noc_app.api import create_app
from noc_app.service import NocService

ROOT = Path(__file__).resolve().parents[1]
CAT = "telco_netmon_febar_catalog"
# the eval schema and every ground-truth / label / scorecard table name
GT = re.compile(r"netmon_eval|\{eval\}|eval_schema|eval_ttd_summary|eval_gt_incidents|bronze_gt_|eval_incident_detection|"
                r"eval_detection_|eval_alert_precision|eval_rca_baseline|eval_dq_capture|genai_eval_labels|"
                r"rca_training_labels|ground_truth/", re.I)
# verification / offline-evaluation scripts allowed to read ground truth (never shown by Genie or the app)
ALLOWED = {"scripts/trace_end_to_end.py", "scripts/capture_evidence.py", "scripts/capture_evidence_step3.py",
           "scripts/capture_evidence_step4.py", "scripts/capture_evidence_step5.py",
           "scripts/genai_eval_local.py", "scripts/genai_early_example.py",
           "scripts/collective_backhaul_experiment.py",  # step 6 offline experiment: scores against ground truth
           "scripts/capture_cost_step6.py"}  # reads the pipeline event log (netmon_eval) for the live update's duration


def _hits(text: str) -> list[str]:
    return sorted(set(m.group(0) for m in GT.finditer(text)))


def test_genie_space_has_no_ground_truth_anywhere():
    s = genie_space.build_space(CAT)
    parts = {
        "tables": [t["identifier"] for t in s["data_sources"]["tables"]] + [json.dumps(s["data_sources"])],
        "instructions": ["".join(x["content"]) for x in s["instructions"]["text_instructions"]],
        "example_sql": ["".join(x["sql"]) for x in s["instructions"]["example_question_sqls"]],
        "snippets": [json.dumps(s["instructions"]["sql_snippets"])],
        "joins": [json.dumps(s["instructions"]["join_specs"])],
        "samples": [json.dumps(s["config"])],
        "benchmarks": [json.dumps(s["benchmarks"])],
    }
    for name, texts in parts.items():
        for text in texts:
            assert not _hits(text), (name, _hits(text))
    for t in s["data_sources"]["tables"]:
        assert t["identifier"].startswith(f"{CAT}.netmon_noc."), t["identifier"]


def test_deployed_genie_file_has_no_ground_truth():
    text = (ROOT / "resources" / "genie" / "noc_space.geniespace.json").read_text()
    assert not _hits(text), _hits(text)
    assert not _hits((ROOT / "resources" / "genie.yml").read_text())


def test_serving_views_read_no_ground_truth():
    sql = (ROOT / "governance" / "sql" / "05_serving_views.sql").read_text()
    body = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    assert not _hits(body), _hits(body)


def test_app_sql_and_sources_have_no_ground_truth():
    sqls = [lakebase.INCIDENTS_SQL, lakebase.INCIDENT_SQL, lakebase.ELEMENT_STATUS_SQL, lakebase.REVIEWS_SQL,
            lakebase.INSERT_REVIEW_SQL, *lakebase.SCHEMA_DDL]
    sqls += [v for k, v in vars(wh).items() if k.endswith("_SQL") and isinstance(v, str)]
    for q in sqls:
        assert not _hits(q), (q[:80], _hits(q))
    for f in [*(ROOT / "app").rglob("*.py"), *(ROOT / "app" / "static").glob("*"), ROOT / "app" / "app.yaml",
              ROOT / "resources" / "app.yml"]:
        if f.is_file() and "__pycache__" not in f.parts:
            assert not _hits(f.read_text()), (f, _hits(f.read_text()))


def test_only_verification_scripts_read_ground_truth():
    """Outside the pipeline / ML / Gen AI evaluation code, only the evidence scripts may name ground truth."""
    offenders = []
    for f in (ROOT / "scripts").glob("*.py"):
        rel = f.relative_to(ROOT).as_posix()
        if _hits(f.read_text()) and rel not in ALLOWED:
            offenders.append(rel)
    assert offenders == [], offenders


@pytest.mark.parametrize("path", ["/api/me", "/api/health", "/api/incidents", "/api/incidents?region=NSW",
                                  "/api/incidents/RCA-1", "/api/regions/NSW/topology",
                                  "/api/regions/NSW/topology?incident_id=RCA-1", "/api/incidents/RCA-1/sms-reviews",
                                  "/api/kpis"])
def test_api_responses_carry_no_ground_truth(path):
    s = NocService(settings(), FakeStore(), FakeWarehouse(), FakeGenie())
    c = TestClient(create_app(lambda: s))
    r = c.get(path, headers={"x-forwarded-email": "lead@banksia.example", "x-forwarded-access-token": "tok-national"})
    assert r.status_code == 200, r.text
    assert not _hits(r.text), _hits(r.text)
    assert "scorecard" not in r.text


POISONED_GENIE = {
    "conversation_id": "c1", "message_id": "m1", "status": "COMPLETED",
    "text": [f"From {CAT}.netmon_eval.eval_ttd_summary: the median backhaul time to detect is 559 s."],
    "sql": f"SELECT fault_type, impact_median_ttd_s FROM {CAT}.netmon_eval.eval_ttd_summary",
    "description": "Reads netmon_eval.eval_gt_incidents and eval_ttd_summary",
    "columns": ["fault_type", "impact_median_ttd_s", "source"],
    "rows": [["BACKHAUL_DEGRADATION", 559.0, "netmon_eval.eval_ttd_summary"]], "row_count": 1,
}


@pytest.mark.parametrize("field", ["all", "sql", "text", "description", "rows"])
def test_genie_ask_never_passes_ground_truth_through(field):
    """POST /api/genie/ask with a Genie that (wrongly) answers from the eval schema: the response exposes none of it."""
    clean = {"conversation_id": "c1", "message_id": "m1", "status": "COMPLETED", "text": ["2 sites are down."],
             "sql": f"SELECT element_id FROM {CAT}.netmon_noc.element_status", "description": "Sites down",
             "columns": ["element_id"], "rows": [["SITE-NSW-00002"]], "row_count": 1}
    ans = dict(POISONED_GENIE) if field == "all" else {**clean, field: POISONED_GENIE[field]}
    if field == "rows":
        ans["columns"] = POISONED_GENIE["columns"]
    s = NocService(settings(), FakeStore(), FakeWarehouse(), FakeGenie(ans))
    c = TestClient(create_app(lambda: s))
    r = c.post("/api/genie/ask", json={"question": "How fast do we detect backhaul faults?"},
               headers={"x-forwarded-email": "lead@banksia.example", "x-forwarded-access-token": "tok-national"})
    assert r.status_code == 200, r.text
    assert not _hits(r.text), _hits(r.text)
    body = r.json()
    assert body["withheld"] is True and body["sql"] is None and body["rows"] == [] and "559" not in r.text
    assert "fault_type" not in r.text


NOC = f"{CAT}.netmon_noc"
CLEAN = {"conversation_id": "c1", "message_id": "m1", "status": "COMPLETED", "text": ["2 sites are down."],
         "sql": f"SELECT element_id FROM {NOC}.element_status WHERE state = 'down'", "description": "Sites down",
         "columns": ["element_id"], "rows": [["SITE-NSW-00002"]], "row_count": 1}


def _ask(ans):
    s = NocService(settings(), FakeStore(), FakeWarehouse(), FakeGenie(ans))
    c = TestClient(create_app(lambda: s))
    r = c.post("/api/genie/ask", json={"question": "What is going on?"},
               headers={"x-forwarded-email": "lead@banksia.example", "x-forwarded-access-token": "tok-national"})
    assert r.status_code == 200, r.text
    return r


# Ground truth WITHOUT any evaluation table being named: label columns or fault-class labels in one field each.
POISON_NO_EVAL_TABLE = {
    "label column in result columns": {"columns": ["element_id", "fault_type"], "rows": [["BH-VIC-0005", "x"]]},
    "label column in sql": {"sql": f"SELECT element_id, is_censored FROM {NOC}.element_status"},
    "label column in text": {"text": ["Its root_element_id is BH-VIC-0005."]},
    "root cause column in description": {"description": "Uses root_cause_element from the incident record"},
    "label column inside a row value": {"rows": [["{\"event_class\": \"fault\"}"]]},
    "fault class in rows, no hypothesis": {"columns": ["element_id", "cause"], "rows": [["BH-VIC-0005", "BACKHAUL_DEGRADATION"]]},
    "fault class in text, no hypothesis": {"text": ["The true fault was SITE_POWER_OUTAGE."]},
    "red-herring class in sql": {"sql": f"SELECT * FROM {NOC}.element_status WHERE note = 'TRAFFIC_SURGE'"},
}


@pytest.mark.parametrize("case", sorted(POISON_NO_EVAL_TABLE))
def test_genie_ask_withholds_ground_truth_labels_without_an_eval_table(case):
    r = _ask({**CLEAN, **POISON_NO_EVAL_TABLE[case]})
    body = r.json()
    assert body["withheld"] is True and body["rows"] == [] and body["sql"] is None, case
    assert body["withheld_reason"] in ("label_column", "label_value")
    for leaked in ("fault_type", "is_censored", "root_element_id", "root_cause", "event_class", "BACKHAUL_DEGRADATION",
                   "SITE_POWER_OUTAGE", "TRAFFIC_SURGE"):
        assert leaked not in r.text, (case, leaked)


CLEAN_ANSWERS = {
    "sites down": CLEAN,
    # the step-4 assistant's operational guess is a fault class, read from its serving column
    "assistant hypothesis": {**CLEAN, "text": ["The assistant's hypothesis for RCA-1 is BACKHAUL_DEGRADATION."],
                             "sql": f"SELECT incident_id, fault_hypothesis FROM {NOC}.incident_ai_summary",
                             "columns": ["incident_id", "fault_hypothesis"], "rows": [["RCA-1", "BACKHAUL_DEGRADATION"]]},
    "prose, not a label": {**CLEAN, "text": ["Latency is rising on every cell behind the link: backhaul degradation "
                                             "is likely; check the root cause with the transport team."]},
    "alarms": {**CLEAN, "sql": f"SELECT element_id, alarm_code, severity, event_ts FROM {NOC}.silver_alarms",
               "columns": ["element_id", "alarm_code", "event_ts"], "rows": [["BH-VIC-0005", "RSL_LOW", "2026-10-09"]]},
}


@pytest.mark.parametrize("case", sorted(CLEAN_ANSWERS))
def test_genie_ask_legitimate_noc_answers_pass(case):
    ans = CLEAN_ANSWERS[case]
    body = _ask(ans).json()
    assert "withheld" not in body, (case, body)
    assert body["rows"] == ans["rows"] and body["text"] == ans["text"] and body["sql"] == ans["sql"]


def test_genie_ask_clean_answer_still_drops_forbidden_columns():
    ans = {**CLEAN, "sql": f"SELECT element_id, severity FROM {NOC}.silver_alarms",
           "columns": ["element_id", "severity"], "rows": [["SITE-NSW-00002", "CRITICAL"]]}
    body = _ask(ans).json()
    assert "withheld" not in body and body["columns"] == ["element_id"] and body["rows"] == [["SITE-NSW-00002"]]


def test_fault_classes_match_the_generator():
    from netmon_datagen.faults import FAULT_SPECS
    from noc_app.safety import FAULT_CLASSES

    assert set(FAULT_CLASSES) == set(FAULT_SPECS)
