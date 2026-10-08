# Sample gold rows

Captured 2026-10-08 13:30 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

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
| 2026-10-08T16:30:00.000Z | CELL-NQL-00011-5G3 | NQL | 5 | 0.0 | 33.9 | 38.6 | -1.6 | -12.7 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] |
| 2026-10-08T16:30:00.000Z | CELL-NSW-00043-4G2 | NSW | 5 | 0.0 | 37.4 | 41.4 | -1.3 | -11.7 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] |
| 2026-10-08T16:30:00.000Z | CELL-NSW-00050-4G1 | NSW | 5 | 0.0 | 84.4 | 90.8 | -1.1 | -12.2 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] |
| 2026-10-08T16:30:00.000Z | CELL-NSW-00080-5G1 | NSW | 5 | 0.0 | 18.4 | 19.6 | -0.6 | -11.6 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] |
| 2026-10-08T16:30:00.000Z | CELL-NSW-00092-4G1 | NSW | 5 | 3.0 | 28.6 | 29.0 | -0.2 | -10.7 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T16:30:00.000Z | CELL-NSW-00092-4G2 | NSW | 5 | 3.0 | 28.7 | 31.1 | -1.1 | -10.1 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T16:30:00.000Z | CELL-NSW-00092-4G3 | NSW | 5 | 3.0 | 29.1 | 31.7 | -0.7 | -8.2 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T16:30:00.000Z | CELL-NSW-00092-5G1 | NSW | 5 | 3.0 | 14.2 | 15.2 | -0.5 | -9.5 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T16:30:00.000Z | CELL-NSW-00092-5G2 | NSW | 5 | 3.0 | 13.9 | 15.1 | -0.6 | -9.6 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T16:30:00.000Z | CELL-NSW-00092-5G3 | NSW | 5 | 3.0 | 10.8 | 11.7 | -0.4 | -8.1 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T16:30:00.000Z | CELL-NSW-00093-4G1 | NSW | 5 | 3.0 | 28.4 | 29.8 | -0.7 | -10.1 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] |
| 2026-10-08T16:30:00.000Z | CELL-NSW-00093-4G2 | NSW | 5 | 3.0 | 28.1 | 29.3 | -0.5 | -9.8 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] |

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
| 2026-10-08T16:34:00.000Z | 2026-10-09T02:34:00.000Z | CELL-NQL-00001-4G1 | 72.7 | 82.4 | 7.76 | -1.26 | false |
| 2026-10-08T16:33:00.000Z | 2026-10-09T02:33:00.000Z | CELL-NQL-00001-4G1 | 75.4 | 82.4 | 7.76 | -0.91 | false |
| 2026-10-08T16:32:00.000Z | 2026-10-09T02:32:00.000Z | CELL-NQL-00001-4G1 | 81.2 | 82.4 | 7.76 | -0.16 | false |
| 2026-10-08T16:31:00.000Z | 2026-10-09T02:31:00.000Z | CELL-NQL-00001-4G1 | 82.4 | 82.4 | 7.76 | -0.01 | false |
| 2026-10-08T16:30:00.000Z | 2026-10-09T02:30:00.000Z | CELL-NQL-00001-4G1 | 75.9 | 82.4 | 7.76 | -0.84 | false |
| 2026-10-08T16:29:00.000Z | 2026-10-09T02:29:00.000Z | CELL-NQL-00001-4G1 | 83.5 | 82.4 | 7.76 | 0.14 | false |
| 2026-10-08T16:28:00.000Z | 2026-10-09T02:28:00.000Z | CELL-NQL-00001-4G1 | 74.1 | 82.4 | 7.76 | -1.08 | false |
| 2026-10-08T16:27:00.000Z | 2026-10-09T02:27:00.000Z | CELL-NQL-00001-4G1 | 71.9 | 82.4 | 7.76 | -1.36 | false |

_8 row(s)_

## gold_cell_baseline: sample

```sql
SELECT valid_date, cell_id, local_hour, day_type, n_days, n_samples, round(b_latency_ms_mean, 1) AS lat_mean,
               round(b_latency_ms_std, 2) AS lat_std, round(b_dl_throughput_mbps_mean, 1) AS dl_mean
        FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline ORDER BY valid_date DESC, cell_id, local_hour LIMIT 6
```

