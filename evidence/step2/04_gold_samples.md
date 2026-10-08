# Sample gold rows

Captured 2026-10-08 19:38 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

## gold_cell_health_5m: degraded windows in the live stream

```sql
SELECT window_start, cell_id, region_code, n_reports, round(availability_pct, 1) AS avail,
               round(latency_ms, 1) AS latency, round(b_latency_ms_mean, 1) AS base_latency,
               round(latency_ms_z, 1) AS latency_z, round(dl_throughput_mbps_z, 1) AS dl_z, flags
        FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m WHERE is_degraded
        ORDER BY window_start DESC, cell_id LIMIT 12
```

| window_start | cell_id | region_code | n_reports | avail | latency | base_latency | latency_z | dl_z | flags |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T00:45:00.000Z | CELL-NSW-00025-4G1 | NSW | 5 | 100.0 | 132.1 | 43.9 | 28.1 | -5.3 | ["latency_degradation","packet_loss"] |
| 2026-10-09T00:45:00.000Z | CELL-NSW-00025-4G2 | NSW | 5 | 100.0 | 129.6 | 40.8 | 24.1 | -4.2 | ["latency_degradation","packet_loss"] |
| 2026-10-09T00:45:00.000Z | CELL-NSW-00025-4G3 | NSW | 5 | 100.0 | 129.3 | 38.4 | 34.6 | -3.2 | ["latency_degradation","packet_loss"] |
| 2026-10-09T00:45:00.000Z | CELL-NSW-00030-4G1 | NSW | 5 | 100.0 | 95.6 | 40.8 | 18.1 | -2.8 | ["latency_degradation","packet_loss"] |
| 2026-10-09T00:45:00.000Z | CELL-NSW-00030-4G2 | NSW | 5 | 100.0 | 101.0 | 41.7 | 17.3 | -2.8 | ["latency_degradation","packet_loss"] |
| 2026-10-09T00:45:00.000Z | CELL-NSW-00030-4G3 | NSW | 5 | 100.0 | 103.6 | 39.4 | 16.4 | -3.6 | ["latency_degradation","packet_loss"] |
| 2026-10-09T00:45:00.000Z | CELL-NSW-00031-4G1 | NSW | 5 | 100.0 | 101.8 | 38.8 | 21.0 | -2.6 | ["latency_degradation","packet_loss"] |
| 2026-10-09T00:45:00.000Z | CELL-NSW-00031-4G2 | NSW | 5 | 100.0 | 102.4 | 41.4 | 20.0 | -2.3 | ["latency_degradation","packet_loss"] |
| 2026-10-09T00:45:00.000Z | CELL-NSW-00031-4G3 | NSW | 5 | 100.0 | 97.3 | 38.3 | 16.5 | -2.0 | ["latency_degradation","packet_loss"] |
| 2026-10-09T00:45:00.000Z | CELL-NSW-00031-5G1 | NSW | 5 | 100.0 | 83.2 | 20.4 | 26.4 | -2.5 | ["latency_degradation","packet_loss"] |
| 2026-10-09T00:45:00.000Z | CELL-NSW-00031-5G2 | NSW | 5 | 100.0 | 77.7 | 16.4 | 30.6 | -3.4 | ["latency_degradation","packet_loss"] |
| 2026-10-09T00:45:00.000Z | CELL-NSW-00031-5G3 | NSW | 4 | 100.0 | 77.1 | 17.9 | 29.6 | -2.6 | ["latency_degradation","packet_loss"] |

_12 row(s)_

## gold_cell_health_1m: one healthy cell, latest windows

```sql
WITH c AS (SELECT cell_id FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m WHERE granularity_s = 60 AND NOT is_degraded
                   ORDER BY window_start DESC, cell_id LIMIT 1)
        SELECT window_start, window_start_local, cell_id, round(latency_ms, 1) AS latency,
               round(b_latency_ms_mean, 1) AS base_mean, round(b_latency_ms_std, 2) AS base_std,
               round(latency_ms_z, 2) AS z, is_degraded
        FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m WHERE cell_id = (SELECT cell_id FROM c) ORDER BY window_start DESC LIMIT 8
```

