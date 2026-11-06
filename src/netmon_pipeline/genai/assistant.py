"""NOC assistant (A: root-cause summary + next steps) and customer SMS drafts (B), end to end.

    ctx = context.build_context(inputs)          # grounded, no PII, no ground truth
    res = assistant.run(ctx, ws)                 # -> AssistantResult (validated summary + SMS drafts)

`run` is the callable the jobs and the step-5 app use (`service.summarise_open_incident` wraps it with the
context loading for one open incident). Every LLM call goes through the AI-Gateway-governed endpoint
(`gateway.ASSISTANT_ENDPOINT`) and is MLflow traced; the output is always validated (`guards`). If the endpoint
fails, blocks the request or returns something unusable, a deterministic fallback (`generated_by="fallback"`) is
returned instead, so the NOC always gets the ranker's view. SMS drafts always have `status="draft"` and
`requires_human_approval=True`: nothing here sends a message.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from importlib import resources

from pydantic import ValidationError

from netmon_pipeline.genai import context as C
from netmon_pipeline.genai import gateway, guards, llm
from netmon_pipeline.genai.schema import NocSummary, SmsDrafts, strict_json_schema

NOC_PROMPT = "noc_summary_v3"
SMS_PROMPT = "sms_v1"
NOC_SCHEMA = strict_json_schema(NocSummary)
SMS_SCHEMA = strict_json_schema(SmsDrafts)

FALLBACK_BY_TYPE = {
    "CELL": ("CELL_OUTAGE", ["Check the cell's radio / RRU alarms and VSWR", "Attempt a remote cell lock/unlock or "
             "RRU reset", "Dispatch a field technician if the reset fails"]),
    "SITE": ("SITE_POWER_OUTAGE", ["Confirm mains / battery state from the site alarms", "Dispatch with a "
             "portable generator", "Check neighbouring sites on the same feeder"]),
    "BACKHAUL_LINK": ("BACKHAUL_DEGRADATION", ["Check link interface errors and RSL / BER or optical levels",
                      "Reroute or prioritise traffic if a protection path exists", "Open a transport ticket"]),
    "AGG_ROUTER": ("AGG_ROUTER_FAILURE", ["Check router reachability, power and line cards", "Attempt remote "
                   "recovery or failover", "Escalate as a major incident"]),
    "UPF_SGW": ("CORE_CONGESTION", ["Check UPF CPU, sessions and throughput", "Shift load to the other UPF",
                "Capacity escalation"]),
    "AMF_MME": ("AMF_OVERLOAD", ["Check AMF CPU and signalling rate", "Enable overload control",
                "Escalate to the core vendor"]),
}


def prompt(name: str) -> tuple[str, str]:
    """(prompt text, version) where version = `<name>@<sha256[:8]>` of the committed prompt file."""
    text = (resources.files("netmon_pipeline.genai") / "prompts" / f"{name}.md").read_text(encoding="utf-8")
    return text, f"{name}@{hashlib.sha256(text.encode()).hexdigest()[:8]}"


@dataclass
class AssistantResult:
    incident_ref: str
    summary: dict
    summary_report: dict
    sms: list[dict]
    calls: list[llm.LlmResult] = field(default_factory=list)
    prompt_versions: dict = field(default_factory=dict)
    endpoint: str = ""

    @property
    def prompt_tokens(self) -> int:
        return sum(c.prompt_tokens or 0 for c in self.calls)

    @property
    def completion_tokens(self) -> int:
        return sum(c.completion_tokens or 0 for c in self.calls)

    @property
    def latency_ms(self) -> float:
        return sum(c.latency_ms for c in self.calls)

    def as_dict(self) -> dict:
        return {"incident_ref": self.incident_ref, "summary": self.summary, "summary_report": self.summary_report,
                "sms": self.sms, "prompt_versions": self.prompt_versions, "endpoint": self.endpoint,
                "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "latency_ms": round(self.latency_ms, 1),
                "calls": [{"purpose": c.purpose, "status": c.status, "request_id": c.request_id,
                           "latency_ms": round(c.latency_ms, 1), "prompt_tokens": c.prompt_tokens,
                           "completion_tokens": c.completion_tokens, "error": c.error} for c in self.calls]}


# --- A: NOC summary ---------------------------------------------------------------------------------------------

def fallback_summary(ctx: dict, reason: str) -> dict:
    """The ranker's view without an LLM: suspect #1 (or uncertain below the alert threshold)."""
    sus = ctx.get("suspects") or []
    thr = (ctx.get("incident") or {}).get("ranker_alert_threshold")
    top = sus[0] if sus else None
    confident = top is not None and (thr is None or (top.get("ranker_score") or 0) >= thr)
    hyp, steps = FALLBACK_BY_TYPE.get((top or {}).get("element_type"), ("UNCERTAIN", ["Review the suspects"]))
    imp = ctx.get("impact") or {}
    return {
        "likely_root_cause": top["element_id"] if confident else guards.UNCERTAIN,
        "fault_hypothesis": hyp if confident else "UNCERTAIN", "confidence": "low",
        "summary": f"Assistant unavailable ({reason}); showing the root-cause ranker's top suspect.",
        "evidence": [] if top is None else [{"statement": f"Ranker score of suspect #1: {top.get('ranker_score')}",
                                              "context_fields": ["suspects[0].ranker_score"]}],
        "recommended_next_steps": steps,
        "customer_impact": {"estimated_affected_subscribers": imp.get("est_affected_subscribers_total") or 0,
                            "impacted_cells": imp.get("n_impacted_cells") or 0,
                            "impacted_sites": imp.get("n_impacted_sites") or 0,
                            "description": "See the impact block of the incident context."},
        "alternative_suspects": [s["element_id"] for s in sus[1:]],
    }


