# Latency and cost

Captured 2026-11-06 02:27 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

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
| 346 | 6411.0 | 8012.0 | 21350.0 | 4896.0 | 772.0 | 2.02 |

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
| 323 | 6606.0 | 7925.0 | 9098.0 | 4705.0 | 791.0 | 2.02 |

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
| noc_summary | 1044 | 5232.0 | 6501.0 | 4218.0 | 723.0 |
| sms_drafts | 1071 | 1223.0 | 1672.0 | 581.0 | 49.0 |

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
| 2026-11-05 | ENTERPRISE_SERVERLESS_REAL_TIME_INFERENCE_US_EAST_N_VIRGINIA | DBU | 0.0000 | 0.0000 |

_1 row(s)_

## Gateway usage tracking: tokens on the endpoint (this workspace)

```sql
SELECT count(*) AS requests, sum(u.input_token_count) AS input_tokens, sum(u.output_token_count) AS output_tokens
        FROM system.serving.endpoint_usage u JOIN system.serving.served_entities e
          ON u.served_entity_id = e.served_entity_id AND e.workspace_id = u.workspace_id
        WHERE u.workspace_id = '7474648429104135' AND e.endpoint_name = 'databricks-gpt-5-4-mini' AND u.request_time >= '2026-11-05'
```

| requests | input_tokens | output_tokens |
|---|---|---|
| 3543 | 8372962 | 1249535 |

_1 row(s)_
