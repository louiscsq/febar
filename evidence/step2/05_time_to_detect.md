# Time-to-detect, localisation and precision against ground truth

Captured 2026-10-08 19:38 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

Scored incidents: customer-impacting and not censored. Two separate metrics (docs/pipeline.md):

- **(a) customer-impact detection** — first detection on any element of the incident's footprint; `impact_ttd_s` = (evidence time + measured pipeline latency for live files) − `impact_start_ts`. This is the 5-minute SLA metric.
- **(b) root-element localisation** — a detection or the topology rollup lands on an element of `root_element_ids` (any one counts for cluster faults).

`history` = 15-minute-ROP backfill (cannot meet a 5-minute SLA by construction); `stream` = 1-minute live feed. Fault-only rows (`event_class = fault`) are the headline; planned work is suppressed by the change calendar and reported separately.

## Headline: faults only

```sql
SELECT source_run, event_class, n_incidents, n_impact_detected, impact_detected_pct, impact_median_ttd_s, impact_p90_ttd_s, impact_within_5min_pct, n_root_localised, root_localised_pct, localisation_median_ttd_s, localised_within_5min_pct, median_evidence_lag_s, median_pipeline_latency_s FROM telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary WHERE event_class = 'fault' AND fault_type = 'ALL'
        ORDER BY source_run DESC
```

| source_run | event_class | n_incidents | n_impact_detected | impact_detected_pct | impact_median_ttd_s | impact_p90_ttd_s | impact_within_5min_pct | n_root_localised | root_localised_pct | localisation_median_ttd_s | localised_within_5min_pct | median_evidence_lag_s | median_pipeline_latency_s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stream | fault | 26 | 26 | 100.0 | 141.4 | 430.4 | 88.5 | 26 | 100.0 | 144.4 | 88.5 | 94.0 | 39.2 |
| history | fault | 16 | 15 | 93.8 | 61.5 | 1057.0 | 75.0 | 14 | 87.5 | 61.5 | 68.8 | 61.5 | NULL |

_2 row(s)_

## All event classes

```sql
SELECT source_run, event_class, n_incidents, n_impact_detected, impact_detected_pct, impact_median_ttd_s, impact_p90_ttd_s, impact_within_5min_pct, n_root_localised, root_localised_pct, localisation_median_ttd_s, localised_within_5min_pct, median_evidence_lag_s, median_pipeline_latency_s FROM telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary WHERE fault_type = 'ALL'
        ORDER BY source_run DESC, CASE event_class WHEN 'fault' THEN 0 WHEN 'ALL' THEN 9 ELSE 1 END, event_class
```

| source_run | event_class | n_incidents | n_impact_detected | impact_detected_pct | impact_median_ttd_s | impact_p90_ttd_s | impact_within_5min_pct | n_root_localised | root_localised_pct | localisation_median_ttd_s | localised_within_5min_pct | median_evidence_lag_s | median_pipeline_latency_s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stream | fault | 26 | 26 | 100.0 | 141.4 | 430.4 | 88.5 | 26 | 100.0 | 144.4 | 88.5 | 94.0 | 39.2 |
| stream | ALL | 26 | 26 | 100.0 | 141.4 | 430.4 | 88.5 | 26 | 100.0 | 144.4 | 88.5 | 94.0 | 39.2 |
| history | fault | 16 | 15 | 93.8 | 61.5 | 1057.0 | 75.0 | 14 | 87.5 | 61.5 | 68.8 | 61.5 | NULL |
| history | planned | 2 | 2 | 100.0 | 33.0 | 35.4 | 100.0 | 2 | 100.0 | 33.0 | 100.0 | 33.0 | NULL |
| history | red_herring | 1 | 1 | 100.0 | 1070.0 | 1070.0 | 0.0 | 1 | 100.0 | 2150.0 | 0.0 | 1070.0 | NULL |
| history | ALL | 19 | 18 | 94.7 | 59.0 | 1200.8 | 73.7 | 17 | 89.5 | 59.0 | 68.4 | 59.0 | NULL |

_6 row(s)_

## Per fault type

