"""Capture text evidence of step 4 (Gen AI NOC assistant, SMS drafts, AI Gateway) into evidence/step4/.

SQL runs on the warehouse through the Databricks CLI (as scripts/capture_evidence.py); endpoint, job, MLflow and
Lakebase metadata come from the Databricks SDK with the CLI profile's OAuth login. No secret is read or written.
System tables on this workspace are account-wide: every system-table query is filtered to this workspace's ID and
the assistant's endpoint, so no other workspace's data is captured.

    python scripts/capture_evidence_step4.py --profile febar --warehouse <id> [--only gateway,examples,...]

`06_guardrail_tests.md` is written by scripts/genai_guardrail_tests.py (it calls the live endpoint).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from capture_evidence import Runner, md_table  # noqa: E402
from capture_evidence_step3 import ALARM_COUNTS_SQL  # noqa: E402

from netmon_pipeline.genai import gateway  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "evidence" / "step4"
CAT = "telco_netmon_febar_catalog"
G, E, R = f"{CAT}.netmon_genai", f"{CAT}.netmon_eval", f"{CAT}.netmon_rca"
EP = gateway.ASSISTANT_ENDPOINT
JOBS = ["banksia-genai-build-evalset", "banksia-genai-evaluate", "banksia-genai-assistant",
        "banksia-genai-lakebase-check", "banksia-rca-any-alert-metric"]


class Doc:
    def __init__(self, r: Runner, name: str, title: str, intro: str = ""):
        self.r, self.path = r, OUT / name
        self.parts = [f"# {title}\n", f"Captured {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC from workspace profile "
                      f"`{r.profile}` by `scripts/capture_evidence_step4.py`.\n"]
        if intro:
            self.parts.append(intro.strip() + "\n")

    def query(self, heading: str, sql: str, note: str = "", max_cell: int = 160) -> tuple[list, list]:
        cols, rows = self.r.sql(sql)
        self.parts += [f"## {heading}\n", note.strip() + "\n" if note else "", "```sql\n" + sql.strip() + "\n```\n",
                       md_table(cols, rows, max_cell=max_cell)]
        return cols, rows

    def text(self, heading: str, body: str) -> None:
        self.parts += [f"## {heading}\n", body.strip() + "\n"]

    def code(self, heading: str, obj, note: str = "", lang: str = "json") -> None:
        body = obj if isinstance(obj, str) else json.dumps(obj, indent=2, default=str)
        self.parts += [f"## {heading}\n", note.strip() + "\n" if note else "", f"```{lang}\n{body}\n```\n"]

    def write(self) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(p for p in self.parts if p))
        print("wrote", self.path)


def workspace_id(w) -> str:
    return str(w.get_workspace_id())


# ---------------------------------------------------------------------------------------------------------------

def gateway_doc(r: Runner, w) -> None:
    d = Doc(r, "01_gateway_config.md", "AI Gateway configuration of the assistant endpoint", f"""
The assistant calls the Databricks-hosted pay-per-token Foundation Model endpoint `{EP}` (GPT-5.4 mini). AI Gateway is
configured on it from code (`netmon_pipeline.genai.gateway`, applied by `scripts/genai_configure_gateway.py`). Below:
the live endpoint config as returned by the serving API (it holds no secrets), what the code asks for, and the
feature that the workspace rejects.""")
    d.code("Live endpoint AI Gateway config (GET /api/2.0/serving-endpoints/{name})", gateway.current_config(w, EP))
    d.code("What the code asks for (`gateway.desired_config`)",
           gateway.desired_config(gateway.GatewaySpec(CAT, "netmon_genai")))
    d.text("Feature status", f"""
| feature | status on this workspace |
|---|---|
| usage tracking | **on**: per-request tokens in `system.serving.endpoint_usage` (see `02_inference_log.md`) |
| rate limits | **on**: {gateway.ENDPOINT_CALLS_PER_MIN} calls / min per endpoint, {gateway.USER_CALLS_PER_MIN} calls / min per user |
| PII guardrail, input | **on, BLOCK** (demonstrated in `06_guardrail_tests.md`) |
| PII guardrail, output | **on, BLOCK** |
| safety guardrail, output | **on** |
| safety guardrail, input | **off by choice**: flagged benign NOC prompts as "violent-crimes" on 3 / 3 identical requests (request `2f3ef1b0-83b2-4510-aef5-e7ce8ba81141`). Prompt injection is handled by `guards.sanitize_free_text` (tested live in `06_guardrail_tests.md`) |
| inference table | **fails to enable**: `PUT .../ai-gateway` with `inference_table_config` returns `500 INTERNAL_ERROR: java.nio.channels.ClosedChannelException` (request `1e3b343b-f98f-4784-a001-b5a9e67826a0`; same in schema `netmon_rca`), after creating an empty `<prefix>_payload` table (dropped). **Equivalent in code:** every request / response is logged by `llm.RequestLog` to `netmon_genai.noc_assistant_request_log` |
""")
    d.write()


def inference_log(r: Runner, wsid: str) -> None:
    d = Doc(r, "02_inference_log.md", "Request / response logging and gateway usage tracking", """
