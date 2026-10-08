# Time-to-detect, localisation and precision against ground truth

Captured 2026-10-08 18:04 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

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
| stream | fault | 26 | 26 | 100.0 | 126.8 | 244.8 | 92.3 | 26 | 100.0 | 126.8 | 92.3 | 88.5 | 36.3 |
| history | fault | 16 | 15 | 93.8 | 61.5 | 1057.0 | 75.0 | 14 | 87.5 | 61.5 | 68.8 | 61.5 | NULL |

_2 row(s)_

## All event classes

```sql
SELECT source_run, event_class, n_incidents, n_impact_detected, impact_detected_pct, impact_median_ttd_s, impact_p90_ttd_s, impact_within_5min_pct, n_root_localised, root_localised_pct, localisation_median_ttd_s, localised_within_5min_pct, median_evidence_lag_s, median_pipeline_latency_s FROM telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary WHERE fault_type = 'ALL'
        ORDER BY source_run DESC, CASE event_class WHEN 'fault' THEN 0 WHEN 'ALL' THEN 9 ELSE 1 END, event_class
```

| source_run | event_class | n_incidents | n_impact_detected | impact_detected_pct | impact_median_ttd_s | impact_p90_ttd_s | impact_within_5min_pct | n_root_localised | root_localised_pct | localisation_median_ttd_s | localised_within_5min_pct | median_evidence_lag_s | median_pipeline_latency_s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stream | fault | 26 | 26 | 100.0 | 126.8 | 244.8 | 92.3 | 26 | 100.0 | 126.8 | 92.3 | 88.5 | 36.3 |
| stream | planned | 2 | 2 | 100.0 | 160.7 | 167.5 | 100.0 | 2 | 100.0 | 160.7 | 100.0 | 80.5 | 80.2 |
| stream | ALL | 28 | 28 | 100.0 | 127.9 | 235.4 | 92.9 | 28 | 100.0 | 127.9 | 92.9 | 88.5 | 37.0 |
| history | fault | 16 | 15 | 93.8 | 61.5 | 1057.0 | 75.0 | 14 | 87.5 | 61.5 | 68.8 | 61.5 | NULL |
| history | planned | 2 | 2 | 100.0 | 33.0 | 35.4 | 100.0 | 2 | 100.0 | 33.0 | 100.0 | 33.0 | NULL |
| history | red_herring | 1 | 1 | 100.0 | 1070.0 | 1070.0 | 0.0 | 1 | 100.0 | 2150.0 | 0.0 | 1070.0 | NULL |
| history | ALL | 19 | 18 | 94.7 | 59.0 | 1200.8 | 73.7 | 17 | 89.5 | 59.0 | 68.4 | 59.0 | NULL |

_7 row(s)_

## Per fault type

```sql
SELECT source_run, event_class, fault_type, n_incidents, impact_detected_pct, impact_median_ttd_s,
               impact_within_5min_pct, root_localised_pct, localisation_median_ttd_s, localised_within_5min_pct
        FROM telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary WHERE fault_type <> 'ALL'
        ORDER BY source_run DESC, CASE event_class WHEN 'fault' THEN 0 ELSE 1 END, event_class, fault_type
```

