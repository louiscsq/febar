"""The app API never returns IMSI / MSISDN or ground-truth label columns; app config declares its resources."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app_fakes import FakeGenie, FakeStore, FakeWarehouse, incident_row, settings
from netmon_pipeline.rca.features import LABEL_COLUMNS
from noc_app import genie as genie_mod
from noc_app import safety
from noc_app.api import create_app
from noc_app.service import NocService

ROOT = Path(__file__).resolve().parents[1]
H = {"x-forwarded-email": "lead@banksia.example", "x-forwarded-access-token": "tok-national"}
RAW_IMSI, RAW_MSISDN = "001010123456789", "+999123456789"


def poisoned_store():
    """Rows that (wrongly) carry PII and label columns and raw identifiers in text: none may reach a response."""
    extra = {"imsi": RAW_IMSI, "msisdn": RAW_MSISDN, "subscriber_key": "k1", "fault_type": "SITE_POWER_OUTAGE",
             "is_root": True, "root_element_ids": ["SITE-NSW-00002"], "case_label": "fault",
             "estimated_impacted_subscribers": 367, "impact_start_ts": "2026-10-09T00:08:38Z"}
    rows = [{**incident_row(), **extra, "ai_summary": f"caller {RAW_MSISDN} imsi {RAW_IMSI}"},
            {**incident_row("RCA-2", "VIC", "SITE-VIC-00002"), **extra}]
    store = FakeStore(incidents=rows)
    for region in store.status.values():
        for r in region:
            r.update(extra)
    return store


def client(store=None, genie=None):
    s = NocService(settings(), store or poisoned_store(), FakeWarehouse(), genie or FakeGenie())
    return TestClient(create_app(lambda: s))


def keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from keys(v)


def assert_clean(resp):
    assert resp.status_code == 200, resp.text
    body = resp.json()
    bad = {k for k in keys(body) if k.lower() in safety.FORBIDDEN_COLUMNS}
    assert not bad, bad
    assert RAW_IMSI not in resp.text and RAW_MSISDN not in resp.text
    return body


def test_every_read_endpoint_is_clean():
    c = client()
    for path in ["/api/me", "/api/incidents", "/api/incidents?region=NSW", "/api/incidents/RCA-1",
                 "/api/regions/NSW/topology", "/api/regions/NSW/topology?incident_id=RCA-1",
                 "/api/incidents/RCA-1/sms-reviews", "/api/kpis", "/api/health"]:
        assert_clean(c.get(path, headers=H))


def test_write_endpoint_is_clean_and_records_the_forwarded_user():
    c = client()
    r = c.post("/api/incidents/RCA-1/sms-review", headers=H, json={"decision": "approve", "summary_id": "SUM-RCA-1"})
    body = assert_clean(r)
    assert body["reviewed_by"] == "lead@banksia.example" and body["sent"] is False
    assert "draft_text" not in body
    r = c.post("/api/incidents/RCA-1/sms-review", headers=H, json={"decision": "approve", "summary_id": "SUM-X"})
    assert r.status_code == 409
    r = c.post("/api/incidents/RCA-1/sms-review", json={"decision": "approve"})  # no identity forwarded
    assert r.status_code == 401


def test_genie_answers_are_scrubbed():
    ans = {"conversation_id": "c", "message_id": "m", "status": "COMPLETED", "text": [f"call {RAW_MSISDN}"],
           "sql": "SELECT imsi, cell_id FROM x", "columns": ["imsi", "cell_id", "fault_type"],
           "rows": [[RAW_IMSI, "CELL-1", "X"]], "row_count": 1}
    # the client-side table scrub drops forbidden columns, then the API scrubs again
    cols, rows = safety.scrub_table(ans["columns"], ans["rows"])
    assert cols == ["cell_id"] and rows == [["CELL-1"]]
    c = client(genie=FakeGenie({**ans, "columns": cols, "rows": rows}))
    body = assert_clean(c.post("/api/genie/ask", headers=H, json={"question": "who called?"}))
    assert body["columns"] == ["cell_id"]


def test_genie_message_mapping_scrubs_query_results():
    class Obj:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    col = lambda n: Obj(name=n)  # noqa: E731
    sr = Obj(manifest=Obj(schema=Obj(columns=[col("msisdn"), col("region_code")])),
             result=Obj(data_array=[[RAW_MSISDN, "NSW"]]))

    class W:
        class genie:  # noqa: N801
            @staticmethod
            def get_message_attachment_query_result(*a):
                return Obj(statement_response=sr)

    msg = Obj(conversation_id="c", message_id="m", id="m", status=None, error=None, attachments=[
        Obj(text=Obj(content=f"number {RAW_MSISDN}"), query=None, attachment_id="a0"),
        Obj(text=None, query=Obj(query="SELECT 1", description="d"), attachment_id="a1")])
    out = genie_mod._message_to_answer(W, "space", msg)
    assert out["columns"] == ["region_code"] and out["rows"] == [["NSW"]]
    assert RAW_MSISDN not in str(out)


def test_label_list_matches_step3_labels():
    assert set(LABEL_COLUMNS) - {"incident_id"} == safety.LABEL_COLUMNS


@pytest.mark.parametrize(("text", "clean"), [
    (f"imsi {RAW_IMSI}.", "imsi [redacted]."), (f"tel {RAW_MSISDN}", "tel [redacted]"),
    ("masked 00101********33 / +999******961", "masked 00101********33 / +999******961"),
    ("CELL-NSW-00105-4G1 at 2026-10-09T00:10:42Z, 420 subs", "CELL-NSW-00105-4G1 at 2026-10-09T00:10:42Z, 420 subs"),
])
def test_redaction(text, clean):
    assert safety.redact_text(text) == clean


def test_app_sources_never_reference_sessions_or_raw_ground_truth():
    for f in (ROOT / "app").rglob("*.py"):
        src = f.read_text().lower()
        assert "silver_sessions" not in src, f
        for gt in ("eval_gt_incidents", "bronze_gt_", "eval_incident_detection", "genai_eval_labels"):
            assert gt not in src, (f, gt)
    # the only eval-schema read is the labelled KPI scorecard
    wsrc = (ROOT / "app" / "noc_app" / "warehouse.py").read_text()
    assert re.findall(r"\{eval\}\.(\w+)", wsrc) == ["eval_ttd_summary"]


def test_app_yaml_and_bundle_declare_the_resources():
    app_yaml = (ROOT / "app" / "app.yaml").read_text()
    bundle = (ROOT / "resources" / "app.yml").read_text()
    for name in re.findall(r"valueFrom: ([\w-]+)", app_yaml):
        assert f"- name: {name}" in bundle, name
    for scope in ("- sql", "- dashboards.genie"):
        assert scope in bundle
    assert "database:" in bundle and "CAN_CONNECT_AND_CREATE" in bundle
    assert "${resources.genie_spaces.noc_genie.id}" in bundle
    for text in (app_yaml, bundle):
        assert not re.search(r"(password|secret|token)\s*[:=]\s*\S", text, re.I)
    reqs = (ROOT / "app" / "requirements.txt").read_text()
    assert "psycopg" in reqs and "databricks-sdk" in reqs