`netmon_genai.noc_assistant_request_log` holds every LLM request and response of the assistant (job runs, evaluation
runs): the request JSON as sent (system prompt + context), the raw response text, status (`ok`, `blocked` by a
gateway guardrail, `error`), latency, attempts and tokens. It stands in for the AI Gateway inference table, which
cannot be enabled on this workspace (`01_gateway_config.md`). The gateway's own usage tracking
(`system.serving.endpoint_usage`) records each request's tokens independently; the two join on `client_request_id`
for calls made since fix round 1 (see the join below).""")
    d.query("Request log: volume by purpose and status", f"""
        SELECT purpose, status, count(*) AS n, round(avg(latency_ms)) AS avg_latency_ms,
               round(avg(prompt_tokens)) AS avg_prompt_tokens, round(avg(completion_tokens)) AS avg_completion_tokens,
               min(request_time) AS first, max(request_time) AS last
        FROM {G}.noc_assistant_request_log GROUP BY 1, 2 ORDER BY 1, 2""")
    d.query("Request log: sample rows (request and response truncated)", f"""
        SELECT request_id, request_time, purpose, prompt_version, incident_ref, status, latency_ms, prompt_tokens,
               completion_tokens, substr(request, 1, 300) AS request_head,
               substr(get_json_object(request, '$.messages[1].content'), 1, 400) AS user_message_head,
               substr(response, 1, 400) AS response_head
        FROM {G}.noc_assistant_request_log WHERE status = 'ok' ORDER BY request_time DESC LIMIT 4""", max_cell=420)
    d.query("Request log: guardrail blocks (sample)", f"""
        SELECT request_id, request_time, purpose, incident_ref, status, substr(error, 1, 300) AS error_head
        FROM {G}.noc_assistant_request_log WHERE status <> 'ok' ORDER BY request_time DESC LIMIT 5""", max_cell=320)
    d.query("Gateway usage tracking (system.serving.endpoint_usage), this workspace and endpoint, by day", f"""
        SELECT to_date(u.request_time) AS day, count(*) AS requests, sum(CAST(u.status_code = 200 AS INT)) AS ok_200,
               sum(u.input_token_count) AS input_tokens, sum(u.output_token_count) AS output_tokens
        FROM system.serving.endpoint_usage u JOIN system.serving.served_entities e
          ON u.served_entity_id = e.served_entity_id AND e.workspace_id = u.workspace_id
        WHERE u.workspace_id = '{wsid}' AND e.endpoint_name = '{EP}' AND u.request_time >= '2026-11-05'
        GROUP BY 1 ORDER BY 1""")
    d.query("Gateway usage tracking: sample rows", f"""
        SELECT u.databricks_request_id, u.client_request_id, u.request_time, u.status_code, u.input_token_count,
               u.output_token_count, u.request_streaming
        FROM system.serving.endpoint_usage u JOIN system.serving.served_entities e
          ON u.served_entity_id = e.served_entity_id AND e.workspace_id = u.workspace_id
        WHERE u.workspace_id = '{wsid}' AND e.endpoint_name = '{EP}' AND u.request_time >= '2026-11-05'
        ORDER BY u.request_time DESC LIMIT 6""")
    d.query("Request log joined to gateway usage rows on client_request_id", f"""
        SELECT l.request_id AS client_request_id, u.databricks_request_id, l.request_time AS logged_at, u.request_time,
               l.purpose, l.status, l.prompt_tokens AS logged_prompt_tokens, u.input_token_count AS gateway_input_tokens,
               l.completion_tokens AS logged_completion_tokens, u.output_token_count AS gateway_output_tokens
        FROM {G}.noc_assistant_request_log l
        JOIN system.serving.endpoint_usage u ON u.client_request_id = l.request_id AND u.workspace_id = '{wsid}'
        ORDER BY u.request_time DESC LIMIT 8""",
            "Since fix round 1 the assistant sends `client_request_id` in the request body (`llm.chat_json`); the "
            "gateway's usage tracking records it, so each usage row joins its request-log row on it, and the token "
            "counts match. Earlier calls sent the id only as an `X-Request-Id` header, which usage tracking does not "
            "record: their usage rows have `client_request_id` NULL and can only be correlated by time and token "
            "counts. `system.serving.endpoint_usage` lands with a lag of about 1–2 hours.")
    d.query("Join coverage: request-log rows with and without a matching usage row", f"""
        SELECT l.response_id IS NOT NULL AS logged_with_client_id_fix, count(*) AS log_rows,
               count(u.client_request_id) AS joined_usage_rows
        FROM {G}.noc_assistant_request_log l
        LEFT JOIN system.serving.endpoint_usage u ON u.client_request_id = l.request_id AND u.workspace_id = '{wsid}'
        GROUP BY 1 ORDER BY 1""",
            "`response_id` is only logged since the fix, so it separates the two generations of rows.")
    d.write()


EXAMPLE_SQL = f"""
    SELECT r.eval_id, r.fault_type, r.root_element_ids, r.ranker_top1, r.llm_root, r.llm_vs_ranker, r.confidence,
           r.fault_hypothesis, r.summary_json, r.summary_report_json, r.sms_texts, c.context_json
    FROM {G}.genai_eval_results_dev r JOIN {G}.genai_eval_contexts c ON c.eval_id = r.eval_id
    WHERE r.eval_id = '{{eid}}'"""


def examples(r: Runner) -> None:
    picks = {
        "Slow backhaul degradation": "fault_type = 'BACKHAUL_DEGRADATION' AND root_agreement",
        "The assistant is uncertain": "NOT answered",
        "Site power outage": "fault_type = 'SITE_POWER_OUTAGE' AND root_agreement",
        "Aggregation router failure": "fault_type = 'AGG_ROUTER_FAILURE' AND root_agreement",
        "Cell outage": "fault_type = 'CELL_OUTAGE' AND root_agreement",
    }
    d = Doc(r, "03_worked_examples.md", "Worked examples: context -> structured NOC summary -> SMS drafts", """