| window_start | window_start_local | cell_id | latency | base_mean | base_std | z | is_degraded |
|---|---|---|---|---|---|---|---|
| 2026-10-09T00:51:00.000Z | 2026-10-09T10:51:00.000Z | CELL-NQL-00001-4G1 | 82.2 | 84.2 | 6.5 | -0.3 | false |
| 2026-10-09T00:50:00.000Z | 2026-10-09T10:50:00.000Z | CELL-NQL-00001-4G1 | 87.8 | 84.2 | 6.5 | 0.56 | false |
| 2026-10-09T00:49:00.000Z | 2026-10-09T10:49:00.000Z | CELL-NQL-00001-4G1 | 79.5 | 84.2 | 6.5 | -0.72 | false |
| 2026-10-09T00:48:00.000Z | 2026-10-09T10:48:00.000Z | CELL-NQL-00001-4G1 | 87.3 | 84.2 | 6.5 | 0.48 | false |
| 2026-10-09T00:47:00.000Z | 2026-10-09T10:47:00.000Z | CELL-NQL-00001-4G1 | 85.1 | 84.2 | 6.5 | 0.15 | false |
| 2026-10-09T00:46:00.000Z | 2026-10-09T10:46:00.000Z | CELL-NQL-00001-4G1 | 74.8 | 84.2 | 6.5 | -1.44 | false |
| 2026-10-09T00:45:00.000Z | 2026-10-09T10:45:00.000Z | CELL-NQL-00001-4G1 | 90.7 | 84.2 | 6.5 | 1.01 | false |
| 2026-10-09T00:44:00.000Z | 2026-10-09T10:44:00.000Z | CELL-NQL-00001-4G1 | 81.7 | 84.2 | 6.5 | -0.38 | false |

_8 row(s)_

## gold_cell_baseline: sample

```sql
SELECT valid_date, cell_id, local_hour, day_type, n_days, n_samples, round(b_latency_ms_mean, 1) AS lat_mean,
               round(b_latency_ms_std, 2) AS lat_std, round(b_dl_throughput_mbps_mean, 1) AS dl_mean
        FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline ORDER BY valid_date DESC, cell_id, local_hour LIMIT 6
```

| valid_date | cell_id | local_hour | day_type | n_days | n_samples | lat_mean | lat_std | dl_mean |
|---|---|---|---|---|---|---|---|---|
| 2026-10-10 | CELL-NQL-00001-4G1 | 0 | weekend | 4 | 16 | 81.1 | 6.06 | 92.9 |
| 2026-10-10 | CELL-NQL-00001-4G1 | 0 | weekday | 9 | 36 | 81.0 | 7.0 | 90.2 |
| 2026-10-10 | CELL-NQL-00001-4G1 | 1 | weekday | 9 | 36 | 82.9 | 6.56 | 91.8 |
| 2026-10-10 | CELL-NQL-00001-4G1 | 1 | weekend | 4 | 16 | 82.3 | 4.93 | 90.6 |
| 2026-10-10 | CELL-NQL-00001-4G1 | 2 | weekday | 9 | 35 | 82.2 | 7.75 | 91.5 |
| 2026-10-10 | CELL-NQL-00001-4G1 | 2 | weekend | 4 | 16 | 79.5 | 7.88 | 91.3 |

_6 row(s)_

## gold_impact_detections: latest live detections

```sql
SELECT detected_ts, signal_source, element_type, element_id, region_code, signal_start_ts, evidence_ts,
               round(pipeline_latency_s, 1) AS pipeline_latency_s, flags, severity_score, in_maintenance
        FROM telco_netmon_febar_catalog.netmon_gold.gold_impact_detections WHERE landed_ts IS NOT NULL ORDER BY detected_ts DESC LIMIT 12
```

