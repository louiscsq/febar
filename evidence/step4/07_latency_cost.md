# Latency and cost

Captured 2026-11-06 08:13 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

Latency is measured client side per incident (summary call + SMS call(s), job -> endpoint), from the evaluation
results. Tokens come from the responses (and match the gateway's usage tracking). Cost: pay-per-token DBUs that
billing attributes to `databricks-gpt-5-4-mini` in this workspace (`system.billing.usage`, filtered to this workspace and endpoint; it
lags a few hours behind the calls), and the per-incident figure from the dev / holdout runs' token counts.

## DEV: latency and tokens per incident

```sql
SELECT count(*) AS n, round(percentile(latency_ms, 0.5)) AS p50_ms, round(percentile(latency_ms, 0.95)) AS p95_ms,
                   round(max(latency_ms)) AS max_ms, round(avg(prompt_tokens)) AS prompt_tokens_mean,
                   round(avg(completion_tokens)) AS completion_tokens_mean, round(avg(n_calls), 2) AS calls_per_incident
            FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_results_dev
```

| n | p50_ms | p95_ms | max_ms | prompt_tokens_mean | completion_tokens_mean | calls_per_incident |
|---|---|---|---|---|---|---|
| 346 | 6014.0 | 7289.0 | 8501.0 | 4887.0 | 776.0 | 2.03 |

_1 row(s)_

## HOLDOUT: latency and tokens per incident

```sql
SELECT count(*) AS n, round(percentile(latency_ms, 0.5)) AS p50_ms, round(percentile(latency_ms, 0.95)) AS p95_ms,
                   round(max(latency_ms)) AS max_ms, round(avg(prompt_tokens)) AS prompt_tokens_mean,
                   round(avg(completion_tokens)) AS completion_tokens_mean, round(avg(n_calls), 2) AS calls_per_incident
            FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_results_holdout
```

| n | p50_ms | p95_ms | max_ms | prompt_tokens_mean | completion_tokens_mean | calls_per_incident |
|---|---|---|---|---|---|---|
| 323 | 6307.0 | 7406.0 | 8300.0 | 4824.0 | 759.0 | 2.0 |

_1 row(s)_

## Request log: latency per call type

```sql
SELECT purpose, count(*) AS n, round(percentile(latency_ms, 0.5)) AS p50_ms,
               round(percentile(latency_ms, 0.95)) AS p95_ms, round(avg(prompt_tokens)) AS prompt_tokens,
               round(avg(completion_tokens)) AS completion_tokens
        FROM telco_netmon_febar_catalog.netmon_genai.noc_assistant_request_log WHERE status = 'ok' GROUP BY 1 ORDER BY 1
```

| purpose | n | p50_ms | p95_ms | prompt_tokens | completion_tokens |
|---|---|---|---|---|---|
| noc_summary | 1741 | 5065.0 | 6337.0 | 4258.0 | 725.0 |
| sms_drafts | 1786 | 1209.0 | 1649.0 | 581.0 | 49.0 |

_2 row(s)_

## Billing: DBUs attributed to the assistant endpoint (this workspace)

List price $0.07 / DBU for the `*_MODEL_SERVING` pay-per-token SKUs (`system.billing.list_prices`).

```sql
SELECT usage_date, sku_name, usage_unit, round(sum(usage_quantity), 4) AS dbus,
               round(sum(usage_quantity) * 0.07, 4) AS usd_at_list_price
        FROM system.billing.usage
        WHERE workspace_id = '7474648429104135' AND usage_metadata.endpoint_name = 'databricks-gpt-5-4-mini' AND usage_date >= '2026-11-05'
        GROUP BY ALL ORDER BY 1
```

| usage_date | sku_name | usage_unit | dbus | usd_at_list_price |
|---|---|---|---|---|
| 2026-11-05 | ENTERPRISE_OPENAI_MODEL_SERVING | DBU | 0.3105 | 0.0217 |
| 2026-11-05 | ENTERPRISE_SERVERLESS_REAL_TIME_INFERENCE_US_EAST_N_VIRGINIA | DBU | 0.0004 | 0.0000 |
| 2026-11-06 | ENTERPRISE_OPENAI_MODEL_SERVING | DBU | 188.2638 | 13.1785 |
| 2026-11-06 | ENTERPRISE_SERVERLESS_REAL_TIME_INFERENCE_US_EAST_N_VIRGINIA | DBU | 0.0630 | 0.0044 |

_4 row(s)_

## Gateway usage tracking: tokens on the endpoint (this workspace)

```sql
SELECT count(*) AS requests, sum(u.input_token_count) AS input_tokens, sum(u.output_token_count) AS output_tokens
        FROM system.serving.endpoint_usage u JOIN system.serving.served_entities e
          ON u.served_entity_id = e.served_entity_id AND e.workspace_id = u.workspace_id
        WHERE u.workspace_id = '7474648429104135' AND e.endpoint_name = 'databricks-gpt-5-4-mini' AND u.request_time >= '2026-11-05'
```

| requests | input_tokens | output_tokens |
|---|---|---|
| 4315 | 10235708 | 1545632 |

_1 row(s)_
