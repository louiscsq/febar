# Platform running cost (C2)

Generated 2026-11-07 03:09 UTC by `scripts/capture_cost_step6.py` from `system.billing.usage` joined to `system.billing.list_prices` (list price in force at each usage record, `pricing.default`, USD). DBUs and USD at **list price**; no discounts.

## Summary

- Since the workspace was created (2026-10-08T05:56:51.000Z) to the last billed record (2026-11-06T23:50:00.000Z): **2373.6 DBU,
  USD 410.21 at list price**. **149.2 units have no list price** (`GENIE_FREE_USAGE`, the free Genie
  tier), so they are counted in the DBUs but not in the USD.
- Steady state per day, at list price, under the assumptions stated in "Steady-state estimate per day":
  - **serving components, excluding ingestion: about USD 59 / day** (85 DBU: Lakebase, app, SQL
    warehouse 8 h, RCA endpoint at zero when idle, predictive optimization, storage);
  - **with the pipeline triggered every 15 min: about USD 84 / day** (+USD 26);
  - upper bound with a continuous pipeline at the measured, 12x-accelerated live rate: about USD
    648 / day (+USD 590); a 1x live feed would cost less, but that was not measured;
  - a warm RCA endpoint adds about USD 4 / day.

## Workspace

```sql
SELECT workspace_id, workspace_name, workspace_url, create_time
FROM system.access.workspaces_latest WHERE workspace_url = 'https://fevm-telco-netmon-febar.cloud.databricks.com'
```

| workspace_id | workspace_name | workspace_url | create_time |
|---|---|---|---|
| 7474648429104135 | telco-netmon-febar | https://fevm-telco-netmon-febar.cloud.databricks.com | 2026-10-08T05:56:51.000Z |

_1 row(s)_


## Billing coverage

Billing rows arrive with a lag; the step-6 experiment queries of this session (2026-11-07 UTC) are not in it yet.

```sql
SELECT min(usage_start_time) AS first_usage, max(usage_end_time) AS last_usage, count(DISTINCT usage_date) AS days_with_usage,
       count(*) AS n_records
FROM system.billing.usage WHERE workspace_id = '7474648429104135'
```

| first_usage | last_usage | days_with_usage | n_records |
|---|---|---|---|
| 2026-10-08T06:00:00.000Z | 2026-11-06T23:50:00.000Z | 30 | 3589 |

_1 row(s)_


## Total since the workspace was created

```sql
SELECT round(sum(CASE WHEN u.usage_unit = 'DBU' THEN u.usage_quantity END), 1) AS dbu,
       round(sum(u.usage_quantity * p.pricing.default), 2) AS usd_list,
       round(sum(CASE WHEN p.sku_name IS NULL THEN u.usage_quantity END), 1) AS unpriced_quantity

  FROM system.billing.usage u
  LEFT JOIN system.billing.list_prices p ON p.sku_name = u.sku_name AND p.cloud = u.cloud AND p.usage_unit = u.usage_unit
   AND u.usage_start_time >= p.price_start_time AND (p.price_end_time IS NULL OR u.usage_start_time < p.price_end_time)
  WHERE u.workspace_id = '7474648429104135'
```

| dbu | usd_list | unpriced_quantity |
|---|---|---|
| 2373.6 | 410.21 | 149.2 |

_1 row(s)_


## By product and SKU

`GENIE_FREE_USAGE` has no list price (free Genie usage tier), so it adds DBUs but no USD.

```sql
SELECT u.billing_origin_product AS product, u.sku_name, u.usage_unit, round(sum(u.usage_quantity), 2) AS quantity,
       round(sum(u.usage_quantity * p.pricing.default), 2) AS usd_list, min(u.usage_date) AS first_day, max(u.usage_date) AS last_day

  FROM system.billing.usage u
  LEFT JOIN system.billing.list_prices p ON p.sku_name = u.sku_name AND p.cloud = u.cloud AND p.usage_unit = u.usage_unit
   AND u.usage_start_time >= p.price_start_time AND (p.price_end_time IS NULL OR u.usage_start_time < p.price_end_time)
  WHERE u.workspace_id = '7474648429104135'
GROUP BY ALL ORDER BY usd_list DESC NULLS LAST
```