```sql
SELECT source_run, event_class, fault_type, n_incidents, impact_detected_pct, impact_median_ttd_s,
               impact_within_5min_pct, root_localised_pct, localisation_median_ttd_s, localised_within_5min_pct
        FROM telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary WHERE fault_type <> 'ALL'
        ORDER BY source_run DESC, CASE event_class WHEN 'fault' THEN 0 ELSE 1 END, event_class, fault_type
```

| source_run | event_class | fault_type | n_incidents | impact_detected_pct | impact_median_ttd_s | impact_within_5min_pct | root_localised_pct | localisation_median_ttd_s | localised_within_5min_pct |
|---|---|---|---|---|---|---|---|---|---|
| stream | fault | AGG_ROUTER_FAILURE | 1 | 100.0 | 23.4 | 100.0 | 100.0 | 206.0 | 100.0 |
| stream | fault | BACKHAUL_DEGRADATION | 3 | 100.0 | 807.9 | 0.0 | 100.0 | 1166.0 | 0.0 |
| stream | fault | CELL_OUTAGE | 20 | 100.0 | 132.7 | 100.0 | 100.0 | 132.7 | 100.0 |
| stream | fault | SITE_POWER_OUTAGE | 2 | 100.0 | 235.5 | 100.0 | 100.0 | 235.5 | 100.0 |
| history | fault | AGG_ROUTER_FAILURE | 2 | 100.0 | 0.0 | 100.0 | 100.0 | 20.0 | 100.0 |
| history | fault | AMF_OVERLOAD | 1 | 100.0 | 390.0 | 0.0 | 100.0 | 1499.0 | 0.0 |
| history | fault | BACKHAUL_DEGRADATION | 1 | 100.0 | 1724.0 | 0.0 | 100.0 | 1909.0 | 0.0 |
| history | fault | BUSHFIRE_GRID_OUTAGE | 1 | 100.0 | 172.0 | 100.0 | 100.0 | 172.0 | 100.0 |
| history | fault | CELL_OUTAGE | 6 | 100.0 | 56.5 | 100.0 | 100.0 | 56.5 | 100.0 |
| history | fault | CORE_CONGESTION | 2 | 50.0 | 1067.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| history | fault | CYCLONE_BACKHAUL_CUT | 1 | 100.0 | 0.0 | 100.0 | 100.0 | 1720.0 | 0.0 |
| history | fault | LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 178.0 | 100.0 | 100.0 | 178.0 | 100.0 |
| history | fault | SITE_POWER_OUTAGE | 1 | 100.0 | 75.0 | 100.0 | 100.0 | 75.0 | 100.0 |
| history | planned | PLANNED_MAINTENANCE | 2 | 100.0 | 33.0 | 100.0 | 100.0 | 33.0 | 100.0 |
| history | red_herring | TRAFFIC_SURGE | 1 | 100.0 | 1070.0 | 0.0 | 100.0 | 2150.0 | 0.0 |

_15 row(s)_

## Live-stream fault incidents

```sql
SELECT incident_id, fault_type, root_element_type, impact_start_ts, impact_detected, first_signal_source,
               first_element_type, round(evidence_lag_s, 0) AS evidence_lag_s,
               round(first_pipeline_latency_s, 1) AS pipeline_latency_s, round(impact_ttd_s, 1) AS impact_ttd_s,
               impact_within_sla, root_localised, localisation_source, round(localisation_ttd_s, 1) AS localisation_ttd_s
        FROM telco_netmon_febar_catalog.netmon_eval.eval_incident_detection WHERE source_run = 'stream' AND event_class = 'fault'
        ORDER BY impact_start_ts
```

