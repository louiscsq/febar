# Time-to-detect against ground truth

Captured 2026-10-08 13:31 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

Scored incidents: customer-impacting and not censored. `ttd_s` = (evidence time + measured pipeline latency for live files) − `impact_start_ts`. `history` is the 15-minute-ROP backfill (cannot meet a 5-minute SLA by construction); `stream` is the 1-minute live feed. See docs/pipeline.md.

## Summary per run (median / p90 TTD, % within 5 minutes)

`event_class = ALL` covers every scored incident; `fault` excludes planned maintenance (which the NOC suppresses via the change calendar) and red herrings.

```sql
SELECT * FROM telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary WHERE fault_type = 'ALL' ORDER BY source_run, event_class
```

| source_run | event_class | fault_type | n_incidents | n_detected | detected_pct | median_ttd_s | p90_ttd_s | within_5min_pct | median_evidence_lag_s | median_pipeline_latency_s |
|---|---|---|---|---|---|---|---|---|---|---|
| history | ALL | ALL | 19 | 18 | 94.7 | 59.0 | 1200.8 | 73.7 | 59.0 | NULL |
| history | fault | ALL | 16 | 15 | 93.8 | 61.5 | 1057.0 | 75.0 | 61.5 | NULL |
| history | planned | ALL | 2 | 2 | 100.0 | 33.0 | 35.4 | 100.0 | 33.0 | NULL |
| history | red_herring | ALL | 1 | 1 | 100.0 | 1070.0 | 1070.0 | 0.0 | 1070.0 | NULL |
| stream | ALL | ALL | 16 | 16 | 100.0 | 119.9 | 364.8 | 87.5 | 76.0 | 35.9 |
| stream | fault | ALL | 7 | 7 | 100.0 | 130.0 | 662.1 | 71.4 | 73.0 | 30.2 |
| stream | planned | ALL | 9 | 9 | 100.0 | 118.7 | 131.2 | 100.0 | 79.0 | 40.9 |

_7 row(s)_

## Per fault type

```sql
SELECT * FROM telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary WHERE fault_type <> 'ALL' ORDER BY source_run, event_class, fault_type
```

| source_run | event_class | fault_type | n_incidents | n_detected | detected_pct | median_ttd_s | p90_ttd_s | within_5min_pct | median_evidence_lag_s | median_pipeline_latency_s |
|---|---|---|---|---|---|---|---|---|---|---|
| history | fault | AGG_ROUTER_FAILURE | 2 | 2 | 100.0 | 0.0 | 0.0 | 100.0 | 0.0 | NULL |
| history | fault | AMF_OVERLOAD | 1 | 1 | 100.0 | 390.0 | 390.0 | 0.0 | 390.0 | NULL |
| history | fault | BACKHAUL_DEGRADATION | 1 | 1 | 100.0 | 1724.0 | 1724.0 | 0.0 | 1724.0 | NULL |
| history | fault | BUSHFIRE_GRID_OUTAGE | 1 | 1 | 100.0 | 172.0 | 172.0 | 100.0 | 172.0 | NULL |
| history | fault | CELL_OUTAGE | 6 | 6 | 100.0 | 56.5 | 65.5 | 100.0 | 56.5 | NULL |
| history | fault | CORE_CONGESTION | 2 | 1 | 50.0 | 1067.0 | 1920.6 | 0.0 | 1067.0 | NULL |
| history | fault | CYCLONE_BACKHAUL_CUT | 1 | 1 | 100.0 | 0.0 | 0.0 | 100.0 | 0.0 | NULL |
| history | fault | LONG_HAUL_FIBRE_CUT | 1 | 1 | 100.0 | 178.0 | 178.0 | 100.0 | 178.0 | NULL |
| history | fault | SITE_POWER_OUTAGE | 1 | 1 | 100.0 | 75.0 | 75.0 | 100.0 | 75.0 | NULL |
| history | planned | PLANNED_MAINTENANCE | 2 | 2 | 100.0 | 33.0 | 35.4 | 100.0 | 33.0 | NULL |
| history | red_herring | TRAFFIC_SURGE | 1 | 1 | 100.0 | 1070.0 | 1070.0 | 0.0 | 1070.0 | NULL |
| stream | fault | BACKHAUL_DEGRADATION | 2 | 2 | 100.0 | 693.3 | 818.1 | 0.0 | 663.0 | 30.3 |
| stream | fault | CELL_OUTAGE | 3 | 3 | 100.0 | 79.2 | 86.5 | 100.0 | 49.0 | 30.2 |
| stream | fault | SITE_POWER_OUTAGE | 2 | 2 | 100.0 | 161.2 | 186.1 | 100.0 | 88.5 | 72.7 |
| stream | planned | PLANNED_MAINTENANCE | 9 | 9 | 100.0 | 118.7 | 131.2 | 100.0 | 79.0 | 40.9 |