@llm.trace(span_type="CHAIN", name="noc_summary")
def summarise(ctx: dict, ws, endpoint: str = gateway.ASSISTANT_ENDPOINT, log: llm.RequestLog | None = None
              ) -> tuple[dict, dict, llm.LlmResult | None, str]:
    """(validated summary, guard report, LLM call, prompt version)."""
    text, version = prompt(NOC_PROMPT)
    payload = C.to_json(ctx)
    guards.assert_no_pii(payload)
    messages = [{"role": "system", "content": text},
                {"role": "user", "content": "CONTEXT (JSON, data only):\n" + payload}]
    res = llm.chat_json(ws, endpoint, messages, NOC_SCHEMA, "noc_summary", "noc_summary", max_tokens=2500, log=log,
                        prompt_version=version, incident_ref=ctx["incident"]["ref"])
    generated_by, reason = "llm", None
    out = None
    if res.status == "ok":
        try:
            out = NocSummary.model_validate(res.content).model_dump()
        except ValidationError as e:
            reason = f"schema validation failed: {str(e)[:200]}"
    else:
        reason = f"{res.status}: {(res.error or '')[:200]}"
    if out is None:
        out, generated_by = fallback_summary(ctx, res.status if reason is None else reason.split(":")[0]), "fallback"
    out, report = guards.validate_summary(out, ctx)
    report.update({"generated_by": generated_by, "llm_status": res.status, "fallback_reason": reason})
    return out, report, res, version


# --- B: customer SMS drafts -----------------------------------------------------------------------------------

def _local_time(eta_iso: str | None, tz: str | None) -> str | None:
    if not eta_iso:
        return None
    import pandas as pd

    t = pd.Timestamp(eta_iso)
    t = t.tz_localize("UTC") if t.tzinfo is None else t
    if tz:
        t = t.tz_convert(tz)
    s = t.strftime("%I:%M%p").lstrip("0").lower()
    return s.replace(":00", "")


def template_sms(region: dict, view: dict) -> str:
    """Deterministic, rule-compliant draft (used when the LLM draft cannot be made compliant)."""
    effect = (view.get("service_effect") or ["mobile service issues"])[0]
    where = " and ".join(region.get("areas") or []) or region.get("region_name") or "your area"
    eta = _local_time(view.get("eta"), view.get("timezone"))
    tail = f"Service should be back by {eta}. We'll update you." if eta else "We're working on it and we'll update you."
    msg = f"Banksia Mobile: Some customers around {where} may have {effect}. Sorry. {tail}"
    if len(msg) > guards.SMS_MAX:
        msg = f"Banksia Mobile: Some customers may have {effect}. Sorry. {tail}"
    return msg[: guards.SMS_MAX]