| incident_id | fault_type | root_element_type | impact_start_ts | impact_detected | first_signal_source | first_element_type | evidence_lag_s | pipeline_latency_s | impact_ttd_s | impact_within_sla | root_localised | localisation_source | localisation_ttd_s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| INC-2026100819-00001 | CELL_OUTAGE | CELL | 2026-10-08T19:01:54.000Z | true | alarm | CELL | 66 | 164.6 | 230.6 | true | true | detection | 230.6 |
| INC-2026100819-00002 | CELL_OUTAGE | CELL | 2026-10-08T19:12:29.000Z | true | alarm | CELL | 91 | 109.6 | 200.6 | true | true | detection | 200.6 |
| INC-2026100819-00004 | CELL_OUTAGE | CELL | 2026-10-08T19:16:19.000Z | true | alarm | CELL | 41 | 94.6 | 135.6 | true | true | detection | 135.6 |
| INC-2026100819-00006 | CELL_OUTAGE | CELL | 2026-10-08T19:29:23.000Z | true | alarm | CELL | 97 | 52.4 | 149.4 | true | true | detection | 149.4 |
| INC-2026100820-00001 | CELL_OUTAGE | CELL | 2026-10-08T20:14:15.000Z | true | alarm | CELL | 45 | 30.8 | 75.8 | true | true | detection | 75.8 |
| INC-2026100820-00002 | CELL_OUTAGE | CELL | 2026-10-08T20:16:43.000Z | true | kpi | CELL | 77 | 28.8 | 105.8 | true | true | detection | 105.8 |
| INC-2026100820-00003 | CELL_OUTAGE | CELL | 2026-10-08T20:23:10.000Z | true | alarm | CELL | 110 | 32.8 | 142.8 | true | true | detection | 142.8 |
| INC-2026100820-00004 | CELL_OUTAGE | CELL | 2026-10-08T20:26:14.000Z | true | alarm | CELL | 106 | 33.9 | 139.9 | true | true | detection | 139.9 |
| INC-2026100820-00005 | CELL_OUTAGE | CELL | 2026-10-08T20:34:08.000Z | true | alarm | CELL | 112 | 38.5 | 150.5 | true | true | detection | 150.5 |
| INC-2026100819-00005 | SITE_POWER_OUTAGE | SITE | 2026-10-08T20:36:10.000Z | true | alarm | SITE | 230 | 43.6 | 273.6 | true | true | detection | 273.6 |
| INC-2026100820-00006 | BACKHAUL_DEGRADATION | BACKHAUL_LINK | 2026-10-08T20:36:59.000Z | true | kpi | CELL | 781 | 50.2 | 831.2 | false | true | rollup | 1201.0 |
| INC-2026100820-00007 | CELL_OUTAGE | CELL | 2026-10-08T20:54:00.000Z | true | alarm | CELL | 120 | 39.2 | 159.2 | true | true | detection | 159.2 |
| INC-2026100820-00009 | CELL_OUTAGE | CELL | 2026-10-08T20:55:15.000Z | true | alarm | CELL | 45 | 39.2 | 84.2 | true | true | detection | 84.2 |
| INC-2026100820-00010 | CELL_OUTAGE | CELL | 2026-10-08T20:57:14.000Z | true | kpi | CELL | 106 | 40.7 | 146.7 | true | true | detection | 146.7 |
| INC-2026100820-00008 | SITE_POWER_OUTAGE | SITE | 2026-10-08T21:46:15.000Z | true | alarm | SITE | 165 | 32.4 | 197.4 | true | true | detection | 197.4 |
| INC-2026100821-00001 | CELL_OUTAGE | CELL | 2026-10-08T21:58:16.000Z | true | alarm | CELL | 44 | 29.6 | 73.6 | true | true | detection | 73.6 |
| INC-2026100821-00002 | CELL_OUTAGE | CELL | 2026-10-08T21:59:22.000Z | true | alarm | CELL | 98 | 31.9 | 129.9 | true | true | detection | 129.9 |
| INC-2026100822-00001 | CELL_OUTAGE | CELL | 2026-10-08T22:01:37.000Z | true | alarm | CELL | 83 | 38.4 | 121.4 | true | true | detection | 121.4 |
| INC-2026100822-00003 | CELL_OUTAGE | CELL | 2026-10-08T22:11:06.000Z | true | alarm | CELL | 54 | 37.6 | 91.6 | true | true | detection | 91.6 |
| INC-2026100822-00004 | BACKHAUL_DEGRADATION | BACKHAUL_LINK | 2026-10-08T22:27:34.000Z | true | kpi | CELL | 746 | 61.9 | 807.9 | false | true | rollup | 1166.0 |
| INC-2026100822-00006 | CELL_OUTAGE | CELL | 2026-10-08T22:37:30.000Z | true | alarm | CELL | 30 | 43.8 | 73.8 | true | true | detection | 73.8 |
| INC-2026100822-00007 | BACKHAUL_DEGRADATION | BACKHAUL_LINK | 2026-10-08T22:41:33.000Z | true | kpi | CELL | 507 | 80.2 | 587.2 | false | true | rollup | 927.0 |
| INC-2026100823-00004 | AGG_ROUTER_FAILURE | AGG_ROUTER | 2026-10-08T23:18:34.000Z | true | alarm | BACKHAUL_LINK | 0 | 57.4 | 23.4 | true | true | rollup | 206.0 |
| INC-2026100823-00007 | CELL_OUTAGE | CELL | 2026-10-08T23:35:06.000Z | true | alarm | CELL | 54 | 31.9 | 85.9 | true | true | detection | 85.9 |
| INC-2026100900-00001 | CELL_OUTAGE | CELL | 2026-10-09T00:03:10.000Z | true | kpi | CELL | 110 | 35.9 | 145.9 | true | true | detection | 145.9 |
| INC-2026100900-00002 | CELL_OUTAGE | CELL | 2026-10-09T00:09:28.000Z | true | alarm | CELL | 32 | 72.3 | 104.3 | true | true | detection | 104.3 |

