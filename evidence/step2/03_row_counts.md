# Row counts per table

Captured 2026-10-08 15:31 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

## All pipeline tables

Counts as seen by the capturing user (member of `noc_national`, so row filters pass every region). silver_sessions / gold_impact_detections are row-filtered tables.

```sql
SELECT 'netmon_bronze.bronze_kpis' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_bronze.bronze_kpis
UNION ALL SELECT 'netmon_bronze.bronze_alarms' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_bronze.bronze_alarms
UNION ALL SELECT 'netmon_bronze.bronze_sessions' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_bronze.bronze_sessions
UNION ALL SELECT 'netmon_bronze.bronze_topology_nodes' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_bronze.bronze_topology_nodes
UNION ALL SELECT 'netmon_bronze.bronze_topology_edges' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_bronze.bronze_topology_edges
UNION ALL SELECT 'netmon_bronze.bronze_maintenance_windows' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_bronze.bronze_maintenance_windows
UNION ALL SELECT 'netmon_silver.silver_kpis' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_silver.silver_kpis
UNION ALL SELECT 'netmon_silver.silver_alarms' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_silver.silver_alarms
UNION ALL SELECT 'netmon_silver.silver_sessions' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_silver.silver_sessions
UNION ALL SELECT 'netmon_silver.silver_quarantine' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_silver.silver_quarantine
UNION ALL SELECT 'netmon_silver.silver_topology_nodes' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes
UNION ALL SELECT 'netmon_silver.silver_topology_edges' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_silver.silver_topology_edges
UNION ALL SELECT 'netmon_silver.silver_maintenance_windows' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows
UNION ALL SELECT 'netmon_gold.gold_cell_baseline' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline
UNION ALL SELECT 'netmon_gold.gold_cell_health_1m' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m
UNION ALL SELECT 'netmon_gold.gold_cell_health_5m' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m
UNION ALL SELECT 'netmon_gold.gold_impact_detections' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_gold.gold_impact_detections
UNION ALL SELECT 'netmon_gold.gold_element_impact_5m' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m
UNION ALL SELECT 'netmon_gold.gold_cell_sessions_5m' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m
UNION ALL SELECT 'netmon_eval.bronze_gt_incidents' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_eval.bronze_gt_incidents
UNION ALL SELECT 'netmon_eval.bronze_gt_dq_injections' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections
UNION ALL SELECT 'netmon_eval.eval_gt_incidents' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents
UNION ALL SELECT 'netmon_eval.eval_detection_log' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_eval.eval_detection_log
UNION ALL SELECT 'netmon_eval.eval_incident_detection' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_eval.eval_incident_detection
UNION ALL SELECT 'netmon_eval.eval_rca_baseline' AS table_name, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline
```

| table_name | n_rows |
|---|---|
| netmon_silver.silver_sessions | 1304712 |
| netmon_silver.silver_maintenance_windows | 6 |
| netmon_gold.gold_impact_detections | 23752 |
| netmon_eval.eval_gt_incidents | 79 |
| netmon_bronze.bronze_kpis | 2445043 |
| netmon_bronze.bronze_alarms | 20441 |
| netmon_bronze.bronze_sessions | 1323152 |
| netmon_bronze.bronze_topology_nodes | 3774 |
| netmon_bronze.bronze_topology_edges | 3766 |
| netmon_bronze.bronze_maintenance_windows | 6 |
| netmon_silver.silver_kpis | 2410993 |
| netmon_silver.silver_alarms | 20155 |
| netmon_silver.silver_quarantine | 33926 |
| netmon_silver.silver_topology_nodes | 1887 |
| netmon_silver.silver_topology_edges | 1883 |
| netmon_gold.gold_cell_baseline | 1016375 |
| netmon_gold.gold_cell_health_1m | 2401794 |
| netmon_gold.gold_cell_health_5m | 2006088 |
| netmon_gold.gold_element_impact_5m | 87480 |
| netmon_gold.gold_cell_sessions_5m | 1094380 |
| netmon_eval.bronze_gt_incidents | 79 |
| netmon_eval.bronze_gt_dq_injections | 90468 |
| netmon_eval.eval_detection_log | 23752 |
| netmon_eval.eval_incident_detection | 54 |
| netmon_eval.eval_rca_baseline | 54 |

_25 row(s)_

## Bronze and silver by generator run

```sql
SELECT 'kpis' AS feed, _source_run AS run, count(*) AS bronze FROM telco_netmon_febar_catalog.netmon_bronze.bronze_kpis GROUP BY 2
        UNION ALL SELECT 'alarms', _source_run, count(*) FROM telco_netmon_febar_catalog.netmon_bronze.bronze_alarms GROUP BY 2
        UNION ALL SELECT 'sessions', _source_run, count(*) FROM telco_netmon_febar_catalog.netmon_bronze.bronze_sessions GROUP BY 2
        ORDER BY 1, 2
```

| feed | run | bronze |
|---|---|---|
| alarms | history | 16730 |
| alarms | stream | 3711 |
| kpis | history | 1932342 |
| kpis | stream | 512701 |
| sessions | history | 1314879 |
| sessions | stream | 8273 |

_6 row(s)_

## Silver by generator run

```sql
SELECT 'kpis' AS feed, source_run AS run, count(*) AS silver, count_if(is_late) AS late_kept,
               min(event_ts) AS min_event_ts, max(event_ts) AS max_event_ts FROM telco_netmon_febar_catalog.netmon_silver.silver_kpis GROUP BY 2
        UNION ALL SELECT 'alarms', source_run, count(*), count_if(is_late), min(event_ts), max(event_ts)
          FROM telco_netmon_febar_catalog.netmon_silver.silver_alarms GROUP BY 2
        UNION ALL SELECT 'sessions', source_run, count(*), count_if(is_late), min(start_ts), max(start_ts)
          FROM telco_netmon_febar_catalog.netmon_silver.silver_sessions GROUP BY 2
        ORDER BY 1, 2
```

| feed | run | silver | late_kept | min_event_ts | max_event_ts |
|---|---|---|---|---|---|
| alarms | history | 16494 | 166 | 2026-09-24T00:00:03.000Z | 2026-10-08T01:47:14.000Z |
| alarms | stream | 3661 | 35 | 2026-10-08T14:51:35.000Z | 2026-10-08T20:50:00.000Z |
| kpis | history | 1905432 | 19228 | 2026-09-24T00:00:00.000Z | 2026-10-07T23:45:00.000Z |
| kpis | stream | 505561 | 5112 | 2026-10-08T14:51:00.000Z | 2026-10-08T20:50:00.000Z |
| sessions | history | 1296569 | 13079 | 2026-09-24T00:00:00.000Z | 2026-10-07T23:59:59.000Z |
| sessions | stream | 8143 | 72 | 2026-10-08T14:51:00.000Z | 2026-10-08T20:50:59.000Z |

_6 row(s)_
