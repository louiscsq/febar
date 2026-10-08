# Sample gold rows

Captured 2026-10-08 15:31 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

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
| 2026-10-08T20:40:00.000Z | CELL-NQL-00009-4G2 | NQL | 5 | 0.0 | 115.7 | 138.5 | -1.8 | -10.9 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] |
| 2026-10-08T20:40:00.000Z | CELL-NSW-00031-5G2 | NSW | 5 | 0.0 | 14.2 | 16.5 | -1.1 | -9.0 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] |
| 2026-10-08T20:40:00.000Z | CELL-NSW-00057-4G2 | NSW | 5 | 0.0 | 32.8 | 40.9 | -2.0 | -8.0 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] |
| 2026-10-08T20:40:00.000Z | CELL-NSW-00090-4G2 | NSW | 5 | 0.0 | 85.2 | 106.0 | -2.4 | -8.9 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] |
| 2026-10-08T20:40:00.000Z | CELL-NSW-00113-4G2 | NSW | 5 | 0.0 | 27.0 | 36.7 | -2.3 | -7.3 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] |
| 2026-10-08T20:40:00.000Z | CELL-VIC-00004-5G1 | VIC | 5 | 0.0 | 12.2 | 14.8 | -1.3 | -10.0 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] |
| 2026-10-08T20:40:00.000Z | CELL-VIC-00059-5G2 | VIC | 5 | 0.0 | 13.9 | 17.2 | -1.6 | -10.5 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] |
| 2026-10-08T20:40:00.000Z | CELL-VIC-00065-4G1 | VIC | 5 | 100.0 | 157.7 | 45.2 | 29.3 | -5.3 | ["latency_degradation","packet_loss","throughput_collapse","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T20:40:00.000Z | CELL-VIC-00065-4G2 | VIC | 5 | 100.0 | 176.0 | 44.6 | 32.5 | -5.5 | ["latency_degradation","packet_loss","throughput_collapse","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T20:40:00.000Z | CELL-VIC-00065-4G3 | VIC | 5 | 100.0 | 172.4 | 42.3 | 35.0 | -7.4 | ["latency_degradation","packet_loss","throughput_collapse","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T20:40:00.000Z | CELL-WA-00012-5G2 | WA | 5 | 0.0 | 15.7 | 17.4 | -0.8 | -8.4 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] |
| 2026-10-08T20:40:00.000Z | CELL-WA-00015-4G1 | WA | 5 | 0.0 | 29.8 | 31.9 | -0.8 | -10.9 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] |

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
| 2026-10-08T20:47:00.000Z | 2026-10-09T06:47:00.000Z | CELL-NQL-00001-4G1 | 94.1 | 88.1 | 7.5 | 0.8 | false |
| 2026-10-08T20:46:00.000Z | 2026-10-09T06:46:00.000Z | CELL-NQL-00001-4G1 | 75.8 | 88.1 | 7.5 | -1.64 | false |
| 2026-10-08T20:45:00.000Z | 2026-10-09T06:45:00.000Z | CELL-NQL-00001-4G1 | 86.4 | 88.1 | 7.5 | -0.23 | false |
| 2026-10-08T20:44:00.000Z | 2026-10-09T06:44:00.000Z | CELL-NQL-00001-4G1 | 93.9 | 88.1 | 7.5 | 0.77 | false |
| 2026-10-08T20:43:00.000Z | 2026-10-09T06:43:00.000Z | CELL-NQL-00001-4G1 | 86.2 | 88.1 | 7.5 | -0.26 | false |
| 2026-10-08T20:42:00.000Z | 2026-10-09T06:42:00.000Z | CELL-NQL-00001-4G1 | 85.1 | 88.1 | 7.5 | -0.4 | false |
| 2026-10-08T20:41:00.000Z | 2026-10-09T06:41:00.000Z | CELL-NQL-00001-4G1 | 88.0 | 88.1 | 7.5 | -0.02 | false |
| 2026-10-08T20:40:00.000Z | 2026-10-09T06:40:00.000Z | CELL-NQL-00001-4G1 | 102.9 | 88.1 | 7.5 | 1.97 | false |

_8 row(s)_

## gold_cell_baseline: sample

```sql
SELECT valid_date, cell_id, local_hour, day_type, n_days, n_samples, round(b_latency_ms_mean, 1) AS lat_mean,
               round(b_latency_ms_std, 2) AS lat_std, round(b_dl_throughput_mbps_mean, 1) AS dl_mean
        FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline ORDER BY valid_date DESC, cell_id, local_hour LIMIT 6
```

| valid_date | cell_id | local_hour | day_type | n_days | n_samples | lat_mean | lat_std | dl_mean |
|---|---|---|---|---|---|---|---|---|
| 2026-10-10 | CELL-NQL-00001-4G1 | 0 | weekday | 10 | 45 | 81.4 | 7.09 | 90.6 |
| 2026-10-10 | CELL-NQL-00001-4G1 | 0 | weekend | 4 | 16 | 81.1 | 6.06 | 92.9 |
| 2026-10-10 | CELL-NQL-00001-4G1 | 1 | weekday | 10 | 62 | 83.1 | 6.38 | 89.7 |
| 2026-10-10 | CELL-NQL-00001-4G1 | 1 | weekend | 4 | 16 | 82.3 | 4.93 | 90.6 |
| 2026-10-10 | CELL-NQL-00001-4G1 | 2 | weekday | 10 | 79 | 82.4 | 7.16 | 90.9 |
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
| 2026-10-08T15:22:45.079Z | kpi | CELL | CELL-WA-00035-4G1 | WA | 2026-10-08T18:16:00.000Z | 2026-10-08T20:52:00.000Z | 49.1 | ["latency_degradation","packet_loss","throughput_collapse","rrc_degradation","drop_rate_spike"] | 1 | false |
| 2026-10-08T15:22:45.079Z | kpi | CELL | CELL-NQL-00019-4G2 | NQL | 2026-10-08T16:30:00.000Z | 2026-10-08T20:52:00.000Z | 49.1 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | true |
| 2026-10-08T15:22:45.079Z | kpi | CELL | CELL-WA-00011-5G2 | WA | 2026-10-08T16:41:00.000Z | 2026-10-08T20:52:00.000Z | 49.1 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | true |
| 2026-10-08T15:22:45.079Z | kpi | CELL | CELL-NQL-00015-4G3 | NQL | 2026-10-08T16:43:00.000Z | 2026-10-08T20:52:00.000Z | 49.1 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | true |
| 2026-10-08T15:22:45.079Z | kpi | CELL | CELL-NSW-00082-4G1 | NSW | 2026-10-08T16:41:00.000Z | 2026-10-08T20:52:00.000Z | 50.1 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] | 3 | false |
| 2026-10-08T15:22:45.079Z | kpi | CELL | CELL-WA-00036-5G1 | WA | 2026-10-08T19:52:00.000Z | 2026-10-08T20:52:00.000Z | 49.1 | ["latency_degradation","packet_loss","drop_rate_spike"] | 1 | false |
| 2026-10-08T15:22:45.079Z | kpi | CELL | CELL-NSW-00083-5G2 | NSW | 2026-10-08T17:15:00.000Z | 2026-10-08T20:52:00.000Z | 49.1 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] | 3 | false |
| 2026-10-08T15:22:45.079Z | kpi | CELL | CELL-WA-00035-5G2 | WA | 2026-10-08T19:06:00.000Z | 2026-10-08T20:52:00.000Z | 49.1 | ["latency_degradation","packet_loss"] | 1 | false |
| 2026-10-08T15:22:45.079Z | kpi | CELL | CELL-VIC-00104-5G1 | VIC | 2026-10-08T20:50:00.000Z | 2026-10-08T20:52:00.000Z | 50.1 | ["latency_degradation","packet_loss"] | 1 | false |
| 2026-10-08T15:22:45.079Z | kpi | CELL | CELL-NQL-00022-4G1 | NQL | 2026-10-08T16:30:00.000Z | 2026-10-08T20:52:00.000Z | 49.1 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | true |
| 2026-10-08T15:22:45.079Z | kpi | CELL | CELL-WA-00012-5G2 | WA | 2026-10-08T18:57:00.000Z | 2026-10-08T20:52:00.000Z | 49.1 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | false |
| 2026-10-08T15:22:45.079Z | kpi | CELL | CELL-NQL-00011-4G1 | NQL | 2026-10-08T16:00:00.000Z | 2026-10-08T20:52:00.000Z | 49.1 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] | 3 | false |

