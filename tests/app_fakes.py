"""In-memory stand-ins for the app's three sources (Lakebase store, SQL warehouse as the user, Genie)."""

from __future__ import annotations

from datetime import datetime, timezone

from noc_app import warehouse as wh
from noc_app.config import Settings


def node(eid, etype, parent, region="NSW", lat=-33.9, lon=151.1, **kw):
    return {"element_id": eid, "element_type": etype, "name": f"{etype.lower()} {eid}", "parent_id": parent,
            "region_code": region, "lat": lat, "lon": lon, **kw}


def topology_nodes(region="NSW", n_bh=6, n_sites=4):
    """AMF > UPF > 2 routers > n_bh backhaul links (router 1) > n_sites sites on BH-1 > 3 cells each."""
    r = region
    nodes = [node(f"AMF-{r}-01", "AMF_MME", None, r), node(f"UPF-{r}-01", "UPF_SGW", f"AMF-{r}-01", r),
             node(f"AGG-{r}-01", "AGG_ROUTER", f"UPF-{r}-01", r), node(f"AGG-{r}-02", "AGG_ROUTER", f"UPF-{r}-01", r)]
    for b in range(1, n_bh + 1):
        nodes.append(node(f"BH-{r}-{b:04d}", "BACKHAUL_LINK", f"AGG-{r}-01", r))
    for s in range(1, n_sites + 1):
        sid = f"SITE-{r}-{s:05d}"
        nodes.append(node(sid, "SITE", f"BH-{r}-0001", r, lat=-33.9 + s / 100))
        for c in range(1, 4):
            nodes.append(node(f"CELL-{r}-{s:05d}-4G{c}", "CELL", sid, r, lat=-33.9 + s / 100))
    return nodes


def status_rows(region="NSW", down_site="SITE-NSW-00002", incident="RCA-1"):
    rows = []
    for n in topology_nodes(region):
        st = "ok"
        if n["element_id"] == down_site or n["parent_id"] == down_site:
            st = "down"
        elif n["element_id"] in (f"BH-{region}-0001", f"AGG-{region}-01", f"UPF-{region}-01", f"AMF-{region}-01"):
            st = "impacted"
        rows.append({"element_id": n["element_id"], "element_type": n["element_type"], "parent_id": n["parent_id"],
                     "region_code": region, "state": st, "rca_score": 0.97 if n["element_id"] == down_site else 0.01,
                     "n_impacted_cells": 3.0 if st != "ok" else 0.0, "n_desc_cells": 3.0,
                     "open_incident_id": incident if n["element_id"] == down_site else None,
                     "suspect_rank": 1.0 if n["element_id"] == down_site else None})
    return rows


T0 = datetime(2026, 10, 9, 0, 10, tzinfo=timezone.utc)


def incident_row(incident_id="RCA-1", region="NSW", suspect="SITE-NSW-00002", draft="Banksia: outage near X."):
    return {"incident_id": incident_id, "region_code": region, "detected_ts": T0, "last_scored_ts": T0,
            "status": "open", "suspect_1_id": suspect, "suspect_1_type": "SITE", "suspect_1_score": 0.97,
            "suspect_2_id": f"BH-{region}-0001", "suspect_2_type": "BACKHAUL_LINK", "suspect_2_score": 0.02,
            "suspect_3_id": f"AGG-{region}-01", "suspect_3_type": "AGG_ROUTER", "suspect_3_score": 0.01,
            "n_impacted_cells": 3, "n_candidates": 9, "model_version": "5", "summary_id": f"SUM-{incident_id}",
            "ai_generated_at": T0, "likely_root_cause": suspect, "fault_hypothesis": "SITE_POWER_OUTAGE",
            "confidence": "high", "ai_summary": "Site dark after mains failure.",
            "next_steps_json": '["Check mains power alarms", "Dispatch field tech"]',
            "est_affected_subscribers": 420, "ai_impacted_cells": 3, "ai_impacted_sites": 1,
            "impact_description": "3 cells dark", "sms_draft_text": draft, "sms_draft_status": "draft",
            "ai_generated_by": "llm", "noc_prompt_version": "noc_summary_v3@abc", "sms_decision": None,
            "sms_reviewed_by": None, "sms_reviewed_at": None}