_15 row(s)_

## Live-stream incidents

```sql
SELECT incident_id, fault_type, severity, region_code, root_element_id, impact_start_ts, is_detected,
               first_signal_source, first_element_id, first_flags, round(evidence_lag_s, 0) AS evidence_lag_s,
               round(first_pipeline_latency_s, 1) AS pipeline_latency_s, round(ttd_s, 1) AS ttd_s,
               detected_within_sla, root_detected
        FROM telco_netmon_febar_catalog.netmon_eval.eval_incident_detection WHERE source_run = 'stream' ORDER BY impact_start_ts
```

| incident_id | fault_type | severity | region_code | root_element_id | impact_start_ts | is_detected | first_signal_source | first_element_id | first_flags | evidence_lag_s | pipeline_latency_s | ttd_s | detected_within_sla | root_detected |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| INC-2026100812-00002 | SITE_POWER_OUTAGE | major | NSW | SITE-NSW-00052 | 2026-10-08T12:45:47.000Z | true | kpi | CELL-NSW-00052-5G2 | ["cell_unavailable","attach_failure","rrc_collapse","rrc_degradation"] | 73 | 119.3 | 192.3 | true | true |
| INC-2026100812-00003 | BACKHAUL_DEGRADATION | minor | VIC | BH-VIC-0015 | 2026-10-08T12:52:20.000Z | true | kpi | CELL-VIC-00031-4G2 | ["packet_loss"] | 820 | 29.3 | 849.3 | false | false |
| INC-2026100813-00001 | CELL_OUTAGE | minor | VIC | CELL-VIC-00089-5G1 | 2026-10-08T13:24:04.000Z | true | alarm | CELL-VIC-00089-5G1 | ["CELL_OUT_OF_SERVICE"] | 56 | 32.3 | 88.3 | true | true |
| INC-2026100813-00002 | SITE_POWER_OUTAGE | major | NQL | SITE-NQL-00017 | 2026-10-08T13:31:16.000Z | true | alarm | SITE-NQL-00017 | ["NE_UNREACHABLE"] | 104 | 26.0 | 130.0 | true | true |
| INC-2026100813-00003 | PLANNED_MAINTENANCE | critical | VIC | AGG-VIC-03 | 2026-10-08T13:42:21.000Z | true | kpi | CELL-VIC-00048-5G1 | ["cell_unavailable","attach_failure","rrc_collapse","rrc_degradation"] | 99 | 32.1 | 131.1 | true | true |
| INC-2026100813-00004 | BACKHAUL_DEGRADATION | major | NSW | BH-NSW-0003 | 2026-10-08T13:42:34.000Z | true | kpi | CELL-NSW-00007-4G2 | ["packet_loss"] | 506 | 31.3 | 537.3 | false | false |
| INC-2026100813-00005 | CELL_OUTAGE | minor | NSW | CELL-NSW-00085-4G1 | 2026-10-08T13:45:34.000Z | true | alarm | CELL-NSW-00085-4G1 | ["CELL_OUT_OF_SERVICE"] | 26 | 28.6 | 54.6 | true | true |
| INC-2026100813-00006 | PLANNED_MAINTENANCE | critical | NSW | AGG-NSW-04 | 2026-10-08T13:53:31.000Z | true | alarm | AGG-NSW-04 | ["NODE_DOWN"] | 89 | 39.4 | 128.4 | true | true |
| INC-2026100813-00008 | PLANNED_MAINTENANCE | major | NSW | SITE-NSW-00044 | 2026-10-08T14:00:27.000Z | true | alarm | SITE-NSW-00044 | ["NE_UNREACHABLE"] | 93 | 28.1 | 121.1 | true | true |
| INC-2026100814-00001 | CELL_OUTAGE | minor | WA | CELL-WA-00025-4G1 | 2026-10-08T14:02:11.000Z | true | alarm | CELL-WA-00025-4G1 | ["CELL_OUT_OF_SERVICE"] | 49 | 30.2 | 79.2 | true | true |
| INC-2026100814-00006 | PLANNED_MAINTENANCE | major | VIC | AGG-VIC-01 | 2026-10-08T14:39:05.000Z | true | alarm | AGG-VIC-01 | ["NODE_DOWN"] | 55 | 41.5 | 96.5 | true | true |
| INC-2026100813-00009 | PLANNED_MAINTENANCE | minor | NSW | SITE-NSW-00027 | 2026-10-08T14:47:08.000Z | true | alarm | SITE-NSW-00027 | ["NE_UNREACHABLE"] | 52 | 47.3 | 99.3 | true | true |
| INC-2026100814-00008 | PLANNED_MAINTENANCE | minor | NQL | SITE-NQL-00004 | 2026-10-08T14:50:29.000Z | true | alarm | SITE-NQL-00004 | ["NE_UNREACHABLE"] | 91 | 40.9 | 131.9 | true | true |
| INC-2026100813-00010 | PLANNED_MAINTENANCE | minor | NSW | SITE-NSW-00002 | 2026-10-08T14:53:03.000Z | true | alarm | SITE-NSW-00002 | ["NE_UNREACHABLE"] | 57 | 47.3 | 104.3 | true | true |
| INC-2026100814-00011 | PLANNED_MAINTENANCE | minor | NSW | SITE-NSW-00010 | 2026-10-08T15:24:41.000Z | true | kpi | CELL-NSW-00010-4G1 | ["cell_unavailable","attach_failure","rrc_collapse","rrc_degradation"] | 79 | 39.7 | 118.7 | true | true |
| INC-2026100814-00012 | PLANNED_MAINTENANCE | minor | VIC | SITE-VIC-00106 | 2026-10-08T15:27:27.000Z | true | alarm | SITE-VIC-00106 | ["NE_UNREACHABLE"] | 33 | 43.1 | 76.1 | true | true |