_26 row(s)_

## Ground-truth incidents in the live stream (incl. censored and non-impacting)

```sql
SELECT event_class, fault_type, is_customer_impacting, is_censored, count(*) AS n
        FROM telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents WHERE source_run = 'stream' GROUP BY ALL ORDER BY ALL
```

| event_class | fault_type | is_customer_impacting | is_censored | n |
|---|---|---|---|---|
| fault | AGG_ROUTER_FAILURE | true | false | 1 |
| fault | BACKHAUL_DEGRADATION | true | false | 3 |
| fault | BACKHAUL_DEGRADATION | true | true | 6 |
| fault | CELL_OUTAGE | true | false | 20 |
| fault | CELL_OUTAGE | true | true | 9 |
| fault | LONG_HAUL_FIBRE_CUT | true | true | 1 |
| fault | SITE_POWER_OUTAGE | true | false | 2 |
| fault | SITE_POWER_OUTAGE | true | true | 2 |
| red_herring | ALARM_STORM | false | false | 6 |
| red_herring | ALARM_STORM | false | true | 1 |
| red_herring | FLAPPING_ELEMENT | false | true | 2 |

_11 row(s)_

## Alert-level fault precision (detections grouped per element per episode)

An alert = the detections on one element of one run until one starts > 10 min after the previous signal ended (one page). It takes the highest-priority label of its rows; suppressed when its first row is in a change window. `alert_fault_precision_pct` = TP alerts / (TP + FP alerts).

```sql
SELECT * FROM telco_netmon_febar_catalog.netmon_eval.eval_alert_precision
        ORDER BY source_run DESC, CASE signal_source WHEN 'ALL' THEN 0 ELSE 1 END, signal_source
```

| source_run | signal_source | n_alerts | n_fault_tp | n_censored_excluded | n_planned | n_planned_suppressed | n_planned_unsuppressed_fp | n_red_herring_fp | n_unexplained_fp | alert_fault_precision_pct | maintenance_suppression_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| stream | ALL | 231 | 104 | 58 | 0 | 0 | 0 | 0 | 69 | 60.1 | NULL |
| stream | alarm | 21 | 17 | 4 | 0 | 0 | 0 | 0 | 0 | 100.0 | NULL |
| stream | kpi | 210 | 87 | 54 | 0 | 0 | 0 | 0 | 69 | 55.8 | NULL |
| history | ALL | 1567 | 961 | 0 | 176 | 176 | 0 | 27 | 403 | 69.1 | 100.0 |
| history | alarm | 78 | 74 | 0 | 4 | 4 | 0 | 0 | 0 | 100.0 | 100.0 |
| history | kpi | 1489 | 887 | 0 | 172 | 172 | 0 | 27 | 403 | 67.4 | 100.0 |

_6 row(s)_