class FakeStore:
    def __init__(self, incidents=None, status=None):
        self.rows = incidents if incidents is not None else [incident_row(), incident_row("RCA-2", "VIC",
                                                                                          "SITE-VIC-00002")]
        self.status = status if status is not None else {"NSW": status_rows("NSW"),
                                                          "VIC": status_rows("VIC", "SITE-VIC-00002", "RCA-2")}
        self.saved: list[dict] = []
        self.calls: list[tuple] = []

    def incidents(self, regions):
        self.calls.append(("incidents", tuple(regions)))
        return [dict(r) for r in self.rows if r["region_code"] in regions]

    def incident(self, incident_id, regions):
        self.calls.append(("incident", incident_id, tuple(regions)))
        for r in self.rows:
            if r["incident_id"] == incident_id and r["region_code"] in regions:
                last = next((s for s in reversed(self.saved) if s["incident_id"] == incident_id
                             and s["summary_id"] == r["summary_id"]), None)
                return {**r, **({"sms_decision": last["decision"], "sms_reviewed_by": last["reviewed_by"],
                                 "sms_reviewed_at": last["reviewed_at"]} if last else {})}
        return None

    def element_status(self, region):
        return [dict(r) for r in self.status.get(region, [])]

    def insert_review(self, row):
        saved = {**row, "reviewed_at": T0, "sent_at": None, "send_channel": "none"}
        saved.pop("draft_text")
        self.saved.append(saved)
        return dict(saved)

    def reviews(self, incident_id, regions):
        return [s for s in reversed(self.saved) if s["incident_id"] == incident_id and s["region_code"] in regions]

    def ping(self):
        return {"pg_user": "app-sp", "server_time": "2026-11-07T00:00:00Z"}


class FakeWarehouse:
    """Answers the app's UC queries; `regions_by_token` stands in for the row filter of the netmon_noc views."""

    def __init__(self, regions_by_token=None):
        self.regions_by_token = regions_by_token or {"tok-national": ["NSW", "VIC"], "tok-nsw": ["NSW"]}
        self.calls: list[tuple] = []

    def query(self, user_token, sql, params=None):
        self.calls.append((user_token, sql, params))
        assert "netmon_eval" not in sql and "{eval}" not in sql, "the app must never query ground truth"
        visible = self.regions_by_token.get(user_token, [])
        if sql == wh.REGION_SCOPE_SQL:
            return [{"region_code": r} for r in visible]
        if sql == wh.TOPOLOGY_SQL:
            return topology_nodes(params["region"]) if params["region"] in visible else []
        if sql == wh.DETECTION_TIMES_SQL:
            return [{"incident_id": params["incident_id"], "time_to_detect_s": 162.4, "detected_within_5min": True,
                     "first_impact_signal_ts": "2026-10-09T00:08:00Z", "first_detection_ts": "2026-10-09T00:10:42Z"}]
        if sql == wh.KPI_SQL:
            return [{"region_code": r, "n_open_incidents": 1, "mttd_s": 160.0, "pct_detected_within_5min": 100.0}
                    for r in visible]
        raise AssertionError(f"unexpected SQL {sql}")


class FakeGenie:
    def __init__(self, answer=None):
        self.answer = answer
        self.calls: list[tuple] = []

    def ask(self, user_token, question, conversation_id=None):
        self.calls.append((user_token, question, conversation_id))
        return self.answer or {"conversation_id": "c1", "message_id": "m1", "status": "COMPLETED",
                               "text": ["2 sites are down."], "sql": "SELECT 1", "columns": ["element_id"],
                               "rows": [["SITE-NSW-00002"]], "row_count": 1}


def settings(**kw):
    base = dict(catalog="cat", warehouse_id="wh", genie_space_id="space", lakebase_instance="lb",
                app_identity="app-sp-client-id", dev_regions=())
    base.update(kw)
    return Settings(**base)
