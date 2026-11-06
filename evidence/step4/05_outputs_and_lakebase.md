# Output tables (UC) and the Lakebase sync

Captured 2026-11-06 08:13 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

`banksia-genai-assistant` (table-update trigger on `netmon_rca.open_incidents`) writes the assistant's results to Unity
Catalog and syncs the latest summary per open incident to Lakebase for the step-5 app.

## Tables in netmon_genai

```sql
SELECT table_name, table_type, comment FROM telco_netmon_febar_catalog.information_schema.tables
        WHERE table_schema = 'netmon_genai' ORDER BY 1
```

| table_name | table_type | comment |
|---|---|---|
| __07a8ea76_5fa9_4a5d_90bf_b0a339c0f58a_netmon_serving_netmon_genai_lb_incident_ai_latest_7338a95c_1434_4d76_b5b6_116004ac4665 | MANAGED | NULL |
| customer_notice_drafts | MANAGED | Proactive customer outage SMS DRAFTS, one per incident x affected region. status = 'draft' and requires_human_approval = true always; approved_by / approved_at / sent_at stay NULL: this system never sends. A human approves and sends from t… |
| event_log_07a8ea76_5fa9_4a5d_90bf_b0a339c0f58a | MANAGED | NULL |
| genai_eval_contexts | MANAGED | Gen AI evaluation set: one grounded incident context per scored step-3 incident with a case output at the SLA moment (dev = history_1m 10-14..10-15, holdout = holdout_1m). context_json is exactly what the assistant sees. No ground truth: l… |
| genai_eval_contexts_pr5 | MANAGED | Snapshot before PR #6 (run-unique alarm IDs): state of netmon_genai.genai_eval_contexts as of main 58004a7 |
| genai_eval_results_dev | MANAGED | Gen AI assistant evaluation (dev): per incident, the assistant's root vs the ranker's top-1 vs ground truth, guard repairs, SMS compliance, judges, latency and tokens. MLflow run cae6c002bb9144df8944f82458769eca. |
| genai_eval_results_dev_pr5 | MANAGED | Snapshot before PR #6 (run-unique alarm IDs): state of netmon_genai.genai_eval_results_dev as of main 58004a7 |
| genai_eval_results_holdout | MANAGED | Gen AI assistant evaluation (holdout): per incident, the assistant's root vs the ranker's top-1 vs ground truth, guard repairs, SMS compliance, judges, latency and tokens. MLflow run fb0197f68d634db68b6b6757a6705517. |
| genai_eval_results_holdout_pr5 | MANAGED | Snapshot before PR #6 (run-unique alarm IDs): state of netmon_genai.genai_eval_results_holdout as of main 58004a7 |
| genai_eval_summary_dev | MANAGED | Gen AI evaluation summary (dev), overall and per fault type. |
| genai_eval_summary_dev_pr5 | MANAGED | Snapshot before PR #6 (run-unique alarm IDs): state of netmon_genai.genai_eval_summary_dev as of main 58004a7 |
| genai_eval_summary_holdout | MANAGED | Gen AI evaluation summary (holdout), overall and per fault type. |
| genai_eval_summary_holdout_pr5 | MANAGED | Snapshot before PR #6 (run-unique alarm IDs): state of netmon_genai.genai_eval_summary_holdout as of main 58004a7 |
| incident_ai_latest | MANAGED | Latest NOC assistant summary and SMS draft per open incident (status = draft). Source of the Lakebase synced table lb_incident_ai_latest read by the step-5 app. |
| incident_ai_latest_pr5 | MANAGED | Snapshot before PR #6 (run-unique alarm IDs): state of netmon_genai.incident_ai_latest as of main 58004a7 |
| incident_ai_summaries | MANAGED | Every NOC assistant summary (status = draft, for NOC review): incident, endpoint / prompt / context / ranker versions, generated_at, likely root cause (a suspect or 'uncertain'), evidence, next steps, customer impact, guard report, latency… |
| lakebase_ai_check | MANAGED | NULL |
| lb_incident_ai_latest | FOREIGN | Database table synced from another UC table |
| noc_assistant_request_log | MANAGED | Every LLM request / response of the NOC assistant (request JSON, response text, status incl. gateway guardrail blocks, latency, tokens). Stands in for the AI Gateway inference table, which fails to enable on this workspace (docs/genai_assi… |

_19 row(s)_

## incident_ai_summaries: rows by generator and status

```sql
SELECT status, generated_by, noc_prompt_version, assistant_endpoint, count(*) AS n,
               count(DISTINCT incident_id) AS incidents, min(generated_at) AS first, max(generated_at) AS last
        FROM telco_netmon_febar_catalog.netmon_genai.incident_ai_summaries GROUP BY ALL
```

| status | generated_by | noc_prompt_version | assistant_endpoint | n | incidents | first | last |
|---|---|---|---|---|---|---|---|
| draft | llm | noc_summary_v3@cfda4dd5 | databricks-gpt-5-4-mini | 51 | 18 | 2026-11-06T01:59:36.148Z | 2026-11-06T07:42:33.256Z |
| draft | llm | noc_summary_v2@35d1de37 | databricks-gpt-5-4-mini | 17 | 17 | 2026-11-06T00:48:53.365Z | 2026-11-06T00:48:53.365Z |

_2 row(s)_

## incident_ai_summaries: sample

```sql
SELECT incident_id, region_code, generated_at, status, likely_root_cause, fault_hypothesis, confidence,
               substr(summary, 1, 220) AS summary, est_affected_subscribers, impacted_cells, latency_ms, prompt_tokens,
               completion_tokens FROM telco_netmon_febar_catalog.netmon_genai.incident_ai_summaries ORDER BY generated_at DESC, incident_id LIMIT 6
```

| incident_id | region_code | generated_at | status | likely_root_cause | fault_hypothesis | confidence | summary | est_affected_subscribers | impacted_cells | latency_ms | prompt_tokens | completion_tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RCA-1073d4d88aa7e05b | VIC | 2026-11-06T07:42:33.256Z | draft | CELL-VIC-00062-5G2 | CELL_OUTAGE | high | The impacted pattern is confined to one 5G cell, with availability at 0.0 and a fully degraded KPI profile on that cell, while the parent site and upstream elements are mostly unaffected. There are no active alarms in sc | 0 | 1 | 4892.4 | 4488 | 683 |
| RCA-27ed3e8af852d33a | VIC | 2026-11-06T07:42:33.256Z | draft | BH-VIC-0005 | BACKHAUL_DEGRADATION | high | The strongest fit is a degradation on backhaul link BH-VIC-0005 affecting all 12 impacted cells behind it, with very high latency and loss plus reduced downlink throughput and RRC success. The evidence points to a transp | 550 | 12 | 7414.3 | 4762 | 948 |
| RCA-399fe9bb03f3b4cb | VIC | 2026-11-06T07:42:33.256Z | draft | CELL-VIC-00022-5G3 | CELL_OUTAGE | high | The strongest match is CELL-VIC-00022-5G3: it has an active critical CELL_OUT_OF_SERVICE alarm, service down, and the cell is fully unavailable with severe RRC and throughput degradation. The parent site and upstream ele | 90 | 1 | 5616.0 | 4683 | 722 |
| RCA-4b24e8c0bfedac1a | NSW | 2026-11-06T07:42:33.256Z | draft | BH-NSW-0010 | BACKHAUL_DEGRADATION | high | The evidence points to degraded fibre backhaul on BH-NSW-0010 affecting its single child site SITE-NSW-00025 and all 3 impacted cells. KPI patterns show severe latency and loss with reduced downlink throughput and RRC su | 240 | 3 | 6422.8 | 4773 | 874 |
| RCA-60fe3d71c22893d5 | NSW | 2026-11-06T07:42:33.256Z | draft | CELL-NSW-00123-4G3 | CELL_OUTAGE | high | The strongest signal is a single impacted 4G cell with 0.0% availability and 0.0% attach success while its parent site remains largely up at 66.7% availability. There are no alarms on the cell itself, but the impact is i | 0 | 1 | 7124.5 | 4812 | 807 |
| RCA-944a68e9bf7eff9b | VIC | 2026-11-06T07:42:33.256Z | draft | CELL-VIC-00107-5G1 | CELL_OUTAGE | high | The evidence points to a single-cell outage on CELL-VIC-00107-5G1 in VIC: availability is 0.0%, attach success is 0.0%, RRC success is extremely low, and downlink throughput is severely degraded, while the suspect has no | 0 | 1 | 5600.4 | 4491 | 756 |

_6 row(s)_

## customer_notice_drafts: every draft is a draft (never sent)

```sql
SELECT status, requires_human_approval, count(*) AS n, count(approved_by) AS approved, count(sent_at) AS sent,
               max(chars) AS max_chars, sum(CAST(violations_json <> '[]' AS INT)) AS with_violations
        FROM telco_netmon_febar_catalog.netmon_genai.customer_notice_drafts GROUP BY ALL
```

| status | requires_human_approval | n | approved | sent | max_chars | with_violations |
|---|---|---|---|---|---|---|
| draft | true | 68 | 0 | 0 | 155 | 0 |

_1 row(s)_

## customer_notice_drafts: sample

```sql
SELECT incident_id, region_code, generated_at, status, requires_human_approval, sent_at, chars, generated_by,
               text FROM telco_netmon_febar_catalog.netmon_genai.customer_notice_drafts ORDER BY generated_at DESC, incident_id LIMIT 6
```

| incident_id | region_code | generated_at | status | requires_human_approval | sent_at | chars | generated_by | text |
|---|---|---|---|---|---|---|---|---|
| RCA-1073d4d88aa7e05b | VIC | 2026-11-06T07:42:33.256Z | draft | true | NULL | 119 | llm | Banksia Mobile: No mobile service and calls and data may drop or fail in Melbourne & Victoria. Sorry. We'll update you. |
| RCA-27ed3e8af852d33a | VIC | 2026-11-06T07:42:33.256Z | draft | true | NULL | 140 | llm | Banksia Mobile: Slow mobile data and calls and data may drop or fail in Melbourne & Victoria, incl Melbourne. Sorry. We'll keep you updated. |
| RCA-399fe9bb03f3b4cb | VIC | 2026-11-06T07:42:33.256Z | draft | true | NULL | 146 | llm | Banksia Mobile: Some customers in Geelong and Melbourne & Victoria may have no mobile service or calls and data may drop. Sorry. We'll update you. |
| RCA-4b24e8c0bfedac1a | NSW | 2026-11-06T07:42:33.256Z | draft | true | NULL | 103 | llm | Banksia Mobile: Slow mobile data and calls may drop or fail in Sydney and NSW. Sorry. We'll update you. |
| RCA-60fe3d71c22893d5 | NSW | 2026-11-06T07:42:33.256Z | draft | true | NULL | 155 | llm | Banksia Mobile: Customers in Bathurst and Sydney & NSW may have no mobile service, and calls and data may drop or fail to connect. Sorry. We'll update you. |
| RCA-944a68e9bf7eff9b | VIC | 2026-11-06T07:42:33.256Z | draft | true | NULL | 124 | llm | Banksia Mobile: No mobile service and calls and data may drop in Ballarat and Melbourne & Victoria. Sorry. We'll update you. |

_6 row(s)_

## incident_ai_latest (Delta source of the synced table)

```sql
SELECT incident_id, region_code, likely_root_cause, confidence, status, sms_draft_status,
               substr(sms_draft_text, 1, 160) AS sms_draft_text, refreshed_at
        FROM telco_netmon_febar_catalog.netmon_genai.incident_ai_latest ORDER BY incident_id LIMIT 6
```

| incident_id | region_code | likely_root_cause | confidence | status | sms_draft_status | sms_draft_text | refreshed_at |
|---|---|---|---|---|---|---|---|
| RCA-1073d4d88aa7e05b | VIC | CELL-VIC-00062-5G2 | high | draft | draft | Banksia Mobile: No mobile service and calls and data may drop or fail in Melbourne & Victoria. Sorry. We'll update you. | 2026-11-06T07:42:33.256Z |
| RCA-27ed3e8af852d33a | VIC | BH-VIC-0005 | high | draft | draft | Banksia Mobile: Slow mobile data and calls and data may drop or fail in Melbourne & Victoria, incl Melbourne. Sorry. We'll keep you updated. | 2026-11-06T07:42:33.256Z |
| RCA-399fe9bb03f3b4cb | VIC | CELL-VIC-00022-5G3 | high | draft | draft | Banksia Mobile: Some customers in Geelong and Melbourne & Victoria may have no mobile service or calls and data may drop. Sorry. We'll update you. | 2026-11-06T07:42:33.256Z |
| RCA-4b24e8c0bfedac1a | NSW | BH-NSW-0010 | high | draft | draft | Banksia Mobile: Slow mobile data and calls may drop or fail in Sydney and NSW. Sorry. We'll update you. | 2026-11-06T07:42:33.256Z |
| RCA-60fe3d71c22893d5 | NSW | CELL-NSW-00123-4G3 | high | draft | draft | Banksia Mobile: Customers in Bathurst and Sydney & NSW may have no mobile service, and calls and data may drop or fail to connect. Sorry. We'll update you. | 2026-11-06T07:42:33.256Z |
| RCA-944a68e9bf7eff9b | VIC | CELL-VIC-00107-5G1 | high | draft | draft | Banksia Mobile: No mobile service and calls and data may drop in Ballarat and Melbourne & Victoria. Sorry. We'll update you. | 2026-11-06T07:42:33.256Z |

_6 row(s)_

## Synced table lb_incident_ai_latest

```json
{
  "name": "telco_netmon_febar_catalog.netmon_genai.lb_incident_ai_latest",
  "database_instance": null,
  "logical_database": null,
  "source": "telco_netmon_febar_catalog.netmon_genai.incident_ai_latest",
  "primary_key": [
    "incident_id"
  ],
  "scheduling_policy": "SyncedTableSchedulingPolicy.TRIGGERED",
  "state": "SyncedTableState.SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE",
  "message": "Synced table creation succeeded using Delta Live Tables: https://fevm-telco-netmon-febar.cloud.databricks.com#joblist/pipelines/07a8ea76-5fa9-4a5d-90bf-b0a339c0f58a/updates/00f43967-02ca-40ab-b7a0-cfa5bfd386f1.",
  "last_sync": "12"
}
```

## Lakebase read-back with psycopg + OAuth (job banksia-genai-lakebase-check)

```sql
SELECT run_at, query, n, p50_ms, p95_ms, p99_ms, max_ms, rows, open_incidents_without_summary
        FROM telco_netmon_febar_catalog.netmon_genai.lakebase_ai_check ORDER BY run_at DESC, query LIMIT 4
```

| run_at | query | n | p50_ms | p95_ms | p99_ms | max_ms | rows | open_incidents_without_summary |
|---|---|---|---|---|---|---|---|---|
| 2026-11-06T07:48:51.783362+00:00 | ai summary by incident_id (PK) | 300 | 3.83 | 8.06 | 18.28 | 26.43 | 17 | 0 |
| 2026-11-06T07:48:51.783362+00:00 | open incidents of a region + AI summary | 300 | 3.18 | 6.43 | 11.39 | 18.62 | 17 | 0 |
| 2026-11-06T02:25:42.481988+00:00 | ai summary by incident_id (PK) | 300 | 2.81 | 6.0 | 7.98 | 10.4 | 17 | 0 |
| 2026-11-06T02:25:42.481988+00:00 | open incidents of a region + AI summary | 300 | 3.28 | 10.99 | 19.28 | 27.21 | 17 | 0 |

_4 row(s)_

## Rows read back from Postgres (netmon_genai.lb_incident_ai_latest)

```json
[
  {
    "incident_id": "RCA-1073d4d88aa7e05b",
    "region_code": "VIC",
    "likely_root_cause": "CELL-VIC-00062-5G2",
    "fault_hypothesis": "CELL_OUTAGE",
    "confidence": "high",
    "status": "draft",
    "summary": "The impacted pattern is confined to one 5G cell, with availability at 0.0 and a fully degraded KPI profile on that cell, while the parent site and upstream elements are mostly unaffected. There are no active alarms in scope, so this looks like a cell-level outage rather than a broader transport, core, or site power problem.",
    "sms_draft_text": "Banksia Mobile: No mobile service and calls and data may drop or fail in Melbourne & Victoria. Sorry. We'll update you.",
    "sms_draft_status": "draft",
    "generated_by": "llm",
    "generated_at": "2026-11-06 07:42:33.256247+00:00"
  },
  {
    "incident_id": "RCA-27ed3e8af852d33a",
    "region_code": "VIC",
    "likely_root_cause": "BH-VIC-0005",
    "fault_hypothesis": "BACKHAUL_DEGRADATION",
    "confidence": "high",
    "status": "draft",
    "summary": "The strongest fit is a degradation on backhaul link BH-VIC-0005 affecting all 12 impacted cells behind it, with very high latency and loss plus reduced downlink throughput and RRC success. The evidence points to a transport issue rather than a cell or site outage: the link shows no active alarms, the impact spans all impacted children under the link, and the KPI pattern is severe but not silent. If this is correct, the next minutes should keep showing degraded KPIs across those cells until the backhaul recovers or is rerouted.",
    "sms_draft_text": "Banksia Mobile: Slow mobile data and calls and data may drop or fail in Melbourne & Victoria, incl Melbourne. Sorry. We'll keep you updated.",
    "sms_draft_status": "draft",
    "generated_by": "llm",
    "generated_at": "2026-11-06 07:42:33.256247+00:00"
  },
  {
    "incident_id": "RCA-399fe9bb03f3b4cb",
    "region_code": "VIC",
    "likely_root_cause": "CELL-VIC-00022-5G3",
    "fault_hypothesis": "CELL_OUTAGE",
    "confidence": "high",
    "status": "draft",
    "summary": "The strongest match is CELL-VIC-00022-5G3: it has an active critical CELL_OUT_OF_SERVICE alarm, service down, and the cell is fully unavailable with severe RRC and throughput degradation. The parent site and upstream elements are not showing a matching outage pattern, so this looks like a single-cell outage rather than a site or transport fault.",
    "sms_draft_text": "Banksia Mobile: Some customers in Geelong and Melbourne & Victoria may have no mobile service or calls and data may drop. Sorry. We'll update you.",
    "sms_draft_status": "draft",
    "generated_by": "llm",
    "generated_at": "2026-11-06 07:42:33.256247+00:00"
  },
  {
    "incident_id": "RCA-4b24e8c0bfedac1a",
    "region_code": "NSW",
    "likely_root_cause": "BH-NSW-0010",
    "fault_hypothesis": "BACKHAUL_DEGRADATION",
    "confidence": "high",
    "status": "draft",
    "summary": "The evidence points to degraded fibre backhaul on BH-NSW-0010 affecting its single child site SITE-NSW-00025 and all 3 impacted cells. KPI patterns show severe latency and loss with reduced downlink throughput and RRC success, while availability stays at 100% and there are no cell-level service-down alarms, which fits degradation rather than a full cut or cell outage.",
    "sms_draft_text": "Banksia Mobile: Slow mobile data and calls may drop or fail in Sydney and NSW. Sorry. We'll update you.",
    "sms_draft_status": "draft",
    "generated_by": "llm",
    "generated_at": "2026-11-06 07:42:33.256247+00:00"
  },
  {
    "incident_id": "RCA-60fe3d71c22893d5",
    "region_code": "NSW",
    "likely_root_cause": "CELL-NSW-00123-4G3",
    "fault_hypothesis": "CELL_OUTAGE",
    "confidence": "high",
    "status": "draft",
    "summary": "The strongest signal is a single impacted 4G cell with 0.0% availability and 0.0% attach success while its parent site remains largely up at 66.7% availability. There are no alarms on the cell itself, but the impact is isolated to CELL-NSW-00123-4G3 and the ranker\u2019s top suspect aligns with a cell-level outage pattern rather than a broader site or transport fault.",
    "sms_draft_text": "Banksia Mobile: Customers in Bathurst and Sydney & NSW may have no mobile service, and calls and data may drop or fail to connect. Sorry. We'll update you.",
    "sms_draft_status": "draft",
    "generated_by": "llm",
    "generated_at": "2026-11-06 07:42:33.256247+00:00"
  }
]
```