## Detection-row fault precision and maintenance suppression

One row per detection (a degraded cell-minute or an alarm), so long incidents with many cells weigh heavily. Labels in priority order: uncensored fault = TP; overlapping a censored incident = excluded; planned work = suppressed when `in_maintenance` (else a false page); red herring (e.g. TRAFFIC_SURGE) = FP; nothing = FP. `row_fault_precision_pct` = TP / (TP + FP).

```sql
SELECT * FROM telco_netmon_febar_catalog.netmon_eval.eval_detection_precision
        ORDER BY source_run DESC, CASE signal_source WHEN 'ALL' THEN 0 ELSE 1 END, signal_source
```

| source_run | signal_source | n_rows | n_fault_tp | n_censored_excluded | n_planned | n_planned_suppressed | n_planned_unsuppressed_fp | n_red_herring_fp | n_unexplained_fp | row_fault_precision_pct | maintenance_suppression_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| stream | ALL | 8335 | 5313 | 2924 | 0 | 0 | 0 | 0 | 98 | 98.2 | NULL |
| stream | alarm | 73 | 60 | 13 | 0 | 0 | 0 | 0 | 0 | 100.0 | NULL |
| stream | kpi | 8262 | 5253 | 2911 | 0 | 0 | 0 | 0 | 98 | 98.2 | NULL |
| history | ALL | 3739 | 2635 | 0 | 517 | 517 | 0 | 171 | 416 | 81.8 | 100.0 |
| history | alarm | 354 | 181 | 0 | 173 | 173 | 0 | 0 | 0 | 100.0 | 100.0 |
| history | kpi | 3385 | 2454 | 0 | 344 | 344 | 0 | 171 | 416 | 80.7 | 100.0 |

_6 row(s)_

## History AMF_OVERLOAD INC-00016: localisation and the inputs it was qualified and timed from

```sql
SELECT incident_id, impact_start_ts, localisation_source, localised_element,
               round(localisation_ttd_s) AS localisation_ttd_s, round(impact_ttd_s) AS impact_ttd_s
        FROM telco_netmon_febar_catalog.netmon_eval.eval_incident_detection WHERE source_run = 'history' AND incident_id = 'INC-00016'
```

| incident_id | impact_start_ts | localisation_source | localised_element | localisation_ttd_s | impact_ttd_s |
|---|---|---|---|---|---|
| INC-00016 | 2026-10-03T10:09:01.000Z | rollup | AMF-VIC-01 | 1499 | 390 |

_1 row(s)_

## INC-00016: qualifying rollup windows of the root (real-time, on-time records only)

The first qualifying window is what localises the incident. Its cells' windows contain only on-time records (next table), and `evidence_ts` is the latest arrival among those same records.

```sql
WITH inc AS (SELECT * FROM telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents WHERE source_run = 'history' AND incident_id = 'INC-00016')
        SELECT f.window_start, f.window_end, f.element_id, f.n_desc_cells, f.n_degraded_cells, f.n_silent_cells,
               round(f.impacted_fraction, 3) AS impacted_fraction, f.n_service_down_alarms, f.evidence_ts,
               greatest(f.window_end + INTERVAL 2 MINUTES, coalesce(f.evidence_ts, f.window_end)) AS available_ts,
               round((unix_millis(greatest(f.window_end + INTERVAL 2 MINUTES, coalesce(f.evidence_ts, f.window_end)))
                      - unix_millis(i.impact_start_ts)) / 1000.0) AS seconds_after_impact_start
        FROM inc i JOIN telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m f
          ON f.source_run = i.source_run AND f.element_id = i.root_element_id
         AND f.window_end > i.impact_start_ts AND f.window_start < i.impact_end_ts
        WHERE f.impacted_fraction >= 0.8 OR f.n_service_down_alarms > 0
        ORDER BY f.window_start
```

| window_start | window_end | element_id | n_desc_cells | n_degraded_cells | n_silent_cells | impacted_fraction | n_service_down_alarms | evidence_ts | available_ts | seconds_after_impact_start |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-03T10:15:00.000Z | 2026-10-03T10:20:00.000Z | AMF-VIC-01 | 528 | 518 | 10 | 1.0 | 0 | 2026-10-03T10:34:00.000Z | 2026-10-03T10:34:00.000Z | 1499 |