_16 row(s)_

## Ground-truth incidents in the live stream (incl. censored and non-impacting)

```sql
SELECT event_class, fault_type, is_customer_impacting, is_censored, count(*) AS n
        FROM telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents WHERE source_run = 'stream' GROUP BY ALL ORDER BY ALL
```

| event_class | fault_type | is_customer_impacting | is_censored | n |
|---|---|---|---|---|
| fault | AGG_ROUTER_FAILURE | true | true | 3 |
| fault | BACKHAUL_DEGRADATION | true | false | 2 |
| fault | BACKHAUL_DEGRADATION | true | true | 1 |
| fault | CELL_OUTAGE | true | false | 3 |
| fault | CELL_OUTAGE | true | true | 6 |
| fault | LONG_HAUL_FIBRE_CUT | true | true | 2 |
| fault | SITE_POWER_OUTAGE | true | false | 2 |
| fault | SITE_POWER_OUTAGE | true | true | 1 |
| planned | PLANNED_MAINTENANCE | true | false | 9 |
| red_herring | ALARM_STORM | false | false | 4 |
| red_herring | FLAPPING_ELEMENT | false | true | 2 |

_11 row(s)_

## Detection precision (detections explained by any ground-truth event)

```sql
SELECT * FROM telco_netmon_febar_catalog.netmon_eval.eval_detection_precision ORDER BY source_run, signal_source
```

| source_run | signal_source | n_detections | n_explained | n_fault | n_planned | n_red_herring | explained_pct | n_in_maintenance_window |
|---|---|---|---|---|---|---|---|---|
| history | alarm | 354 | 354 | 181 | 173 | 0 | 100.0 | 173 |
| history | kpi | 3385 | 2969 | 2454 | 344 | 171 | 87.7 | 344 |
| stream | alarm | 734 | 734 | 331 | 403 | 0 | 100.0 | 642 |
| stream | kpi | 28710 | 28706 | 18173 | 10533 | 0 | 100.0 | 23345 |

_4 row(s)_

## RCA topology-heuristic baseline (hit@1 / hit@3 vs root_element_ids)

```sql
SELECT source_run, fault_type, count(*) AS n, round(100.0 * avg(CAST(hit_at_1 AS INT)), 1) AS hit1_pct,
               round(100.0 * avg(CAST(hit_at_3 AS INT)), 1) AS hit3_pct
        FROM telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline GROUP BY GROUPING SETS ((source_run), (source_run, fault_type))
        ORDER BY source_run, fault_type NULLS FIRST
```

| source_run | fault_type | n | hit1_pct | hit3_pct |
|---|---|---|---|---|
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
| stream | NULL | 16 | 43.8 | 56.3 |
| stream | BACKHAUL_DEGRADATION | 2 | 0.0 | 50.0 |
| stream | CELL_OUTAGE | 3 | 33.3 | 33.3 |
| stream | PLANNED_MAINTENANCE | 9 | 44.4 | 55.6 |
| stream | SITE_POWER_OUTAGE | 2 | 100.0 | 100.0 |

_17 row(s)_
