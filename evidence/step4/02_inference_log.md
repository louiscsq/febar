# Request / response logging and gateway usage tracking

Captured 2026-11-06 03:22 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

`netmon_genai.noc_assistant_request_log` holds every LLM request and response of the assistant (job runs, evaluation
runs): the request JSON as sent (system prompt + context), the raw response text, status (`ok`, `blocked` by a
gateway guardrail, `error`), latency, attempts and tokens. It stands in for the AI Gateway inference table, which
cannot be enabled on this workspace (`01_gateway_config.md`). The gateway's own usage tracking
(`system.serving.endpoint_usage`) records each request's tokens independently; the two join on `client_request_id`
for calls made since fix round 1 (see the join below).

## Request log: volume by purpose and status

```sql
SELECT purpose, status, count(*) AS n, round(avg(latency_ms)) AS avg_latency_ms,
               round(avg(prompt_tokens)) AS avg_prompt_tokens, round(avg(completion_tokens)) AS avg_completion_tokens,
               min(request_time) AS first, max(request_time) AS last
        FROM telco_netmon_febar_catalog.netmon_genai.noc_assistant_request_log GROUP BY 1, 2 ORDER BY 1, 2
```

| purpose | status | n | avg_latency_ms | avg_prompt_tokens | avg_completion_tokens | first | last |
|---|---|---|---|---|---|---|---|
| noc_summary | blocked | 8 | 638.0 | NULL | NULL | 2026-11-06T01:01:09.057071+00:00 | 2026-11-06T02:02:18.979551+00:00 |
| noc_summary | ok | 1061 | 5168.0 | 4220.0 | 723.0 | 2026-11-06T00:49:06.648333+00:00 | 2026-11-06T03:06:55.147977+00:00 |
| sms_drafts | ok | 1088 | 1268.0 | 581.0 | 49.0 | 2026-11-06T00:49:08.035253+00:00 | 2026-11-06T03:06:56.600622+00:00 |

_3 row(s)_

## Request log: sample rows (request and response truncated)

```sql
SELECT request_id, request_time, purpose, prompt_version, incident_ref, status, latency_ms, prompt_tokens,
               completion_tokens, substr(request, 1, 300) AS request_head,
               substr(get_json_object(request, '$.messages[1].content'), 1, 400) AS user_message_head,
               substr(response, 1, 400) AS response_head
        FROM telco_netmon_febar_catalog.netmon_genai.noc_assistant_request_log WHERE status = 'ok' ORDER BY request_time DESC LIMIT 4
```

