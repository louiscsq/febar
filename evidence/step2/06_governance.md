# Unity Catalog governance: masks, row filters, grants, tags

Captured 2026-10-08 13:31 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

Policies are declared on the pipeline tables and backed by the functions in `governance/sql/01_functions.sql`; grants and tags by `02_grants.sql` / `03_comments_tags.sql`.

## Column masks

```sql
SELECT table_schema, table_name, column_name, mask_name FROM telco_netmon_febar_catalog.information_schema.column_masks
        ORDER BY ALL
```

| table_schema | table_name | column_name | mask_name |
|---|---|---|---|
| netmon_silver | silver_sessions | imsi | telco_netmon_febar_catalog.netmon_gov.mask_imsi |
| netmon_silver | silver_sessions | msisdn | telco_netmon_febar_catalog.netmon_gov.mask_msisdn |

_2 row(s)_

## Row filters

```sql
SELECT table_schema, table_name, filter_name, target_columns FROM telco_netmon_febar_catalog.information_schema.row_filters
        ORDER BY ALL
```

| table_schema | table_name | filter_name | target_columns |
|---|---|---|---|
| netmon_gold | gold_impact_detections | telco_netmon_febar_catalog.netmon_gov.region_filter | region_code |
| netmon_silver | silver_sessions | telco_netmon_febar_catalog.netmon_gov.region_filter | region_code |

_2 row(s)_

## Policy function definitions

```sql
SELECT routine_name, routine_definition FROM telco_netmon_febar_catalog.information_schema.routines
        WHERE routine_schema = 'netmon_gov' ORDER BY 1
```

