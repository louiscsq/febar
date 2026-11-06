"""NOC app data access: region scope from UC, Lakebase reads, the SMS approve / reject write path, KPIs, Genie."""

from __future__ import annotations

import pytest

from app_fakes import FakeGenie, FakeStore, FakeWarehouse, incident_row, settings
from noc_app import lakebase
from noc_app import warehouse as wh
from noc_app.service import BadRequest, Conflict, Forbidden, NocService, NotFound, Unauthorized, User

NATIONAL = User("lead@banksia.example", "tok-national")
NSW = User("nsw.analyst@banksia.example", "tok-nsw")
NOBODY = User("visitor@banksia.example", "tok-none")


def svc(store=None, warehouse=None, genie=None, **kw):
    return NocService(settings(**kw), store or FakeStore(), warehouse or FakeWarehouse(), genie or FakeGenie())


# ---- scope ---------------------------------------------------------------------------------------------------------

def test_region_scope_comes_from_uc_as_the_user():
    w = FakeWarehouse()
    s = svc(warehouse=w)
    assert s.regions(NATIONAL) == ["NSW", "VIC"]
    assert s.regions(NSW) == ["NSW"]
    assert s.regions(NOBODY) == []
    assert all(c[1] == wh.REGION_SCOPE_SQL for c in w.calls)
    assert [c[0] for c in w.calls] == ["tok-national", "tok-nsw", "tok-none"]  # each user's own token
    s.regions(NSW)
    assert len(w.calls) == 3  # cached per user


def test_without_a_user_token_only_explicit_dev_regions():
    assert svc().regions(User("x", None)) == []
    assert svc(dev_regions=("WA",)).regions(User("x", None)) == ["WA"]


def test_lakebase_reads_are_restricted_to_the_users_regions():
    store = FakeStore()
    s = svc(store=store)
    assert [i["incident_id"] for i in s.incidents(NSW)] == ["RCA-1"]
    assert ("incidents", ("NSW",)) in store.calls
    assert {i["region_code"] for i in s.incidents(NATIONAL)} == {"NSW", "VIC"}
    assert s.incidents(NOBODY) == []
    with pytest.raises(Forbidden):
        s.incidents(NSW, region="VIC")
    with pytest.raises(NotFound):  # another region's incident is invisible, not just hidden in the list
        s.incident(NSW, "RCA-2")
    with pytest.raises(Forbidden):
        s.topology(NSW, "VIC")


def test_lakebase_sql_filters_by_region_and_never_reads_uc_ground_truth():
    for q in (lakebase.INCIDENTS_SQL, lakebase.INCIDENT_SQL, lakebase.REVIEWS_SQL):
        assert "region_code = ANY(%(regions)s)" in q
    assert "%(incident_id)s" in lakebase.INCIDENT_SQL
    blob = " ".join([lakebase.INCIDENTS_SQL, lakebase.ELEMENT_STATUS_SQL, lakebase.REVIEWS_SQL]).lower()
    for t in ("netmon_eval", "silver_sessions", "imsi", "msisdn", "fault_type", "is_root"):
        assert t not in blob


# ---- incident panel and topology ------------------------------------------------------------------------------------

def test_incident_panel_contents():
    d = svc().incident(NATIONAL, "RCA-1")
    assert d["pinpoint"]["element_id"] == "SITE-NSW-00002" and d["pinpoint"]["state"] == "down"
    assert [s["rank"] for s in d["suspects"]] == [1, 2, 3]
    assert [p["element_id"] for p in d["path_from_core"]] == ["AMF-NSW-01", "UPF-NSW-01", "AGG-NSW-01",
                                                                "BH-NSW-0001", "SITE-NSW-00002"]
    assert d["detection"]["time_to_detect_s"] == 162.4 and d["detection"]["detected_within_5min"]
    assert d["impact"] == {"impacted_cells": 3, "impacted_sites": 1, "est_affected_subscribers": 420,
                           "description": "3 cells dark"}
    assert d["ai"]["next_steps"] == ["Check mains power alarms", "Dispatch field tech"]
    assert d["ai"]["agrees_with_ranker"] is True
    assert d["sms"]["decision"] == "pending" and d["sms"]["sent"] is False
    assert d["sms"]["draft_sha256"] == lakebase.draft_sha256("Banksia: outage near X.")


def test_incident_panel_survives_a_warehouse_failure():
    class Broken(FakeWarehouse):
        def query(self, user_token, sql, params=None):
            if sql == wh.REGION_SCOPE_SQL:
                return super().query(user_token, sql, params)
            raise RuntimeError("warehouse starting")

    d = svc(warehouse=Broken()).incident(NATIONAL, "RCA-1")
    assert d["detection"]["available"] is False and "warehouse starting" in d["detection"]["error"]
    assert d["pinpoint"]["element_id"] == "SITE-NSW-00002"  # from Lakebase
    assert d["path_from_core"] == []