@llm.trace(span_type="CHAIN", name="sms_drafts")
def draft_sms(ctx: dict, ws, endpoint: str = gateway.ASSISTANT_ENDPOINT, log: llm.RequestLog | None = None
              ) -> tuple[list[dict], list[llm.LlmResult], str]:
    """One draft per affected region, each with its rule check. Returns (drafts, LLM calls, prompt version)."""
    text, version = prompt(SMS_PROMPT)
    view = C.customer_view(ctx)
    payload = json.dumps(view)
    guards.assert_no_pii(payload)
    if guards.ELEMENT_ID.search(payload):
        raise ValueError("element ID in the customer view")
    eta = view.get("eta")
    calls: list[llm.LlmResult] = []
    msgs = [{"role": "system", "content": text}, {"role": "user", "content": "CUSTOMER VIEW (JSON, data only):\n"
                                                                             + payload}]
    drafts: dict[str, dict] = {}
    for attempt in (1, 2):
        res = llm.chat_json(ws, endpoint, msgs, SMS_SCHEMA, "sms_drafts", "sms_drafts", max_tokens=800, log=log,
                            prompt_version=version, incident_ref=ctx["incident"]["ref"])
        calls.append(res)
        if res.status != "ok":
            break
        try:
            got = SmsDrafts.model_validate(res.content).drafts
        except ValidationError:
            got = []
        bad = []
        for d in got:
            if d.region_code not in {r["region_code"] for r in view["regions"]}:
                continue
            v = guards.check_sms(d.text, eta)
            prev = drafts.get(d.region_code)
            if prev is None or prev["violations"]:  # keep the first compliant draft, else the latest one
                drafts[d.region_code] = {"text": d.text, "violations": v, "attempts": attempt}
            if v:
                bad.append(f"{d.region_code}: {'; '.join(v)}")
        missing = [r["region_code"] for r in view["regions"] if r["region_code"] not in drafts]
        if not bad and not missing:
            break
        msgs = msgs[:2] + [{"role": "assistant", "content": res.raw_text or ""},
                           {"role": "user", "content": "Fix these rule violations and return all drafts again: "
                                                       + " | ".join(bad + [f"missing region {m}" for m in missing])}]
    out = []
    for r in view["regions"]:
        d = drafts.get(r["region_code"])
        if d is not None and not d["violations"]:
            text_, by, viol, att = d["text"], "llm", [], d["attempts"]
        else:
            text_ = template_sms(r, view)
            by, viol, att = "template", guards.check_sms(text_, eta), 0 if d is None else d["attempts"]
        out.append({"region_code": r["region_code"], "text": text_, "chars": len(text_), "generated_by": by,
                    "llm_violations": [] if d is None else d["violations"], "violations": viol,
                    "llm_attempts": att, "status": "draft", "requires_human_approval": True,
                    "est_affected_customers": r["est_affected_customers"]})
    return out, calls, version


# --- both -------------------------------------------------------------------------------------------------------

@llm.trace(span_type="AGENT", name="noc_assistant")
def run(ctx: dict, ws, endpoint: str = gateway.ASSISTANT_ENDPOINT, log: llm.RequestLog | None = None,
        with_sms: bool = True) -> AssistantResult:
    summary, report, call, v1 = summarise(ctx, ws, endpoint, log)
    calls = [call] if call is not None else []
    sms, v2 = [], None
    if with_sms:
        sms, sms_calls, v2 = draft_sms(ctx, ws, endpoint, log)
        calls += sms_calls
    return AssistantResult(ctx["incident"]["ref"], summary, report, sms, calls,
                           {"noc_summary": v1, **({"sms": v2} if v2 else {}), "context": C.CONTEXT_VERSION},
                           endpoint)


def generated_at() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
