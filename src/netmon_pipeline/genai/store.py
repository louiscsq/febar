"""Output tables of the assistant (Unity Catalog, schema `netmon_genai`) and the rows written to them.

| table | write | content |
|---|---|---|
| `incident_ai_summaries` | append | every generated NOC summary: incident, model / prompt / context versions, generated_at, the structured output, the guard report, latency, tokens, `status = 'draft'` (for the NOC to review) and the context it was grounded on |
| `customer_notice_drafts` | append | one SMS draft per incident x affected region: text, rule check, `status = 'draft'`, `requires_human_approval = true`; `approved_by` / `approved_at` / `sent_at` are always NULL here: **this system never sends**, a human approves and sends in the customer-comms tool |
| `incident_ai_latest` | MERGE (Change Data Feed) | the latest summary + SMS draft per **open** incident (closed incidents deleted); source of the Lakebase synced table `lb_incident_ai_latest` the step-5 app reads |
| `noc_assistant_request_log` | append | every LLM request / response (in place of the AI Gateway inference table; see `gateway.apply`) |
"""

from __future__ import annotations

import json
import uuid

import pandas as pd

from netmon_pipeline.genai import assistant
from netmon_pipeline.genai.llm import RequestLog

SUMMARY_DDL = (
    "summary_id STRING, incident_id STRING, source_run STRING, region_code STRING, generated_at TIMESTAMP, "
    "as_of TIMESTAMP, suspects_signature STRING, status STRING, assistant_endpoint STRING, noc_prompt_version STRING, "
    "context_version STRING, ranker_model_version STRING, likely_root_cause STRING, fault_hypothesis STRING, "
    "confidence STRING, summary STRING, evidence_json STRING, next_steps_json STRING, est_affected_subscribers BIGINT, "
    "impacted_cells BIGINT, impacted_sites BIGINT, impact_description STRING, alternative_suspects_json STRING, "
    "generated_by STRING, n_repairs BIGINT, guard_report_json STRING, latency_ms DOUBLE, prompt_tokens BIGINT, "
    "completion_tokens BIGINT, context_json STRING")
DRAFT_DDL = (
    "draft_id STRING, summary_id STRING, incident_id STRING, region_code STRING, generated_at TIMESTAMP, status STRING, "
    "requires_human_approval BOOLEAN, approved_by STRING, approved_at TIMESTAMP, sent_at TIMESTAMP, channel STRING, "
    "text STRING, chars BIGINT, generated_by STRING, violations_json STRING, llm_violations_json STRING, "
    "est_affected_customers BIGINT, sms_prompt_version STRING")
LATEST_DDL = (
    "incident_id STRING, summary_id STRING, source_run STRING, region_code STRING, generated_at TIMESTAMP, "
    "as_of TIMESTAMP, suspects_signature STRING, status STRING, likely_root_cause STRING, fault_hypothesis STRING, "
    "confidence STRING, summary STRING, next_steps_json STRING, evidence_json STRING, est_affected_subscribers BIGINT, "
    "impacted_cells BIGINT, impacted_sites BIGINT, impact_description STRING, sms_draft_text STRING, "
    "sms_draft_status STRING, n_sms_drafts BIGINT, generated_by STRING, noc_prompt_version STRING, "
    "assistant_endpoint STRING, refreshed_at TIMESTAMP")
REQUEST_LOG_DDL = (
    "request_id STRING, request_time STRING, endpoint STRING, purpose STRING, prompt_version STRING, incident_ref STRING, "
    "status STRING, error STRING, latency_ms DOUBLE, attempts BIGINT, prompt_tokens BIGINT, completion_tokens BIGINT, "
    "request_sha256 STRING, request STRING, response STRING")


def suspects_signature(row: dict) -> str:
    """Identity of what the summary was grounded on and how: the suspects, the ranker version and the prompt version.
    A new summary is generated only when this changes (new incident, re-ranked suspects, new model, new prompt)."""
    keys = ("suspect_1_id", "suspect_2_id", "suspect_3_id", "model_version")
    return "|".join([*(str(row.get(k) or "") for k in keys), assistant.prompt(assistant.NOC_PROMPT)[1]])


