# Time-to-detect, localisation and precision against ground truth

Captured 2026-10-08 15:31 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

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
| stream | fault | 31 | 31 | 100.0 | 111.7 | 265.3 | 90.3 | 30 | 96.8 | 113.5 | 87.1 | 74.0 | 39.8 |
| history | fault | 16 | 15 | 93.8 | 61.5 | 1057.0 | 75.0 | 14 | 87.5 | 61.5 | 68.8 | 61.5 | NULL |

_2 row(s)_

## All event classes

```sql
SELECT source_run, event_class, n_incidents, n_impact_detected, impact_detected_pct, impact_median_ttd_s, impact_p90_ttd_s, impact_within_5min_pct, n_root_localised, root_localised_pct, localisation_median_ttd_s, localised_within_5min_pct, median_evidence_lag_s, median_pipeline_latency_s FROM telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary WHERE fault_type = 'ALL'
        ORDER BY source_run DESC, CASE event_class WHEN 'fault' THEN 0 WHEN 'ALL' THEN 9 ELSE 1 END, event_class
```

| source_run | event_class | n_incidents | n_impact_detected | impact_detected_pct | impact_median_ttd_s | impact_p90_ttd_s | impact_within_5min_pct | n_root_localised | root_localised_pct | localisation_median_ttd_s | localised_within_5min_pct | median_evidence_lag_s | median_pipeline_latency_s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stream | fault | 31 | 31 | 100.0 | 111.7 | 265.3 | 90.3 | 30 | 96.8 | 113.5 | 87.1 | 74.0 | 39.8 |
| stream | planned | 4 | 4 | 100.0 | 112.8 | 123.0 | 100.0 | 4 | 100.0 | 112.8 | 100.0 | 81.0 | 36.8 |
| stream | ALL | 35 | 35 | 100.0 | 111.7 | 264.8 | 91.4 | 34 | 97.1 | 113.5 | 88.6 | 74.0 | 39.8 |
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
| stream | fault | AGG_ROUTER_FAILURE | 4 | 100.0 | 54.1 | 100.0 | 100.0 | 101.0 | 100.0 |
| stream | fault | BACKHAUL_DEGRADATION | 3 | 100.0 | 429.9 | 0.0 | 100.0 | 731.0 | 0.0 |
| stream | fault | CELL_OUTAGE | 19 | 100.0 | 109.4 | 100.0 | 100.0 | 109.4 | 100.0 |
| stream | fault | SITE_POWER_OUTAGE | 5 | 100.0 | 199.4 | 100.0 | 80.0 | 199.4 | 80.0 |
| stream | planned | PLANNED_MAINTENANCE | 4 | 100.0 | 112.8 | 100.0 | 100.0 | 112.8 | 100.0 |
| history | fault | AGG_ROUTER_FAILURE | 2 | 100.0 | 0.0 | 100.0 | 100.0 | 20.0 | 100.0 |
| history | fault | AMF_OVERLOAD | 1 | 100.0 | 390.0 | 0.0 | 100.0 | 127373.0 | 0.0 |
| history | fault | BACKHAUL_DEGRADATION | 1 | 100.0 | 1724.0 | 0.0 | 100.0 | 1909.0 | 0.0 |
| history | fault | BUSHFIRE_GRID_OUTAGE | 1 | 100.0 | 172.0 | 100.0 | 100.0 | 172.0 | 100.0 |
| history | fault | CELL_OUTAGE | 6 | 100.0 | 56.5 | 100.0 | 100.0 | 56.5 | 100.0 |
| history | fault | CORE_CONGESTION | 2 | 50.0 | 1067.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| history | fault | CYCLONE_BACKHAUL_CUT | 1 | 100.0 | 0.0 | 100.0 | 100.0 | 1720.0 | 0.0 |
| history | fault | LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 178.0 | 100.0 | 100.0 | 178.0 | 100.0 |
| history | fault | SITE_POWER_OUTAGE | 1 | 100.0 | 75.0 | 100.0 | 100.0 | 75.0 | 100.0 |
| history | planned | PLANNED_MAINTENANCE | 2 | 100.0 | 33.0 | 100.0 | 100.0 | 33.0 | 100.0 |
| history | red_herring | TRAFFIC_SURGE | 1 | 100.0 | 1070.0 | 0.0 | 100.0 | 2150.0 | 0.0 |

