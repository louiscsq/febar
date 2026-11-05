# Lineage: Volume → bronze → silver → gold

Captured 2026-10-08 20:03 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

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
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T19:28:57.488Z | 1030 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T18:58:44.258Z | 4 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T19:28:59.138Z | 1272 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T18:58:41.889Z | 6 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_maintenance_windows | STREAMING_TABLE | PIPELINE | 2026-10-08T19:28:58.310Z | 30 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T19:28:57.493Z | 1167 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T18:58:37.630Z | 6 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_topology_edges | STREAMING_TABLE | PIPELINE | 2026-10-08T19:28:59.621Z | 29 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_topology_nodes | STREAMING_TABLE | PIPELINE | 2026-10-08T19:29:00.130Z | 29 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | PIPELINE | 2026-10-08T19:28:57.644Z | 1294 |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | PIPELINE | 2026-10-08T18:58:42.557Z | 5 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_eval.bronze_gt_incidents | STREAMING_TABLE | PIPELINE | 2026-10-08T19:28:57.482Z | 74 |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_alert_precision | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:26.798Z | 8 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_alert_precision | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:26.798Z | 8 |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T19:06:55.111Z | 4 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T19:30:47.011Z | 1028 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T19:30:47.011Z | 1028 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T19:30:47.011Z | 1028 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T19:30:47.011Z | 1028 |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_detection_precision | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:26.916Z | 17 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_detection_precision | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:26.916Z | 17 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:12.391Z | 17 |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:12.391Z | 17 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:12.391Z | 17 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:12.391Z | 17 |
| telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:12.391Z | 17 |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_incidents | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:29:05.766Z | 22 |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:46.477Z | 19 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:46.477Z | 19 |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:46.477Z | 12 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:45.568Z | 21 |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:45.568Z | 21 |
| telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:50.249Z | 20 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_eval.netmon_pipeline_event_log | TABLE | PIPELINE | 2026-10-08T19:31:51.669Z | 488 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:30:40.441Z | 17 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | STREAMING_TABLE | PIPELINE | 2026-10-08T19:30:45.118Z | 503 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | STREAMING_TABLE | PIPELINE | 2026-10-08T19:12:49.412Z | 3 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | STREAMING_TABLE | PIPELINE | 2026-10-08T19:30:45.118Z | 503 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T19:31:16.248Z | 502 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T19:18:09.243Z | 3 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T19:31:16.248Z | 502 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m_retrospective | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:00:55.756Z | 1 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m_retrospective | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:44.495Z | 3 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m_retrospective | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m_retrospective | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:08:20.974Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m_retrospective | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:44.495Z | 5 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T19:30:22.956Z | 462 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T19:16:15.913Z | 4 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T19:30:22.956Z | 462 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:38.924Z | 19 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:38.924Z | 19 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:38.924Z | 19 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:31:38.924Z | 19 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T19:30:48.927Z | 1019 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T17:33:58.190Z | 4 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T19:30:48.927Z | 1019 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T19:30:48.927Z | 1019 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T19:30:48.927Z | 1019 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_baseline | VIEW | NULL | 2026-10-08T18:24:34.728Z | 9 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_baseline | VIEW | JOB | 2026-10-08T17:58:58.623Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_baseline | VIEW | NULL | 2026-10-08T18:24:34.728Z | 9 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_baseline | VIEW | JOB | 2026-10-08T17:58:58.623Z | 1 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_health_1m | VIEW | NULL | 2026-10-08T18:24:34.728Z | 9 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_health_1m | VIEW | JOB | 2026-10-08T17:58:59.693Z | 1 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_health_5m | VIEW | NULL | 2026-10-08T18:24:34.728Z | 9 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_health_5m | VIEW | JOB | 2026-10-08T17:59:00.707Z | 1 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_sessions_5m | VIEW | NULL | 2026-10-08T18:24:34.728Z | 9 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_sessions_5m | VIEW | JOB | 2026-10-08T17:59:04.142Z | 2 |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_element_impact_5m | VIEW | NULL | 2026-10-08T18:24:34.728Z | 9 |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_element_impact_5m | VIEW | JOB | 2026-10-08T17:59:03.053Z | 2 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_impact_detections | VIEW | NULL | 2026-10-08T18:24:34.728Z | 9 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_impact_detections | VIEW | JOB | 2026-10-08T17:59:01.748Z | 2 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_alarms | VIEW | NULL | 2026-10-08T18:24:34.728Z | 9 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_alarms | VIEW | JOB | 2026-10-08T17:58:51.849Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_kpis | VIEW | NULL | 2026-10-08T18:24:34.728Z | 9 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_kpis | VIEW | JOB | 2026-10-08T17:58:50.828Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_maintenance_windows | VIEW | NULL | 2026-10-08T18:24:34.728Z | 9 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_maintenance_windows | VIEW | JOB | 2026-10-08T17:58:57.348Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_maintenance_windows | VIEW | NULL | 2026-10-08T18:24:34.728Z | 9 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_maintenance_windows | VIEW | JOB | 2026-10-08T17:58:57.348Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_sessions | VIEW | NULL | 2026-10-08T18:24:38.028Z | 17 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_sessions | VIEW | JOB | 2026-10-08T17:58:53.322Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_topology_edges | VIEW | NULL | 2026-10-08T18:24:34.728Z | 9 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_topology_edges | VIEW | JOB | 2026-10-08T17:58:56.090Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_topology_edges | VIEW | NULL | 2026-10-08T18:24:34.728Z | 9 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_topology_edges | VIEW | JOB | 2026-10-08T17:58:56.090Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_topology_nodes | VIEW | NULL | 2026-10-08T18:24:34.728Z | 9 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_topology_nodes | VIEW | JOB | 2026-10-08T17:58:54.710Z | 1 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T19:29:14.812Z | 699 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T19:06:03.753Z | 4 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T19:29:14.812Z | 699 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T19:29:11.985Z | 610 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T19:08:29.631Z | 3 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T19:29:11.985Z | 610 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T17:24:27.902Z | 5 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_maintenance_windows | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:29:05.731Z | 23 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T19:29:15.369Z | 1538 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T19:29:14.128Z | 1702 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T19:29:16.120Z | 1713 |
| telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T19:13:13.474Z | 14 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T19:29:16.120Z | 1912 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T19:29:13.400Z | 704 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T19:07:25.030Z | 5 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T19:29:13.400Z | 704 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_topology_edges | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:29:08.112Z | 19 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_topology_nodes | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T19:29:09.851Z | 21 |

_105 row(s)_

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
| bronze_alarms | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/alarms/ | 3154 |
| bronze_gt_incidents | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/ground_truth/incidents/ | 23 |
| bronze_gt_incidents | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/ground_truth/incidents/ | 53 |
| bronze_kpis | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/kpis/ | 1932342 |
| bronze_kpis | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/kpis/ | 515598 |
| bronze_sessions | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/sessions/ | 1314879 |
| bronze_sessions | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/sessions/ | 24577 |
| bronze_topology_nodes | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/topology_nodes/ | 1887 |
| bronze_topology_nodes | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/topology_nodes/ | 1887 |

_10 row(s)_
