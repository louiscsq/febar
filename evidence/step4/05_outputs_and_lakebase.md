# Output tables (UC) and the Lakebase sync

Captured 2026-11-06 02:27 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

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
| genai_eval_results_dev | MANAGED | Gen AI assistant evaluation (dev): per incident, the assistant's root vs the ranker's top-1 vs ground truth, guard repairs, SMS compliance, judges, latency and tokens. MLflow run a3ec3955c745457492240515d67f929d. |
| genai_eval_results_holdout | MANAGED | Gen AI assistant evaluation (holdout): per incident, the assistant's root vs the ranker's top-1 vs ground truth, guard repairs, SMS compliance, judges, latency and tokens. MLflow run c403ff94c1c7436eabd43e026231035c. |
| genai_eval_summary_dev | MANAGED | Gen AI evaluation summary (dev), overall and per fault type. |
| genai_eval_summary_holdout | MANAGED | Gen AI evaluation summary (holdout), overall and per fault type. |
| incident_ai_latest | MANAGED | Latest NOC assistant summary and SMS draft per open incident (status = draft). Source of the Lakebase synced table lb_incident_ai_latest read by the step-5 app. |
| incident_ai_summaries | MANAGED | Every NOC assistant summary (status = draft, for NOC review): incident, endpoint / prompt / context / ranker versions, generated_at, likely root cause (a suspect or 'uncertain'), evidence, next steps, customer impact, guard report, latency… |
| lakebase_ai_check | MANAGED | NULL |
| lb_incident_ai_latest | FOREIGN | Database table synced from another UC table |
| noc_assistant_request_log | MANAGED | Every LLM request / response of the NOC assistant (request JSON, response text, status incl. gateway guardrail blocks, latency, tokens). Stands in for the AI Gateway inference table, which fails to enable on this workspace (docs/genai_assi… |

_13 row(s)_

## incident_ai_summaries: rows by generator and status

```sql
SELECT status, generated_by, noc_prompt_version, assistant_endpoint, count(*) AS n,
               count(DISTINCT incident_id) AS incidents, min(generated_at) AS first, max(generated_at) AS last
        FROM telco_netmon_febar_catalog.netmon_genai.incident_ai_summaries GROUP BY ALL
```

| status | generated_by | noc_prompt_version | assistant_endpoint | n | incidents | first | last |
|---|---|---|---|---|---|---|---|
| draft | llm | noc_summary_v3@cfda4dd5 | databricks-gpt-5-4-mini | 17 | 17 | 2026-11-06T01:59:36.148Z | 2026-11-06T01:59:36.148Z |
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
| RCA-1073d4d88aa7e05b | VIC | 2026-11-06T01:59:36.148Z | draft | CELL-VIC-00062-5G2 | CELL_OUTAGE | high | The evidence points to a single-cell outage on CELL-VIC-00062-5G2: it is fully impacted with 0.0% availability, 0.0% attach success, 0.0% PRB utilisation, and severe radio/service KPI collapse while its site context is o | 0 | 1 | 6323.1 | 4488 | 743 |
| RCA-27ed3e8af852d33a | VIC | 2026-11-06T01:59:36.148Z | draft | BH-VIC-0005 | BACKHAUL_DEGRADATION | high | BH-VIC-0005 is the strongest match: every impacted descendant cell is degraded, while the link itself carries the full impacted child set and no alarms are active. The KPI pattern shows severe latency, loss, throughput,  | 550 | 12 | 7164.3 | 4762 | 919 |
| RCA-399fe9bb03f3b4cb | VIC | 2026-11-06T01:59:36.148Z | draft | CELL-VIC-00022-5G3 | CELL_OUTAGE | high | Cell CELL-VIC-00022-5G3 is the strongest root-cause candidate: it has an active CRITICAL CELL_OUT_OF_SERVICE alarm, service_down is true, and its availability is 0.0 with severe RRC and throughput degradation. The site/r | 90 | 1 | 6820.8 | 4560 | 781 |
| RCA-4b24e8c0bfedac1a | NSW | 2026-11-06T01:59:36.148Z | draft | BH-NSW-0010 | BACKHAUL_DEGRADATION | high | The strongest match is degradation on backhaul link BH-NSW-0010: all 3 impacted cells behind it show severe latency and loss with reduced throughput, while the site itself and the link have no service-down alarms. The pa | 240 | 3 | 6489.7 | 4773 | 876 |
| RCA-55424701801c7330 | NSW | 2026-11-06T01:59:36.148Z | draft | CELL-NSW-00051-4G3 | CELL_OUTAGE | high | The evidence points to a single-cell outage on CELL-NSW-00051-4G3 in the remote NSW area near Wollongong. That cell is fully impacted with 0.0% availability, 0.0% attach success, a CELL_OUT_OF_SERVICE alarm and an RRU_FA | 20 | 1 | 5870.7 | 6166 | 738 |
| RCA-60fe3d71c22893d5 | NSW | 2026-11-06T01:59:36.148Z | draft | CELL-NSW-00123-4G3 | CELL_OUTAGE | medium | The impact is concentrated on one rural 4G cell in NSW: CELL-NSW-00123-4G3 is fully impacted with availability 0.0 and DL throughput z -9.5, while its parent site still has 2 of 3 cells up (availability 66.7). There is n | 0 | 1 | 6512.5 | 4812 | 823 |

_6 row(s)_

## customer_notice_drafts: every draft is a draft (never sent)

```sql
SELECT status, requires_human_approval, count(*) AS n, count(approved_by) AS approved, count(sent_at) AS sent,
               max(chars) AS max_chars, sum(CAST(violations_json <> '[]' AS INT)) AS with_violations
        FROM telco_netmon_febar_catalog.netmon_genai.customer_notice_drafts GROUP BY ALL
```

| status | requires_human_approval | n | approved | sent | max_chars | with_violations |
|---|---|---|---|---|---|---|
| draft | true | 34 | 0 | 0 | 147 | 0 |

_1 row(s)_

## customer_notice_drafts: sample

```sql
SELECT incident_id, region_code, generated_at, status, requires_human_approval, sent_at, chars, generated_by,
               text FROM telco_netmon_febar_catalog.netmon_genai.customer_notice_drafts ORDER BY generated_at DESC, incident_id LIMIT 6
```

| incident_id | region_code | generated_at | status | requires_human_approval | sent_at | chars | generated_by | text |
|---|---|---|---|---|---|---|---|---|
| RCA-1073d4d88aa7e05b | VIC | 2026-11-06T01:59:36.148Z | draft | true | NULL | 121 | llm | Banksia Mobile: No mobile service and calls and data may drop or fail in Melbourne and Victoria. Sorry. We'll update you. |
| RCA-27ed3e8af852d33a | VIC | 2026-11-06T01:59:36.148Z | draft | true | NULL | 120 | llm | Banksia Mobile: Slow mobile data and calls may drop or fail to connect in Melbourne & Victoria. Sorry. We'll update you. |
| RCA-399fe9bb03f3b4cb | VIC | 2026-11-06T01:59:36.148Z | draft | true | NULL | 122 | llm | Banksia Mobile: No mobile service and calls or data may drop in Geelong and Melbourne & Victoria. Sorry. We'll update you. |
| RCA-4b24e8c0bfedac1a | NSW | 2026-11-06T01:59:36.148Z | draft | true | NULL | 110 | llm | Banksia Mobile: Slow mobile data and calls and data may drop in Sydney and NSW. Sorry. We'll keep you updated. |
| RCA-55424701801c7330 | NSW | 2026-11-06T01:59:36.148Z | draft | true | NULL | 147 | llm | Banksia Mobile: Some customers in Wollongong and Sydney & NSW may have no mobile service. Calls and data may drop or fail. Sorry. We'll update you. |
| RCA-60fe3d71c22893d5 | NSW | 2026-11-06T01:59:36.148Z | draft | true | NULL | 124 | llm | Banksia Mobile: Bathurst may have no mobile service and calls and data may drop or fail to connect. Sorry. We'll update you. |

_6 row(s)_

## incident_ai_latest (Delta source of the synced table)

```sql
SELECT incident_id, region_code, likely_root_cause, confidence, status, sms_draft_status,
               substr(sms_draft_text, 1, 160) AS sms_draft_text, refreshed_at
        FROM telco_netmon_febar_catalog.netmon_genai.incident_ai_latest ORDER BY incident_id LIMIT 6
```

| incident_id | region_code | likely_root_cause | confidence | status | sms_draft_status | sms_draft_text | refreshed_at |
|---|---|---|---|---|---|---|---|
| RCA-1073d4d88aa7e05b | VIC | CELL-VIC-00062-5G2 | high | draft | draft | Banksia Mobile: No mobile service and calls and data may drop or fail in Melbourne and Victoria. Sorry. We'll update you. | 2026-11-06T01:59:36.148Z |
| RCA-27ed3e8af852d33a | VIC | BH-VIC-0005 | high | draft | draft | Banksia Mobile: Slow mobile data and calls may drop or fail to connect in Melbourne & Victoria. Sorry. We'll update you. | 2026-11-06T01:59:36.148Z |
| RCA-399fe9bb03f3b4cb | VIC | CELL-VIC-00022-5G3 | high | draft | draft | Banksia Mobile: No mobile service and calls or data may drop in Geelong and Melbourne & Victoria. Sorry. We'll update you. | 2026-11-06T01:59:36.148Z |
| RCA-4b24e8c0bfedac1a | NSW | BH-NSW-0010 | high | draft | draft | Banksia Mobile: Slow mobile data and calls and data may drop in Sydney and NSW. Sorry. We'll keep you updated. | 2026-11-06T01:59:36.148Z |
| RCA-55424701801c7330 | NSW | CELL-NSW-00051-4G3 | high | draft | draft | Banksia Mobile: Some customers in Wollongong and Sydney & NSW may have no mobile service. Calls and data may drop or fail. Sorry. We'll update you. | 2026-11-06T01:59:36.148Z |
| RCA-60fe3d71c22893d5 | NSW | CELL-NSW-00123-4G3 | medium | draft | draft | Banksia Mobile: Bathurst may have no mobile service and calls and data may drop or fail to connect. Sorry. We'll update you. | 2026-11-06T01:59:36.148Z |

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
  "message": "Synced table creation succeeded using Delta Live Tables: https://fevm-telco-netmon-febar.cloud.databricks.com#joblist/pipelines/07a8ea76-5fa9-4a5d-90bf-b0a339c0f58a/updates/1cd12833-9adb-4c8a-950a-c394dea5c4ed.",
  "last_sync": "8"
}
```

## Lakebase read-back with psycopg + OAuth (job banksia-genai-lakebase-check)

```sql
SELECT run_at, query, n, p50_ms, p95_ms, p99_ms, max_ms, rows, open_incidents_without_summary
        FROM telco_netmon_febar_catalog.netmon_genai.lakebase_ai_check ORDER BY run_at DESC, query LIMIT 4