_16 row(s)_

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
| INC-2026100815-00001 | CELL_OUTAGE | CELL | 2026-10-08T15:01:46.000Z | true | alarm | CELL | 74 | 113.9 | 187.9 | true | true | detection | 187.9 |
| INC-2026100815-00003 | CELL_OUTAGE | CELL | 2026-10-08T15:11:13.000Z | true | alarm | CELL | 47 | 68.9 | 115.9 | true | true | detection | 115.9 |
| INC-2026100815-00007 | AGG_ROUTER_FAILURE | AGG_ROUTER | 2026-10-08T15:26:05.000Z | true | alarm | BACKHAUL_LINK | 0 | 99.1 | 94.1 | true | true | detection | 149.1 |
| INC-2026100815-00009 | AGG_ROUTER_FAILURE | AGG_ROUTER | 2026-10-08T15:37:30.000Z | true | alarm | BACKHAUL_LINK | 0 | 48.0 | 18.0 | true | true | detection | 89.1 |
| INC-2026100815-00002 | SITE_POWER_OUTAGE | SITE | 2026-10-08T15:47:24.000Z | true | alarm | SITE | 156 | 35.0 | 191.0 | true | true | detection | 191.0 |
| INC-2026100815-00011 | AGG_ROUTER_FAILURE | AGG_ROUTER | 2026-10-08T16:00:50.000Z | true | alarm | BACKHAUL_LINK | 10 | 44.2 | 54.2 | true | true | detection | 54.2 |
| INC-2026100816-00001 | CELL_OUTAGE | CELL | 2026-10-08T16:03:33.000Z | true | alarm | CELL | 87 | 36.2 | 123.2 | true | true | detection | 123.2 |
| INC-2026100815-00005 | SITE_POWER_OUTAGE | SITE | 2026-10-08T16:17:58.000Z | true | kpi | CELL | 62 | 22.2 | 84.2 | true | true | detection | 226.3 |
| INC-2026100816-00002 | CELL_OUTAGE | CELL | 2026-10-08T16:25:45.000Z | true | kpi | CELL | 75 | 34.4 | 109.4 | true | true | detection | 109.4 |
| INC-2026100815-00004 | SITE_POWER_OUTAGE | SITE | 2026-10-08T16:26:09.000Z | true | alarm | SITE | 171 | 28.4 | 199.4 | true | true | detection | 199.4 |
| INC-2026100816-00003 | CELL_OUTAGE | CELL | 2026-10-08T16:26:12.000Z | true | alarm | CELL | 108 | 33.4 | 141.4 | true | true | detection | 141.4 |
| INC-2026100816-00004 | CELL_OUTAGE | CELL | 2026-10-08T16:31:37.000Z | true | kpi | CELL | 83 | 36.0 | 119.0 | true | true | detection | 119.0 |
| INC-2026100816-00006 | CELL_OUTAGE | CELL | 2026-10-08T16:37:14.000Z | true | alarm | CELL | 46 | 42.0 | 88.0 | true | true | detection | 88.0 |
| INC-2026100816-00007 | CELL_OUTAGE | CELL | 2026-10-08T16:37:55.000Z | true | kpi | CELL | 65 | 41.0 | 106.0 | true | true | detection | 106.0 |
| INC-2026100816-00008 | CELL_OUTAGE | CELL | 2026-10-08T16:38:06.000Z | true | alarm | CELL | 54 | 44.9 | 98.9 | true | true | detection | 98.9 |
| INC-2026100815-00008 | SITE_POWER_OUTAGE | SITE | 2026-10-08T16:53:14.000Z | true | kpi | CELL | 226 | 39.3 | 265.3 | true | false | NULL | 0.0 |
| INC-2026100816-00011 | CELL_OUTAGE | CELL | 2026-10-08T16:56:50.000Z | true | kpi | CELL | 70 | 35.3 | 105.3 | true | true | detection | 105.3 |
| INC-2026100817-00001 | CELL_OUTAGE | CELL | 2026-10-08T17:10:42.000Z | true | alarm | CELL | 78 | 26.2 | 104.2 | true | true | detection | 104.2 |
| INC-2026100816-00010 | SITE_POWER_OUTAGE | SITE | 2026-10-08T17:25:10.000Z | true | alarm | SITE | 230 | 34.1 | 264.1 | true | true | detection | 264.1 |
| INC-2026100817-00002 | AGG_ROUTER_FAILURE | AGG_ROUTER | 2026-10-08T17:39:02.000Z | true | alarm | BACKHAUL_LINK | 0 | 55.9 | 53.9 | true | true | detection | 112.9 |
| INC-2026100817-00003 | CELL_OUTAGE | CELL | 2026-10-08T17:41:55.000Z | true | kpi | CELL | 65 | 27.9 | 92.9 | true | true | detection | 92.9 |
| INC-2026100817-00004 | BACKHAUL_DEGRADATION | BACKHAUL_LINK | 2026-10-08T17:42:50.000Z | true | kpi | CELL | 550 | 29.8 | 579.8 | false | true | rollup | 850.0 |
| INC-2026100817-00005 | CELL_OUTAGE | CELL | 2026-10-08T17:44:46.000Z | true | alarm | CELL | 74 | 37.7 | 111.7 | true | true | detection | 111.7 |
| INC-2026100817-00006 | BACKHAUL_DEGRADATION | BACKHAUL_LINK | 2026-10-08T17:44:49.000Z | true | kpi | CELL | 311 | 39.8 | 350.8 | false | true | rollup | 731.0 |
| INC-2026100817-00008 | CELL_OUTAGE | CELL | 2026-10-08T17:50:59.000Z | true | alarm | CELL | 61 | 38.1 | 99.1 | true | true | detection | 99.1 |
| INC-2026100817-00009 | CELL_OUTAGE | CELL | 2026-10-08T17:55:12.000Z | true | alarm | CELL | 48 | 53.2 | 101.2 | true | true | detection | 101.2 |
| INC-2026100818-00002 | CELL_OUTAGE | CELL | 2026-10-08T18:13:07.000Z | true | kpi | CELL | 113 | 42.5 | 155.5 | true | true | detection | 155.5 |
| INC-2026100818-00003 | CELL_OUTAGE | CELL | 2026-10-08T18:23:29.000Z | true | kpi | CELL | 91 | 40.2 | 131.2 | true | true | detection | 131.2 |
| INC-2026100818-00005 | BACKHAUL_DEGRADATION | BACKHAUL_LINK | 2026-10-08T18:40:43.000Z | true | kpi | CELL | 377 | 52.9 | 429.9 | false | true | rollup | 677.0 |
| INC-2026100818-00008 | CELL_OUTAGE | CELL | 2026-10-08T18:57:18.000Z | true | alarm | CELL | 42 | 45.7 | 87.7 | true | true | detection | 87.7 |
| INC-2026100819-00001 | CELL_OUTAGE | CELL | 2026-10-08T19:01:54.000Z | true | kpi | CELL | 66 | 47.5 | 113.5 | true | true | detection | 113.5 |