Full examples from the final **dev** evaluation run (`genai_eval_results_dev`), across fault types: the grounded
context exactly as the model received it, the validated structured summary, the guard report and the SMS drafts.
The ground-truth line under each heading is shown for the reader only: it comes from `netmon_eval.genai_eval_labels`
and was used for scoring, never in a prompt. A live open incident (no ground truth) closes the file.""")
    for title, cond in picks.items():
        _, rows = r.sql(f"SELECT eval_id FROM {G}.genai_eval_results_dev WHERE {cond} ORDER BY eval_id LIMIT 1")
        if not rows:
            d.text(title, "(no case of this kind in the dev run)")
            continue
        cols, rr = r.sql(EXAMPLE_SQL.format(eid=rows[0][0]))
        x = dict(zip(cols, rr[0], strict=True))
        d.text(f"{title} (`{x['eval_id']}`)",
               f"Ground truth (scoring only): fault type `{x['fault_type']}`, valid roots `{x['root_element_ids']}`. "
               f"Ranker top-1 `{x['ranker_top1']}`; assistant `{x['llm_root']}` ({x['confidence']}, "
               f"`{x['fault_hypothesis']}`): **{x['llm_vs_ranker']}**.")
        d.code("Context (input)", json.loads(x["context_json"]))
        d.code("NOC summary (validated output)", json.loads(x["summary_json"]))
        d.code("Guard report", json.loads(x["summary_report_json"]))
        d.code("SMS drafts (status = draft, human approval required)", json.loads(x["sms_texts"]))
    cols, rr = r.sql(f"""SELECT incident_id, generated_at, likely_root_cause, confidence, fault_hypothesis, summary,
                         next_steps_json, evidence_json, context_json FROM {G}.incident_ai_summaries
                         ORDER BY generated_at DESC, incident_id LIMIT 1""")
    if rr:
        x = dict(zip(cols, rr[0], strict=True))
        _, dr = r.sql(f"SELECT region_code, text, status, requires_human_approval, sent_at FROM "
                      f"{G}.customer_notice_drafts WHERE incident_id = '{x['incident_id']}' ORDER BY generated_at DESC LIMIT 3")
        d.text(f"Live open incident `{x['incident_id']}` (job `banksia-genai-assistant`, no ground truth)",
               f"Generated {x['generated_at']}: `{x['likely_root_cause']}` ({x['confidence']}, `{x['fault_hypothesis']}`).")
        d.code("Context (input)", json.loads(x["context_json"]))
        d.code("Summary", {"summary": x["summary"], "evidence": json.loads(x["evidence_json"]),
                           "recommended_next_steps": json.loads(x["next_steps_json"])})
        d.code("SMS drafts", [dict(zip(["region_code", "text", "status", "requires_human_approval", "sent_at"], v,
                                       strict=True)) for v in dr])
    d.write()


METRICS = ["n", "llm_root_agreement_pct", "ranker_top1_agreement_pct", "answered_pct", "llm_selective_accuracy_pct",
           "ranker_top1_on_answered_pct", "changed_to_correct", "changed_correct_to_wrong", "changed_wrong_to_wrong",
           "uncertain_on_correct", "uncertain_on_wrong", "fault_hypothesis_match_pct", "hallucinated_root_pct",
           "hallucinated_element_pct", "evidence_field_validity_pct", "fallback_pct", "sms_compliant_pct",
           "sms_llm_first_try_compliant_pct", "sms_llm_compliant_after_repair_pct", "judge_groundedness_pct",
           "judge_sms_guidelines_pct", "latency_p50_ms", "latency_p95_ms", "prompt_tokens_mean",
           "completion_tokens_mean"]


def evaluation_doc(r: Runner) -> None:
    d = Doc(r, "04_evaluation.md", "MLflow GenAI evaluation: dev and holdout (separately)", f"""