```

| run_at | query | n | p50_ms | p95_ms | p99_ms | max_ms | rows | open_incidents_without_summary |
|---|---|---|---|---|---|---|---|---|
| 2026-11-06T02:25:42.481988+00:00 | ai summary by incident_id (PK) | 300 | 2.81 | 6.0 | 7.98 | 10.4 | 17 | 0 |
| 2026-11-06T02:25:42.481988+00:00 | open incidents of a region + AI summary | 300 | 3.28 | 10.99 | 19.28 | 27.21 | 17 | 0 |
| 2026-11-06T02:04:07.995427+00:00 | ai summary by incident_id (PK) | 300 | 2.97 | 8.65 | 11.85 | 18.22 | 17 | 0 |
| 2026-11-06T02:04:07.995427+00:00 | open incidents of a region + AI summary | 300 | 3.21 | 8.33 | 14.3 | 19.28 | 17 | 0 |

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
    "summary": "The evidence points to a single-cell outage on CELL-VIC-00062-5G2: it is fully impacted with 0.0% availability, 0.0% attach success, 0.0% PRB utilisation, and severe radio/service KPI collapse while its site context is otherwise not showing a broader site dark pattern. There are no active alarms in scope, so the strongest confirmation would be whether the cell remains silent or recovers in the next KPI windows, and whether the RRU/radio path shows a local fault.",
    "sms_draft_text": "Banksia Mobile: No mobile service and calls and data may drop or fail in Melbourne and Victoria. Sorry. We'll update you.",
    "sms_draft_status": "draft",
    "generated_by": "llm",
    "generated_at": "2026-11-06 01:59:36.148380+00:00"
  },
  {
    "incident_id": "RCA-27ed3e8af852d33a",
    "region_code": "VIC",
    "likely_root_cause": "BH-VIC-0005",
    "fault_hypothesis": "BACKHAUL_DEGRADATION",
    "confidence": "high",
    "status": "draft",
    "summary": "BH-VIC-0005 is the strongest match: every impacted descendant cell is degraded, while the link itself carries the full impacted child set and no alarms are active. The KPI pattern shows severe latency, loss, throughput, RRC success and drop-rate deviation across the 12 impacted cells over the last hour, which fits a backhaul degradation on the link feeding those sites.{",
    "sms_draft_text": "Banksia Mobile: Slow mobile data and calls may drop or fail to connect in Melbourne & Victoria. Sorry. We'll update you.",
    "sms_draft_status": "draft",
    "generated_by": "llm",
    "generated_at": "2026-11-06 01:59:36.148380+00:00"
  },
  {
    "incident_id": "RCA-399fe9bb03f3b4cb",
    "region_code": "VIC",
    "likely_root_cause": "CELL-VIC-00022-5G3",
    "fault_hypothesis": "CELL_OUTAGE",
    "confidence": "high",
    "status": "draft",
    "summary": "Cell CELL-VIC-00022-5G3 is the strongest root-cause candidate: it has an active CRITICAL CELL_OUT_OF_SERVICE alarm, service_down is true, and its availability is 0.0 with severe RRC and throughput degradation. The site/router/core ancestors are not carrying a matching failure pattern, so this looks like a single-cell outage rather than a broader transport or core issue.",
    "sms_draft_text": "Banksia Mobile: No mobile service and calls or data may drop in Geelong and Melbourne & Victoria. Sorry. We'll update you.",
    "sms_draft_status": "draft",
    "generated_by": "llm",
    "generated_at": "2026-11-06 01:59:36.148380+00:00"
  },
  {
    "incident_id": "RCA-4b24e8c0bfedac1a",
    "region_code": "NSW",
    "likely_root_cause": "BH-NSW-0010",
    "fault_hypothesis": "BACKHAUL_DEGRADATION",
    "confidence": "high",
    "status": "draft",
    "summary": "The strongest match is degradation on backhaul link BH-NSW-0010: all 3 impacted cells behind it show severe latency and loss with reduced throughput, while the site itself and the link have no service-down alarms. The pattern is consistent with a fibre backhaul problem affecting one site, not a site power outage or wider router/UPF incident.",
    "sms_draft_text": "Banksia Mobile: Slow mobile data and calls and data may drop in Sydney and NSW. Sorry. We'll keep you updated.",
    "sms_draft_status": "draft",
    "generated_by": "llm",
    "generated_at": "2026-11-06 01:59:36.148380+00:00"
  },
  {
    "incident_id": "RCA-55424701801c7330",
    "region_code": "NSW",
    "likely_root_cause": "CELL-NSW-00051-4G3",
    "fault_hypothesis": "CELL_OUTAGE",
    "confidence": "high",
    "status": "draft",
    "summary": "The evidence points to a single-cell outage on CELL-NSW-00051-4G3 in the remote NSW area near Wollongong. That cell is fully impacted with 0.0% availability, 0.0% attach success, a CELL_OUT_OF_SERVICE alarm and an RRU_FAILURE alarm, while the parent site and upstream transport/core elements show no matching site-wide silent pattern. The impact is limited to one cell and about 20 subscribers.",
    "sms_draft_text": "Banksia Mobile: Some customers in Wollongong and Sydney & NSW may have no mobile service. Calls and data may drop or fail. Sorry. We'll update you.",
    "sms_draft_status": "draft",
    "generated_by": "llm",
    "generated_at": "2026-11-06 01:59:36.148380+00:00"
  }
]
```
