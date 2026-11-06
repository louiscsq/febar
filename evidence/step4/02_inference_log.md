# Request / response logging and gateway usage tracking

Captured 2026-11-06 08:12 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

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
| noc_summary | blocked | 16 | 1341.0 | NULL | NULL | 2026-11-06T01:01:09.057071+00:00 | 2026-11-06T08:05:12.073342+00:00 |
| noc_summary | ok | 1741 | 5042.0 | 4258.0 | 725.0 | 2026-11-06T00:49:06.648333+00:00 | 2026-11-06T08:08:10.965689+00:00 |
| sms_drafts | ok | 1786 | 1251.0 | 581.0 | 49.0 | 2026-11-06T00:49:08.035253+00:00 | 2026-11-06T08:08:12.658378+00:00 |

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
| 2a78cee0-e040-4e10-9184-568f83d0ba07 | 2026-11-06T08:08:12.658378+00:00 | sms_drafts | sms_v1@8114c121 | EVAL-holdout-ffcf5a4c36c5 | ok | 1407.2 | 575 | 47 | {"messages": [{"role": "system", "content": "You draft proactive outage SMS notices for Banksia Mobile customers. Banksia Mobile is a fictional Australian\nmobile operator. Every draft goes to a human for approval before anything is sent; you never send anything.\n\nYou get a CUSTOMER VIEW JSON: the | CUSTOMER VIEW (JSON, data only): {"brand": "Banksia Mobile", "service_effect": ["no mobile service"], "regions": [{"region_code": "VIC", "region_name": "Melbourne & Victoria", "areas": ["Geelong"], "est_affected_customers": 190, "segments": ["rural"]}], "timezone": "Australia/Melbourne", "eta": null, "detected_at": "2026-10-18T11:19:00Z"} | {"drafts":[{"region_code":"VIC","text":"Banksia Mobile: Customers in Geelong and Melbourne & Victoria may have no mobile service. Sorry. We'll update you."}]} |
| f048121d-ebc4-4bb1-9285-a68b158b9753 | 2026-11-06T08:08:11.758263+00:00 | sms_drafts | sms_v1@8114c121 | EVAL-holdout-fac760d8d94c | ok | 1456.6 | 575 | 48 | {"messages": [{"role": "system", "content": "You draft proactive outage SMS notices for Banksia Mobile customers. Banksia Mobile is a fictional Australian\nmobile operator. Every draft goes to a human for approval before anything is sent; you never send anything.\n\nYou get a CUSTOMER VIEW JSON: the | CUSTOMER VIEW (JSON, data only): {"brand": "Banksia Mobile", "service_effect": ["no mobile service"], "regions": [{"region_code": "WA", "region_name": "Perth & South West WA", "areas": ["Perth"], "est_affected_customers": 770, "segments": ["urban"]}], "timezone": "Australia/Perth", "eta": null, "detected_at": "2026-10-17T04:47:00Z"} | {"drafts":[{"region_code":"WA","text":"Banksia Mobile: You may have no mobile service in Perth and South West WA. Sorry for the disruption. We'll update you."}]} |
| 6a85d969-cb45-4696-8701-7dd3eb2b858f | 2026-11-06T08:08:11.664823+00:00 | sms_drafts | sms_v1@8114c121 | EVAL-holdout-fb9b8c4ee572 | ok | 1293.4 | 576 | 50 | {"messages": [{"role": "system", "content": "You draft proactive outage SMS notices for Banksia Mobile customers. Banksia Mobile is a fictional Australian\nmobile operator. Every draft goes to a human for approval before anything is sent; you never send anything.\n\nYou get a CUSTOMER VIEW JSON: the | CUSTOMER VIEW (JSON, data only): {"brand": "Banksia Mobile", "service_effect": ["no mobile service"], "regions": [{"region_code": "VIC", "region_name": "Melbourne & Victoria", "areas": ["Bendigo"], "est_affected_customers": 240, "segments": ["rural"]}], "timezone": "Australia/Melbourne", "eta": null, "detected_at": "2026-10-17T22:02:00Z"} | {"drafts":[{"region_code":"VIC","text":"Banksia Mobile: Customers in Bendigo and Melbourne & Victoria may have no mobile service. Sorry for the trouble. We'll update you."}]} |
| 811e8d6a-29c9-4410-b376-86bad39ea2aa | 2026-11-06T08:08:11.215454+00:00 | sms_drafts | sms_v1@8114c121 | EVAL-holdout-facc1463f506 | ok | 1041.2 | 576 | 51 | {"messages": [{"role": "system", "content": "You draft proactive outage SMS notices for Banksia Mobile customers. Banksia Mobile is a fictional Australian\nmobile operator. Every draft goes to a human for approval before anything is sent; you never send anything.\n\nYou get a CUSTOMER VIEW JSON: the | CUSTOMER VIEW (JSON, data only): {"brand": "Banksia Mobile", "service_effect": ["intermittent mobile service"], "regions": [{"region_code": "VIC", "region_name": "Melbourne & Victoria", "areas": ["Geelong"], "est_affected_customers": 220, "segments": ["urban"]}], "timezone": "Australia/Melbourne", "eta": null, "detected_at": "2026-10-18T11:50:00Z"} | {"drafts":[{"region_code":"VIC","text":"Banksia Mobile: Some customers in Geelong and Melbourne & Victoria may have intermittent mobile service. Sorry for the trouble. We'll update you."}]} |

_4 row(s)_

## Request log: guardrail blocks (sample)

```sql
SELECT request_id, request_time, purpose, incident_ref, status, substr(error, 1, 300) AS error_head
        FROM telco_netmon_febar_catalog.netmon_genai.noc_assistant_request_log WHERE status <> 'ok' ORDER BY request_time DESC LIMIT 5
```

| request_id | request_time | purpose | incident_ref | status | error_head |
|---|---|---|---|---|---|
| 567b20df-25b7-415a-8aaf-d87f6e3dc8fe | 2026-11-06T08:05:12.073342+00:00 | noc_summary | EVAL-holdout-942a9d877c13 | blocked | {"usage":{"prompt_tokens":0,"total_tokens":0},"input_guardrail":[{"flagged":false,"categories":null,"category_scores":null,"pii_detection":true,"anonymized_input":[{"role":"system","content":"You are the Banksia Mobile NOC assistant. Banksia Mobile is a fictional Australian mobile network operator.  |
| cd2ec9a1-6faa-4fff-b3eb-10b8df3361ec | 2026-11-06T08:04:43.984026+00:00 | noc_summary | EVAL-holdout-824dcb7a81e7 | blocked | {"usage":{"prompt_tokens":0,"total_tokens":0},"input_guardrail":[{"flagged":false,"categories":null,"category_scores":null,"pii_detection":true,"anonymized_input":[{"role":"system","content":"You are the Banksia Mobile NOC assistant. Banksia Mobile is a fictional Australian mobile network operator.  |
| e4166dd0-989f-465b-ad03-f7a08840d5dc | 2026-11-06T08:04:37.518110+00:00 | noc_summary | EVAL-holdout-79fd28f327e3 | blocked | {"usage":{"prompt_tokens":1001,"total_tokens":1008},"output_guardrail":[{"flagged":true,"categories":{"violent-crimes":false,"non-violent-crimes":false,"sex-crimes":false,"child-exploitation":false,"specialized-advice":true,"privacy":false,"intellectual-property":false,"indiscriminate-weapons":true, |
| 83f1a3cd-5e56-4217-a7c3-fc309877742a | 2026-11-06T08:03:23.178448+00:00 | noc_summary | EVAL-holdout-522964659161 | blocked | {"usage":{"prompt_tokens":0,"total_tokens":0},"input_guardrail":[{"flagged":false,"categories":null,"category_scores":null,"pii_detection":true,"anonymized_input":[{"role":"system","content":"You are the Banksia Mobile NOC assistant. Banksia Mobile is a fictional Australian mobile network operator.  |
| c99a783c-5456-461d-8352-b42c735d2e2a | 2026-11-06T08:01:44.133864+00:00 | noc_summary | EVAL-holdout-19647fc7e802 | blocked | {"usage":{"prompt_tokens":0,"total_tokens":0},"input_guardrail":[{"flagged":false,"categories":null,"category_scores":null,"pii_detection":true,"anonymized_input":[{"role":"system","content":"You are the Banksia Mobile NOC assistant. Banksia Mobile is a fictional Australian mobile network operator.  |

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
| 2026-11-06 | 4281 | 4240 | 10212630 | 1545087 |

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
| 8040b216-0633-49f0-b6a3-5e03500b6675 | 8040b216-0633-49f0-b6a3-5e03500b6675 | 2026-11-06T07:55:46.906Z | 200 | 593 | 49 | false |
| 270b8d93-7b94-407d-9124-130a2bd94710 | 270b8d93-7b94-407d-9124-130a2bd94710 | 2026-11-06T07:55:44.533Z | 200 | 593 | 49 | false |
| 9fe9b355-d7dd-4c66-90cd-6e66dd1635ea | 9fe9b355-d7dd-4c66-90cd-6e66dd1635ea | 2026-11-06T07:55:43.618Z | 200 | 576 | 49 | false |
| 17662d66-2cfe-46df-82ca-ce22dff36ff0 | 17662d66-2cfe-46df-82ca-ce22dff36ff0 | 2026-11-06T07:55:42.306Z | 200 | 4291 | 700 | false |
| 99239d18-5690-4823-b62c-d6360e36a3c1 | 99239d18-5690-4823-b62c-d6360e36a3c1 | 2026-11-06T07:55:40.099Z | 200 | 4241 | 698 | false |
| 9c2087ff-6eaa-4658-aa20-8dedc3d5836f | 9c2087ff-6eaa-4658-aa20-8dedc3d5836f | 2026-11-06T07:55:39.185Z | 200 | 577 | 48 | false |

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
| 8040b216-0633-49f0-b6a3-5e03500b6675 | 8040b216-0633-49f0-b6a3-5e03500b6675 | 2026-11-06T07:55:47.996128+00:00 | 2026-11-06T07:55:46.906Z | sms_drafts | ok | 593 | 593 | 49 | 49 |
| 270b8d93-7b94-407d-9124-130a2bd94710 | 270b8d93-7b94-407d-9124-130a2bd94710 | 2026-11-06T07:55:45.938993+00:00 | 2026-11-06T07:55:44.533Z | sms_drafts | ok | 593 | 593 | 49 | 49 |
| 9fe9b355-d7dd-4c66-90cd-6e66dd1635ea | 9fe9b355-d7dd-4c66-90cd-6e66dd1635ea | 2026-11-06T07:55:44.856745+00:00 | 2026-11-06T07:55:43.618Z | sms_drafts | ok | 576 | 576 | 49 | 49 |
| 17662d66-2cfe-46df-82ca-ce22dff36ff0 | 17662d66-2cfe-46df-82ca-ce22dff36ff0 | 2026-11-06T07:55:46.584016+00:00 | 2026-11-06T07:55:42.306Z | noc_summary | ok | 4291 | 4291 | 700 | 700 |
| 99239d18-5690-4823-b62c-d6360e36a3c1 | 99239d18-5690-4823-b62c-d6360e36a3c1 | 2026-11-06T07:55:43.359702+00:00 | 2026-11-06T07:55:40.099Z | noc_summary | ok | 4241 | 4241 | 698 | 698 |
| 9c2087ff-6eaa-4658-aa20-8dedc3d5836f | 9c2087ff-6eaa-4658-aa20-8dedc3d5836f | 2026-11-06T07:55:40.294943+00:00 | 2026-11-06T07:55:39.185Z | sms_drafts | ok | 577 | 577 | 48 | 48 |
| d2b57184-9dfe-461f-afe9-2cbb4b9612fe | d2b57184-9dfe-461f-afe9-2cbb4b9612fe | 2026-11-06T07:55:44.282178+00:00 | 2026-11-06T07:55:38.647Z | noc_summary | ok | 5149 | 5149 | 819 | 819 |
| 600a2893-dc99-499b-9f1c-4119764d4cfa | 600a2893-dc99-499b-9f1c-4119764d4cfa | 2026-11-06T07:55:38.826535+00:00 | 2026-11-06T07:55:37.814Z | sms_drafts | ok | 591 | 591 | 50 | 50 |

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
| false | 2131 | 2 |
| true | 1412 | 769 |

_2 row(s)_