_1 row(s)_

## INC-00016: the root's descendant cell windows behind that rollup (late records used = 0)

```sql
WITH inc AS (SELECT * FROM telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents WHERE source_run = 'history' AND incident_id = 'INC-00016')
        SELECT h.window_start, count(*) AS cell_windows, count_if(h.is_degraded) AS degraded_cell_windows,
               sum(h.n_reports) AS records_used, sum(h.n_late_reports) AS late_records_used,
               max(CASE WHEN h.is_degraded THEN h.evidence_ts END) AS latest_qualifying_arrival
        FROM inc i JOIN telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m h
          ON h.source_run = i.source_run AND h.amf_id = i.root_element_id
         AND h.window_end > i.impact_start_ts AND h.window_start < i.impact_end_ts
        GROUP BY h.window_start ORDER BY h.window_start
```

| window_start | cell_windows | degraded_cell_windows | records_used | late_records_used | latest_qualifying_arrival |
|---|---|---|---|---|---|
| 2026-10-03T10:15:00.000Z | 518 | 518 | 518 | 0 | 2026-10-03T10:34:00.000Z |
| 2026-10-03T10:30:00.000Z | 524 | 0 | 524 | 0 | NULL |

_2 row(s)_

## Real-time vs retrospective 5-minute windows: late records

```sql
SELECT 'gold_cell_health_5m (real-time, scored)' AS table_name, count(*) AS windows,
               sum(n_reports) AS records, sum(n_late_reports) AS late_records FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m
        UNION ALL
        SELECT 'gold_cell_health_5m_retrospective (never scored)', count(*), sum(n_reports), sum(n_late_reports)
        FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m_retrospective
```

| table_name | windows | records | late_records |
|---|---|---|---|
| gold_cell_health_5m (real-time, scored) | 1987413 | 2382505 | 0 |
| gold_cell_health_5m_retrospective (never scored) | 2008061 | 2413825 | 24359 |

_2 row(s)_

## RCA topology-heuristic baseline (hit@1 / hit@3 vs root_element_ids)

```sql
SELECT source_run, fault_type, count(*) AS n, round(100.0 * avg(CAST(hit_at_1 AS INT)), 1) AS hit1_pct,
               round(100.0 * avg(CAST(hit_at_3 AS INT)), 1) AS hit3_pct
        FROM telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline GROUP BY GROUPING SETS ((source_run), (source_run, fault_type))
        ORDER BY source_run DESC, fault_type NULLS FIRST
```

| source_run | fault_type | n | hit1_pct | hit3_pct |
|---|---|---|---|---|
| stream | NULL | 26 | 53.8 | 73.1 |
| stream | AGG_ROUTER_FAILURE | 1 | 100.0 | 100.0 |
| stream | BACKHAUL_DEGRADATION | 3 | 100.0 | 100.0 |
| stream | CELL_OUTAGE | 20 | 40.0 | 65.0 |
| stream | SITE_POWER_OUTAGE | 2 | 100.0 | 100.0 |
| history | NULL | 19 | 57.9 | 68.4 |
| history | AGG_ROUTER_FAILURE | 2 | 100.0 | 100.0 |
| history | AMF_OVERLOAD | 1 | 100.0 | 100.0 |
| history | BACKHAUL_DEGRADATION | 1 | 100.0 | 100.0 |
| history | BUSHFIRE_GRID_OUTAGE | 1 | 100.0 | 100.0 |
| history | CELL_OUTAGE | 6 | 16.7 | 50.0 |
| history | CORE_CONGESTION | 2 | 0.0 | 0.0 |
| history | CYCLONE_BACKHAUL_CUT | 1 | 100.0 | 100.0 |
| history | LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 100.0 |
| history | PLANNED_MAINTENANCE | 2 | 100.0 | 100.0 |
| history | SITE_POWER_OUTAGE | 1 | 100.0 | 100.0 |
| history | TRAFFIC_SURGE | 1 | 0.0 | 0.0 |

_17 row(s)_