`banksia-genai-evaluate` runs `mlflow.genai.evaluate` over the evaluation set: one grounded context per scored step-3
incident that had a case output at the SLA moment. **Dev** = `history_1m` 2026-10-14 … 10-15 (prompt iteration
happened here only). **Holdout** = `holdout_1m` 2026-10-17 … 10-18, run **once** with the frozen prompts (the job
refuses to re-run it). Ground truth reaches only the scorers (`expectations`). Assistant `{EP}`; LLM judges
`{gateway.JUDGE_ENDPOINT}` (another model family). Definitions: `netmon_pipeline.genai.scorers`.

- `llm_root_agreement_pct`: the assistant's root is in the valid root list; "uncertain" counts as a miss.
- `ranker_top1_agreement_pct`: the ranker's suspect #1 on the same contexts (step 3's top-1 at the SLA moment).
- `llm_selective_accuracy_pct` / `ranker_top1_on_answered_pct`: agreement on the cases the assistant answered.
- `changed_*` / `uncertain_*`: counts of cases where the assistant departs from the ranker.
- `hallucinated_*`: the raw output named a root that is not a suspect / any element ID not in the context
  (before the guard repaired it). `evidence_field_validity_pct`: cited context paths that exist.
- `sms_*`: final drafts compliant (always, by construction: non-compliant drafts are replaced by the template) /
  the LLM's own drafts compliant at the first try / after one repair round.
- latency = sum of the summary and SMS calls per incident (client side, job -> endpoint); tokens per incident.""")
    for split in ("dev", "holdout"):
        cols, rows = r.sql(f"SELECT * FROM {G}.genai_eval_summary_{split} WHERE `group` = 'ALL_WITH_CASE'")
        if not rows:
            d.text(split.upper(), "(not evaluated)")
            continue
        m = dict(zip(cols, rows[0], strict=True))
        body = "| metric | value |\n|---|---|\n" + "\n".join(f"| {k} | {m.get(k)} |" for k in
                                                              [*METRICS, "n_scored_incidents",
                                                               "ranker_top1_all_scored_pct",
                                                               "llm_root_agreement_all_scored_pct", "mlflow_run_id",
                                                               "noc_prompt_version", "sms_prompt_version",
                                                               "wall_minutes"] if k in m)
        d.text(f"{split.upper()}: overall", body)
        d.query(f"{split.upper()}: by fault type", f"""
            SELECT `group` AS fault_type, n, llm_root_agreement_pct, ranker_top1_agreement_pct, answered_pct,
                   llm_selective_accuracy_pct, changed_to_correct, changed_correct_to_wrong, uncertain_on_correct,
                   uncertain_on_wrong, fault_hypothesis_match_pct, hallucinated_element_pct, sms_llm_first_try_compliant_pct,
                   judge_groundedness_pct, latency_p50_ms
            FROM {G}.genai_eval_summary_{split} WHERE `group` <> 'ALL_WITH_CASE' ORDER BY CAST(n AS INT) DESC""")
        d.query(f"{split.upper()}: every case where the assistant departs from the ranker", f"""
            SELECT eval_id, fault_type, root_element_ids, ranker_top1, llm_root, llm_vs_ranker, confidence,
                   fault_hypothesis FROM {G}.genai_eval_results_{split}
            WHERE llm_vs_ranker <> 'same' ORDER BY llm_vs_ranker, fault_type, eval_id""")
    d.write()


def outputs(r: Runner, w) -> None:
    d = Doc(r, "05_outputs_and_lakebase.md", "Output tables (UC) and the Lakebase sync", """
