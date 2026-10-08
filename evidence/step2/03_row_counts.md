# Row counts per table

Captured 2026-10-08 18:04 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

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
| netmon_silver.silver_sessions | 1314454 |
| netmon_silver.silver_maintenance_windows | 4 |
| netmon_gold.gold_impact_detections | 10460 |
| netmon_eval.eval_gt_incidents | 70 |
| netmon_bronze.bronze_kpis | 2447659 |
| netmon_bronze.bronze_alarms | 18817 |
| netmon_bronze.bronze_sessions | 1333026 |
| netmon_bronze.bronze_topology_nodes | 3774 |
| netmon_bronze.bronze_topology_edges | 3766 |
| netmon_bronze.bronze_maintenance_windows | 4 |
| netmon_silver.silver_kpis | 2413549 |
| netmon_silver.silver_alarms | 18549 |
| netmon_silver.silver_quarantine | 34042 |
| netmon_silver.silver_topology_nodes | 1887 |
| netmon_silver.silver_topology_edges | 1883 |
| netmon_gold.gold_cell_baseline | 1016375 |
| netmon_gold.gold_cell_health_1m | 2404350 |
| netmon_gold.gold_cell_health_5m | 2008000 |
| netmon_gold.gold_element_impact_5m | 83039 |
| netmon_gold.gold_cell_sessions_5m | 1102240 |
| netmon_eval.bronze_gt_incidents | 70 |
| netmon_eval.bronze_gt_dq_injections | 90749 |
| netmon_eval.eval_detection_log | 10460 |
| netmon_eval.eval_incident_detection | 47 |
| netmon_eval.eval_rca_baseline | 47 |

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
| alarms | stream | 2087 |
| kpis | history | 1932342 |
| kpis | stream | 515317 |
| sessions | history | 1314879 |
| sessions | stream | 18147 |

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
| alarms | stream | 2055 | 20 | 2026-10-08T17:24:09.000Z | 2026-10-08T23:22:26.000Z |
| kpis | history | 1905432 | 19228 | 2026-09-24T00:00:00.000Z | 2026-10-07T23:45:00.000Z |
| kpis | stream | 508117 | 5133 | 2026-10-08T17:23:00.000Z | 2026-10-08T23:22:00.000Z |
| sessions | history | 1296569 | 13079 | 2026-09-24T00:00:00.000Z | 2026-10-07T23:59:59.000Z |
| sessions | stream | 17885 | 173 | 2026-10-08T17:23:03.000Z | 2026-10-08T23:22:59.000Z |

_6 row(s)_