_12 row(s)_

## gold_impact_detections: pipeline latency (live files)

```sql
SELECT signal_source, count(*) AS n, round(percentile(pipeline_latency_s, 0.5), 1) AS p50_s,
               round(percentile(pipeline_latency_s, 0.9), 1) AS p90_s, round(max(pipeline_latency_s), 1) AS max_s
        FROM telco_netmon_febar_catalog.netmon_gold.gold_impact_detections WHERE landed_ts IS NOT NULL GROUP BY signal_source
```

| signal_source | n | p50_s | p90_s | max_s |
|---|---|---|---|---|
| kpi | 19700 | 44.9 | 59.4 | 190.0 |
| alarm | 313 | 40.6 | 63.1 | 113.9 |

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
| 2026-10-08T18:10:00.000Z | AMF-WA-01 | AMF_MME | 183 | 30 | 12 | 0.16 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T18:10:00.000Z | UPF-WA-01 | UPF_SGW | 183 | 30 | 12 | 0.16 | 3 | 4 | 0.16 | 0 | 0 | NULL |
| 2026-10-08T18:15:00.000Z | AMF-WA-01 | AMF_MME | 183 | 28 | 9 | 0.15 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T18:15:00.000Z | UPF-WA-01 | UPF_SGW | 183 | 28 | 9 | 0.15 | 3 | 4 | 0.15 | 0 | 0 | NULL |
| 2026-10-08T18:20:00.000Z | AMF-WA-01 | AMF_MME | 183 | 24 | 6 | 0.13 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T18:00:00.000Z | AMF-WA-01 | AMF_MME | 183 | 24 | 12 | 0.13 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T17:55:00.000Z | AMF-WA-01 | AMF_MME | 183 | 24 | 12 | 0.13 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T18:25:00.000Z | AMF-WA-01 | AMF_MME | 183 | 24 | 6 | 0.13 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T18:05:00.000Z | AMF-WA-01 | AMF_MME | 183 | 24 | 12 | 0.13 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T17:55:00.000Z | UPF-WA-01 | UPF_SGW | 183 | 24 | 12 | 0.13 | 2 | 4 | 0.13 | 0 | 0 | NULL |
| 2026-10-08T18:25:00.000Z | UPF-WA-01 | UPF_SGW | 183 | 24 | 6 | 0.13 | 2 | 4 | 0.13 | 0 | 0 | NULL |
| 2026-10-08T18:05:00.000Z | UPF-WA-01 | UPF_SGW | 183 | 24 | 12 | 0.13 | 2 | 4 | 0.13 | 0 | 0 | NULL |

