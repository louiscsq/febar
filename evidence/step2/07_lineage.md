# Lineage: Volume → bronze → silver → gold

Captured 2026-10-08 18:29 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

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
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:28.485Z | 842 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T17:27:19.351Z | 3 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:30.207Z | 1034 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T17:26:00.492Z | 5 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_maintenance_windows | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:29.544Z | 27 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:28.471Z | 963 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T17:26:00.480Z | 5 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_topology_edges | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:30.713Z | 25 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_topology_nodes | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:31.487Z | 25 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:28.873Z | 1035 |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | PIPELINE | 2026-10-08T16:35:38.655Z | 4 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_eval.bronze_gt_incidents | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:28.460Z | 60 |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_alert_precision | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:57:44.273Z | 5 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_alert_precision | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:57:44.273Z | 5 |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T17:33:41.494Z | 3 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T17:54:13.510Z | 861 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T17:54:13.510Z | 861 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T17:54:13.510Z | 861 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T17:54:13.510Z | 861 |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_detection_precision | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:57:43.458Z | 14 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_detection_precision | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:57:43.458Z | 14 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:22:36.344Z | 14 |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:22:36.344Z | 14 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:22:36.344Z | 14 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:22:36.344Z | 14 |
| telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:22:36.344Z | 14 |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_incidents | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:56:37.140Z | 19 |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:57:50.436Z | 16 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:57:50.436Z | 16 |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:57:50.436Z | 9 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:57:49.460Z | 18 |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:57:49.460Z | 18 |
| telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:57:53.994Z | 17 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_eval.netmon_pipeline_event_log | TABLE | PIPELINE | 2026-10-08T17:57:55.469Z | 412 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:56:49.711Z | 14 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | STREAMING_TABLE | PIPELINE | 2026-10-08T17:54:16.883Z | 426 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | STREAMING_TABLE | PIPELINE | 2026-10-08T16:48:20.178Z | 2 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | STREAMING_TABLE | PIPELINE | 2026-10-08T17:54:16.883Z | 426 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T17:54:15.825Z | 424 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T17:44:02.175Z | 2 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T17:54:15.825Z | 424 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:43.863Z | 390 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T17:53:34.761Z | 3 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:43.863Z | 390 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:57:43.645Z | 16 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:57:43.645Z | 16 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:57:43.645Z | 16 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:57:43.645Z | 16 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T17:54:13.943Z | 843 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T17:33:58.190Z | 4 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T17:54:13.943Z | 843 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T17:54:13.943Z | 843 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T17:54:13.943Z | 843 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_baseline | VIEW | NULL | 2026-10-08T15:51:54.837Z | 5 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_baseline | VIEW | JOB | 2026-10-08T17:58:58.623Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_baseline | VIEW | NULL | 2026-10-08T15:51:54.837Z | 5 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_baseline | VIEW | JOB | 2026-10-08T17:58:58.623Z | 1 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_health_1m | VIEW | NULL | 2026-10-08T15:51:54.837Z | 5 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_health_1m | VIEW | JOB | 2026-10-08T17:58:59.693Z | 1 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_health_5m | VIEW | NULL | 2026-10-08T15:51:54.837Z | 5 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_health_5m | VIEW | JOB | 2026-10-08T17:59:00.707Z | 1 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_sessions_5m | VIEW | JOB | 2026-10-08T17:59:04.142Z | 2 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_sessions_5m | VIEW | NULL | 2026-10-08T15:51:54.837Z | 5 |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_element_impact_5m | VIEW | JOB | 2026-10-08T17:59:03.053Z | 2 |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_element_impact_5m | VIEW | NULL | 2026-10-08T15:51:54.837Z | 5 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_impact_detections | VIEW | JOB | 2026-10-08T17:59:01.748Z | 2 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_impact_detections | VIEW | NULL | 2026-10-08T15:51:54.837Z | 5 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_alarms | VIEW | NULL | 2026-10-08T15:51:54.837Z | 5 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_alarms | VIEW | JOB | 2026-10-08T17:58:51.849Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_kpis | VIEW | NULL | 2026-10-08T15:51:54.837Z | 5 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_kpis | VIEW | JOB | 2026-10-08T17:58:50.828Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_maintenance_windows | VIEW | NULL | 2026-10-08T15:51:54.837Z | 5 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_maintenance_windows | VIEW | JOB | 2026-10-08T17:58:57.348Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_maintenance_windows | VIEW | NULL | 2026-10-08T15:51:54.837Z | 5 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_maintenance_windows | VIEW | JOB | 2026-10-08T17:58:57.348Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_sessions | VIEW | NULL | 2026-10-08T15:51:58.256Z | 9 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_sessions | VIEW | JOB | 2026-10-08T17:58:53.322Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_topology_edges | VIEW | NULL | 2026-10-08T15:51:54.837Z | 5 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_topology_edges | VIEW | JOB | 2026-10-08T17:58:56.090Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_topology_edges | VIEW | NULL | 2026-10-08T15:51:54.837Z | 5 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_topology_edges | VIEW | JOB | 2026-10-08T17:58:56.090Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_topology_nodes | VIEW | NULL | 2026-10-08T15:51:54.837Z | 5 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_topology_nodes | VIEW | JOB | 2026-10-08T17:58:54.710Z | 1 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:46.046Z | 576 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T17:34:10.815Z | 3 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:46.046Z | 576 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:43.069Z | 504 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T17:35:51.465Z | 2 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:43.069Z | 504 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:24:27.902Z | 5 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_maintenance_windows | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:56:37.097Z | 20 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:46.396Z | 1273 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:45.189Z | 1400 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:47.108Z | 1417 |
| telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T17:50:23.089Z | 11 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:47.108Z | 1612 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:44.397Z | 589 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T17:34:35.759Z | 4 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T17:56:44.397Z | 589 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_topology_edges | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:56:39.292Z | 16 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_topology_nodes | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:56:41.063Z | 18 |

_101 row(s)_

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
| bronze_alarms | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/alarms/ | 2087 |
| bronze_gt_incidents | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/ground_truth/incidents/ | 23 |
| bronze_gt_incidents | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/ground_truth/incidents/ | 47 |
| bronze_kpis | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/kpis/ | 1932342 |
| bronze_kpis | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/kpis/ | 515317 |
| bronze_sessions | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/sessions/ | 1314879 |
| bronze_sessions | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/sessions/ | 18147 |
| bronze_topology_nodes | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/topology_nodes/ | 1887 |
| bronze_topology_nodes | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/topology_nodes/ | 1887 |

_10 row(s)_