_31 row(s)_

## Ground-truth incidents in the live stream (incl. censored and non-impacting)

```sql
SELECT event_class, fault_type, is_customer_impacting, is_censored, count(*) AS n
        FROM telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents WHERE source_run = 'stream' GROUP BY ALL ORDER BY ALL
```

| event_class | fault_type | is_customer_impacting | is_censored | n |
|---|---|---|---|---|
| fault | AGG_ROUTER_FAILURE | true | false | 4 |
| fault | BACKHAUL_DEGRADATION | true | false | 3 |
| fault | BACKHAUL_DEGRADATION | true | true | 1 |
| fault | CELL_OUTAGE | true | false | 19 |
| fault | CELL_OUTAGE | true | true | 9 |
| fault | SITE_POWER_OUTAGE | true | false | 5 |
| fault | SITE_POWER_OUTAGE | true | true | 4 |
| planned | PLANNED_MAINTENANCE | true | false | 4 |
| red_herring | ALARM_STORM | false | false | 5 |
| red_herring | FLAPPING_ELEMENT | false | true | 2 |

_10 row(s)_

## Fault-detection precision and maintenance suppression

Each detection labelled in priority order: uncensored fault = TP; overlapping a censored incident = excluded; planned work = suppressed when `in_maintenance` (else a false page); red herring (e.g. TRAFFIC_SURGE) = FP; nothing = FP. `fault_precision_pct` = TP / (TP + FP).

```sql
SELECT * FROM telco_netmon_febar_catalog.netmon_eval.eval_detection_precision
        ORDER BY source_run DESC, CASE signal_source WHEN 'ALL' THEN 0 ELSE 1 END, signal_source
```

| source_run | signal_source | n_detections | n_fault_tp | n_censored_excluded | n_planned | n_planned_suppressed | n_planned_unsuppressed_fp | n_red_herring_fp | n_unexplained_fp | fault_precision_pct | maintenance_suppression_pct | n_other_in_maintenance |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stream | ALL | 20013 | 18117 | 594 | 1301 | 1267 | 34 | 0 | 1 | 99.8 | 97.4 | 0 |
| stream | alarm | 313 | 233 | 13 | 67 | 60 | 7 | 0 | 0 | 97.1 | 89.6 | 0 |
| stream | kpi | 19700 | 17884 | 581 | 1234 | 1207 | 27 | 0 | 1 | 99.8 | 97.8 | 0 |
| history | ALL | 3739 | 2635 | 0 | 517 | 517 | 0 | 171 | 416 | 81.8 | 100.0 | 0 |
| history | alarm | 354 | 181 | 0 | 173 | 173 | 0 | 0 | 0 | 100.0 | 100.0 | 0 |
| history | kpi | 3385 | 2454 | 0 | 344 | 344 | 0 | 171 | 416 | 80.7 | 100.0 | 0 |

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
| stream | NULL | 35 | 34.3 | 51.4 |
| stream | AGG_ROUTER_FAILURE | 4 | 75.0 | 100.0 |
| stream | BACKHAUL_DEGRADATION | 3 | 66.7 | 100.0 |
| stream | CELL_OUTAGE | 19 | 15.8 | 21.1 |
| stream | PLANNED_MAINTENANCE | 4 | 50.0 | 75.0 |
| stream | SITE_POWER_OUTAGE | 5 | 40.0 | 80.0 |
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

_18 row(s)_