_12 row(s)_

## gold_cell_sessions_5m: highest failure windows

```sql
SELECT window_start, cell_id, region_code, n_sessions, n_setup_failed, n_dropped, n_no_service,
               n_subscribers_approx, round(failure_rate, 2) AS failure_rate
        FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m WHERE n_sessions >= 3 ORDER BY failure_rate DESC, window_start DESC LIMIT 8
```

| window_start | cell_id | region_code | n_sessions | n_setup_failed | n_dropped | n_no_service | n_subscribers_approx | failure_rate |
|---|---|---|---|---|---|---|---|---|
| 2026-10-08T20:20:00.000Z | CELL-VIC-00064-5G3 | VIC | 4 | 4 | 0 | 4 | 4 | 1.0 |
| 2026-10-08T19:40:00.000Z | CELL-VIC-00004-5G3 | VIC | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-07T00:10:00.000Z | CELL-NQL-00012-4G1 | NQL | 3 | 0 | 3 | 0 | 3 | 1.0 |
| 2026-10-01T12:05:00.000Z | CELL-WA-00016-4G1 | WA | 3 | 2 | 1 | 0 | 3 | 1.0 |
| 2026-10-01T12:00:00.000Z | CELL-NQL-00012-5G3 | NQL | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-01T11:30:00.000Z | CELL-NQL-00012-5G3 | NQL | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-01T11:20:00.000Z | CELL-NQL-00012-5G2 | NQL | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-01T10:55:00.000Z | CELL-NQL-00012-5G2 | NQL | 3 | 3 | 0 | 3 | 3 | 1.0 |

_8 row(s)_