| valid_date | cell_id | local_hour | day_type | n_days | n_samples | lat_mean | lat_std | dl_mean |
|---|---|---|---|---|---|---|---|---|
| 2026-10-09 | CELL-NQL-00001-4G1 | 0 | weekday | 10 | 95 | 81.9 | 5.94 | 89.7 |
| 2026-10-09 | CELL-NQL-00001-4G1 | 0 | weekend | 4 | 16 | 81.1 | 6.06 | 92.9 |
| 2026-10-09 | CELL-NQL-00001-4G1 | 1 | weekday | 10 | 95 | 82.9 | 6.43 | 90.2 |
| 2026-10-09 | CELL-NQL-00001-4G1 | 1 | weekend | 4 | 16 | 82.3 | 4.93 | 90.6 |
| 2026-10-09 | CELL-NQL-00001-4G1 | 2 | weekend | 4 | 16 | 79.5 | 7.88 | 91.3 |
| 2026-10-09 | CELL-NQL-00001-4G1 | 2 | weekday | 10 | 71 | 81.5 | 7.0 | 90.7 |

_6 row(s)_

## gold_impact_detections: latest live detections

```sql
SELECT detected_ts, signal_source, element_type, element_id, region_code, signal_start_ts, evidence_ts,
               round(pipeline_latency_s, 1) AS pipeline_latency_s, flags, severity_score, in_maintenance
        FROM telco_netmon_febar_catalog.netmon_gold.gold_impact_detections WHERE landed_ts IS NOT NULL ORDER BY detected_ts DESC LIMIT 12
```

| detected_ts | signal_source | element_type | element_id | region_code | signal_start_ts | evidence_ts | pipeline_latency_s | flags | severity_score | in_maintenance |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-08T13:19:26.250Z | kpi | CELL | CELL-NSW-00094-5G1 | NSW | 2026-10-08T16:37:00.000Z | 2026-10-08T16:39:00.000Z | 35.3 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] | 3 | true |
| 2026-10-08T13:19:26.250Z | kpi | CELL | CELL-NSW-00097-4G3 | NSW | 2026-10-08T16:36:00.000Z | 2026-10-08T16:38:00.000Z | 36.3 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] | 3 | true |
| 2026-10-08T13:19:26.250Z | kpi | CELL | CELL-VIC-00050-4G2 | VIC | 2026-10-08T13:46:00.000Z | 2026-10-08T16:39:00.000Z | 34.3 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | true |
| 2026-10-08T13:19:26.250Z | kpi | CELL | CELL-NSW-00124-4G3 | NSW | 2026-10-08T16:37:00.000Z | 2026-10-08T16:39:00.000Z | 35.3 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] | 3 | true |
| 2026-10-08T13:19:26.250Z | kpi | CELL | CELL-VIC-00047-5G2 | VIC | 2026-10-08T13:47:00.000Z | 2026-10-08T16:39:00.000Z | 35.3 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | true |
| 2026-10-08T13:19:26.250Z | kpi | CELL | CELL-NSW-00098-4G1 | NSW | 2026-10-08T16:06:00.000Z | 2026-10-08T16:39:00.000Z | 34.3 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] | 3 | true |
| 2026-10-08T13:19:26.250Z | kpi | CELL | CELL-VIC-00049-5G3 | VIC | 2026-10-08T14:03:00.000Z | 2026-10-08T16:39:00.000Z | 34.3 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation"] | 3 | true |
| 2026-10-08T13:19:26.250Z | kpi | CELL | CELL-NSW-00121-4G2 | NSW | 2026-10-08T16:08:00.000Z | 2026-10-08T16:39:00.000Z | 34.3 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] | 3 | true |
| 2026-10-08T13:19:26.250Z | kpi | CELL | CELL-NSW-00102-4G1 | NSW | 2026-10-08T16:36:00.000Z | 2026-10-08T16:38:00.000Z | 36.3 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] | 3 | true |
| 2026-10-08T13:19:26.250Z | kpi | CELL | CELL-NSW-00095-4G3 | NSW | 2026-10-08T16:37:00.000Z | 2026-10-08T16:39:00.000Z | 35.3 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] | 3 | true |
| 2026-10-08T13:19:26.250Z | kpi | CELL | CELL-NSW-00096-4G1 | NSW | 2026-10-08T16:36:00.000Z | 2026-10-08T16:38:00.000Z | 36.3 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] | 3 | true |
| 2026-10-08T13:19:26.250Z | kpi | CELL | CELL-NSW-00128-4G3 | NSW | 2026-10-08T16:37:00.000Z | 2026-10-08T16:39:00.000Z | 35.3 | ["cell_unavailable","attach_failure","rrc_collapse","throughput_collapse","rrc_degradation","drop_rate_spike"] | 3 | true |