| product | sku_name | usage_unit | quantity | usd_list | first_day | last_day |
|---|---|---|---|---|---|---|
| SQL | ENTERPRISE_SERVERLESS_SQL_COMPUTE_US_EAST_N_VIRGINIA | DBU | 222.62 | 155.83 | 2026-10-08 | 2026-11-06 |
| MODEL_SERVING | ENTERPRISE_ANTHROPIC_MODEL_SERVING | DBU | 1425.16 | 99.76 | 2026-11-06 | 2026-11-06 |
| DLT | ENTERPRISE_JOBS_SERVERLESS_COMPUTE_US_EAST_N_VIRGINIA | DBU | 203.26 | 91.47 | 2026-10-08 | 2026-11-06 |
| MODEL_SERVING | ENTERPRISE_OPENAI_MODEL_SERVING | DBU | 265.53 | 18.59 | 2026-11-05 | 2026-11-06 |
| JOBS | ENTERPRISE_JOBS_SERVERLESS_COMPUTE_US_EAST_N_VIRGINIA | DBU | 39.98 | 17.99 | 2026-10-08 | 2026-11-06 |
| LAKEBASE | ENTERPRISE_DATABASE_SERVERLESS_COMPUTE_US_EAST_N_VIRGINIA | DBU | 27.19 | 14.14 | 2026-11-05 | 2026-11-06 |
| APPS | ENTERPRISE_ALL_PURPOSE_SERVERLESS_COMPUTE_US_EAST_N_VIRGINIA | DBU | 6.00 | 5.70 | 2026-11-06 | 2026-11-06 |
| PREDICTIVE_OPTIMIZATION | ENTERPRISE_JOBS_SERVERLESS_COMPUTE_US_EAST_N_VIRGINIA | DBU | 8.61 | 3.87 | 2026-10-08 | 2026-11-06 |
| MODEL_SERVING | ENTERPRISE_SERVERLESS_REAL_TIME_INFERENCE_US_EAST_N_VIRGINIA | DBU | 24.01 | 1.68 | 2026-11-05 | 2026-11-06 |
| LAKEBASE | ENTERPRISE_JOBS_SERVERLESS_COMPUTE_US_EAST_N_VIRGINIA | DBU | 1.81 | 0.82 | 2026-11-05 | 2026-11-06 |
| DEFAULT_STORAGE | PREMIUM_DATABRICKS_STORAGE_US_EAST_N_VIRGINIA | DSU | 12.22 | 0.28 | 2026-10-08 | 2026-11-06 |
| NETWORKING | PUBLIC_CONNECTIVITY_DATA_PROCESSED_US_EAST_N_VIRGINIA | GB | 1.36 | 0.06 | 2026-10-08 | 2026-11-06 |
| AI_GATEWAY | ENTERPRISE_SERVERLESS_REAL_TIME_INFERENCE_US_EAST_N_VIRGINIA | DBU | 0.21 | 0.01 | 2026-11-05 | 2026-11-06 |
| NETWORKING | INTER_REGION_EGRESS_FROM_US_EAST_N_VIRGINIA | GB | 0.10 | 0.00 | 2026-10-08 | 2026-11-06 |
| LAKEBASE | ENTERPRISE_DATABRICKS_STORAGE_US_EAST_N_VIRGINIA | DSU | 0.03 | 0.00 | 2026-11-05 | 2026-11-06 |
| NETWORKING | INTERNET_EGRESS_FROM_US_EAST_N_VIRGINIA | GB | 0.00 | 0.00 | 2026-11-05 | 2026-11-06 |
| MODEL_SERVING | ENTERPRISE_GEMINI_MODEL_SERVING | DBU | 0.02 | 0.00 | 2026-11-05 | 2026-11-05 |
| GENIE | GENIE_FREE_USAGE | DBU | 149.20 | NULL | 2026-11-06 | 2026-11-06 |

