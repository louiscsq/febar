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
           "scripts/genai_eval_local.py", "scripts/genai_early_example.py"}


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