`banksia-genai-assistant` (table-update trigger on `netmon_rca.open_incidents`) writes the assistant's results to Unity
Catalog and syncs the latest summary per open incident to Lakebase for the step-5 app.""")
    d.query("Tables in netmon_genai", f"""
        SELECT table_name, table_type, comment FROM {CAT}.information_schema.tables
        WHERE table_schema = 'netmon_genai' ORDER BY 1""", max_cell=240)
    d.query("incident_ai_summaries: rows by generator and status", f"""
        SELECT status, generated_by, noc_prompt_version, assistant_endpoint, count(*) AS n,
               count(DISTINCT incident_id) AS incidents, min(generated_at) AS first, max(generated_at) AS last
        FROM {G}.incident_ai_summaries GROUP BY ALL""")
    d.query("incident_ai_summaries: sample", f"""
        SELECT incident_id, region_code, generated_at, status, likely_root_cause, fault_hypothesis, confidence,
               substr(summary, 1, 220) AS summary, est_affected_subscribers, impacted_cells, latency_ms, prompt_tokens,
               completion_tokens FROM {G}.incident_ai_summaries ORDER BY generated_at DESC, incident_id LIMIT 6""",
            max_cell=240)
    d.query("customer_notice_drafts: every draft is a draft (never sent)", f"""
        SELECT status, requires_human_approval, count(*) AS n, count(approved_by) AS approved, count(sent_at) AS sent,
               max(chars) AS max_chars, sum(CAST(violations_json <> '[]' AS INT)) AS with_violations
        FROM {G}.customer_notice_drafts GROUP BY ALL""")
    d.query("customer_notice_drafts: sample", f"""
        SELECT incident_id, region_code, generated_at, status, requires_human_approval, sent_at, chars, generated_by,
               text FROM {G}.customer_notice_drafts ORDER BY generated_at DESC, incident_id LIMIT 6""", max_cell=200)
    d.query("incident_ai_latest (Delta source of the synced table)", f"""
        SELECT incident_id, region_code, likely_root_cause, confidence, status, sms_draft_status,
               substr(sms_draft_text, 1, 160) AS sms_draft_text, refreshed_at
        FROM {G}.incident_ai_latest ORDER BY incident_id LIMIT 6""", max_cell=200)
    try:
        st = w.database.get_synced_database_table(f"{G}.lb_incident_ai_latest")
        dss = st.data_synchronization_status
        d.code("Synced table lb_incident_ai_latest", {
            "name": st.name, "database_instance": st.database_instance_name, "logical_database": st.logical_database_name,
            "source": st.spec.source_table_full_name, "primary_key": st.spec.primary_key_columns,
            "scheduling_policy": str(st.spec.scheduling_policy), "state": str(dss.detailed_state) if dss else None,
            "message": dss.message if dss else None,
            "last_sync": str(getattr(getattr(dss, "triggered_update_status", None), "last_processed_commit_version", ""))})
    except Exception as e:  # noqa: BLE001
        d.text("Synced table lb_incident_ai_latest", f"not readable: {str(e)[:300]}")
    d.query("Lakebase read-back with psycopg + OAuth (job banksia-genai-lakebase-check)", f"""
        SELECT run_at, query, n, p50_ms, p95_ms, p99_ms, max_ms, rows, open_incidents_without_summary
        FROM {G}.lakebase_ai_check ORDER BY run_at DESC, query LIMIT 4""")
    cols, rows = r.sql(f"SELECT details FROM {G}.lakebase_ai_check ORDER BY run_at DESC LIMIT 1")
    if rows:
        det = json.loads(rows[0][0])
        d.code("Rows read back from Postgres (netmon_genai.lb_incident_ai_latest)", det.get("sample"))
    d.write()


def cost(r: Runner, wsid: str) -> None:
    d = Doc(r, "07_latency_cost.md", "Latency and cost", f"""