def rows_for(inc: dict, ctx: dict, res: assistant.AssistantResult, generated_at: pd.Timestamp
             ) -> tuple[dict, list[dict], dict]:
    s = res.summary
    sid = str(uuid.uuid4())
    imp = s["customer_impact"]
    summary = {
        "summary_id": sid, "incident_id": inc["incident_id"], "source_run": inc.get("source_run"),
        "region_code": inc["region_code"], "generated_at": generated_at, "as_of": ctx["incident"]["as_of"],
        "suspects_signature": suspects_signature(inc), "status": "draft", "assistant_endpoint": res.endpoint,
        "noc_prompt_version": res.prompt_versions.get("noc_summary"), "context_version": res.prompt_versions.get("context"),
        "ranker_model_version": str(inc.get("model_version") or ""), "likely_root_cause": s["likely_root_cause"],
        "fault_hypothesis": s["fault_hypothesis"], "confidence": s["confidence"], "summary": s["summary"],
        "evidence_json": json.dumps(s["evidence"]), "next_steps_json": json.dumps(s["recommended_next_steps"]),
        "est_affected_subscribers": imp.get("estimated_affected_subscribers"), "impacted_cells": imp.get("impacted_cells"),
        "impacted_sites": imp.get("impacted_sites"), "impact_description": imp.get("description"),
        "alternative_suspects_json": json.dumps(s["alternative_suspects"]),
        "generated_by": res.summary_report.get("generated_by"), "n_repairs": res.summary_report.get("n_repairs"),
        "guard_report_json": json.dumps(res.summary_report, default=str), "latency_ms": round(res.latency_ms, 1),
        "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
        "context_json": json.dumps(ctx, separators=(",", ":")),
    }
    drafts = [{
        "draft_id": str(uuid.uuid4()), "summary_id": sid, "incident_id": inc["incident_id"],
        "region_code": d["region_code"], "generated_at": generated_at, "status": "draft",
        "requires_human_approval": True, "approved_by": None, "approved_at": None, "sent_at": None, "channel": "sms",
        "text": d["text"], "chars": d["chars"], "generated_by": d["generated_by"],
        "violations_json": json.dumps(d["violations"]), "llm_violations_json": json.dumps(d["llm_violations"]),
        "est_affected_customers": d["est_affected_customers"], "sms_prompt_version": res.prompt_versions.get("sms"),
    } for d in res.sms]
    latest = {k: summary[k] for k in ("incident_id", "summary_id", "source_run", "region_code", "generated_at", "as_of",
                                      "suspects_signature", "status", "likely_root_cause", "fault_hypothesis",
                                      "confidence", "summary", "next_steps_json", "evidence_json",
                                      "est_affected_subscribers", "impacted_cells", "impacted_sites",
                                      "impact_description", "generated_by", "noc_prompt_version", "assistant_endpoint")}
    latest.update({"sms_draft_text": drafts[0]["text"] if drafts else None,
                   "sms_draft_status": "draft" if drafts else None, "n_sms_drafts": len(drafts)})
    return summary, drafts, latest


def write_request_log(spark, log: RequestLog, table: str) -> int:
    """Append the request log to a Delta table (created on first use)."""
    if not log.rows:
        return 0
    from netmon_pipeline.rca.live import conform

    df = conform(pd.DataFrame(log.rows), REQUEST_LOG_DDL)
    spark.createDataFrame(df, schema=REQUEST_LOG_DDL).write.mode("append").saveAsTable(table)
    spark.sql(f"COMMENT ON TABLE {table} IS 'Every LLM request / response of the NOC assistant (request JSON, "
              "response text, status incl. gateway guardrail blocks, latency, tokens). Stands in for the AI Gateway "
              "inference table, which fails to enable on this workspace (docs/genai_assistant.md).'")
    return len(log.rows)