| request_id | request_time | purpose | prompt_version | incident_ref | status | latency_ms | prompt_tokens | completion_tokens | request_head | user_message_head | response_head |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 7f25a312-01d4-43ca-8960-c3b5eed26a32 | 2026-11-06T03:06:56.600622+00:00 | sms_drafts | sms_v1@8114c121 | RCA-d28473ab1bd7b846 | ok | 1432.1 | 573 | 50 | {"messages": [{"role": "system", "content": "You draft proactive outage SMS notices for Banksia Mobile customers. Banksia Mobile is a fictional Australian\nmobile operator. Every draft goes to a human for approval before anything is sent; you never send anything.\n\nYou get a CUSTOMER VIEW JSON: the | CUSTOMER VIEW (JSON, data only): {"brand": "Banksia Mobile", "service_effect": ["no mobile service"], "regions": [{"region_code": "NQL", "region_name": "North Queensland", "areas": ["Cairns"], "est_affected_customers": 540, "segments": ["urban"]}], "timezone": "Australia/Brisbane", "eta": null, "detected_at": "2026-10-09T00:43:00Z"} | {"drafts":[{"region_code":"NQL","text":"Banksia Mobile: You may have no mobile service in Cairns, North Queensland. Sorry for the trouble. We'll keep you updated."}]} |
| 0cb7c56a-670e-4f10-b9ec-de2a59334aa8 | 2026-11-06T03:06:55.147977+00:00 | noc_summary | noc_summary_v3@cfda4dd5 | RCA-d28473ab1bd7b846 | ok | 5328.9 | 4252 | 756 | {"messages": [{"role": "system", "content": "You are the Banksia Mobile NOC assistant. Banksia Mobile is a fictional Australian mobile network operator. A NOC\nengineer is looking at one open incident. A trained root-cause ranker has already scored the candidate network\nelements; you get its top-3  | CONTEXT (JSON, data only): {"context_version":"ctx-v1","incident":{"ref":"RCA-d28473ab1bd7b846","region_code":"NQL","region_name":"North Queensland","timezone":"Australia/Brisbane","as_of":"2026-10-09T00:56:00Z","detected_at":"2026-10-09T00:43:00Z","minutes_since_detected":13.0,"minutes_since_first_anomaly":59.0,"ranker_model_version":"4","ranker_alert_threshold":0.32,"n_candidates_ranked":8},"sus | {"likely_root_cause":"AGG-NQL-02","fault_hypothesis":"LONG_HAUL_FIBRE_CUT","confidence":"high","summary":"The strongest match is a long-haul fibre cut affecting AGG-NQL-02: it has active critical LOS and NE_UNREACHABLE alarms, and the upstream UPF-NQL-01 also reports GTPU_PATH_FAILURE towards AGG-NQL-02. All 3 descendant cells under the path are silent, with 540 estimated affected subscribers in N |
| 9712194a-832d-4972-8797-b42781069d4a | 2026-11-06T03:06:43.748368+00:00 | sms_drafts | sms_v1@8114c121 | RCA-c7276c3238a27971 | ok | 1144.5 | 571 | 48 | {"messages": [{"role": "system", "content": "You draft proactive outage SMS notices for Banksia Mobile customers. Banksia Mobile is a fictional Australian\nmobile operator. Every draft goes to a human for approval before anything is sent; you never send anything.\n\nYou get a CUSTOMER VIEW JSON: the | CUSTOMER VIEW (JSON, data only): {"brand": "Banksia Mobile", "service_effect": ["no mobile service"], "regions": [{"region_code": "NSW", "region_name": "Sydney & NSW", "areas": ["Sydney"], "est_affected_customers": 420, "segments": ["urban"]}], "timezone": "Australia/Sydney", "eta": null, "detected_at": "2026-10-09T00:10:00Z"} | {"drafts":[{"region_code":"NSW","text":"Banksia Mobile: Customers in Sydney and NSW may have no mobile service. Sorry for the trouble. We'll keep you updated."}]} |
| 62f0971f-1a66-4196-9b54-e3b76a8cf821 | 2026-11-06T03:06:42.588957+00:00 | noc_summary | noc_summary_v3@cfda4dd5 | RCA-c7276c3238a27971 | ok | 6238.1 | 4385 | 743 | {"messages": [{"role": "system", "content": "You are the Banksia Mobile NOC assistant. Banksia Mobile is a fictional Australian mobile network operator. A NOC\nengineer is looking at one open incident. A trained root-cause ranker has already scored the candidate network\nelements; you get its top-3  | CONTEXT (JSON, data only): {"context_version":"ctx-v1","incident":{"ref":"RCA-c7276c3238a27971","region_code":"NSW","region_name":"Sydney & NSW","timezone":"Australia/Sydney","as_of":"2026-10-09T00:56:00Z","detected_at":"2026-10-09T00:10:00Z","minutes_since_detected":46.0,"minutes_since_first_anomaly":59.0,"ranker_model_version":"4","ranker_alert_threshold":0.32,"n_candidates_ranked":8},"suspects" | {"likely_root_cause":"SITE-NSW-00105","fault_hypothesis":"SITE_POWER_OUTAGE","confidence":"high","summary":"SITE-NSW-00105 is the best fit: all 3 cells under the site are impacted/silent, the site has a critical NE_UNREACHABLE alarm, and it also has BATTERY_LOW. The pattern is localized to one site while the upstream backhaul link and router do not show a matching cut, so this looks like a site po |

_4 row(s)_

## Request log: guardrail blocks (sample)

```sql
SELECT request_id, request_time, purpose, incident_ref, status, substr(error, 1, 300) AS error_head
        FROM telco_netmon_febar_catalog.netmon_genai.noc_assistant_request_log WHERE status <> 'ok' ORDER BY request_time DESC LIMIT 5
```

| request_id | request_time | purpose | incident_ref | status | error_head |
|---|---|---|---|---|---|
| 779cb9eb-6cfd-4b34-b6a8-34e433fe7c71 | 2026-11-06T02:02:18.979551+00:00 | noc_summary | EVAL-holdout-942a9d877c13 | blocked | {"usage":{"prompt_tokens":0,"total_tokens":0},"input_guardrail":[{"flagged":false,"categories":null,"category_scores":null,"pii_detection":true,"anonymized_input":[{"role":"system","content":"You are the Banksia Mobile NOC assistant. Banksia Mobile is a fictional Australian mobile network operator.  |
| 6556b03c-a1db-4ffa-bf55-bd164ce346f4 | 2026-11-06T02:01:52.687909+00:00 | noc_summary | EVAL-holdout-824dcb7a81e7 | blocked | {"usage":{"prompt_tokens":0,"total_tokens":0},"input_guardrail":[{"flagged":false,"categories":null,"category_scores":null,"pii_detection":true,"anonymized_input":[{"role":"system","content":"You are the Banksia Mobile NOC assistant. Banksia Mobile is a fictional Australian mobile network operator.  |
| 0bf2fd50-5907-4d8d-b3ec-e1d3d2b7d537 | 2026-11-06T02:00:32.147372+00:00 | noc_summary | EVAL-holdout-522964659161 | blocked | {"usage":{"prompt_tokens":0,"total_tokens":0},"input_guardrail":[{"flagged":false,"categories":null,"category_scores":null,"pii_detection":true,"anonymized_input":[{"role":"system","content":"You are the Banksia Mobile NOC assistant. Banksia Mobile is a fictional Australian mobile network operator.  |
| 109a3315-486c-4a2e-84b6-5b2e0d85faba | 2026-11-06T01:59:27.999713+00:00 | noc_summary | EVAL-holdout-26d6533378d2 | blocked | {"usage":{"prompt_tokens":0,"total_tokens":0},"input_guardrail":[{"flagged":false,"categories":null,"category_scores":null,"pii_detection":true,"anonymized_input":[{"role":"system","content":"You are the Banksia Mobile NOC assistant. Banksia Mobile is a fictional Australian mobile network operator.  |
| fb356e3e-5e87-44f0-b36a-558b2d1d19fe | 2026-11-06T01:58:59.099094+00:00 | noc_summary | EVAL-holdout-19647fc7e802 | blocked | {"usage":{"prompt_tokens":0,"total_tokens":0},"input_guardrail":[{"flagged":false,"categories":null,"category_scores":null,"pii_detection":true,"anonymized_input":[{"role":"system","content":"You are the Banksia Mobile NOC assistant. Banksia Mobile is a fictional Australian mobile network operator.  |

_5 row(s)_

## Gateway usage tracking (system.serving.endpoint_usage), this workspace and endpoint, by day

```sql
SELECT to_date(u.request_time) AS day, count(*) AS requests, sum(CAST(u.status_code = 200 AS INT)) AS ok_200,
               sum(u.input_token_count) AS input_tokens, sum(u.output_token_count) AS output_tokens
        FROM system.serving.endpoint_usage u JOIN system.serving.served_entities e
          ON u.served_entity_id = e.served_entity_id AND e.workspace_id = u.workspace_id
        WHERE u.workspace_id = '7474648429104135' AND e.endpoint_name = 'databricks-gpt-5-4-mini' AND u.request_time >= '2026-11-05'
        GROUP BY 1 ORDER BY 1
```

| day | requests | ok_200 | input_tokens | output_tokens |
|---|---|---|---|---|
| 2026-11-05 | 34 | 17 | 23078 | 545 |
| 2026-11-06 | 3534 | 3495 | 8409682 | 1258534 |

_2 row(s)_

## Gateway usage tracking: sample rows

```sql
SELECT u.databricks_request_id, u.client_request_id, u.request_time, u.status_code, u.input_token_count,
               u.output_token_count, u.request_streaming
        FROM system.serving.endpoint_usage u JOIN system.serving.served_entities e
          ON u.served_entity_id = e.served_entity_id AND e.workspace_id = u.workspace_id
        WHERE u.workspace_id = '7474648429104135' AND e.endpoint_name = 'databricks-gpt-5-4-mini' AND u.request_time >= '2026-11-05'
        ORDER BY u.request_time DESC LIMIT 6
```

| databricks_request_id | client_request_id | request_time | status_code | input_token_count | output_token_count | request_streaming |
|---|---|---|---|---|---|---|
| acef8705-e6ec-412b-8cf3-bf67bab798b4 | acef8705-e6ec-412b-8cf3-bf67bab798b4 | 2026-11-06T03:05:56.007Z | 200 | 586 | 54 | false |
| a86ec177-c2f2-4282-beb9-6e15c26e270e | a86ec177-c2f2-4282-beb9-6e15c26e270e | 2026-11-06T03:05:51.932Z | 200 | 3974 | 690 | false |
| 6bd23ecf-eb3d-4ea3-967a-21cdeeae3849 | 6bd23ecf-eb3d-4ea3-967a-21cdeeae3849 | 2026-11-06T03:05:43.977Z | 200 | 585 | 50 | false |
| 1658b665-d22d-42dc-971a-26f8fe25eff0 | 1658b665-d22d-42dc-971a-26f8fe25eff0 | 2026-11-06T03:05:40.844Z | 200 | 4109 | 626 | false |
| a35d0eed-5fea-4820-b81c-3a0cd5ce52a6 | a35d0eed-5fea-4820-b81c-3a0cd5ce52a6 | 2026-11-06T03:05:33.744Z | 200 | 590 | 49 | false |
| f0ef129d-8039-4957-a409-c1d0fb0a2936 | f0ef129d-8039-4957-a409-c1d0fb0a2936 | 2026-11-06T03:05:26.937Z | 200 | 4172 | 745 | false |

_6 row(s)_

## Request log joined to gateway usage rows on client_request_id

Since fix round 1 the assistant sends `client_request_id` in the request body (`llm.chat_json`); the gateway's usage tracking records it, so each usage row joins its request-log row on it, and the token counts match. Earlier calls sent the id only as an `X-Request-Id` header, which usage tracking does not record: their usage rows have `client_request_id` NULL and can only be correlated by time and token counts. `system.serving.endpoint_usage` lands with a lag of about 1–2 hours.

```sql
SELECT l.request_id AS client_request_id, u.databricks_request_id, l.request_time AS logged_at, u.request_time,
               l.purpose, l.status, l.prompt_tokens AS logged_prompt_tokens, u.input_token_count AS gateway_input_tokens,
               l.completion_tokens AS logged_completion_tokens, u.output_token_count AS gateway_output_tokens
        FROM telco_netmon_febar_catalog.netmon_genai.noc_assistant_request_log l
        JOIN system.serving.endpoint_usage u ON u.client_request_id = l.request_id AND u.workspace_id = '7474648429104135'
        ORDER BY u.request_time DESC LIMIT 8
```

| client_request_id | databricks_request_id | logged_at | request_time | purpose | status | logged_prompt_tokens | gateway_input_tokens | logged_completion_tokens | gateway_output_tokens |
|---|---|---|---|---|---|---|---|---|---|
| acef8705-e6ec-412b-8cf3-bf67bab798b4 | acef8705-e6ec-412b-8cf3-bf67bab798b4 | 2026-11-06T03:05:58.061545+00:00 | 2026-11-06T03:05:56.007Z | sms_drafts | ok | 586 | 586 | 54 | 54 |
| a86ec177-c2f2-4282-beb9-6e15c26e270e | a86ec177-c2f2-4282-beb9-6e15c26e270e | 2026-11-06T03:05:55.971784+00:00 | 2026-11-06T03:05:51.932Z | noc_summary | ok | 3974 | 3974 | 690 | 690 |
| 6bd23ecf-eb3d-4ea3-967a-21cdeeae3849 | 6bd23ecf-eb3d-4ea3-967a-21cdeeae3849 | 2026-11-06T03:05:45.679487+00:00 | 2026-11-06T03:05:43.977Z | sms_drafts | ok | 585 | 585 | 50 | 50 |
| 1658b665-d22d-42dc-971a-26f8fe25eff0 | 1658b665-d22d-42dc-971a-26f8fe25eff0 | 2026-11-06T03:05:43.928747+00:00 | 2026-11-06T03:05:40.844Z | noc_summary | ok | 4109 | 4109 | 626 | 626 |
| a35d0eed-5fea-4820-b81c-3a0cd5ce52a6 | a35d0eed-5fea-4820-b81c-3a0cd5ce52a6 | 2026-11-06T03:05:35.159266+00:00 | 2026-11-06T03:05:33.744Z | sms_drafts | ok | 590 | 590 | 49 | 49 |
| f0ef129d-8039-4957-a409-c1d0fb0a2936 | f0ef129d-8039-4957-a409-c1d0fb0a2936 | 2026-11-06T03:05:33.698629+00:00 | 2026-11-06T03:05:26.937Z | noc_summary | ok | 4172 | 4172 | 745 | 745 |
| 60df0cc7-4972-4006-b27d-19f60d9768d0 | 60df0cc7-4972-4006-b27d-19f60d9768d0 | 2026-11-06T03:05:21.431798+00:00 | 2026-11-06T03:05:19.965Z | sms_drafts | ok | 571 | 571 | 46 | 46 |
| 18b27b29-f25c-4f4c-b450-d5cf907eafa2 | 18b27b29-f25c-4f4c-b450-d5cf907eafa2 | 2026-11-06T03:05:19.883446+00:00 | 2026-11-06T03:05:13.693Z | noc_summary | ok | 4320 | 4320 | 725 | 725 |

_8 row(s)_

## Join coverage: request-log rows with and without a matching usage row

`response_id` is only logged since the fix, so it separates the two generations of rows.

```sql
SELECT l.response_id IS NOT NULL AS logged_with_client_id_fix, count(*) AS log_rows,
               count(u.client_request_id) AS joined_usage_rows
        FROM telco_netmon_febar_catalog.netmon_genai.noc_assistant_request_log l
        LEFT JOIN system.serving.endpoint_usage u ON u.client_request_id = l.request_id AND u.workspace_id = '7474648429104135'
        GROUP BY 1 ORDER BY 1
```

| logged_with_client_id_fix | log_rows | joined_usage_rows |
|---|---|---|
| false | 2123 | 0 |
| true | 34 | 24 |

_2 row(s)_