| source_run | event_class | fault_type | n_incidents | impact_detected_pct | impact_median_ttd_s | impact_within_5min_pct | root_localised_pct | localisation_median_ttd_s | localised_within_5min_pct |
|---|---|---|---|---|---|---|---|---|---|
| stream | fault | BACKHAUL_DEGRADATION | 2 | 100.0 | 621.5 | 0.0 | 100.0 | 939.0 | 0.0 |
| stream | fault | CELL_OUTAGE | 22 | 100.0 | 119.0 | 100.0 | 100.0 | 119.0 | 100.0 |
| stream | fault | SITE_POWER_OUTAGE | 2 | 100.0 | 205.3 | 100.0 | 100.0 | 205.3 | 100.0 |
| stream | planned | PLANNED_MAINTENANCE | 2 | 100.0 | 160.7 | 100.0 | 100.0 | 160.7 | 100.0 |
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
| INC-2026100817-00001 | CELL_OUTAGE | CELL | 2026-10-08T17:27:34.000Z | true | alarm | CELL | 86 | 135.2 | 221.2 | true | true | detection | 221.2 |
| INC-2026100818-00001 | CELL_OUTAGE | CELL | 2026-10-08T18:04:53.000Z | true | alarm | CELL | 67 | 48.2 | 115.2 | true | true | detection | 115.2 |
| INC-2026100818-00002 | CELL_OUTAGE | CELL | 2026-10-08T18:10:40.000Z | true | alarm | CELL | 80 | 38.2 | 118.2 | true | true | detection | 118.2 |
| INC-2026100818-00004 | CELL_OUTAGE | CELL | 2026-10-08T18:23:29.000Z | true | kpi | CELL | 91 | 35.0 | 126.0 | true | true | detection | 126.0 |
| INC-2026100818-00005 | CELL_OUTAGE | CELL | 2026-10-08T18:28:54.000Z | true | alarm | CELL | 66 | 24.9 | 90.9 | true | true | detection | 90.9 |
| INC-2026100818-00006 | CELL_OUTAGE | CELL | 2026-10-08T18:36:58.000Z | true | kpi | CELL | 62 | 30.0 | 92.0 | true | true | detection | 92.0 |
| INC-2026100818-00007 | BACKHAUL_DEGRADATION | BACKHAUL_LINK | 2026-10-08T18:40:43.000Z | true | kpi | CELL | 377 | 43.3 | 420.3 | false | true | rollup | 677.0 |
| INC-2026100818-00008 | CELL_OUTAGE | CELL | 2026-10-08T18:48:54.000Z | true | alarm | CELL | 66 | 31.4 | 97.4 | true | true | detection | 97.4 |
| INC-2026100818-00009 | CELL_OUTAGE | CELL | 2026-10-08T18:49:56.000Z | true | kpi | CELL | 64 | 35.3 | 99.3 | true | true | detection | 99.3 |
| INC-2026100818-00003 | SITE_POWER_OUTAGE | SITE | 2026-10-08T19:05:22.000Z | true | alarm | SITE | 98 | 44.4 | 142.4 | true | true | detection | 142.4 |
| INC-2026100819-00001 | CELL_OUTAGE | CELL | 2026-10-08T19:12:29.000Z | true | kpi | CELL | 91 | 37.2 | 128.2 | true | true | detection | 128.2 |
| INC-2026100819-00003 | CELL_OUTAGE | CELL | 2026-10-08T19:22:09.000Z | true | alarm | CELL | 51 | 35.8 | 86.8 | true | true | detection | 86.8 |
| INC-2026100819-00005 | CELL_OUTAGE | CELL | 2026-10-08T19:29:23.000Z | true | alarm | CELL | 97 | 44.1 | 141.1 | true | true | detection | 141.1 |
| INC-2026100819-00007 | CELL_OUTAGE | CELL | 2026-10-08T19:57:28.000Z | true | alarm | CELL | 92 | 35.6 | 127.6 | true | true | detection | 127.6 |
| INC-2026100820-00001 | CELL_OUTAGE | CELL | 2026-10-08T20:14:15.000Z | true | alarm | CELL | 45 | 44.3 | 89.3 | true | true | detection | 89.3 |
| INC-2026100820-00002 | CELL_OUTAGE | CELL | 2026-10-08T20:16:43.000Z | true | kpi | CELL | 77 | 34.3 | 111.3 | true | true | detection | 111.3 |
| INC-2026100820-00003 | CELL_OUTAGE | CELL | 2026-10-08T20:23:10.000Z | true | alarm | CELL | 110 | 35.8 | 145.8 | true | true | detection | 145.8 |
| INC-2026100820-00004 | CELL_OUTAGE | CELL | 2026-10-08T20:26:14.000Z | true | alarm | CELL | 106 | 34.0 | 140.0 | true | true | detection | 140.0 |
| INC-2026100820-00005 | CELL_OUTAGE | CELL | 2026-10-08T20:34:08.000Z | true | alarm | CELL | 112 | 34.4 | 146.4 | true | true | detection | 146.4 |
| INC-2026100819-00002 | SITE_POWER_OUTAGE | SITE | 2026-10-08T20:36:10.000Z | true | alarm | SITE | 230 | 38.3 | 268.3 | true | true | detection | 268.3 |
| INC-2026100820-00006 | BACKHAUL_DEGRADATION | BACKHAUL_LINK | 2026-10-08T20:36:59.000Z | true | kpi | CELL | 781 | 41.7 | 822.7 | false | true | rollup | 1201.0 |
| INC-2026100820-00007 | CELL_OUTAGE | CELL | 2026-10-08T20:54:00.000Z | true | alarm | CELL | 120 | 32.5 | 152.5 | true | true | detection | 152.5 |
| INC-2026100820-00009 | CELL_OUTAGE | CELL | 2026-10-08T20:55:15.000Z | true | alarm | CELL | 45 | 32.5 | 77.5 | true | true | detection | 77.5 |
| INC-2026100821-00002 | CELL_OUTAGE | CELL | 2026-10-08T21:59:22.000Z | true | alarm | CELL | 98 | 42.8 | 140.8 | true | true | detection | 140.8 |
| INC-2026100822-00001 | CELL_OUTAGE | CELL | 2026-10-08T22:01:37.000Z | true | alarm | CELL | 83 | 36.8 | 119.8 | true | true | detection | 119.8 |
| INC-2026100822-00006 | CELL_OUTAGE | CELL | 2026-10-08T22:37:30.000Z | true | alarm | CELL | 30 | 42.7 | 72.7 | true | true | detection | 72.7 |

_26 row(s)_

## Ground-truth incidents in the live stream (incl. censored and non-impacting)

```sql
SELECT event_class, fault_type, is_customer_impacting, is_censored, count(*) AS n
        FROM telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents WHERE source_run = 'stream' GROUP BY ALL ORDER BY ALL
```