_18 row(s)_


## By resource (pipelines, model serving incl. the RCA endpoint, Lakebase, app, SQL warehouse, jobs, foundation models)

Pipeline `80449004-...` is `banksia-netmon-pipeline`; warehouse `d7fa853ab15b20a3` is the project's serverless SQL warehouse; `banksia-rca-ranker` is the RCA serving endpoint; `databricks-*` endpoints are foundation-model pay-per-token (step 4 assistant and its evaluation).

```sql
SELECT u.billing_origin_product AS product,
       coalesce(u.usage_metadata.endpoint_name, u.usage_metadata.job_name, u.usage_metadata.app_name,
                u.usage_metadata.dlt_pipeline_id, u.usage_metadata.warehouse_id, u.usage_metadata.database_instance_id,
                '(workspace)') AS resource,
       u.product_features.serving_type AS serving_type, round(sum(u.usage_quantity), 2) AS quantity, u.usage_unit,
       round(sum(u.usage_quantity * p.pricing.default), 2) AS usd_list

  FROM system.billing.usage u
  LEFT JOIN system.billing.list_prices p ON p.sku_name = u.sku_name AND p.cloud = u.cloud AND p.usage_unit = u.usage_unit
   AND u.usage_start_time >= p.price_start_time AND (p.price_end_time IS NULL OR u.usage_start_time < p.price_end_time)
  WHERE u.workspace_id = '7474648429104135'
GROUP BY ALL HAVING sum(u.usage_quantity) > 0.01 ORDER BY usd_list DESC NULLS LAST
```

| product | resource | serving_type | quantity | usage_unit | usd_list |
|---|---|---|---|---|---|
| SQL | d7fa853ab15b20a3 | NULL | 222.62 | DBU | 155.83 |
| MODEL_SERVING | databricks-claude-sonnet-5-5 | FOUNDATION_MODEL | 1425.16 | DBU | 99.76 |
| DLT | 80449004-f45a-4b32-8215-f68fdf6acfd9 | NULL | 203.26 | DBU | 91.47 |
| MODEL_SERVING | databricks-gpt-5-4-mini | FOUNDATION_MODEL | 265.53 | DBU | 18.59 |
| LAKEBASE | (workspace) | NULL | 27.19 | DBU | 14.14 |
| JOBS | banksia-rca-train | NULL | 17.18 | DBU | 7.73 |
| APPS | banksia-noc-topology | NULL | 6.00 | DBU | 5.70 |
| PREDICTIVE_OPTIMIZATION | (workspace) | NULL | 8.61 | DBU | 3.87 |
| MODEL_SERVING | banksia-rca-ranker | MODEL | 24.01 | DBU | 1.68 |
| JOBS | banksia-genai-build-evalset | NULL | 3.68 | DBU | 1.66 |
| JOBS | banksia-genai-evaluate | NULL | 3.49 | DBU | 1.57 |
| JOBS | banksia-netmon-stream-generator | NULL | 3.37 | DBU | 1.52 |
| JOBS | banksia-genai-assistant | NULL | 2.32 | DBU | 1.04 |
| JOBS | banksia-rca-score-live | NULL | 2.11 | DBU | 0.95 |
| JOBS | banksia-rca-evaluate-holdout | NULL | 1.97 | DBU | 0.89 |
| JOBS | banksia-netmon-governance | NULL | 1.48 | DBU | 0.67 |
| JOBS | banksia-rca-lakebase-check | NULL | 0.83 | DBU | 0.38 |
| JOBS | banksia-rca-any-alert-metric | NULL | 0.72 | DBU | 0.32 |
| LAKEBASE | eb85df61-12fb-4bfe-8baf-0a24254ef161 | NULL | 0.66 | DBU | 0.30 |
| JOBS | banksia-genai-lakebase-check | NULL | 0.66 | DBU | 0.30 |
| JOBS | banksia-netmon-replace-run-feeds | NULL | 0.63 | DBU | 0.29 |
| DEFAULT_STORAGE | (workspace) | NULL | 12.22 | DSU | 0.28 |
| JOBS | banksia-rca-generate-training-history | NULL | 0.62 | DBU | 0.28 |
| LAKEBASE | de1a6b07-9c92-4c50-bc8d-dd195d68e6f5 | NULL | 0.61 | DBU | 0.28 |
| JOBS | banksia-rca-generate-holdout | NULL | 0.59 | DBU | 0.27 |
| LAKEBASE | 07a8ea76-5fa9-4a5d-90bf-b0a339c0f58a | NULL | 0.54 | DBU | 0.24 |
| JOBS | banksia-netmon-generate-history | NULL | 0.30 | DBU | 0.13 |
| NETWORKING | (workspace) | NULL | 1.46 | GB | 0.06 |
| JOBS | banksia-app-lakebase-grants | NULL | 0.02 | DBU | 0.01 |
| AI_GATEWAY | databricks-gpt-5-4-mini | NULL | 0.09 | DBU | 0.01 |
| AI_GATEWAY | databricks-claude-sonnet-5-5 | NULL | 0.12 | DBU | 0.01 |
| LAKEBASE | (workspace) | NULL | 0.03 | DSU | 0.00 |
| MODEL_SERVING | databricks-gemini-3-8-flash | FOUNDATION_MODEL | 0.02 | DBU | 0.00 |
| GENIE | (workspace) | NULL | 149.20 | DBU | NULL |