| routine_name | routine_definition |
|---|---|
| is_pii_privileged | is_account_group_member('pii_privileged') OR is_member('pii_privileged') |
| mask_imsi | CASE   WHEN imsi IS NULL THEN NULL   WHEN `telco_netmon_febar_catalog`.`netmon_gov`.is_pii_privileged() THEN imsi   ELS… |
| mask_msisdn | CASE   WHEN msisdn IS NULL THEN NULL   WHEN `telco_netmon_febar_catalog`.`netmon_gov`.is_pii_privileged() THEN msisdn  … |
| region_filter | is_account_group_member('noc_national') OR is_member('noc_national')   OR is_account_group_member(concat('noc_region_',… |

_4 row(s)_

## Grants (catalog, gold schema, silver_sessions)

Grantees are the persona service principals' application ids (UC rejects the workspace-local groups; see docs/pipeline.md). Mapping: see the persona table below.

```sql
SELECT grantee, privilege_type, 'CATALOG' AS object, catalog_name AS name
        FROM telco_netmon_febar_catalog.information_schema.catalog_privileges WHERE grantee NOT LIKE '%@%'
        UNION ALL
        SELECT grantee, privilege_type, 'SCHEMA', schema_name FROM telco_netmon_febar_catalog.information_schema.schema_privileges
        WHERE schema_name LIKE 'netmon%' AND grantee NOT LIKE '%@%'
        UNION ALL
        SELECT grantee, privilege_type, 'TABLE', table_name FROM telco_netmon_febar_catalog.information_schema.table_privileges
        WHERE table_schema = 'netmon_silver' AND grantee NOT LIKE '%@%'
        ORDER BY 3, 4, 1, 2
```

| grantee | privilege_type | object | name |
|---|---|---|---|
| 227a0d30-fe32-47f9-867f-9c91c13db70a | USE_CATALOG | CATALOG | telco_netmon_febar_catalog |
| 2ee944da-a522-49e2-8600-6c72e454ce2c | USE_CATALOG | CATALOG | telco_netmon_febar_catalog |
| 8855855c-202f-4260-bf4f-85f2ac215524 | USE_CATALOG | CATALOG | telco_netmon_febar_catalog |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | CATALOG | telco_netmon_febar_catalog |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | CATALOG | telco_netmon_febar_catalog |
| bb41b303-d6b4-4dd0-b524-b25e2f3a3433 | USE_CATALOG | CATALOG | telco_netmon_febar_catalog |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | SCHEMA | netmon_bronze |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | SCHEMA | netmon_bronze |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | SCHEMA | netmon_eval |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | SCHEMA | netmon_eval |
| 227a0d30-fe32-47f9-867f-9c91c13db70a | SELECT | SCHEMA | netmon_gold |
| 227a0d30-fe32-47f9-867f-9c91c13db70a | USE_SCHEMA | SCHEMA | netmon_gold |
| 2ee944da-a522-49e2-8600-6c72e454ce2c | SELECT | SCHEMA | netmon_gold |
| 2ee944da-a522-49e2-8600-6c72e454ce2c | USE_SCHEMA | SCHEMA | netmon_gold |
| 8855855c-202f-4260-bf4f-85f2ac215524 | SELECT | SCHEMA | netmon_gold |
| 8855855c-202f-4260-bf4f-85f2ac215524 | USE_SCHEMA | SCHEMA | netmon_gold |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | SCHEMA | netmon_gold |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | SCHEMA | netmon_gold |
| bb41b303-d6b4-4dd0-b524-b25e2f3a3433 | SELECT | SCHEMA | netmon_gold |
| bb41b303-d6b4-4dd0-b524-b25e2f3a3433 | USE_SCHEMA | SCHEMA | netmon_gold |
| 227a0d30-fe32-47f9-867f-9c91c13db70a | USE_SCHEMA | SCHEMA | netmon_gov |
| 2ee944da-a522-49e2-8600-6c72e454ce2c | USE_SCHEMA | SCHEMA | netmon_gov |
| 8855855c-202f-4260-bf4f-85f2ac215524 | USE_SCHEMA | SCHEMA | netmon_gov |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | SCHEMA | netmon_gov |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | SCHEMA | netmon_gov |
| bb41b303-d6b4-4dd0-b524-b25e2f3a3433 | USE_SCHEMA | SCHEMA | netmon_gov |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | SCHEMA | netmon_raw |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | SCHEMA | netmon_raw |
| 227a0d30-fe32-47f9-867f-9c91c13db70a | USE_SCHEMA | SCHEMA | netmon_silver |
| 2ee944da-a522-49e2-8600-6c72e454ce2c | USE_SCHEMA | SCHEMA | netmon_silver |
| 8855855c-202f-4260-bf4f-85f2ac215524 | USE_SCHEMA | SCHEMA | netmon_silver |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | SCHEMA | netmon_silver |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | SCHEMA | netmon_silver |
| bb41b303-d6b4-4dd0-b524-b25e2f3a3433 | USE_SCHEMA | SCHEMA | netmon_silver |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | TABLE | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_alarms_1 |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | TABLE | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_alarms_1 |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | TABLE | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_kpis_1 |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | TABLE | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_kpis_1 |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | TABLE | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_maintenance_windows_1 |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | TABLE | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_maintenance_windows_1 |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | TABLE | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_quarantine_1 |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | TABLE | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_quarantine_1 |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | TABLE | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_sessions_1 |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | TABLE | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_sessions_1 |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | TABLE | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_topology_edges_1 |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | TABLE | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_topology_edges_1 |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | TABLE | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_topology_nodes_1 |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | TABLE | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_topology_nodes_1 |
| 227a0d30-fe32-47f9-867f-9c91c13db70a | SELECT | TABLE | silver_alarms |
| 2ee944da-a522-49e2-8600-6c72e454ce2c | SELECT | TABLE | silver_alarms |
| 8855855c-202f-4260-bf4f-85f2ac215524 | SELECT | TABLE | silver_alarms |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | TABLE | silver_alarms |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | TABLE | silver_alarms |
| bb41b303-d6b4-4dd0-b524-b25e2f3a3433 | SELECT | TABLE | silver_alarms |
| 227a0d30-fe32-47f9-867f-9c91c13db70a | SELECT | TABLE | silver_kpis |
| 2ee944da-a522-49e2-8600-6c72e454ce2c | SELECT | TABLE | silver_kpis |
| 8855855c-202f-4260-bf4f-85f2ac215524 | SELECT | TABLE | silver_kpis |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | TABLE | silver_kpis |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | TABLE | silver_kpis |
| bb41b303-d6b4-4dd0-b524-b25e2f3a3433 | SELECT | TABLE | silver_kpis |
| 227a0d30-fe32-47f9-867f-9c91c13db70a | SELECT | TABLE | silver_maintenance_windows |
| 2ee944da-a522-49e2-8600-6c72e454ce2c | SELECT | TABLE | silver_maintenance_windows |
| 8855855c-202f-4260-bf4f-85f2ac215524 | SELECT | TABLE | silver_maintenance_windows |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | TABLE | silver_maintenance_windows |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | TABLE | silver_maintenance_windows |
| bb41b303-d6b4-4dd0-b524-b25e2f3a3433 | SELECT | TABLE | silver_maintenance_windows |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | TABLE | silver_quarantine |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | TABLE | silver_quarantine |
| 227a0d30-fe32-47f9-867f-9c91c13db70a | SELECT | TABLE | silver_sessions |
| 2ee944da-a522-49e2-8600-6c72e454ce2c | SELECT | TABLE | silver_sessions |
| 8855855c-202f-4260-bf4f-85f2ac215524 | SELECT | TABLE | silver_sessions |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | TABLE | silver_sessions |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | TABLE | silver_sessions |
| bb41b303-d6b4-4dd0-b524-b25e2f3a3433 | SELECT | TABLE | silver_sessions |
| 227a0d30-fe32-47f9-867f-9c91c13db70a | SELECT | TABLE | silver_topology_edges |
| 2ee944da-a522-49e2-8600-6c72e454ce2c | SELECT | TABLE | silver_topology_edges |
| 8855855c-202f-4260-bf4f-85f2ac215524 | SELECT | TABLE | silver_topology_edges |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | TABLE | silver_topology_edges |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | TABLE | silver_topology_edges |
| bb41b303-d6b4-4dd0-b524-b25e2f3a3433 | SELECT | TABLE | silver_topology_edges |
| 227a0d30-fe32-47f9-867f-9c91c13db70a | SELECT | TABLE | silver_topology_nodes |
| 2ee944da-a522-49e2-8600-6c72e454ce2c | SELECT | TABLE | silver_topology_nodes |
| 8855855c-202f-4260-bf4f-85f2ac215524 | SELECT | TABLE | silver_topology_nodes |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | ALL_PRIVILEGES | TABLE | silver_topology_nodes |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | MANAGE | TABLE | silver_topology_nodes |
| bb41b303-d6b4-4dd0-b524-b25e2f3a3433 | SELECT | TABLE | silver_topology_nodes |

_86 row(s)_

## Tags: schemas and tables

```sql
SELECT 'schema' AS level, schema_name AS object, tag_name, tag_value FROM telco_netmon_febar_catalog.information_schema.schema_tags
        UNION ALL
        SELECT 'table', concat(schema_name, '.', table_name), tag_name, tag_value
        FROM telco_netmon_febar_catalog.information_schema.table_tags WHERE schema_name LIKE 'netmon%'
        ORDER BY 1, 2, 3
```

| level | object | tag_name | tag_value |
|---|---|---|---|
| schema | netmon_bronze | contains_pii | true |
| schema | netmon_bronze | domain | operations |
| schema | netmon_bronze | layer | bronze |
| schema | netmon_eval | domain | operations |
| schema | netmon_eval | ground_truth | true |
| schema | netmon_eval | netmon_layer | evaluation |
| schema | netmon_gold | contains_pii | false |
| schema | netmon_gold | domain | operations |
| schema | netmon_gold | layer | gold |
| schema | netmon_raw | domain | operations |
| schema | netmon_raw | netmon_layer | landing |
| schema | netmon_silver | contains_pii | true |
| schema | netmon_silver | domain | operations |
| schema | netmon_silver | layer | silver |
| table | netmon_bronze.bronze_sessions | access | engineering_only |
| table | netmon_bronze.bronze_sessions | classification | restricted |
| table | netmon_bronze.bronze_sessions | contains_pii | true |
| table | netmon_bronze.bronze_sessions | domain | operations |
| table | netmon_bronze.bronze_sessions | netmon_domain | customer_experience |
| table | netmon_eval.eval_gt_incidents | ground_truth | true |
| table | netmon_eval.eval_gt_incidents | use | evaluation_only |
| table | netmon_eval.eval_incident_detection | ground_truth | true |
| table | netmon_eval.eval_incident_detection | use | evaluation_only |
| table | netmon_gold.gold_cell_baseline | domain | operations |
| table | netmon_gold.gold_cell_baseline | grain | cell_hour_daytype |
| table | netmon_gold.gold_cell_baseline | netmon_domain | network_performance |
| table | netmon_gold.gold_cell_health_1m | domain | operations |
| table | netmon_gold.gold_cell_health_1m | grain | cell_1m |
| table | netmon_gold.gold_cell_health_1m | netmon_domain | network_performance |
| table | netmon_gold.gold_cell_health_5m | domain | operations |
| table | netmon_gold.gold_cell_health_5m | grain | cell_5m |
| table | netmon_gold.gold_cell_health_5m | netmon_domain | network_performance |
| table | netmon_gold.gold_cell_sessions_5m | contains_pii | false |
| table | netmon_gold.gold_cell_sessions_5m | domain | operations |
| table | netmon_gold.gold_cell_sessions_5m | grain | cell_5m |
| table | netmon_gold.gold_cell_sessions_5m | netmon_domain | customer_experience |
| table | netmon_gold.gold_element_impact_5m | consumer | ml_rca_model |
| table | netmon_gold.gold_element_impact_5m | domain | operations |
| table | netmon_gold.gold_element_impact_5m | grain | element_5m |
| table | netmon_gold.gold_element_impact_5m | netmon_domain | root_cause_analysis |
| table | netmon_gold.gold_impact_detections | consumer | noc,lakebase,app |
| table | netmon_gold.gold_impact_detections | domain | operations |
| table | netmon_gold.gold_impact_detections | netmon_domain | service_assurance |
| table | netmon_gold.gold_impact_detections | row_filter | by_region |
| table | netmon_gold.gold_impact_detections | sla | 5min |
| table | netmon_silver.silver_alarms | contains_pii | false |
| table | netmon_silver.silver_alarms | domain | operations |
| table | netmon_silver.silver_alarms | netmon_domain | fault_management |
| table | netmon_silver.silver_kpis | contains_pii | false |
| table | netmon_silver.silver_kpis | domain | operations |
| table | netmon_silver.silver_kpis | netmon_domain | network_performance |
| table | netmon_silver.silver_quarantine | access | engineering_only |
| table | netmon_silver.silver_quarantine | classification | restricted |
| table | netmon_silver.silver_quarantine | domain | quality |
| table | netmon_silver.silver_sessions | classification | confidential |
| table | netmon_silver.silver_sessions | contains_pii | true |
| table | netmon_silver.silver_sessions | domain | operations |
| table | netmon_silver.silver_sessions | masked | imsi,msisdn |
| table | netmon_silver.silver_sessions | netmon_domain | customer_experience |
| table | netmon_silver.silver_sessions | row_filter | by_region |
| table | netmon_silver.silver_topology_nodes | domain | operations |
| table | netmon_silver.silver_topology_nodes | netmon_domain | network_inventory |

_62 row(s)_

## Tags: PII columns

```sql
SELECT schema_name, table_name, column_name, tag_name, tag_value FROM telco_netmon_febar_catalog.information_schema.column_tags
        WHERE schema_name LIKE 'netmon%' ORDER BY ALL
```

| schema_name | table_name | column_name | tag_name | tag_value |
|---|---|---|---|---|
| netmon_bronze | bronze_sessions | imsi | classification | restricted |
| netmon_bronze | bronze_sessions | imsi | netmon_pii | imsi |
| netmon_bronze | bronze_sessions | msisdn | class.phone_number |  |
| netmon_bronze | bronze_sessions | msisdn | classification | restricted |
| netmon_bronze | bronze_sessions | msisdn | netmon_pii | msisdn |
| netmon_silver | silver_sessions | imsi | classification | confidential |
| netmon_silver | silver_sessions | imsi | masked | mask_imsi |
| netmon_silver | silver_sessions | imsi | netmon_pii | imsi |
| netmon_silver | silver_sessions | msisdn | class.phone_number |  |
| netmon_silver | silver_sessions | msisdn | classification | confidential |
| netmon_silver | silver_sessions | msisdn | masked | mask_msisdn |
| netmon_silver | silver_sessions | msisdn | netmon_pii | msisdn |
| netmon_silver | silver_sessions | subscriber_key | netmon_pii | pseudonymous |

_13 row(s)_

## Table and column comments (key tables)

```sql
SELECT table_schema, table_name, left(comment, 150) AS comment FROM telco_netmon_febar_catalog.information_schema.tables
        WHERE table_schema IN ('netmon_silver', 'netmon_gold', 'netmon_eval') ORDER BY 1, 2
```

| table_schema | table_name | comment |
|---|---|---|
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_bronze_gt_dq_injections_1 | GROUND TRUTH audit log of every injected data-quality defect. Evaluation only. |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_bronze_gt_incidents_1 | GROUND TRUTH incident labels as written by the generator. Evaluation only: never a feature source. |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_eval_detection_log_1 | Unfiltered copy of the impact detections for offline scoring (gold_impact_detections is row-filtered for NOC users). Sa… |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_eval_detection_precision_1 | Share of detections explained by any ground-truth event (incl. red herrings, planned work and censored incidents), per … |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_eval_dq_capture_1 | Data-quality defects injected by the generator (ground truth) vs how the pipeline handled them: quarantined (malformed/… |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_eval_gt_incidents_1 | GROUND TRUTH incidents, typed (UTC), one row per (source_run, incident_id). Labels only. |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_eval_incident_detection_1 | Per scored incident (customer-impacting, not censored): first matching detection, time-to-detect (ttd_s, from impact_st… |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_eval_rca_baseline_1 | Topology-heuristic RCA baseline for the later ML model: in the incident's region and first 15 minutes of impact, rank g… |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_eval_ttd_summary_1 | Time-to-detect summary per source run (history = 15-min ROP backfill, stream = 1-min live feed), overall, per event cla… |
| netmon_eval | bronze_gt_dq_injections | GROUND TRUTH audit log of every injected data-quality defect. Evaluation only. |
| netmon_eval | bronze_gt_incidents | GROUND TRUTH incident labels as written by the generator. Evaluation only: never a feature source. |
| netmon_eval | eval_detection_log | Unfiltered copy of the impact detections for offline scoring (gold_impact_detections is row-filtered for NOC users). Sa… |
| netmon_eval | eval_detection_precision | Share of detections explained by any ground-truth event (incl. red herrings, planned work and censored incidents), per … |
| netmon_eval | eval_dq_capture | Data-quality defects injected by the generator (ground truth) vs how the pipeline handled them: quarantined (malformed/… |
| netmon_eval | eval_gt_incidents | GROUND TRUTH incidents, typed (UTC), one row per (source_run, incident_id). Labels only. |
| netmon_eval | eval_incident_detection | Per scored incident (customer-impacting, not censored): first matching detection, time-to-detect (ttd_s, from impact_st… |
| netmon_eval | eval_rca_baseline | Topology-heuristic RCA baseline for the later ML model: in the incident's region and first 15 minutes of impact, rank g… |
| netmon_eval | eval_ttd_summary | Time-to-detect summary per source run (history = 15-min ROP backfill, stream = 1-min live feed), overall, per event cla… |
| netmon_eval | netmon_pipeline_event_log | NULL |
| netmon_gold | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_baseline_1 | Per cell x local hour x day type (weekday/weekend) KPI mean and std over the 14 days strictly before valid_date. Join o… |
| netmon_gold | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_health_1m_1 | Per-cell 1-minute KPI windows (event time, UTC) with baseline means, z-scores, fired rules and is_degraded. Append-only… |
| netmon_gold | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_health_5m_1 | Per-cell 5-minute KPI windows with baseline deviation. Feeds the topology rollup and ML features. |
| netmon_gold | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_sessions_5m_1 | Per-cell 5-minute session outcomes by session end time: setup failures, drops, no-service and approximate distinct subs… |
| netmon_gold | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_element_impact_5m_1 | Topology rollup per element per 5-min window: impacted (degraded or silent) descendant cells, impacted children, parent… |
| netmon_gold | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_impact_detections_1 | Customer-impact detections per cell (KPI rules vs baseline) or element (element-down alarms), with detected_ts (wall cl… |
| netmon_gold | gold_cell_baseline | Per cell x local hour x day type (weekday/weekend) KPI mean and std over the 14 days strictly before valid_date. Join o… |
| netmon_gold | gold_cell_health_1m | Per-cell 1-minute KPI windows (event time, UTC) with baseline means, z-scores, fired rules and is_degraded. Append-only… |
| netmon_gold | gold_cell_health_5m | Per-cell 5-minute KPI windows with baseline deviation. Feeds the topology rollup and ML features. |
| netmon_gold | gold_cell_sessions_5m | Per-cell 5-minute session outcomes by session end time: setup failures, drops, no-service and approximate distinct subs… |
| netmon_gold | gold_element_impact_5m | Topology rollup per element per 5-min window: impacted (degraded or silent) descendant cells, impacted children, parent… |
| netmon_gold | gold_impact_detections | Customer-impact detections per cell (KPI rules vs baseline) or element (element-down alarms), with detected_ts (wall cl… |
| netmon_silver | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_alarms_1 | Validated alarm RAISE/CLEAR events with the element's region and ancestors. is_service_down marks element-down alarms t… |
| netmon_silver | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_kpis_1 | Validated per-cell KPI records: typed, UTC timestamps plus local time from the cell's IANA zone, deduplicated on record… |
| netmon_silver | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_maintenance_windows_1 | Approved change windows (UTC). Operational data the NOC uses to suppress planned work. |
| netmon_silver | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_quarantine_1 | Rows rejected by silver expectations (malformed, null, out-of-range, unknown element) and unparseable JSON lines, with … |
| netmon_silver | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_sessions_1 | Validated sampled xDR sessions. IMSI/MSISDN are column-masked and rows are filtered by the reader's regional NOC group.… |
| netmon_silver | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_topology_edges_1 | Directed topology edges, upstream -> downstream. |
| netmon_silver | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_topology_nodes_1 | Network inventory (one row per element, latest snapshot). Ancestor columns (amf_id .. site_id) include the element itse… |
| netmon_silver | silver_alarms | Validated alarm RAISE/CLEAR events with the element's region and ancestors. is_service_down marks element-down alarms t… |
| netmon_silver | silver_kpis | Validated per-cell KPI records: typed, UTC timestamps plus local time from the cell's IANA zone, deduplicated on record… |
| netmon_silver | silver_maintenance_windows | Approved change windows (UTC). Operational data the NOC uses to suppress planned work. |
| netmon_silver | silver_quarantine | Rows rejected by silver expectations (malformed, null, out-of-range, unknown element) and unparseable JSON lines, with … |
| netmon_silver | silver_sessions | Validated sampled xDR sessions. IMSI/MSISDN are column-masked and rows are filtered by the reader's regional NOC group.… |
| netmon_silver | silver_topology_edges | Directed topology edges, upstream -> downstream. |
| netmon_silver | silver_topology_nodes | Network inventory (one row per element, latest snapshot). Ancestor columns (amf_id .. site_id) include the element itse… |

_45 row(s)_

## Column comments on silver_sessions

```sql
SELECT column_name, data_type, comment FROM telco_netmon_febar_catalog.information_schema.columns
        WHERE table_schema = 'netmon_silver' AND table_name = 'silver_sessions' AND comment IS NOT NULL
        ORDER BY ordinal_position
```

| column_name | data_type | comment |
|---|---|---|
| record_id | STRING | xDR session id (dedupe key) |
| imsi | STRING | PII: subscriber IMSI (masked unless pii_privileged) |
| msisdn | STRING | PII: subscriber MSISDN (masked unless pii_privileged) |
| subscriber_key | STRING | Pseudonymous SHA-256 subscriber key for distinct counts |
| region_code | STRING | Region of the serving cell (row-filter key) |
| start_ts | TIMESTAMP | UTC |
| end_ts | TIMESTAMP | UTC |
| emitted_ts | TIMESTAMP | UTC |
| start_ts_local | TIMESTAMP | Session start in the cell local time zone |

_9 row(s)_

## Workspace-local groups and members

| group | members |
|---|---|
| `noc_national` | netmon-pii-officer, netmon-noc-national, Louis Chen |
| `noc_region_act` | — |
| `noc_region_nql` | — |
| `noc_region_nsw` | netmon-noc-nsw-analyst |
| `noc_region_nt` | — |
| `noc_region_pil` | — |
| `noc_region_qld` | — |
| `noc_region_sa` | — |
| `noc_region_tas` | — |
| `noc_region_vic` | — |
| `noc_region_wa` | netmon-noc-wa-analyst |
| `pii_privileged` | netmon-pii-officer |

## Persona service principals (grantees)

| application id | display name |
|---|---|
| `227a0d30-fe32-47f9-867f-9c91c13db70a` | netmon-noc-national |
| `bb41b303-d6b4-4dd0-b524-b25e2f3a3433` | netmon-noc-nsw-analyst |
| `2ee944da-a522-49e2-8600-6c72e454ce2c` | netmon-noc-wa-analyst |
| `8855855c-202f-4260-bf4f-85f2ac215524` | netmon-pii-officer |

## Current principal (capturing user)

```sql
SELECT current_user() AS user, is_member('noc_national') AS in_noc_national,
               is_member('noc_region_nsw') AS in_noc_region_nsw, is_member('pii_privileged') AS in_pii_privileged,
               telco_netmon_febar_catalog.netmon_gov.is_pii_privileged() AS pii_privileged_fn
```

| user | in_noc_national | in_noc_region_nsw | in_pii_privileged | pii_privileged_fn |
|---|---|---|---|---|
| louis.chen@databricks.com | true | false | false | false |

_1 row(s)_

## Masked output for a non-privileged reader (capturing user is not in pii_privileged)

```sql
SELECT record_id, imsi, msisdn, region_code, outcome FROM telco_netmon_febar_catalog.netmon_silver.silver_sessions
        ORDER BY record_id LIMIT 5
```

| record_id | imsi | msisdn | region_code | outcome |
|---|---|---|---|---|
| S-20260924T0000-0000000 | 00101********76 | +999******374 | NSW | COMPLETED |
| S-20260924T0000-0000001 | 00101********87 | +999******875 | NSW | COMPLETED |
| S-20260924T0000-0000002 | 00101********15 | +999******623 | NSW | COMPLETED |
| S-20260924T0000-0000003 | 00101********42 | +999******580 | NSW | COMPLETED |
| S-20260924T0000-0000004 | 00101********05 | +999******813 | NSW | COMPLETED |

_5 row(s)_

## Mask shape check, non-privileged

```sql
SELECT count(*) AS n_rows,
               count_if(imsi RLIKE '^00101[0-9]{10}$') AS imsi_full_value,
               count_if(imsi RLIKE '^00101[*]{8}[0-9]{2}$') AS imsi_masked,
               count_if(msisdn RLIKE '^[+]999[0-9]{9}$') AS msisdn_full_value,
               count_if(msisdn RLIKE '^[+]999[*]{6}[0-9]{3}$') AS msisdn_masked
        FROM telco_netmon_febar_catalog.netmon_silver.silver_sessions
```

| n_rows | imsi_full_value | imsi_masked | msisdn_full_value | msisdn_masked |
|---|---|---|---|---|
| 1301595 | 0 | 1301595 | 0 | 1301595 |

_1 row(s)_

## Rows visible per region as noc_national

```sql
SELECT 'silver_sessions' AS table_name, region_code, count(*) AS visible_rows FROM telco_netmon_febar_catalog.netmon_silver.silver_sessions GROUP BY 2
        UNION ALL
        SELECT 'gold_impact_detections', region_code, count(*) FROM telco_netmon_febar_catalog.netmon_gold.gold_impact_detections GROUP BY 2
        ORDER BY 1, 2
```

| table_name | region_code | visible_rows |
|---|---|---|
| gold_impact_detections | NQL | 959 |
| gold_impact_detections | NSW | 19459 |
| gold_impact_detections | VIC | 10119 |
| gold_impact_detections | WA | 2646 |
| silver_sessions | NQL | 73380 |
| silver_sessions | NSW | 518073 |
| silver_sessions | VIC | 512597 |
| silver_sessions | WA | 197545 |

_8 row(s)_

## Row filter demo: same user, now only in noc_region_nsw

```sql
SELECT current_user() AS user, is_member('noc_national') AS in_noc_national,
               is_member('noc_region_nsw') AS in_noc_region_nsw, is_member('pii_privileged') AS in_pii_privileged,
               telco_netmon_febar_catalog.netmon_gov.is_pii_privileged() AS pii_privileged_fn
```

| user | in_noc_national | in_noc_region_nsw | in_pii_privileged | pii_privileged_fn |
|---|---|---|---|---|
| louis.chen@databricks.com | false | true | false | false |

_1 row(s)_

## Rows visible per region as noc_region_nsw (only NSW rows remain)

```sql
SELECT 'silver_sessions' AS table_name, region_code, count(*) AS visible_rows FROM telco_netmon_febar_catalog.netmon_silver.silver_sessions GROUP BY 2
        UNION ALL
        SELECT 'gold_impact_detections', region_code, count(*) FROM telco_netmon_febar_catalog.netmon_gold.gold_impact_detections GROUP BY 2
        ORDER BY 1, 2
```

| table_name | region_code | visible_rows |
|---|---|---|
| gold_impact_detections | NSW | 19459 |
| silver_sessions | NSW | 518073 |

_2 row(s)_

## Row filter demo: in no NOC group at all

No rows at all: the filter returns false for every region.

```sql
SELECT 'silver_sessions' AS table_name, region_code, count(*) AS visible_rows FROM telco_netmon_febar_catalog.netmon_silver.silver_sessions GROUP BY 2
        UNION ALL
        SELECT 'gold_impact_detections', region_code, count(*) FROM telco_netmon_febar_catalog.netmon_gold.gold_impact_detections GROUP BY 2
        ORDER BY 1, 2
```

| table_name | region_code | visible_rows |
|---|---|---|

_0 row(s)_

## Mask demo: same user added to pii_privileged

```sql
SELECT current_user() AS user, is_member('noc_national') AS in_noc_national,
               is_member('noc_region_nsw') AS in_noc_region_nsw, is_member('pii_privileged') AS in_pii_privileged,
               telco_netmon_febar_catalog.netmon_gov.is_pii_privileged() AS pii_privileged_fn
```

| user | in_noc_national | in_noc_region_nsw | in_pii_privileged | pii_privileged_fn |
|---|---|---|---|---|
| louis.chen@databricks.com | true | false | true | true |

_1 row(s)_

## Mask shape check, privileged (full values visible; values themselves not printed)

```sql
SELECT count(*) AS n_rows,
               count_if(imsi RLIKE '^00101[0-9]{10}$') AS imsi_full_value,
               count_if(imsi RLIKE '^00101[*]{8}[0-9]{2}$') AS imsi_masked,
               count_if(msisdn RLIKE '^[+]999[0-9]{9}$') AS msisdn_full_value,
               count_if(msisdn RLIKE '^[+]999[*]{6}[0-9]{3}$') AS msisdn_masked
        FROM telco_netmon_febar_catalog.netmon_silver.silver_sessions
```

| n_rows | imsi_full_value | imsi_masked | msisdn_full_value | msisdn_masked |
|---|---|---|---|---|
| 1301595 | 1301595 | 0 | 1301595 | 0 |

_1 row(s)_

## Restored membership

```sql
SELECT current_user() AS user, is_member('noc_national') AS in_noc_national,
               is_member('noc_region_nsw') AS in_noc_region_nsw, is_member('pii_privileged') AS in_pii_privileged,
               telco_netmon_febar_catalog.netmon_gov.is_pii_privileged() AS pii_privileged_fn
```

| user | in_noc_national | in_noc_region_nsw | in_pii_privileged | pii_privileged_fn |
|---|---|---|---|---|
| louis.chen@databricks.com | true | false | false | false |

_1 row(s)_