def test_topology_for_an_incident_highlights_its_suspects():
    t = svc().topology(NATIONAL, "NSW", "RCA-1")
    assert t["graph"]["pinpoint"] == "SITE-NSW-00002"
    assert t["state_counts"]["SITE"]["down"] == 1
    assert any(p["suspect_rank"] == 1 for p in t["map"])
    with pytest.raises(NotFound):
        svc().topology(NATIONAL, "NSW", "RCA-2")  # RCA-2 is a VIC incident


# ---- SMS review write path ------------------------------------------------------------------------------------------

def test_approve_records_who_when_and_never_sends():
    store = FakeStore()
    s = svc(store=store)
    r = s.review_sms(NSW, "RCA-1", "approve", "SUM-RCA-1", "ok to send by hand")
    assert r["decision"] == "approved" and r["reviewed_by"] == NSW.email and r["reviewed_at"]
    assert r["sent"] is False and r["sent_at"] is None and r["send_channel"] == "none"
    row = store.saved[0]
    assert row["app_identity"] == "app-sp-client-id" and row["region_code"] == "NSW"
    assert row["draft_sha256"] == lakebase.draft_sha256("Banksia: outage near X.")
    assert s.incident(NSW, "RCA-1")["sms"]["decision"] == "approved"


def test_reject_then_history_is_append_only():
    store = FakeStore()
    s = svc(store=store)
    s.review_sms(NATIONAL, "RCA-1", "approve", "SUM-RCA-1")
    s.review_sms(NATIONAL, "RCA-1", "reject", "SUM-RCA-1", "wrong suburb")
    hist = s.reviews(NATIONAL, "RCA-1")
    assert [h["decision"] for h in hist] == ["rejected", "approved"]
    assert s.incident(NATIONAL, "RCA-1")["sms"]["decision"] == "rejected"
    assert s.reviews(NSW, "RCA-2") == []  # other region


@pytest.mark.parametrize(("user", "incident", "decision", "summary", "note", "err"), [
    (NSW, "RCA-1", "send", "SUM-RCA-1", None, BadRequest),
    (User(None, "tok-nsw"), "RCA-1", "approve", "SUM-RCA-1", None, Unauthorized),
    (NSW, "RCA-1", "approve", "SUM-OLD", None, Conflict),
    (NSW, "RCA-2", "approve", "SUM-RCA-2", None, NotFound),
    (NOBODY, "RCA-1", "approve", "SUM-RCA-1", None, NotFound),
    (NSW, "RCA-1", "approve", "SUM-RCA-1", "x" * 501, BadRequest),
])
def test_review_rejections(user, incident, decision, summary, note, err):
    store = FakeStore()
    with pytest.raises(err):
        svc(store=store).review_sms(user, incident, decision, summary, note)
    assert store.saved == []


def test_review_without_a_draft_is_a_conflict():
    store = FakeStore(incidents=[incident_row(draft=None)])
    with pytest.raises(Conflict):
        svc(store=store).review_sms(NSW, "RCA-1", "approve", "SUM-RCA-1")


def test_review_table_cannot_record_a_send():
    ddl = " ".join(lakebase.SCHEMA_DDL)
    assert "CHECK (sent_at IS NULL)" in ddl and "CHECK (send_channel = 'none')" in ddl
    assert "CHECK (decision IN ('approved', 'rejected'))" in ddl
    assert "reviewed_by   text NOT NULL" in ddl and "reviewed_at   timestamptz NOT NULL DEFAULT now()" in ddl
    insert = lakebase.INSERT_REVIEW_SQL.split("VALUES")[0]
    assert "sent_at" not in insert and "send_channel" not in insert


# ---- KPIs and Genie ------------------------------------------------------------------------------------------------

def test_kpis_are_operational_only_and_scoped_by_uc():
    s = svc()
    k = s.kpis(NATIONAL)
    assert set(k) == {"operational"}  # no ground-truth scorecard
    assert [r["region_code"] for r in k["operational"]] == ["NSW", "VIC"]
    assert [r["region_code"] for r in s.kpis(NSW)["operational"]] == ["NSW"]


def test_genie_runs_as_the_user():
    g = FakeGenie()
    a = svc(genie=g).ask_genie(NSW, "  Which sites are down?  ")
    assert g.calls == [("tok-nsw", "Which sites are down?", None)]
    assert a["rows"] == [["SITE-NSW-00002"]]
    with pytest.raises(Unauthorized):
        svc().ask_genie(User("x", None), "hi")
    with pytest.raises(BadRequest):
        svc().ask_genie(NSW, " ")
    with pytest.raises(BadRequest):
        svc().ask_genie(NSW, "q" * 501)