_34 row(s)_


## By day

Usage is concentrated on the build / run days; the days between carry storage only.

```sql
SELECT u.usage_date, round(sum(CASE WHEN u.usage_unit = 'DBU' THEN u.usage_quantity END), 1) AS dbu,
       round(sum(u.usage_quantity * p.pricing.default), 2) AS usd_list

  FROM system.billing.usage u
  LEFT JOIN system.billing.list_prices p ON p.sku_name = u.sku_name AND p.cloud = u.cloud AND p.usage_unit = u.usage_unit
   AND u.usage_start_time >= p.price_start_time AND (p.price_end_time IS NULL OR u.usage_start_time < p.price_end_time)
  WHERE u.workspace_id = '7474648429104135'
GROUP BY 1 ORDER BY 1
```

| usage_date | dbu | usd_list |
|---|---|---|
| 2026-10-08 | 276.8 | 142.61 |
| 2026-10-09 | 1.5 | 0.67 |
| 2026-10-10 | NULL | 0.00 |
| 2026-10-11 | NULL | 0.00 |
| 2026-10-12 | NULL | 0.00 |
| 2026-10-13 | NULL | 0.00 |
| 2026-10-14 | NULL | 0.00 |
| 2026-10-15 | 0.5 | 0.21 |
| 2026-10-16 | 0.6 | 0.27 |
| 2026-10-17 | NULL | 0.00 |
| 2026-10-18 | NULL | 0.00 |
| 2026-10-19 | NULL | 0.00 |
| 2026-10-20 | NULL | 0.00 |
| 2026-10-21 | NULL | 0.00 |
| 2026-10-22 | NULL | 0.00 |
| 2026-10-23 | NULL | 0.00 |
| 2026-10-24 | NULL | 0.00 |
| 2026-10-25 | NULL | 0.00 |
| 2026-10-26 | NULL | 0.00 |
| 2026-10-27 | NULL | 0.00 |
| 2026-10-28 | NULL | 0.00 |
| 2026-10-29 | NULL | 0.00 |
| 2026-10-30 | NULL | 0.00 |
| 2026-10-31 | NULL | 0.00 |
| 2026-11-01 | NULL | 0.00 |
| 2026-11-02 | NULL | 0.00 |
| 2026-11-03 | NULL | 0.00 |
| 2026-11-04 | NULL | 0.00 |
| 2026-11-05 | 97.0 | 52.79 |
| 2026-11-06 | 1997.3 | 213.63 |

