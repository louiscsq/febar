# Sample gold rows

Captured 2026-10-08 18:04 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

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
| 2026-10-08T23:15:00.000Z | CELL-NQL-00008-4G1 | NQL | 5 | 86.1 | 116.4 | 118.4 | -0.2 | -1.4 | ["cell_unavailable","attach_failure","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T23:15:00.000Z | CELL-NQL-00008-4G3 | NQL | 5 | 92.9 | 120.8 | 119.3 | 0.2 | -0.3 | ["cell_unavailable","attach_failure","rrc_degradation"] |
| 2026-10-08T23:15:00.000Z | CELL-NQL-00009-4G1 | NQL | 4 | 93.5 | 138.4 | 134.5 | 0.4 | 0.1 | ["cell_unavailable","attach_failure","rrc_degradation"] |
| 2026-10-08T23:15:00.000Z | CELL-NQL-00009-4G2 | NQL | 5 | 94.2 | 128.7 | 131.5 | -0.3 | -0.7 | ["cell_unavailable","attach_failure","rrc_degradation"] |
| 2026-10-08T23:15:00.000Z | CELL-NQL-00009-4G3 | NQL | 5 | 73.5 | 127.8 | 135.2 | -0.7 | -2.7 | ["cell_unavailable","attach_failure","rrc_collapse","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T23:15:00.000Z | CELL-NQL-00010-4G1 | NQL | 5 | 90.3 | 60.4 | 61.8 | -0.3 | -1.3 | ["cell_unavailable","attach_failure","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T23:15:00.000Z | CELL-NQL-00010-5G1 | NQL | 5 | 93.2 | 42.9 | 42.8 | 0.0 | -0.6 | ["cell_unavailable","attach_failure","rrc_degradation"] |
| 2026-10-08T23:15:00.000Z | CELL-NQL-00011-4G1 | NQL | 5 | 76.7 | 71.7 | 74.6 | -0.5 | -2.7 | ["cell_unavailable","attach_failure","rrc_collapse","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T23:15:00.000Z | CELL-NQL-00011-4G3 | NQL | 5 | 74.1 | 66.8 | 74.9 | -1.2 | -1.6 | ["cell_unavailable","attach_failure","rrc_collapse","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T23:15:00.000Z | CELL-NQL-00011-5G1 | NQL | 5 | 72.2 | 43.9 | 49.3 | -1.3 | -1.4 | ["cell_unavailable","attach_failure","rrc_collapse","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T23:15:00.000Z | CELL-NQL-00011-5G2 | NQL | 5 | 80.9 | 48.0 | 49.8 | -0.4 | -1.4 | ["cell_unavailable","attach_failure","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T23:15:00.000Z | CELL-NQL-00011-5G3 | NQL | 5 | 76.1 | 45.8 | 49.0 | -0.8 | -2.6 | ["cell_unavailable","attach_failure","rrc_collapse","rrc_degradation","drop_rate_spike"] |

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
| 2026-10-08T23:19:00.000Z | 2026-10-09T09:19:00.000Z | CELL-NQL-00001-4G1 | 85.7 | 84.9 | 6.66 | 0.13 | false |
| 2026-10-08T23:18:00.000Z | 2026-10-09T09:18:00.000Z | CELL-NQL-00001-4G1 | 89.2 | 84.9 | 6.66 | 0.65 | false |
| 2026-10-08T23:17:00.000Z | 2026-10-09T09:17:00.000Z | CELL-NQL-00001-4G1 | 93.5 | 84.9 | 6.66 | 1.3 | false |
| 2026-10-08T23:16:00.000Z | 2026-10-09T09:16:00.000Z | CELL-NQL-00001-4G1 | 85.0 | 84.9 | 6.66 | 0.02 | false |
| 2026-10-08T23:15:00.000Z | 2026-10-09T09:15:00.000Z | CELL-NQL-00001-4G1 | 80.6 | 84.9 | 6.66 | -0.64 | false |
| 2026-10-08T23:14:00.000Z | 2026-10-09T09:14:00.000Z | CELL-NQL-00001-4G1 | 95.4 | 84.9 | 6.66 | 1.58 | false |
| 2026-10-08T23:13:00.000Z | 2026-10-09T09:13:00.000Z | CELL-NQL-00001-4G1 | 99.0 | 84.9 | 6.66 | 2.12 | false |
| 2026-10-08T23:12:00.000Z | 2026-10-09T09:12:00.000Z | CELL-NQL-00001-4G1 | 78.3 | 84.9 | 6.66 | -0.98 | false |

_8 row(s)_

## gold_cell_baseline: sample

```sql
SELECT valid_date, cell_id, local_hour, day_type, n_days, n_samples, round(b_latency_ms_mean, 1) AS lat_mean,
               round(b_latency_ms_std, 2) AS lat_std, round(b_dl_throughput_mbps_mean, 1) AS dl_mean
        FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline ORDER BY valid_date DESC, cell_id, local_hour LIMIT 6
```

| valid_date | cell_id | local_hour | day_type | n_days | n_samples | lat_mean | lat_std | dl_mean |
|---|---|---|---|---|---|---|---|---|
| 2026-10-10 | CELL-NQL-00001-4G1 | 0 | weekday | 9 | 36 | 81.0 | 7.0 | 90.2 |
| 2026-10-10 | CELL-NQL-00001-4G1 | 0 | weekend | 4 | 16 | 81.1 | 6.06 | 92.9 |
| 2026-10-10 | CELL-NQL-00001-4G1 | 1 | weekend | 4 | 16 | 82.3 | 4.93 | 90.6 |
| 2026-10-10 | CELL-NQL-00001-4G1 | 1 | weekday | 9 | 36 | 82.9 | 6.56 | 91.8 |
| 2026-10-10 | CELL-NQL-00001-4G1 | 2 | weekend | 4 | 16 | 79.5 | 7.88 | 91.3 |
| 2026-10-10 | CELL-NQL-00001-4G1 | 2 | weekday | 9 | 35 | 82.2 | 7.75 | 91.5 |

_6 row(s)_

## gold_impact_detections: latest live detections

```sql
SELECT detected_ts, signal_source, element_type, element_id, region_code, signal_start_ts, evidence_ts,
               round(pipeline_latency_s, 1) AS pipeline_latency_s, flags, severity_score, in_maintenance
        FROM telco_netmon_febar_catalog.netmon_gold.gold_impact_detections WHERE landed_ts IS NOT NULL ORDER BY detected_ts DESC LIMIT 12
```

| detected_ts | signal_source | element_type | element_id | region_code | signal_start_ts | evidence_ts | pipeline_latency_s | flags | severity_score | in_maintenance |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-08T17:53:50.568Z | kpi | CELL | CELL-NSW-00115-4G2 | NSW | 2026-10-08T18:58:00.000Z | 2026-10-08T23:24:00.000Z | 44.6 | ["latency_degradation","packet_loss","throughput_collapse","rrc_degradation","drop_rate_spike"] | 1 | false |
| 2026-10-08T17:53:50.568Z | kpi | CELL | CELL-NSW-00070-5G2 | NSW | 2026-10-08T18:24:00.000Z | 2026-10-08T23:24:00.000Z | 44.6 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | false |
| 2026-10-08T17:53:50.568Z | kpi | CELL | CELL-VIC-00028-4G3 | VIC | 2026-10-08T20:47:00.000Z | 2026-10-08T23:24:00.000Z | 43.6 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | false |
| 2026-10-08T17:53:50.568Z | kpi | CELL | CELL-NSW-00021-4G3 | NSW | 2026-10-08T23:14:00.000Z | 2026-10-08T23:24:00.000Z | 43.6 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | false |
| 2026-10-08T17:53:50.568Z | kpi | CELL | CELL-NSW-00117-4G2 | NSW | 2026-10-08T20:17:00.000Z | 2026-10-08T23:24:00.000Z | 44.6 | ["latency_degradation","packet_loss","rrc_degradation","drop_rate_spike"] | 1 | false |
| 2026-10-08T17:53:50.568Z | kpi | CELL | CELL-NSW-00021-4G2 | NSW | 2026-10-08T18:57:00.000Z | 2026-10-08T23:24:00.000Z | 44.6 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | false |
| 2026-10-08T17:53:50.568Z | kpi | CELL | CELL-NSW-00117-4G3 | NSW | 2026-10-08T19:01:00.000Z | 2026-10-08T23:24:00.000Z | 44.6 | ["latency_degradation","packet_loss","throughput_collapse","rrc_degradation","drop_rate_spike"] | 1 | false |
| 2026-10-08T17:53:50.568Z | kpi | CELL | CELL-WA-00015-4G1 | WA | 2026-10-08T20:47:00.000Z | 2026-10-08T23:24:00.000Z | 43.6 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | false |
| 2026-10-08T17:53:50.568Z | kpi | CELL | CELL-NSW-00021-4G3 | NSW | 2026-10-08T21:26:00.000Z | 2026-10-08T23:24:00.000Z | 44.6 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | false |
| 2026-10-08T17:53:50.568Z | kpi | CELL | CELL-VIC-00060-5G1 | VIC | 2026-10-08T18:35:00.000Z | 2026-10-08T23:24:00.000Z | 44.6 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | false |
| 2026-10-08T17:53:50.568Z | kpi | CELL | CELL-VIC-00105-4G2 | VIC | 2026-10-08T21:18:00.000Z | 2026-10-08T23:24:00.000Z | 44.6 | ["latency_degradation","packet_loss"] | 1 | false |
| 2026-10-08T17:53:50.568Z | kpi | CELL | CELL-NSW-00117-4G2 | NSW | 2026-10-08T19:53:00.000Z | 2026-10-08T23:24:00.000Z | 44.6 | ["latency_degradation","packet_loss","throughput_collapse","rrc_degradation","drop_rate_spike"] | 1 | false |

_12 row(s)_

## gold_impact_detections: pipeline latency (live files)

```sql
SELECT signal_source, count(*) AS n, round(percentile(pipeline_latency_s, 0.5), 1) AS p50_s,
               round(percentile(pipeline_latency_s, 0.9), 1) AS p90_s, round(max(pipeline_latency_s), 1) AS max_s
        FROM telco_netmon_febar_catalog.netmon_gold.gold_impact_detections WHERE landed_ts IS NOT NULL GROUP BY signal_source
```

| signal_source | n | p50_s | p90_s | max_s |
|---|---|---|---|---|
| alarm | 79 | 40.6 | 63.2 | 133.2 |
| kpi | 6642 | 47.6 | 66.6 | 210.3 |

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
| 2026-10-08T20:25:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 28 | 6 | 0.05 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T20:30:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 28 | 6 | 0.05 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T20:25:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 28 | 6 | 0.05 | 4 | 4 | 0.05 | 0 | 0 | NULL |
| 2026-10-08T20:30:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 28 | 6 | 0.05 | 4 | 4 | 0.05 | 0 | 0 | NULL |
| 2026-10-08T20:35:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 27 | 6 | 0.04 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T20:15:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 27 | 6 | 0.04 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T20:20:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 27 | 6 | 0.04 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T20:20:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 27 | 6 | 0.04 | 4 | 4 | 0.04 | 0 | 0 | NULL |
| 2026-10-08T20:35:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 27 | 6 | 0.04 | 4 | 4 | 0.04 | 0 | 0 | NULL |
| 2026-10-08T20:15:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 27 | 6 | 0.04 | 4 | 4 | 0.04 | 0 | 0 | NULL |
| 2026-10-08T21:15:00.000Z | AMF-VIC-01 | AMF_MME | 528 | 25 | 0 | 0.05 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T21:05:00.000Z | AMF-VIC-01 | AMF_MME | 528 | 25 | 0 | 0.05 | 1 | 1 | NULL | 0 | 0 | NULL |

_12 row(s)_

## gold_cell_sessions_5m: highest failure windows

```sql
SELECT window_start, cell_id, region_code, n_sessions, n_setup_failed, n_dropped, n_no_service,
               n_subscribers_approx, round(failure_rate, 2) AS failure_rate
        FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m WHERE n_sessions >= 3 ORDER BY failure_rate DESC, window_start DESC LIMIT 8
```

| window_start | cell_id | region_code | n_sessions | n_setup_failed | n_dropped | n_no_service | n_subscribers_approx | failure_rate |
|---|---|---|---|---|---|---|---|---|
| 2026-10-08T23:20:00.000Z | CELL-NQL-00012-4G1 | NQL | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-08T22:40:00.000Z | CELL-VIC-00088-4G2 | VIC | 3 | 3 | 0 | 3 | 2 | 1.0 |
| 2026-10-08T22:05:00.000Z | CELL-VIC-00088-4G2 | VIC | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-08T21:55:00.000Z | CELL-NSW-00048-4G3 | NSW | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-08T21:35:00.000Z | CELL-VIC-00019-4G1 | VIC | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-08T20:15:00.000Z | CELL-NSW-00048-4G3 | NSW | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-08T19:40:00.000Z | CELL-VIC-00004-5G3 | VIC | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-07T00:10:00.000Z | CELL-NQL-00012-4G1 | NQL | 3 | 0 | 3 | 0 | 3 | 1.0 |

_8 row(s)_
