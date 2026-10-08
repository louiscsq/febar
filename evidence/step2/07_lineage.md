# Lineage: Volume → bronze → silver → gold

Captured 2026-10-08 13:51 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

Captured automatically by Unity Catalog; queried from `system.access.table_lineage`.

## Table-level lineage edges for the netmon schemas

```sql
SELECT coalesce(source_table_full_name, source_path) AS source, source_type,
               target_table_full_name AS target, target_type, entity_type, max(event_time) AS last_seen,
               count(*) AS n_events
        FROM system.access.table_lineage
        WHERE (target_table_full_name LIKE 'telco_netmon_febar_catalog.netmon_%' OR source_table_full_name LIKE 'telco_netmon_febar_catalog.netmon_%')
          AND event_date >= current_date() - INTERVAL 2 DAYS
          AND target_table_full_name IS NOT NULL
        GROUP BY ALL ORDER BY target, source
```

| source | source_type | target | target_type | entity_type | last_seen | n_events |
|---|---|---|---|---|---|---|
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T13:26:48.334Z | 187 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T13:26:49.326Z | 244 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T12:44:36.327Z | 2 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_maintenance_windows | STREAMING_TABLE | PIPELINE | 2026-10-08T13:26:48.625Z | 12 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T13:26:48.341Z | 247 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T12:44:35.276Z | 2 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_topology_edges | STREAMING_TABLE | PIPELINE | 2026-10-08T13:26:49.854Z | 13 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_topology_nodes | STREAMING_TABLE | PIPELINE | 2026-10-08T13:26:50.666Z | 13 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | PIPELINE | 2026-10-08T13:26:48.354Z | 249 |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | PIPELINE | 2026-10-08T12:44:26.722Z | 2 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_eval.bronze_gt_incidents | STREAMING_TABLE | PIPELINE | 2026-10-08T13:26:48.347Z | 17 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:17.991Z | 273 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:17.991Z | 273 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:17.991Z | 273 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:17.991Z | 273 |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_detection_precision | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:23.440Z | 6 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_detection_precision | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:23.440Z | 6 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:17.016Z | 7 |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:17.016Z | 7 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:17.016Z | 7 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:17.016Z | 7 |
| telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:17.016Z | 7 |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_incidents | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:26:56.551Z | 13 |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:23.477Z | 7 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:23.477Z | 7 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:27.034Z | 9 |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:27.034Z | 9 |
| telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:28.669Z | 8 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_eval.netmon_pipeline_event_log | TABLE | PIPELINE | 2026-10-08T13:27:30.064Z | 179 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:09.523Z | 6 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | STREAMING_TABLE | PIPELINE | 2026-10-08T13:23:24.249Z | 149 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | STREAMING_TABLE | PIPELINE | 2026-10-08T13:23:24.249Z | 149 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:16.412Z | 147 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:16.412Z | 147 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:03.880Z | 142 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T13:09:09.073Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:03.880Z | 142 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:23.411Z | 8 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:23.411Z | 8 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:23.411Z | 8 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:23.411Z | 8 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:17.308Z | 277 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T12:49:11.837Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:17.308Z | 277 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:17.308Z | 277 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:17.308Z | 277 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:05.878Z | 175 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:05.878Z | 175 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:02.877Z | 182 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:02.877Z | 182 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T12:44:19.873Z | 1 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_maintenance_windows | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:26:56.500Z | 13 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:06.407Z | 349 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:05.172Z | 409 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:07.066Z | 414 |
| telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T13:04:56.851Z | 2 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:07.066Z | 526 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:04.434Z | 200 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T12:48:45.247Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T13:27:04.434Z | 200 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_topology_edges | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:26:58.867Z | 10 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_topology_nodes | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T13:27:00.823Z | 12 |

_62 row(s)_

## Volume → bronze

On this workspace `system.access.table_lineage` (and the lineage-tracking REST API) record the Auto Loader hop as a PIPELINE-entity edge into each bronze table with a NULL source (see the rows with `source = NULL` above): the Volume path is not populated as a lineage source. The hop is proven instead by `_source_file` (Auto Loader `_metadata.file_path`) on every bronze row:

## Bronze rows by landing Volume directory (_metadata.file_path)

```sql
SELECT 'bronze_kpis' AS table_name, regexp_replace(_source_file, '/date=.*', '/') AS volume_dir, count(*) AS n
        FROM telco_netmon_febar_catalog.netmon_bronze.bronze_kpis GROUP BY 2
        UNION ALL SELECT 'bronze_alarms', regexp_replace(_source_file, '/date=.*', '/'), count(*)
          FROM telco_netmon_febar_catalog.netmon_bronze.bronze_alarms GROUP BY 2
        UNION ALL SELECT 'bronze_sessions', regexp_replace(_source_file, '/date=.*', '/'), count(*)
          FROM telco_netmon_febar_catalog.netmon_bronze.bronze_sessions GROUP BY 2
        UNION ALL SELECT 'bronze_topology_nodes', regexp_replace(_source_file, '/[^/]*$', '/'), count(*)
          FROM telco_netmon_febar_catalog.netmon_bronze.bronze_topology_nodes GROUP BY 2
        UNION ALL SELECT 'bronze_gt_incidents', regexp_replace(_source_file, '/(date=.*|part-.*)$', '/'), count(*)
          FROM telco_netmon_febar_catalog.netmon_eval.bronze_gt_incidents GROUP BY 2
        ORDER BY 1, 2
```

| table_name | volume_dir | n |
|---|---|---|
| bronze_alarms | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/alarms/ | 16730 |
| bronze_alarms | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/alarms/ | 2929 |
| bronze_gt_incidents | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/ground_truth/incidents/ | 23 |
| bronze_gt_incidents | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/ground_truth/incidents/ | 35 |
| bronze_kpis | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/kpis/ | 1932342 |
| bronze_kpis | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/kpis/ | 340638 |
| bronze_sessions | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/sessions/ | 1314879 |
| bronze_sessions | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/sessions/ | 5101 |
| bronze_topology_nodes | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/topology_nodes/ | 1887 |
| bronze_topology_nodes | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/topology_nodes/ | 1887 |

_10 row(s)_