| detected_ts | signal_source | element_type | element_id | region_code | signal_start_ts | evidence_ts | pipeline_latency_s | flags | severity_score | in_maintenance |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-08T19:27:05.162Z | alarm | AGG_ROUTER | AGG-NQL-03 | NQL | 2026-10-08T23:18:44.000Z | 2026-10-09T00:56:00.000Z | 81.2 | ["NODE_DOWN"] | 3 | false |
| 2026-10-08T19:27:01.057Z | kpi | CELL | CELL-NSW-00030-4G1 | NSW | 2026-10-09T00:52:00.000Z | 2026-10-09T00:54:00.000Z | 84.1 | ["latency_degradation","packet_loss"] | 1 | false |
| 2026-10-08T19:27:01.057Z | kpi | CELL | CELL-VIC-00106-4G1 | VIC | 2026-10-08T21:11:00.000Z | 2026-10-09T00:56:00.000Z | 77.1 | ["latency_degradation","packet_loss"] | 1 | false |
| 2026-10-08T19:27:01.057Z | kpi | CELL | CELL-NSW-00123-4G3 | NSW | 2026-10-09T00:52:00.000Z | 2026-10-09T00:54:00.000Z | 84.1 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | false |
| 2026-10-08T19:27:01.057Z | kpi | CELL | CELL-NSW-00111-5G1 | NSW | 2026-10-09T00:18:00.000Z | 2026-10-09T00:56:00.000Z | 77.1 | ["latency_degradation","packet_loss"] | 1 | false |
| 2026-10-08T19:27:01.057Z | kpi | CELL | CELL-NSW-00051-4G3 | NSW | 2026-10-09T00:53:00.000Z | 2026-10-09T00:55:00.000Z | 79.1 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | false |
| 2026-10-08T19:27:01.057Z | kpi | CELL | CELL-NSW-00031-5G2 | NSW | 2026-10-09T00:52:00.000Z | 2026-10-09T00:54:00.000Z | 84.1 | ["latency_degradation","packet_loss"] | 1 | false |
| 2026-10-08T19:27:01.057Z | kpi | CELL | CELL-NSW-00031-5G1 | NSW | 2026-10-09T00:52:00.000Z | 2026-10-09T00:54:00.000Z | 84.1 | ["latency_degradation","packet_loss"] | 1 | false |
| 2026-10-08T19:27:01.057Z | kpi | CELL | CELL-VIC-00011-4G3 | VIC | 2026-10-09T00:53:00.000Z | 2026-10-09T00:55:00.000Z | 79.1 | ["latency_degradation","packet_loss","rrc_degradation","drop_rate_spike"] | 1 | false |
| 2026-10-08T19:27:01.057Z | kpi | CELL | CELL-NSW-00036-5G2 | NSW | 2026-10-09T00:52:00.000Z | 2026-10-09T00:54:00.000Z | 84.1 | ["latency_degradation","packet_loss"] | 1 | false |
| 2026-10-08T19:27:01.057Z | kpi | CELL | CELL-VIC-00005-4G2 | VIC | 2026-10-09T00:54:00.000Z | 2026-10-09T00:56:00.000Z | 77.1 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | false |
| 2026-10-08T19:27:01.057Z | kpi | CELL | CELL-VIC-00010-5G1 | VIC | 2026-10-09T00:54:00.000Z | 2026-10-09T00:56:00.000Z | 77.1 | ["latency_degradation","packet_loss","throughput_collapse","rrc_degradation","drop_rate_spike"] | 1 | false |

_12 row(s)_

## gold_impact_detections: pipeline latency (live files)

```sql
SELECT signal_source, count(*) AS n, round(percentile(pipeline_latency_s, 0.5), 1) AS p50_s,
               round(percentile(pipeline_latency_s, 0.9), 1) AS p90_s, round(max(pipeline_latency_s), 1) AS max_s
        FROM telco_netmon_febar_catalog.netmon_gold.gold_impact_detections WHERE landed_ts IS NOT NULL GROUP BY signal_source
```