| event_class | fault_type | is_customer_impacting | is_censored | n |
|---|---|---|---|---|
| fault | AGG_ROUTER_FAILURE | true | true | 1 |
| fault | BACKHAUL_DEGRADATION | true | false | 2 |
| fault | BACKHAUL_DEGRADATION | true | true | 4 |
| fault | CELL_OUTAGE | false | true | 1 |
| fault | CELL_OUTAGE | true | false | 22 |
| fault | CELL_OUTAGE | true | true | 5 |
| fault | SITE_POWER_OUTAGE | false | true | 1 |
| fault | SITE_POWER_OUTAGE | true | false | 2 |
| fault | SITE_POWER_OUTAGE | true | true | 1 |
| planned | PLANNED_MAINTENANCE | true | false | 2 |
| red_herring | ALARM_STORM | false | false | 4 |
| red_herring | FLAPPING_ELEMENT | false | true | 2 |

_12 row(s)_

## Alert-level fault precision (detections grouped per element per episode)

An alert = the detections on one element of one run until one starts > 10 min after the previous signal ended (one page). It takes the highest-priority label of its rows; suppressed when its first row is in a change window. `alert_fault_precision_pct` = TP alerts / (TP + FP alerts).

```sql
SELECT * FROM telco_netmon_febar_catalog.netmon_eval.eval_alert_precision
        ORDER BY source_run DESC, CASE signal_source WHEN 'ALL' THEN 0 ELSE 1 END, signal_source
```

| source_run | signal_source | n_alerts | n_fault_tp | n_censored_excluded | n_planned | n_planned_suppressed | n_planned_unsuppressed_fp | n_red_herring_fp | n_unexplained_fp | alert_fault_precision_pct | maintenance_suppression_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| stream | ALL | 191 | 65 | 74 | 11 | 11 | 0 | 0 | 41 | 61.3 | 100.0 |
| stream | alarm | 20 | 2 | 16 | 2 | 2 | 0 | 0 | 0 | 100.0 | 100.0 |
| stream | kpi | 171 | 63 | 58 | 9 | 9 | 0 | 0 | 41 | 60.6 | 100.0 |
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
| stream | ALL | 6721 | 4699 | 1608 | 360 | 360 | 0 | 0 | 54 | 98.9 | 100.0 |
| stream | alarm | 79 | 24 | 44 | 11 | 11 | 0 | 0 | 0 | 100.0 | 100.0 |
| stream | kpi | 6642 | 4675 | 1564 | 349 | 349 | 0 | 0 | 54 | 98.9 | 100.0 |
| history | ALL | 3739 | 2635 | 0 | 517 | 517 | 0 | 171 | 416 | 81.8 | 100.0 |
| history | alarm | 354 | 181 | 0 | 173 | 173 | 0 | 0 | 0 | 100.0 | 100.0 |
| history | kpi | 3385 | 2454 | 0 | 344 | 344 | 0 | 171 | 416 | 80.7 | 100.0 |

_6 row(s)_

## RCA topology-heuristic baseline (hit@1 / hit@3 vs root_element_ids)

```sql
SELECT source_run, fault_type, count(*) AS n, round(100.0 * avg(CAST(hit_at_1 AS INT)), 1) AS hit1_pct,
               round(100.0 * avg(CAST(hit_at_3 AS INT)), 1) AS hit3_pct
        FROM telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline GROUP BY GROUPING SETS ((source_run), (source_run, fault_type))
        ORDER BY source_run DESC, fault_type NULLS FIRST
```

| source_run | fault_type | n | hit1_pct | hit3_pct |
|---|---|---|---|---|
| stream | NULL | 28 | 39.3 | 57.1 |
| stream | BACKHAUL_DEGRADATION | 2 | 100.0 | 100.0 |
| stream | CELL_OUTAGE | 22 | 31.8 | 45.5 |
| stream | PLANNED_MAINTENANCE | 2 | 50.0 | 100.0 |
| stream | SITE_POWER_OUTAGE | 2 | 50.0 | 100.0 |
| history | NULL | 19 | 63.2 | 73.7 |
| history | AGG_ROUTER_FAILURE | 2 | 100.0 | 100.0 |
| history | AMF_OVERLOAD | 1 | 100.0 | 100.0 |
| history | BACKHAUL_DEGRADATION | 1 | 100.0 | 100.0 |
| history | BUSHFIRE_GRID_OUTAGE | 1 | 100.0 | 100.0 |
| history | CELL_OUTAGE | 6 | 33.3 | 66.7 |
| history | CORE_CONGESTION | 2 | 0.0 | 0.0 |
| history | CYCLONE_BACKHAUL_CUT | 1 | 100.0 | 100.0 |
| history | LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 100.0 |
| history | PLANNED_MAINTENANCE | 2 | 100.0 | 100.0 |
| history | SITE_POWER_OUTAGE | 1 | 100.0 | 100.0 |
| history | TRAFFIC_SURGE | 1 | 0.0 | 0.0 |

_17 row(s)_
