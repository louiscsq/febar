# Lineage: Volume → bronze → silver → gold

Captured 2026-10-08 15:57 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

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
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:07.299Z | 387 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T14:56:04.937Z | 1 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:08.942Z | 484 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T14:54:51.782Z | 3 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_maintenance_windows | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:08.180Z | 18 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:07.321Z | 472 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T14:54:52.605Z | 3 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_topology_edges | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:09.445Z | 17 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_bronze.bronze_topology_nodes | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:10.250Z | 17 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:07.733Z | 469 |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | PIPELINE | 2026-10-08T14:54:43.375Z | 3 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_eval.bronze_gt_incidents | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:07.288Z | 30 |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T15:02:52.225Z | 1 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T15:26:23.418Z | 429 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T15:26:23.418Z | 429 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T15:26:23.418Z | 429 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | PIPELINE | 2026-10-08T15:26:23.418Z | 429 |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_detection_precision | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:32.100Z | 9 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_detection_precision | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:32.100Z | 9 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:24.491Z | 10 |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:24.491Z | 10 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:24.491Z | 10 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:24.491Z | 10 |
| telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:24.491Z | 10 |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_incidents | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T14:44:34.502Z | 14 |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_log | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:45.974Z | 10 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:45.974Z | 10 |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:45.974Z | 3 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:45.283Z | 12 |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:45.283Z | 12 |
| telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:49.769Z | 11 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_eval.netmon_pipeline_event_log | TABLE | PIPELINE | 2026-10-08T15:26:51.128Z | 250 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:19.121Z | 9 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | STREAMING_TABLE | PIPELINE | 2026-10-08T15:26:24.152Z | 219 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | STREAMING_TABLE | PIPELINE | 2026-10-08T15:09:58.480Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | STREAMING_TABLE | PIPELINE | 2026-10-08T15:26:24.152Z | 219 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T15:26:21.532Z | 222 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T15:13:43.134Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T15:26:21.532Z | 222 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:28.101Z | 208 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T13:09:09.073Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:28.101Z | 208 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:38.944Z | 11 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:38.944Z | 11 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:38.944Z | 11 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:26:38.944Z | 11 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T15:26:22.744Z | 432 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T15:02:53.666Z | 2 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T15:26:22.744Z | 432 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T15:26:22.744Z | 432 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | STREAMING_TABLE | PIPELINE | 2026-10-08T15:26:22.744Z | 432 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_baseline | VIEW | NULL | 2026-10-08T15:36:31.381Z | 2 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_baseline | VIEW | NULL | 2026-10-08T15:36:31.381Z | 2 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_health_1m | VIEW | NULL | 2026-10-08T15:36:31.381Z | 2 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_health_5m | VIEW | NULL | 2026-10-08T15:36:31.381Z | 2 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_sessions_5m | VIEW | NULL | 2026-10-08T15:36:31.381Z | 2 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_cell_sessions_5m | VIEW | JOB | 2026-10-08T15:28:56.424Z | 1 |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_element_impact_5m | VIEW | NULL | 2026-10-08T15:36:31.381Z | 2 |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_element_impact_5m | VIEW | JOB | 2026-10-08T15:28:55.622Z | 1 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_impact_detections | VIEW | NULL | 2026-10-08T15:36:31.381Z | 2 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | TABLE | telco_netmon_febar_catalog.netmon_noc.gold_impact_detections | VIEW | JOB | 2026-10-08T15:28:54.621Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_alarms | VIEW | NULL | 2026-10-08T15:36:31.381Z | 2 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_kpis | VIEW | NULL | 2026-10-08T15:36:31.381Z | 2 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_maintenance_windows | VIEW | NULL | 2026-10-08T15:36:31.381Z | 2 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_maintenance_windows | VIEW | NULL | 2026-10-08T15:36:31.381Z | 2 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_sessions | VIEW | NULL | 2026-10-08T15:36:31.381Z | 4 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_topology_edges | VIEW | NULL | 2026-10-08T15:36:31.381Z | 2 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_topology_edges | VIEW | NULL | 2026-10-08T15:36:31.381Z | 2 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | TABLE | telco_netmon_febar_catalog.netmon_noc.silver_topology_nodes | VIEW | NULL | 2026-10-08T15:36:31.381Z | 2 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:30.081Z | 279 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T15:03:26.304Z | 1 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_alarms | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:30.081Z | 279 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:27.270Z | 269 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_kpis | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:27.270Z | 269 |
| NULL | NULL | telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:01:46.608Z | 3 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_maintenance_windows | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T15:25:19.568Z | 15 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:30.593Z | 627 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:29.330Z | 712 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:31.294Z | 712 |
| telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T15:05:29.775Z | 4 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_quarantine | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:31.294Z | 846 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:28.766Z | 299 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T15:04:19.289Z | 2 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | telco_netmon_febar_catalog.netmon_silver.silver_sessions | STREAMING_TABLE | PIPELINE | 2026-10-08T15:25:28.766Z | 299 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_topology_edges | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T14:44:34.419Z | 11 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_topology_nodes | STREAMING_TABLE | telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | MATERIALIZED_VIEW | PIPELINE | 2026-10-08T14:44:36.306Z | 13 |

_86 row(s)_

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
| bronze_alarms | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/alarms/ | 3711 |
| bronze_gt_incidents | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/ground_truth/incidents/ | 23 |
| bronze_gt_incidents | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/ground_truth/incidents/ | 56 |
| bronze_kpis | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/kpis/ | 1932342 |
| bronze_kpis | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/kpis/ | 512701 |
| bronze_sessions | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/sessions/ | 1314879 |
| bronze_sessions | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/sessions/ | 8273 |
| bronze_topology_nodes | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/history/topology_nodes/ | 1887 |
| bronze_topology_nodes | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/topology_nodes/ | 1887 |

_10 row(s)_