Latency is measured client side per incident (summary call + SMS call(s), job -> endpoint), from the evaluation
results. Tokens come from the responses (and match the gateway's usage tracking). Cost: pay-per-token DBUs that
billing attributes to `{EP}` in this workspace (`system.billing.usage`, filtered to this workspace and endpoint; it
lags a few hours behind the calls), and the per-incident figure from the dev / holdout runs' token counts.""")
    for split in ("dev", "holdout"):
        d.query(f"{split.upper()}: latency and tokens per incident", f"""
            SELECT count(*) AS n, round(percentile(latency_ms, 0.5)) AS p50_ms, round(percentile(latency_ms, 0.95)) AS p95_ms,
                   round(max(latency_ms)) AS max_ms, round(avg(prompt_tokens)) AS prompt_tokens_mean,
                   round(avg(completion_tokens)) AS completion_tokens_mean, round(avg(n_calls), 2) AS calls_per_incident
            FROM {G}.genai_eval_results_{split}""")
    d.query("Request log: latency per call type", f"""
        SELECT purpose, count(*) AS n, round(percentile(latency_ms, 0.5)) AS p50_ms,
               round(percentile(latency_ms, 0.95)) AS p95_ms, round(avg(prompt_tokens)) AS prompt_tokens,
               round(avg(completion_tokens)) AS completion_tokens
        FROM {G}.noc_assistant_request_log WHERE status = 'ok' GROUP BY 1 ORDER BY 1""")
    d.query("Billing: DBUs attributed to the assistant endpoint (this workspace)", f"""
        SELECT usage_date, sku_name, usage_unit, round(sum(usage_quantity), 4) AS dbus,
               round(sum(usage_quantity) * 0.07, 4) AS usd_at_list_price
        FROM system.billing.usage
        WHERE workspace_id = '{wsid}' AND usage_metadata.endpoint_name = '{EP}' AND usage_date >= '2026-11-05'
        GROUP BY ALL ORDER BY 1""",
            "List price $0.07 / DBU for the `*_MODEL_SERVING` pay-per-token SKUs (`system.billing.list_prices`).")
    d.query("Gateway usage tracking: tokens on the endpoint (this workspace)", f"""
        SELECT count(*) AS requests, sum(u.input_token_count) AS input_tokens, sum(u.output_token_count) AS output_tokens
        FROM system.serving.endpoint_usage u JOIN system.serving.served_entities e
          ON u.served_entity_id = e.served_entity_id AND e.workspace_id = u.workspace_id
        WHERE u.workspace_id = '{wsid}' AND e.endpoint_name = '{EP}' AND u.request_time >= '2026-11-05'""")
    d.write()


def runs(r: Runner, w) -> None:
    d = Doc(r, "08_jobs_and_runs.md", "Deployed jobs and their latest runs", """
Jobs deployed by the bundle (`resources/genai.jobs.yml`, `resources/rca.jobs.yml`) and the latest runs that produced
the evidence. The assistant job has a table-update trigger on `netmon_rca.open_incidents`.""")
    rows = []
    for j in w.jobs.list(expand_tasks=False):
        name = j.settings.name if j.settings else ""
        if name not in JOBS:
            continue
        trig = j.settings.trigger.as_dict() if j.settings.trigger else None
        for run in w.jobs.list_runs(job_id=j.job_id, limit=4):
            st = run.state
            rows.append([name, j.job_id, run.run_id, datetime.fromtimestamp(run.start_time / 1000, timezone.utc)
                         .strftime("%Y-%m-%d %H:%M"), str(st.life_cycle_state.value if st and st.life_cycle_state else ""),
                         str(st.result_state.value if st and st.result_state else ""),
                         round((run.end_time - run.start_time) / 60000, 1) if run.end_time else None,
                         json.dumps((run.job_parameters and {p.name: p.value for p in run.job_parameters
                                                             if p.name in ("split", "limit", "force", "judges")}) or {}),
                         json.dumps(trig) if trig else ""])
    d.parts.append(md_table(["job", "job_id", "run_id", "start_utc", "state", "result", "minutes", "params", "trigger"],
                            rows, max_cell=200))
    # what each assistant run did (its notebook exit value): processed vs skipped-unchanged incidents, LLM calls
    out_rows = []
    for j in w.jobs.list(name="banksia-genai-assistant"):
        for run in w.jobs.list_runs(job_id=j.job_id, limit=6):
            full = w.jobs.get_run(run.run_id)
            res = None
            for t in full.tasks or []:
                try:
                    res = json.loads(w.jobs.get_run_output(t.run_id).notebook_output.result or "null")
                except Exception:  # noqa: BLE001
                    res = None
            if not res:
                continue
            out_rows.append([run.run_id, str(run.trigger.value if run.trigger else ""),
                             datetime.fromtimestamp(run.start_time / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M"),
                             res.get("open"), res.get("processed"), res.get("skipped_unchanged"), res.get("llm_calls"),
                             res.get("sms_drafts"), res.get("prompt_tokens"), res.get("completion_tokens"),
                             res.get("minutes"), json.dumps(res.get("synced") or {})])
    d.text("banksia-genai-assistant: run outputs (notebook exit value)", """
Each run's own report (`dbutils.notebook.exit`): open incidents, incidents summarised (new, re-ranked or new prompt),
incidents skipped as unchanged, LLM calls made, SMS drafts written, tokens, minutes of notebook time, Lakebase sync
update started. A `TABLE` trigger is the table-update trigger on `netmon_rca.open_incidents` firing after a
`banksia-rca-score-live` MERGE.""")
    d.parts.append(md_table(["run_id", "trigger", "start_utc", "open", "processed", "skipped_unchanged", "llm_calls",
                             "sms_drafts", "prompt_tokens", "completion_tokens", "minutes", "lakebase_sync_update"],
                            out_rows, max_cell=120))
    d.write()


RERUN_REASON = ("PR #6: run-unique alarm IDs. The holdout's fault alarms had been dropped upstream by a cross-run ID "
                "collision (09_holdout_alarm_gap.md); holdout_1m was re-ingested with corrected alarms and the ranker "
                "retrained (v5) on corrected training data. Prompts frozen at noc_summary_v3 / sms_v1; nothing tuned.")


def _active_alarm_breakdown(d: Doc, split: str, sfx: str, label: str) -> None:
    d.query(f"{label}: assistant vs ranker by whether the context has an active alarm", f"""
        SELECT CAST(get_json_object(c.context_json, '$.alarm_summary.n_active') AS INT) > 0 AS context_has_active_alarm,
               l.fault_type, count(*) AS n, round(100 * avg(CAST(r.root_agreement AS INT)), 1) AS llm_pct,
               round(100 * avg(CAST(r.ranker_top1_agreement AS INT)), 1) AS ranker_pct,
               sum(CAST(r.llm_vs_ranker = 'changed_correct_to_wrong' AS INT)) AS changed_correct_to_wrong,
               sum(CAST(r.llm_vs_ranker = 'uncertain_on_correct' AS INT)) AS uncertain_on_correct,
               sum(CAST(r.llm_vs_ranker = 'changed_to_correct' AS INT)) AS changed_to_correct
        FROM {G}.genai_eval_results_{split}{sfx} r JOIN {G}.genai_eval_contexts{sfx} c USING (eval_id)
        JOIN {E}.genai_eval_labels{sfx} l USING (eval_id)
        GROUP BY GROUPING SETS ((1), (1, 2)) ORDER BY 1, 2 NULLS FIRST""")


def alarm_gap(r: Runner) -> None:
    d = Doc(r, "09_holdout_alarm_gap.md", "Holdout finding: incident alarms lost upstream, and what it does to the LLM", """
**Status: resolved in PR #6** (resolution at the end; old vs new results in `10_holdout_rerun.md` and
`evidence/step3/08_alarm_id_fix.md`). The finding below is rebuilt from the snapshots taken before the fix
(`*_pr5` tables = the state of main 58004a7), so it reads exactly as it was found.

The holdout evaluation showed the assistant **losing** accuracy against the ranker. Root cause found afterwards
(analysis only; nothing was re-run or tuned on the holdout at the time): the generator derived incident alarm IDs from
the batch incident ID (`opaque_id("ALM", incident_id, n)`, with `incident_id` = `INC-00001`, `INC-00002`, … in every
batch run). The holdout's fault alarms therefore reused the alarm IDs of `history_1m`, and the silver layer's
cross-run deduplication (`dropDuplicatesWithinWatermark` on `record_id`) dropped them as redeliveries (dedupe state is
only evicted when a later batch advances the watermark, so the holdout batch was checked against `history_1m`'s keys).
`history_1m` lost 90 alarm IDs to the step-2 `history` run the same way. Background alarm IDs included the run seed
and survived. Result: the alarms that corroborate a fault were missing for much of the holdout, while noise alarms on
neighbouring elements remained.""")
    d.query("Alarms per run before the fix (snapshot)", f"SELECT * FROM {E}.alarm_counts_pr5 ORDER BY run",
            "`removed_by_dedupe` should equal `injected_duplicates`; `missing_ids_held_by_other_run` = distinct IDs "
            "absent from silver whose ID is in silver under another run.")
    for split in ("dev", "holdout"):
        _active_alarm_breakdown(d, split, "_pr5", f"{split.upper()} (before the fix)")
    d.text("Reading (before the fix)", """
- On dev, 340 of 346 contexts carried an active alarm and the assistant matched or beat the ranker.
- On the holdout, about half the contexts carried no active alarm (cell outages: about a third had one). Without the
  root's own alarm, the prompt's "alarms + impact pattern agree" reading fails: the assistant answered `uncertain` on
  correct ranker answers, or followed a surviving noise alarm on a neighbouring backhaul link.
- The lesson holds beyond this defect: OSS alarm feeds do drop and lag in real networks. The ranker, trained on KPIs
  and alarms, degrades gracefully; the LLM, told to look for corroborating alarms, does not.""")
    d.text("Resolution (PR #6)", """
- **Fix**: alarm and change IDs hash a run key (`GeneratorConfig.run_id`, the landing sub-directory = `source_run`);
  event-time ties are broken by the run-independent key, so a new run id changes only IDs
  (`docs/data_model.md`, "IDs across runs"; tests in `tests/test_run_unique_ids.py`, including a regression that
  replays the original drop through the dedupe reference model).
- **Data**: `history_1m` and `holdout_1m` regenerated (same seeds and windows), verified to differ from the ingested
  files only in IDs, and their alarm / DQ-log / change-calendar feeds swapped in by `banksia-netmon-replace-run-feeds`
  (no full refresh). Every run now loses exactly its injected duplicates (table below).
- **Step 3**: training data was affected, so the ranker was retrained once with the frozen design (v5) and the holdout
  re-scored once (`evidence/step3/08_alarm_id_fix.md`).
- **Step 4**: evaluation set rebuilt; dev and the holdout re-run once with the frozen prompts (`force=true`, reason
  recorded on the MLflow run): `10_holdout_rerun.md`.""")
    d.query("Alarms per run after the fix (live)", f"""
        SELECT n.run, o.silver_rows AS silver_before, n.silver_rows AS silver_after, n.injected_duplicates,
               o.removed_by_dedupe AS dedupe_removed_before, n.removed_by_dedupe AS dedupe_removed_after,
               n.distinct_ids_missing_from_silver AS missing_after
        FROM ({ALARM_COUNTS_SQL}) n JOIN {E}.alarm_counts_pr5 o USING (run) ORDER BY n.run""")
    _active_alarm_breakdown(d, "holdout", "", "HOLDOUT (after the fix)")
    d.write()


def rerun_doc(r: Runner) -> None:
    d = Doc(r, "10_holdout_rerun.md", "PR #6: step-4 evaluation re-run after the alarm ID fix (old vs new)", f"""
Prompts frozen at `noc_summary_v3` / `sms_v1`, same scorers, judges and code. The evaluation set was rebuilt
(`banksia-genai-build-evalset`) from the corrected data and the retrained ranker v5, then dev was re-run and the
holdout re-run **once** with `force=true`. Re-run reason recorded on the MLflow run (tag `holdout_rerun_reason`) and in
the result tables (`rerun_reason`): "{RERUN_REASON}"

Old = the published PR #5 results (snapshots `genai_eval_summary_<split>_pr5`, ranker v4, alarms missing on the
holdout); new = this run. Both the inputs (alarms) and the ranker changed, so a difference is not attributable to the
assistant alone. Nothing was tuned on either result.""")
    for split in ("holdout", "dev"):
        _, o = r.sql(f"SELECT * FROM {G}.genai_eval_summary_{split}_pr5 WHERE `group` = 'ALL_WITH_CASE'")
        cols, n = r.sql(f"SELECT * FROM {G}.genai_eval_summary_{split} WHERE `group` = 'ALL_WITH_CASE'")
        oc, _ = r.sql(f"SELECT * FROM {G}.genai_eval_summary_{split}_pr5 LIMIT 0")
        if not n:
            d.text(split.upper(), "(not evaluated)")
            continue
        om, nm = dict(zip(oc, o[0], strict=True)) if o else {}, dict(zip(cols, n[0], strict=True))
        keys = [*METRICS, "n_scored_incidents", "ranker_top1_all_scored_pct", "llm_root_agreement_all_scored_pct",
                "mlflow_run_id", "noc_prompt_version", "sms_prompt_version", "rerun_reason"]
        body = "| metric | old (PR #5) | new (PR #6) |\n|---|---|---|\n" + "\n".join(
            f"| {k} | {om.get(k, '')} | {nm.get(k, '')} |" for k in keys if k in nm or k in om)
        d.text(f"{split.upper()}: overall, old vs new", body)
        sel = ", ".join(f"o.{c} AS old_{c}, n.{c} AS new_{c}" for c in
                        ("n", "llm_root_agreement_pct", "ranker_top1_agreement_pct", "answered_pct",
                         "changed_correct_to_wrong", "uncertain_on_correct"))
        d.query(f"{split.upper()}: by fault type, old vs new", f"""
            SELECT coalesce(n.`group`, o.`group`) AS fault_type, {sel}
            FROM (SELECT * FROM {G}.genai_eval_summary_{split}_pr5 WHERE `group` <> 'ALL_WITH_CASE') o
            FULL OUTER JOIN (SELECT * FROM {G}.genai_eval_summary_{split} WHERE `group` <> 'ALL_WITH_CASE') n
              ON n.`group` = o.`group` ORDER BY CAST(coalesce(n.n, o.n) AS INT) DESC""")
    d.query("HOLDOUT (new): every case where the assistant departs from the ranker", f"""
        SELECT eval_id, fault_type, root_element_ids, ranker_top1, llm_root, llm_vs_ranker, confidence,
               fault_hypothesis FROM {G}.genai_eval_results_holdout
        WHERE llm_vs_ranker <> 'same' ORDER BY llm_vs_ranker, fault_type, eval_id""")
    d.write()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="febar")
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--only")
    a = ap.parse_args()
    from databricks.sdk import WorkspaceClient

    r = Runner(a.profile, a.warehouse)
    w = WorkspaceClient(profile=a.profile)
    wsid = workspace_id(w)
    steps = {"gateway": lambda: gateway_doc(r, w), "log": lambda: inference_log(r, wsid),
             "examples": lambda: examples(r), "evaluation": lambda: evaluation_doc(r), "outputs": lambda: outputs(r, w),
             "cost": lambda: cost(r, wsid), "runs": lambda: runs(r, w), "gap": lambda: alarm_gap(r), "rerun": lambda: rerun_doc(r)}
    for k, f in steps.items():
        if a.only and k not in a.only.split(","):
            continue
        f()


if __name__ == "__main__":
    main()