_12 row(s)_

## gold_impact_detections: pipeline latency (live files)

```sql
SELECT signal_source, count(*) AS n, round(percentile(pipeline_latency_s, 0.5), 1) AS p50_s,
               round(percentile(pipeline_latency_s, 0.9), 1) AS p90_s, round(max(pipeline_latency_s), 1) AS max_s
        FROM telco_netmon_febar_catalog.netmon_gold.gold_impact_detections WHERE landed_ts IS NOT NULL GROUP BY signal_source
```

| signal_source | n | p50_s | p90_s | max_s |
|---|---|---|---|---|
| kpi | 28710 | 36.4 | 46.8 | 116.3 |
| alarm | 734 | 37.6 | 49.0 | 57.6 |

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
| 2026-10-08T14:00:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 211 | 6 | 0.34 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T14:00:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 211 | 6 | 0.34 | 4 | 4 | 0.34 | 0 | 0 | NULL |
| 2026-10-08T14:05:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 209 | 6 | 0.34 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T14:05:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 209 | 6 | 0.34 | 4 | 4 | 0.34 | 0 | 0 | NULL |
| 2026-10-08T15:25:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 205 | 0 | 0.33 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T13:55:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 205 | 6 | 0.33 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T15:30:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 205 | 0 | 0.33 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T15:25:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 205 | 0 | 0.33 | 4 | 4 | 0.33 | 1 | 0 | ["GTPU_PATH_FAILURE"] |
| 2026-10-08T13:55:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 205 | 6 | 0.33 | 4 | 4 | 0.33 | 0 | 0 | NULL |
| 2026-10-08T15:30:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 205 | 0 | 0.33 | 4 | 4 | 0.33 | 0 | 0 | NULL |
| 2026-10-08T13:50:00.000Z | AMF-NSW-01 | AMF_MME | 621 | 203 | 6 | 0.33 | 1 | 1 | NULL | 0 | 0 | NULL |
| 2026-10-08T13:50:00.000Z | UPF-NSW-01 | UPF_SGW | 621 | 203 | 6 | 0.33 | 4 | 4 | 0.33 | 0 | 0 | NULL |

_12 row(s)_

## gold_cell_sessions_5m: highest failure windows

```sql
SELECT window_start, cell_id, region_code, n_sessions, n_setup_failed, n_dropped, n_no_service,
               n_subscribers_approx, round(failure_rate, 2) AS failure_rate
        FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m WHERE n_sessions >= 3 ORDER BY failure_rate DESC, window_start DESC LIMIT 8
```

| window_start | cell_id | region_code | n_sessions | n_setup_failed | n_dropped | n_no_service | n_subscribers_approx | failure_rate |
|---|---|---|---|---|---|---|---|---|
| 2026-10-07T00:10:00.000Z | CELL-NQL-00012-4G1 | NQL | 3 | 0 | 3 | 0 | 3 | 1.0 |
| 2026-10-01T12:05:00.000Z | CELL-WA-00016-4G1 | WA | 3 | 2 | 1 | 0 | 3 | 1.0 |
| 2026-10-01T12:00:00.000Z | CELL-NQL-00012-5G3 | NQL | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-01T11:30:00.000Z | CELL-NQL-00012-5G3 | NQL | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-01T11:20:00.000Z | CELL-NQL-00012-5G2 | NQL | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-01T10:55:00.000Z | CELL-NQL-00012-5G2 | NQL | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-01T10:45:00.000Z | CELL-NQL-00012-4G2 | NQL | 3 | 3 | 0 | 3 | 3 | 1.0 |
| 2026-10-01T10:25:00.000Z | CELL-VIC-00041-4G2 | VIC | 3 | 0 | 3 | 0 | 3 | 1.0 |

_8 row(s)_
