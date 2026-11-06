# Request / response logging and gateway usage tracking

Captured 2026-11-06 02:26 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

`netmon_genai.noc_assistant_request_log` holds every LLM request and response of the assistant (job runs, evaluation
runs): the request JSON as sent (system prompt + context), the raw response text, status (`ok`, `blocked` by a
gateway guardrail, `error`), latency, attempts and tokens. It stands in for the AI Gateway inference table, which
cannot be enabled on this workspace (`01_gateway_config.md`). The gateway's own usage tracking
(`system.serving.endpoint_usage`) records each request's tokens independently.

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
| noc_summary | ok | 1044 | 5167.0 | 4218.0 | 723.0 | 2026-11-06T00:49:06.648333+00:00 | 2026-11-06T02:05:24.813882+00:00 |
| sms_drafts | ok | 1071 | 1266.0 | 581.0 | 49.0 | 2026-11-06T00:49:08.035253+00:00 | 2026-11-06T02:05:26.192829+00:00 |

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
| chatcmpl-Eh3cTFLr2Kw7icxSmigzOZwYU2w37 | 2026-11-06T02:05:26.192829+00:00 | sms_drafts | sms_v1@8114c121 | EVAL-holdout-ffcf5a4c36c5 | ok | 1178.2 | 575 | 44 | {"messages": [{"role": "system", "content": "You draft proactive outage SMS notices for Banksia Mobile customers. Banksia Mobile is a fictional Australian\nmobile operator. Every draft goes to a human for approval before anything is sent; you never send anything.\n\nYou get a CUSTOMER VIEW JSON: the | CUSTOMER VIEW (JSON, data only): {"brand": "Banksia Mobile", "service_effect": ["no mobile service"], "regions": [{"region_code": "VIC", "region_name": "Melbourne & Victoria", "areas": ["Geelong"], "est_affected_customers": 190, "segments": ["rural"]}], "timezone": "Australia/Melbourne", "eta": null, "detected_at": "2026-10-18T11:19:00Z"} | {"drafts":[{"region_code":"VIC","text":"Banksia Mobile: No mobile service in Geelong and Melbourne & Victoria. Sorry. We'll update you."}]} |
| chatcmpl-Eh3cNZgNMjyYvLX52Y88d3rsgdAHY | 2026-11-06T02:05:24.813882+00:00 | noc_summary | noc_summary_v3@cfda4dd5 | EVAL-holdout-ffcf5a4c36c5 | ok | 5806.1 | 3996 | 734 | {"messages": [{"role": "system", "content": "You are the Banksia Mobile NOC assistant. Banksia Mobile is a fictional Australian mobile network operator. A NOC\nengineer is looking at one open incident. A trained root-cause ranker has already scored the candidate network\nelements; you get its top-3  | CONTEXT (JSON, data only): {"context_version":"ctx-v1","incident":{"ref":"EVAL-holdout-ffcf5a4c36c5","region_code":"VIC","region_name":"Melbourne & Victoria","timezone":"Australia/Melbourne","as_of":"2026-10-18T11:19:00Z","detected_at":null,"minutes_since_detected":null,"minutes_since_first_anomaly":55.0,"ranker_model_version":"4","ranker_alert_threshold":0.32,"n_candidates_ranked":9},"suspects":[ | {"likely_root_cause":"SITE-VIC-00069","fault_hypothesis":"CELL_OUTAGE","confidence":"medium","summary":"Three cells under SITE-VIC-00069 are all silent, affecting one rural site and about 190 subscribers in the Geelong area. The site itself has no alarms, while the parent backhaul link and upstream router are not showing a clear transport failure signature; this fits a site/cell-side outage more t |
| chatcmpl-Eh3cMfeoPspWFIXgpcge2F7Gs2HVm | 2026-11-06T02:05:19.058260+00:00 | sms_drafts | sms_v1@8114c121 | EVAL-holdout-fb9b8c4ee572 | ok | 1250.5 | 576 | 47 | {"messages": [{"role": "system", "content": "You draft proactive outage SMS notices for Banksia Mobile customers. Banksia Mobile is a fictional Australian\nmobile operator. Every draft goes to a human for approval before anything is sent; you never send anything.\n\nYou get a CUSTOMER VIEW JSON: the | CUSTOMER VIEW (JSON, data only): {"brand": "Banksia Mobile", "service_effect": ["no mobile service"], "regions": [{"region_code": "VIC", "region_name": "Melbourne & Victoria", "areas": ["Bendigo"], "est_affected_customers": 240, "segments": ["rural"]}], "timezone": "Australia/Melbourne", "eta": null, "detected_at": "2026-10-17T22:02:00Z"} | {"drafts":[{"region_code":"VIC","text":"Banksia Mobile: Customers in Bendigo and Melbourne & Victoria may have no mobile service. Sorry. We'll update you."}]} |
| chatcmpl-Eh3cI2x8DMN22ThcJBCJIuSm45ZoN | 2026-11-06T02:05:16.214102+00:00 | sms_drafts | sms_v1@8114c121 | EVAL-holdout-fac760d8d94c | ok | 1822.1 | 575 | 46 | {"messages": [{"role": "system", "content": "You draft proactive outage SMS notices for Banksia Mobile customers. Banksia Mobile is a fictional Australian\nmobile operator. Every draft goes to a human for approval before anything is sent; you never send anything.\n\nYou get a CUSTOMER VIEW JSON: the | CUSTOMER VIEW (JSON, data only): {"brand": "Banksia Mobile", "service_effect": ["no mobile service"], "regions": [{"region_code": "WA", "region_name": "Perth & South West WA", "areas": ["Perth"], "est_affected_customers": 770, "segments": ["urban"]}], "timezone": "Australia/Perth", "eta": null, "detected_at": "2026-10-17T04:47:00Z"} | {"drafts":[{"region_code":"WA","text":"Banksia Mobile: Sorry, no mobile service in Perth & South West WA, including Perth. We'll keep you updated."}]} |

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
| 2026-11-06 | 3509 | 3470 | 8349884 | 1248990 |

_2 row(s)_

## Gateway usage tracking: sample rows

`client_request_id` is the `X-Request-Id` the assistant sends, so a gateway usage row can be joined to its request-log row.

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
| aac1f447-d869-4503-b554-1c0a1b8fc1f2 | NULL | 2026-11-06T02:06:18.418Z | 400 | 0 | 0 | false |
| 09a0ffc3-257e-41bb-b846-1acdc3bd622c | NULL | 2026-11-06T02:06:17.773Z | 400 | 0 | 0 | false |
| 31ada2d2-80d8-4902-9b32-e8badd0ea5b3 | NULL | 2026-11-06T02:06:15.912Z | 200 | 590 | 51 | false |
| 74febb6b-b57c-4d00-875c-e7557617707e | NULL | 2026-11-06T02:06:09.876Z | 200 | 4371 | 932 | false |
| 519e863c-76c3-4255-9817-36d45239c76a | NULL | 2026-11-06T02:06:08.303Z | 200 | 590 | 51 | false |
| 09e2a10b-47a5-4f0a-a976-477acb3da1ba | NULL | 2026-11-06T02:06:01.745Z | 200 | 4343 | 892 | false |

_6 row(s)_