_30 row(s)_


## Measured rates used for the steady-state estimate

```sql
WITH u AS (SELECT * FROM system.billing.usage WHERE workspace_id = '7474648429104135'),
lb AS (SELECT (unix_timestamp(max(usage_end_time)) - unix_timestamp(min(usage_start_time))) / 3600 AS h FROM u
       WHERE billing_origin_product = 'LAKEBASE'),
live AS (SELECT (unix_millis(max(timestamp)) - unix_millis(min(timestamp))) / 3600000 AS h FROM telco_netmon_febar_catalog.netmon_eval.netmon_pipeline_event_log
         WHERE origin.update_id = 'c6b8b8f3-d608-4c8e-ad14-e41778fbbdad')
SELECT 'lakebase_database_dbu_per_h' AS rate,
       sum(CASE WHEN billing_origin_product = 'LAKEBASE' AND sku_name LIKE '%DATABASE%' THEN usage_quantity END) / (SELECT h FROM lb)
         AS value, 'Lakebase instance compute over its whole billed span (always on)' AS basis FROM u
UNION ALL SELECT 'lakebase_synced_tables_dbu_per_h',
       sum(CASE WHEN billing_origin_product = 'LAKEBASE' AND sku_name LIKE '%JOBS%' THEN usage_quantity END) / (SELECT h FROM lb),
       'synced-table pipelines (Lakebase sync), same span' FROM u
UNION ALL SELECT 'app_dbu_per_h', sum(usage_quantity) / count(DISTINCT date_trunc('hour', usage_start_time)),
       'app compute per billed hour' FROM u WHERE billing_origin_product = 'APPS'
UNION ALL SELECT 'rca_endpoint_dbu_per_active_h', sum(usage_quantity) / count(DISTINCT date_trunc('hour', usage_start_time)),
       'banksia-rca-ranker per billed hour (scale-to-zero when idle)' FROM u WHERE usage_metadata.endpoint_name = 'banksia-rca-ranker'
UNION ALL SELECT 'sql_warehouse_dbu_per_active_h', sum(usage_quantity) / count(DISTINCT date_trunc('hour', usage_start_time)),
       'serverless SQL warehouse per billed hour' FROM u WHERE billing_origin_product = 'SQL'
UNION ALL SELECT 'pipeline_continuous_dbu_per_h', sum(usage_quantity) / (SELECT h FROM live),
       'the continuous live update of the step-2 stream (12x accelerated feed, 34 min)' FROM u
       WHERE usage_metadata.dlt_update_id = 'c6b8b8f3-d608-4c8e-ad14-e41778fbbdad'
UNION ALL SELECT 'pipeline_triggered_update_dbu', percentile(dbu, 0.5),
       'median incremental triggered update (not full refresh, not continuous), 2026-11-05 .. 06' FROM (
         SELECT usage_metadata.dlt_update_id, sum(usage_quantity) AS dbu FROM u
         WHERE billing_origin_product = 'DLT' AND usage_date >= '2026-11-05' AND usage_metadata.dlt_update_id IS NOT NULL
         GROUP BY 1)
UNION ALL SELECT 'predictive_optimization_dbu_per_day', sum(usage_quantity) / 30, 'whole period / 30 days' FROM u
       WHERE billing_origin_product = 'PREDICTIVE_OPTIMIZATION'
UNION ALL SELECT 'storage_dsu_per_day', sum(usage_quantity), 'latest full day (2026-11-06)' FROM u
       WHERE billing_origin_product = 'DEFAULT_STORAGE' AND usage_date = '2026-11-06'
```