| signal_source | n | p50_s | p90_s | max_s |
|---|---|---|---|---|
| alarm | 73 | 59.2 | 71.9 | 164.8 |
| kpi | 8262 | 46.8 | 70.2 | 181.7 |

_2 row(s)_

## gold_element_impact_5m: top root-cause candidates in the live stream

```sql
SELECT window_start, element_id, element_type, n_desc_cells, n_impacted_cells, n_silent_cells,
               round(impacted_fraction, 2) AS frac, n_impacted_children, n_children,
               round(parent_impacted_fraction, 2) AS parent_frac, n_alarms, n_service_down_alarms, alarm_codes
        FROM telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m
        WHERE window_start >= (SELECT max(window_start) - INTERVAL 3 HOURS FROM telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m)
          AND element_type <> 'CELL' AND n_impacted_cells >= 2
        ORDER BY n_impacted_cells DESC, level LIMIT 12
```

| window_start | element_id | element_type | n_desc_cells | n_impacted_cells | n_silent_cells | frac | n_impacted_children | n_children | parent_frac | n_alarms | n_service_down_alarms | alarm_codes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T00:15:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 39 | 9 | 0.06 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-09T00:15:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 39 | 9 | 0.06 | 4 | 4 | 0.06 | 0 | 0 | NULL |
| 2026-10-09T00:05:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 38 | 0 | 0.06 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-09T00:10:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 38 | 9 | 0.06 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-09T00:20:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 38 | 9 | 0.06 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-09T00:05:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 38 | 0 | 0.06 | 4 | 4 | 0.06 | 0 | 0 | NULL |
| 2026-10-09T00:20:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 38 | 9 | 0.06 | 4 | 4 | 0.06 | 0 | 0 | NULL |
| 2026-10-09T00:10:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 38 | 9 | 0.06 | 4 | 4 | 0.06 | 0 | 0 | NULL |
| 2026-10-09T00:40:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 36 | 9 | 0.06 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-09T00:40:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 36 | 9 | 0.06 | 4 | 4 | 0.06 | 1 | 0 | ["PACKET_DROP_HIGH"] |
| 2026-10-09T00:45:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 35 | 9 | 0.06 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-09T00:45:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 35 | 9 | 0.06 | 4 | 4 | 0.06 | 0 | 0 | NULL |

_12 row(s)_

## gold_cell_sessions_5m: highest failure windows

```sql
SELECT window_start, cell_id, region_code, n_sessions, n_setup_failed, n_dropped, n_no_service,
               n_subscribers_approx, round(failure_rate, 2) AS failure_rate
        FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m WHERE n_sessions >= 3 ORDER BY failure_rate DESC, window_start DESC LIMIT 8
```

| window_start | cell_id | region_code | n_sessions | n_setup_failed | n_dropped | n_no_service | n_subscribers_approx | failure_rate |
|---|---|---|---|---|---|---|---|---|
| 2026-10-09T00:30:00.000Z | CELL-NSW-00086-4G1 | NSW | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-08T23:50:00.000Z | CELL-NQL-00012-4G3 | NQL | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-08T23:40:00.000Z | CELL-NQL-00012-5G1 | NQL | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-08T23:35:00.000Z | CELL-NQL-00012-4G1 | NQL | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-08T23:30:00.000Z | CELL-NQL-00012-4G1 | NQL | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-08T23:20:00.000Z | CELL-NQL-00012-4G1 | NQL | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-08T22:40:00.000Z | CELL-VIC-00088-4G2 | VIC | 3 | 3 | 0 | 3 | 2 | 1.0 |
| 2026-10-08T22:05:00.000Z | CELL-VIC-00088-4G2 | VIC | 3 | 3 | 0 | 3 | 3 | 1.0 |

_8 row(s)_
