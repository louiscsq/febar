"""NOC app use cases over three sources, each with its own identity (docs/topology_app.md, "Identity"):

| source | identity | what |
|---|---|---|
| Lakebase (`store`) | app service principal | hot path: open incidents + top-3 suspects, element status, AI summary + SMS draft; the SMS review write |
| SQL warehouse (`warehouse`) | signed-in user (OBO token) | region scope, network inventory, detection timing, KPI scorecard |
| Genie (`genie`) | signed-in user (OBO token) | "Ask Genie" |

Lakebase has no Unity Catalog row filters, so the user's region scope is taken from UC (the regions whose rows the
`netmon_noc` views return for that user) and every Lakebase read and write is restricted to it here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from . import topology
from . import warehouse as wh
from .lakebase import Store, draft_sha256, new_review_id
from .safety import scrub
from .warehouse import TTLCache, Warehouse

DECISIONS = {"approve": "approved", "reject": "rejected"}


class AppError(Exception):
    status = 400


class BadRequest(AppError):
    status = 400


class Unauthorized(AppError):
    status = 401


class Forbidden(AppError):
    status = 403


class NotFound(AppError):
    status = 404


class Conflict(AppError):
    status = 409


@dataclass(frozen=True)
class User:
    email: str | None
    token: str | None = None
    name: str | None = None


def _suspects(inc: dict) -> list[dict]:
    out = []
    for k in (1, 2, 3):
        eid = inc.get(f"suspect_{k}_id")
        if eid:
            out.append({"element_id": eid, "element_type": inc.get(f"suspect_{k}_type"), "rank": k,
                        "score": inc.get(f"suspect_{k}_score")})
    return out


def _json_list(s: Any) -> list:
    if not s:
        return []
    try:
        v = json.loads(s) if isinstance(s, str) else s
        return v if isinstance(v, list) else [v]
    except (TypeError, ValueError):
        return [str(s)]


class NocService:
    def __init__(self, settings, store: Store, warehouse: Warehouse, genie, scope_ttl_s: float = 300,
                 topology_ttl_s: float = 900, timing_ttl_s: float = 120):
        self.s, self.store, self.wh, self.genie = settings, store, warehouse, genie
        self._scope = TTLCache(scope_ttl_s)
        self._topo = TTLCache(topology_ttl_s)
        self._ttd_cache = TTLCache(timing_ttl_s)

    # ---- identity and scope ------------------------------------------------------------------------------------
    def regions(self, user: User) -> list[str]:
        """Regions the user may see, as decided by Unity Catalog (row filter on the netmon_noc views)."""
        if user.token:
            rows = self._scope.get(("scope", user.email), lambda: self.wh.query(user.token, wh.REGION_SCOPE_SQL))
            return sorted({r["region_code"] for r in rows if r.get("region_code")})
        return sorted(self.s.dev_regions)

    def _scoped(self, user: User, region: str | None = None) -> list[str]:
        scope = self.regions(user)
        if region is None:
            return scope
        if region not in scope:
            raise Forbidden(f"region {region} is not in your NOC scope {scope}")
        return [region]

    def me(self, user: User) -> dict:
        return {"user": user.email, "name": user.name, "regions": self.regions(user),
                "on_behalf_of_user": bool(user.token), "identities": {
                    "lakebase": f"app service principal ({self.s.app_identity})",
                    "sql_warehouse": "signed-in user (on-behalf-of token)" if user.token else "none (no user token)",
                    "genie": "signed-in user (on-behalf-of token)" if user.token else "none (no user token)"}}

    # ---- topology ----------------------------------------------------------------------------------------------
    def _nodes(self, user: User, region: str) -> list[dict]:
        return self._topo.get(("topo", region), lambda: self.wh.query(user.token, wh.TOPOLOGY_SQL, {"region": region}))

    def topology(self, user: User, region: str, incident_id: str | None = None) -> dict:
        self._scoped(user, region)
        nodes = self._nodes(user, region)
        status = {r["element_id"]: r for r in self.store.element_status(region)}
        suspects: list[dict] = []
        if incident_id:
            inc = self.store.incident(incident_id, [region])
            if not inc:
                raise NotFound(f"no open incident {incident_id} in {region}")
            suspects = _suspects(inc)
            graph = topology.incident_focus(nodes, status, suspects)
        else:
            graph = topology.region_overview(nodes, status)
        counts: dict[str, dict[str, int]] = {}
        for r in status.values():
            c = counts.setdefault(r["element_type"], {})
            c[r["state"]] = c.get(r["state"], 0) + 1
        return {"region": region, "incident_id": incident_id, "graph": graph,
                "map": topology.map_points(nodes, status, suspects), "state_counts": counts,
                "n_elements": len(nodes)}

    # ---- incidents ---------------------------------------------------------------------------------------------
    def incidents(self, user: User, region: str | None = None) -> list[dict]:
        scope = self._scoped(user, region)
        rows = self.store.incidents(scope) if scope else []
        return [{
            "incident_id": r["incident_id"], "region_code": r["region_code"], "detected_ts": r["detected_ts"],
            "suspect_1_id": r["suspect_1_id"], "suspect_1_type": r["suspect_1_type"],
            "suspect_1_score": r["suspect_1_score"], "n_impacted_cells": r["n_impacted_cells"],
            "est_affected_subscribers": r.get("est_affected_subscribers"),
            "fault_hypothesis": r.get("fault_hypothesis"), "sms_decision": r.get("sms_decision") or "pending",
        } for r in rows]

    def _timing(self, user: User, incident_id: str) -> dict:
        try:
            rows = self._ttd_cache.get(("ttd", incident_id), lambda: self.wh.query(
                user.token, wh.DETECTION_TIMES_SQL, {"incident_id": incident_id}))
            return {"available": bool(rows), **(rows[0] if rows else {})}
        except Exception as e:  # noqa: BLE001 - the panel still renders from Lakebase
            return {"available": False, "error": str(e)[:200]}

    def incident(self, user: User, incident_id: str) -> dict:
        scope = self._scoped(user)
        inc = self.store.incident(incident_id, scope) if scope else None
        if not inc:
            raise NotFound(f"no open incident {incident_id} in your regions")
        region = inc["region_code"]
        status = {r["element_id"]: r for r in self.store.element_status(region)}
        try:
            names = {n["element_id"]: n for n in self._nodes(user, region)}
        except Exception:  # noqa: BLE001
            names = {}
        inv = topology.Inventory(names.values()) if names else None
        suspects = []
        for s in _suspects(inc):
            st, n = status.get(s["element_id"], {}), names.get(s["element_id"], {})
            suspects.append({**s, "name": n.get("name"), "state": st.get("state"), "lat": n.get("lat"),
                             "lon": n.get("lon"), "n_impacted_cells": st.get("n_impacted_cells"),
                             "n_desc_cells": st.get("n_desc_cells"), "n_alarms": st.get("n_alarms")})
        pin = suspects[0] if suspects else None
        path = []
        if pin and inv:
            path = [{"element_id": e, "element_type": names[e]["element_type"], "name": names[e].get("name"),
                     "state": topology.state_of(status, e)} for e in inv.ancestors(pin["element_id"])]
        timing = self._timing(user, incident_id)
        draft = inc.get("sms_draft_text")
        return {
            "incident_id": incident_id, "region_code": region, "status": inc["status"],
            "detected_ts": inc["detected_ts"], "last_scored_ts": inc["last_scored_ts"],
            "model_version": inc["model_version"],
            "detection": timing,
            "impact": {"impacted_cells": inc["n_impacted_cells"], "impacted_sites": inc.get("ai_impacted_sites"),
                       "est_affected_subscribers": inc.get("est_affected_subscribers"),
                       "description": inc.get("impact_description")},
            "pinpoint": pin, "path_from_core": path, "suspects": suspects,
            "ai": {"summary_id": inc.get("summary_id"), "generated_at": inc.get("ai_generated_at"),
                   "likely_root_cause": inc.get("likely_root_cause"), "fault_hypothesis": inc.get("fault_hypothesis"),
                   "confidence": inc.get("confidence"), "summary": inc.get("ai_summary"),
                   "next_steps": _json_list(inc.get("next_steps_json")), "generated_by": inc.get("ai_generated_by"),
                   "prompt_version": inc.get("noc_prompt_version"),
                   "agrees_with_ranker": bool(pin) and inc.get("likely_root_cause") == pin["element_id"]},
            "sms": {"summary_id": inc.get("summary_id"), "text": draft, "draft_status": inc.get("sms_draft_status"),
                    "draft_sha256": draft_sha256(draft) if draft else None,
                    "decision": inc.get("sms_decision") or "pending", "reviewed_by": inc.get("sms_reviewed_by"),
                    "reviewed_at": inc.get("sms_reviewed_at"), "sent": False,
                    "note": "Draft only: this system never sends messages."},
        }

    # ---- SMS draft review (the operational write path) ---------------------------------------------------------
    def review_sms(self, user: User, incident_id: str, decision: str, summary_id: str | None,
                   note: str | None = None) -> dict:
        if decision not in DECISIONS:
            raise BadRequest("decision must be 'approve' or 'reject'")
        if not user.email:
            raise Unauthorized("no signed-in user: reviews need an identity")
        if note is not None and len(note) > 500:
            raise BadRequest("note is limited to 500 characters")
        scope = self._scoped(user)
        inc = self.store.incident(incident_id, scope) if scope else None
        if not inc:
            raise NotFound(f"no open incident {incident_id} in your regions")
        draft = inc.get("sms_draft_text")
        if not draft or not inc.get("summary_id"):
            raise Conflict("this incident has no SMS draft to review")
        if summary_id and summary_id != inc["summary_id"]:
            raise Conflict("the draft changed since you opened it; reload and review the current draft")
        row = {"review_id": new_review_id(), "incident_id": incident_id, "summary_id": inc["summary_id"],
               "region_code": inc["region_code"], "draft_sha256": draft_sha256(draft), "draft_text": draft,
               "decision": DECISIONS[decision], "note": (note or None), "reviewed_by": user.email,
               "app_identity": self.s.app_identity}
        saved = self.store.insert_review(row)
        return {**saved, "sent": False}

    def reviews(self, user: User, incident_id: str) -> list[dict]:
        scope = self._scoped(user)
        return self.store.reviews(incident_id, scope) if scope else []

    # ---- analytics and Genie -----------------------------------------------------------------------------------
    def kpis(self, user: User) -> dict:
        out: dict[str, Any] = {"operational": [], "scorecard": None}
        out["operational"] = self.wh.query(user.token, wh.KPI_SQL)
        try:
            rows = self.wh.query(user.token, wh.SCORECARD_SQL)
            out["scorecard"] = {"available": True, "label": "evaluation (ground-truth scored, live feed)",
                                **(rows[0] if rows else {})}
        except Exception as e:  # noqa: BLE001 - regional roles hold no grant on the eval schema
            out["scorecard"] = {"available": False, "reason": str(e)[:200]}
        return out

    def ask_genie(self, user: User, question: str, conversation_id: str | None = None) -> dict:
        q = (question or "").strip()
        if not q:
            raise BadRequest("empty question")
        if len(q) > 500:
            raise BadRequest("questions are limited to 500 characters")
        if not user.token:
            raise Unauthorized("Ask Genie runs as the signed-in user; no user token was forwarded")
        return scrub(self.genie.ask(user.token, q, conversation_id))