| rate | value | basis |
|---|---|---|
| lakebase_database_dbu_per_h | 0.780535442583732 | Lakebase instance compute over its whole billed span (always on) |
| lakebase_synced_tables_dbu_per_h | 0.051999710685805424 | synced-table pipelines (Lakebase sync), same span |
| app_dbu_per_h | 0.5 | app compute per billed hour |
| rca_endpoint_dbu_per_active_h | 2.4006666666666665 | banksia-rca-ranker per billed hour (scale-to-zero when idle) |
| sql_warehouse_dbu_per_active_h | 6.547645196078431 | serverless SQL warehouse per billed hour |
| pipeline_continuous_dbu_per_h | 54.610945249934986 | the continuous live update of the step-2 stream (12x accelerated feed, 34 min) |
| pipeline_triggered_update_dbu | 0.5921620694444444 | median incremental triggered update (not full refresh, not continuous), 2026-11-05 .. 06 |
| predictive_optimization_dbu_per_day | 0.2868639742708333 | whole period / 30 days |
| storage_dsu_per_day | 3.1003458 | latest full day (2026-11-06) |

_9 row(s)_


## Steady-state estimate per day

What it costs to keep the deployed platform running for one day with no build, backfill, retraining or evaluation:
measured rate (table above) x the stated assumption, priced at today's list price per SKU.

Assumptions: the Lakebase instance and the app run 24 h (both billed continuously while up); the serverless SQL
warehouse is active 8 h/day for NOC use and auto-stops otherwise; the RCA endpoint scales to zero when not
called (warm 24 h shown as an add-on); the pipeline is either triggered every 15 min or continuous (add-ons, measured on
this workspace: the continuous figure comes from the 12x-accelerated live demo, so it over-states a 1x live feed).
Not estimated: foundation-model pay-per-token for the live assistant (all 1690.7 DBU of it on record falls between
2026-11-05T23:00:00.000Z and 2026-11-06T09:00:00.000Z, the step-4 evaluation runs, and pay-per-token rows carry no job id, so the live assistant's own
share is not separable) and Genie (free usage tier, no list price).

| component | assumption | DBU (DSU for storage) / day | USD / unit (list) | USD / day (list) |
|---|---|---|---|---|
| Lakebase instance (CU_1, always on) | 24 h | 18.73 | 0.52 | 9.74 |
| Lakebase synced tables | 24 h at the measured rate | 1.25 | 0.45 | 0.56 |
| Databricks App (banksia-noc-topology) | running 24 h | 12.0 | 0.95 | 11.4 |
| SQL warehouse (serverless) | 8 active h/day | 52.38 | 0.7 | 36.67 |
| RCA serving endpoint (Small, scale-to-zero) | idle: scales to zero | 0.0 | 0.07 | 0.0 |
| Predictive optimization | measured daily average | 0.29 | 0.45 | 0.13 |
| Storage (DSU) | latest full day | 3.1 | 0.023 | 0.07 |
| **serving platform, steady state (sum)** |  | 84.6 |  | 58.57 |
| + RCA endpoint warm 24 h |  | 57.6 | 0.07 | 4.03 |
| + pipeline triggered every 15 min (96 incremental updates) |  | 56.8 | 0.45 | 25.58 |
| + pipeline continuous 24 h at the measured live rate (12x accelerated feed: an upper bound) |  | 1310.7 | 0.45 | 589.8 |

_11 row(s)_


## Summary (repeated)

- Since the workspace was created (2026-10-08T05:56:51.000Z) to the last billed record (2026-11-06T23:50:00.000Z): **2373.6 DBU,
  USD 410.21 at list price**. **149.2 units have no list price** (`GENIE_FREE_USAGE`, the free Genie
  tier), so they are counted in the DBUs but not in the USD.
- Steady state per day, at list price, under the assumptions stated in "Steady-state estimate per day":
  - **serving components, excluding ingestion: about USD 59 / day** (85 DBU: Lakebase, app, SQL
    warehouse 8 h, RCA endpoint at zero when idle, predictive optimization, storage);
  - **with the pipeline triggered every 15 min: about USD 84 / day** (+USD 26);
  - upper bound with a continuous pipeline at the measured, 12x-accelerated live rate: about USD
    648 / day (+USD 590); a 1x live feed would cost less, but that was not measured;
  - a warm RCA endpoint adds about USD 4 / day.
