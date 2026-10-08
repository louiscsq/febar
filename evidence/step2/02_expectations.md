# Expectation pass/fail metrics (pipeline event log)

Captured 2026-10-08 19:37 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

Summed over the latest full refresh and every update after it (history backfill + live stream), so each record is counted once. `drop` rules move rows to `silver_quarantine`; `on_time` is warn-only (late rows are kept, flagged `is_late`); topology rules are `expect_or_fail`.

## Per dataset and rule

```sql
WITH x AS (
          SELECT explode(from_json(details:flow_progress:data_quality:expectations,
                 'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) AS e
          FROM telco_netmon_febar_catalog.netmon_eval.netmon_pipeline_event_log WHERE event_type = 'flow_progress' AND timestamp >= (SELECT max(timestamp) FROM telco_netmon_febar_catalog.netmon_eval.netmon_pipeline_event_log WHERE event_type = 'create_update'
                                   AND details:create_update:full_refresh::boolean)
            AND details:flow_progress:data_quality:expectations IS NOT NULL)
        SELECT e.dataset, e.name AS rule, sum(e.passed_records) AS passed, sum(e.failed_records) AS failed,
               round(100.0 * sum(e.failed_records) / nullif(sum(e.passed_records) + sum(e.failed_records), 0), 3)
                 AS failed_pct
        FROM x GROUP BY e.dataset, e.name ORDER BY e.dataset, failed DESC
```

| dataset | rule | passed | failed | failed_pct |
|---|---|---|---|---|
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | incident_id_not_null | 276 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | on_time | 19548 | 210 | 1.063 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | event_ts_valid | 19716 | 42 | 0.213 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | event_ts_plausible | 19718 | 40 | 0.202 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | alarm_code_not_null | 19728 | 30 | 0.152 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | severity_not_null | 19734 | 24 | 0.121 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | known_element | 19736 | 22 | 0.111 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | element_id_not_null | 19736 | 22 | 0.111 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | record_id_not_null | 19758 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | alarm_id_not_null | 19758 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | on_time | 2409740 | 24359 | 1.001 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | event_ts_valid | 2431001 | 3098 | 0.127 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | latency_ms_not_null | 2432112 | 1987 | 0.082 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | dl_throughput_mbps_not_null | 2432127 | 1972 | 0.081 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | availability_pct_not_null | 2432151 | 1948 | 0.080 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | prb_util_pct_not_null | 2432215 | 1884 | 0.077 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | no_rescued_data | 2432468 | 1631 | 0.067 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | active_users_not_null | 2432582 | 1517 | 0.062 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | rrc_setup_success_pct_not_null | 2432586 | 1513 | 0.062 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | cell_id_not_null | 2432626 | 1473 | 0.061 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | known_element | 2432626 | 1473 | 0.061 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | availability_pct_in_range | 2433267 | 832 | 0.034 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | rrc_setup_success_pct_in_range | 2433275 | 824 | 0.034 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | active_users_in_range | 2433276 | 823 | 0.034 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | latency_ms_in_range | 2433284 | 815 | 0.033 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | dl_throughput_mbps_in_range | 2433302 | 797 | 0.033 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | prb_util_pct_in_range | 2433308 | 791 | 0.032 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | record_id_not_null | 2434099 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | ul_throughput_mbps_in_range | 2434099 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | attach_success_pct_in_range | 2434099 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | session_drop_rate_pct_in_range | 2434099 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | packet_loss_pct_in_range | 2434099 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | valid_window | 22 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | on_time | 1318597 | 13314 | 1.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | start_ts_valid | 1329725 | 2186 | 0.164 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | bytes_dl_not_null | 1330226 | 1685 | 0.127 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | outcome_not_null | 1330575 | 1336 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | bytes_dl_in_range | 1330578 | 1333 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | cell_id_not_null | 1330580 | 1331 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | known_element | 1330580 | 1331 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | duration_s_in_range | 1330582 | 1329 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | imsi_not_null | 1330610 | 1301 | 0.098 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | no_rescued_data | 1331018 | 893 | 0.067 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | record_id_not_null | 1331911 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | bytes_ul_in_range | 1331911 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | edge_endpoints_not_null | 20713 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | valid_level | 20757 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | element_id_not_null | 20757 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | valid_element_type | 20757 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | has_region_and_timezone | 20757 | 0 | 0.000 |

_50 row(s)_

## Dropped rows per silver flow

```sql
SELECT origin.flow_name, sum(details:flow_progress:data_quality:dropped_records::bigint) AS dropped_records
        FROM telco_netmon_febar_catalog.netmon_eval.netmon_pipeline_event_log WHERE event_type = 'flow_progress' AND timestamp >= (SELECT max(timestamp) FROM telco_netmon_febar_catalog.netmon_eval.netmon_pipeline_event_log WHERE event_type = 'create_update'
                                   AND details:create_update:full_refresh::boolean)
          AND details:flow_progress:data_quality:dropped_records IS NOT NULL
        GROUP BY origin.flow_name ORDER BY 1
```

| flow_name | dropped_records |
|---|---|
| telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | 0 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | 0 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_maintenance_windows | 0 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | 0 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_topology_edges | 0 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_topology_nodes | 0 |
| telco_netmon_febar_catalog.netmon_bronze.quarantine_alarms | 0 |
| telco_netmon_febar_catalog.netmon_bronze.quarantine_alarms_corrupt | 0 |
| telco_netmon_febar_catalog.netmon_bronze.quarantine_kpis | 0 |
| telco_netmon_febar_catalog.netmon_bronze.quarantine_kpis_corrupt | 0 |
| telco_netmon_febar_catalog.netmon_bronze.quarantine_sessions | 0 |
| telco_netmon_febar_catalog.netmon_bronze.quarantine_sessions_corrupt | 0 |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | 0 |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_incidents | 0 |
| telco_netmon_febar_catalog.netmon_eval.eval_alert_precision | 0 |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_log | 0 |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_precision | 0 |
| telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | 0 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | 0 |
| telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | 0 |
| telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline | 0 |
| telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary | 0 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | 0 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | 0 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | 0 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m_retrospective | 0 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | 0 |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | 0 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | 0 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | 158 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | 20274 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | 0 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | 11115 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | 0 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | 0 |

_35 row(s)_

## Quarantine by feed and failed rule

```sql
SELECT feed, _source_run AS run, rule, count(*) AS n_rows
        FROM telco_netmon_febar_catalog.netmon_silver.silver_quarantine LATERAL VIEW explode(failed_rules) t AS rule
        GROUP BY ALL ORDER BY feed, run, n_rows DESC
```

| feed | run | rule | n_rows |
|---|---|---|---|
| alarms | history | event_ts_valid | 36 |
| alarms | history | event_ts_plausible | 33 |
| alarms | history | alarm_code_not_null | 25 |
| alarms | history | element_id_not_null | 20 |
| alarms | history | known_element | 20 |
| alarms | history | parseable_record | 19 |
| alarms | history | severity_not_null | 18 |
| alarms | stream | event_ts_plausible | 7 |
| alarms | stream | event_ts_valid | 6 |
| alarms | stream | severity_not_null | 6 |
| alarms | stream | alarm_code_not_null | 5 |
| alarms | stream | parseable_record | 4 |
| alarms | stream | known_element | 2 |
| alarms | stream | element_id_not_null | 2 |
| kpis | history | event_ts_valid | 2442 |
| kpis | history | latency_ms_not_null | 1561 |
| kpis | history | availability_pct_not_null | 1552 |
| kpis | history | dl_throughput_mbps_not_null | 1541 |
| kpis | history | prb_util_pct_not_null | 1490 |
| kpis | history | no_rescued_data | 1320 |
| kpis | history | parseable_record | 1287 |
| kpis | history | active_users_not_null | 1219 |
| kpis | history | rrc_setup_success_pct_not_null | 1187 |
| kpis | history | known_element | 1177 |
| kpis | history | cell_id_not_null | 1177 |
| kpis | history | active_users_in_range | 653 |
| kpis | history | availability_pct_in_range | 648 |
| kpis | history | rrc_setup_success_pct_in_range | 644 |
| kpis | history | latency_ms_in_range | 643 |
| kpis | history | dl_throughput_mbps_in_range | 629 |
| kpis | history | prb_util_pct_in_range | 623 |
| kpis | stream | event_ts_valid | 656 |
| kpis | stream | dl_throughput_mbps_not_null | 431 |
| kpis | stream | latency_ms_not_null | 426 |
| kpis | stream | availability_pct_not_null | 396 |
| kpis | stream | prb_util_pct_not_null | 394 |
| kpis | stream | parseable_record | 379 |
| kpis | stream | rrc_setup_success_pct_not_null | 326 |
| kpis | stream | no_rescued_data | 311 |
| kpis | stream | active_users_not_null | 298 |
| kpis | stream | known_element | 296 |
| kpis | stream | cell_id_not_null | 296 |
| kpis | stream | availability_pct_in_range | 184 |
| kpis | stream | rrc_setup_success_pct_in_range | 180 |
| kpis | stream | latency_ms_in_range | 172 |
| kpis | stream | active_users_in_range | 170 |
| kpis | stream | dl_throughput_mbps_in_range | 168 |
| kpis | stream | prb_util_pct_in_range | 168 |
| sessions | history | start_ts_valid | 2145 |
| sessions | history | bytes_dl_not_null | 1649 |
| sessions | history | outcome_not_null | 1315 |
| sessions | history | duration_s_in_range | 1308 |
| sessions | history | bytes_dl_in_range | 1305 |
| sessions | history | cell_id_not_null | 1303 |
| sessions | history | known_element | 1303 |
| sessions | history | imsi_not_null | 1286 |
| sessions | history | no_rescued_data | 876 |
| sessions | history | parseable_record | 857 |
| sessions | stream | start_ts_valid | 41 |
| sessions | stream | bytes_dl_not_null | 36 |
| sessions | stream | cell_id_not_null | 28 |
| sessions | stream | bytes_dl_in_range | 28 |
| sessions | stream | known_element | 28 |
| sessions | stream | duration_s_in_range | 21 |
| sessions | stream | outcome_not_null | 21 |
| sessions | stream | no_rescued_data | 17 |
| sessions | stream | imsi_not_null | 15 |
| sessions | stream | parseable_record | 15 |

_68 row(s)_

## Quarantine sample (PII redacted)

```sql
SELECT feed, record_id, failed_rules, event_ts_raw, left(payload, 110) AS payload,
               left(_rescued_data, 60) AS rescued, left(_corrupt_record, 70) AS corrupt
        FROM telco_netmon_febar_catalog.netmon_silver.silver_quarantine
        QUALIFY row_number() OVER (PARTITION BY feed, failed_rules[0] ORDER BY record_id) = 1
        ORDER BY feed LIMIT 25
```

| feed | record_id | failed_rules | event_ts_raw | payload | rescued | corrupt |
|---|---|---|---|---|---|---|
| alarms | ALM-041fbe27f3bc060c-R | ["severity_not_null"] | 2026-09-30T10:42:37Z | {"alarm_id":"ALM-041fbe27f3bc060c","event_type":"RAISE","element_id":"UPF-VIC-01","element_type":"UPF_SGW","al | NULL | NULL |
| alarms | ALM-064d759e08d8b5a6-R | ["event_ts_valid"] |  | {"alarm_id":"ALM-064d759e08d8b5a6","event_type":"RAISE","element_id":"UPF-VIC-01","element_type":"UPF_SGW","al | NULL | NULL |
| alarms | ALM-0220f3d7c6eae3e6-C | ["alarm_code_not_null"] | 2026-10-03T08:33:15Z | {"alarm_id":"ALM-0220f3d7c6eae3e6","event_type":"CLEAR","element_id":"SITE-VIC-00098","element_type":"SITE","s | NULL | NULL |
| alarms | ALM-074954cc4f576814-C | ["element_id_not_null","known_element"] | 2026-09-29T09:31:33Z | {"alarm_id":"ALM-074954cc4f576814","event_type":"CLEAR","element_type":"CELL","alarm_code":"SYNC_LOSS","severi | NULL | NULL |
| alarms | ALM-024596b036819e61-R | ["parseable_record"] | NULL | NULL | NULL | {"record_id":"ALM-024596b036819e61-R","alarm_id":"ALM-024596b036819e61 |
| alarms | ALM-00d0a46f80156c2c-R | ["event_ts_plausible"] | 2099-01-01T00:00:00Z | {"alarm_id":"ALM-00d0a46f80156c2c","event_type":"RAISE","element_id":"SITE-VIC-00098","element_type":"SITE","a | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202610082243 | ["dl_throughput_mbps_not_null"] | 2026-10-08T22:43:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-10-08T22:43:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202609260530 | ["event_ts_valid"] | NULL | {"cell_id":"CELL-NQL-00001-4G1","granularity_s":900,"availability_pct":100.0,"active_users":15,"prb_util_pct": | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610082352 | ["cell_id_not_null","known_element"] | 2026-10-08T23:52:00Z | {"event_ts_raw":"2026-10-08T23:52:00Z","granularity_s":60,"availability_pct":100.0,"active_users":5,"prb_util_ | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610031315 | ["prb_util_pct_not_null"] | 2026-10-03T13:15:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-03T13:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610082257 | ["parseable_record"] | NULL | NULL | NULL | {"record_id":"K-CELL-NQL-00001-4G1-202610082257","event_ts":"2026-10-0 |
| kpis | K-CELL-NQL-00001-4G3-202610061415 | ["rrc_setup_success_pct_in_range"] | 2026-10-06T14:15:00Z | {"cell_id":"CELL-NQL-00001-4G3","event_ts_raw":"2026-10-06T14:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202609241415 | ["latency_ms_not_null"] | 2026-09-24T14:15:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-09-24T14:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202609240015 | ["dl_throughput_mbps_in_range"] | 2026-09-24T00:15:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-09-24T00:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202610082233 | ["active_users_in_range"] | 2026-10-08T22:33:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-10-08T22:33:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202609281900 | ["availability_pct_not_null"] | 2026-09-28T19:00:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-09-28T19:00:00Z","granularity_s":900,"active_users":9,"pr | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202609240215 | ["no_rescued_data","dl_throughput_mbps_not_null"] | 2026-09-24T02:15:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-09-24T02:15:00Z","granularity_s":900,"availability_pct":1 | {"dl_throughput_mbps":"ERR","_file_path":"/Volumes/telco_net | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610051145 | ["latency_ms_in_range"] | 2026-10-05T11:45:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-05T11:45:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202610082323 | ["rrc_setup_success_pct_not_null"] | 2026-10-08T23:23:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-10-08T23:23:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202610040315 | ["availability_pct_in_range"] | 2026-10-04T03:15:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-10-04T03:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202609292215 | ["active_users_not_null"] | 2026-09-29T22:15:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-09-29T22:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G3-202610081918 | ["prb_util_pct_in_range"] | 2026-10-08T19:18:00Z | {"cell_id":"CELL-NQL-00001-4G3","event_ts_raw":"2026-10-08T19:18:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| sessions | S-20260924T0000-0001504 | ["bytes_dl_in_range"] | 2026-09-24T00:24:01Z | {"cell_id":"CELL-NSW-00079-5G3","start_ts_raw":"2026-09-24T00:24:01Z","end_ts_raw":"2026-09-24T00:28:35Z","dur | NULL | NULL |
| sessions | S-20260924T0000-0000109 | ["bytes_dl_not_null"] | 2026-09-24T00:12:59Z | {"cell_id":"CELL-NSW-00029-4G3","start_ts_raw":"2026-09-24T00:12:59Z","end_ts_raw":"2026-09-24T00:19:03Z","dur | NULL | NULL |
| sessions | S-20260924T0000-0000113 | ["cell_id_not_null","known_element"] | 2026-09-24T00:13:30Z | {"start_ts_raw":"2026-09-24T00:13:30Z","end_ts_raw":"2026-09-24T00:18:01Z","duration_s":271,"service_type":"vi | NULL | NULL |

_25 row(s)_

## Injected defects (ground truth) vs pipeline handling — eval_dq_capture

`handled_pct` = quarantined (malformed / null / out_of_range), flagged late (late_arrival) or single copy in silver (duplicate). Session dedupe is the same code path and not re-scored.

```sql
SELECT * FROM telco_netmon_febar_catalog.netmon_eval.eval_dq_capture ORDER BY source_run, feed, defect_type, defect_subtype
```

| source_run | feed | defect_type | defect_subtype | n_injected | n_quarantined | n_kept_in_silver | n_flagged_late | n_single_copy_in_silver | handled_pct |
|---|---|---|---|---|---|---|---|---|---|
| history | alarms | duplicate | redelivery | 85 | 0 | 85 | 0 | 85 | 100.0 |
| history | alarms | late_arrival | delayed_delivery | 166 | 0 | 166 | 166 | 166 | 100.0 |
| history | alarms | malformed | bad_timestamp | 17 | 17 | 0 | 0 | 0 | 100.0 |
| history | alarms | malformed | truncated_json | 19 | 19 | 0 | 0 | 0 | 100.0 |
| history | alarms | null | missing_value | 82 | 82 | 0 | 0 | 0 | 100.0 |
| history | alarms | out_of_range | clock_skew | 33 | 33 | 0 | 0 | 0 | 100.0 |
| history | kpis | duplicate | redelivery | 9614 | 0 | 9614 | 0 | 9614 | 100.0 |
| history | kpis | late_arrival | delayed_delivery | 19228 | 0 | 19228 | 19228 | 19228 | 100.0 |
| history | kpis | malformed | bad_timestamp | 1238 | 1238 | 0 | 0 | 0 | 100.0 |
| history | kpis | malformed | truncated_json | 1287 | 1287 | 0 | 0 | 0 | 100.0 |
| history | kpis | malformed | type_mismatch | 1320 | 1320 | 0 | 0 | 0 | 100.0 |
| history | kpis | null | missing_value | 9611 | 9611 | 0 | 0 | 0 | 100.0 |
| history | kpis | out_of_range | impossible_value | 3840 | 3840 | 0 | 0 | 0 | 100.0 |
| history | sessions | duplicate | redelivery | 6538 | 0 | 6538 | 0 | 0 | NULL |
| history | sessions | late_arrival | delayed_delivery | 13079 | 0 | 13079 | 13079 | 0 | 100.0 |
| history | sessions | malformed | bad_timestamp | 881 | 881 | 0 | 0 | 0 | 100.0 |
| history | sessions | malformed | truncated_json | 857 | 857 | 0 | 0 | 0 | 100.0 |
| history | sessions | malformed | type_mismatch | 876 | 876 | 0 | 0 | 0 | 100.0 |
| history | sessions | null | missing_value | 6545 | 6545 | 0 | 0 | 0 | 100.0 |
| history | sessions | out_of_range | impossible_value | 2613 | 2613 | 0 | 0 | 0 | 100.0 |
| stream | alarms | duplicate | redelivery | 18 | 0 | 18 | 0 | 18 | 100.0 |
| stream | alarms | late_arrival | delayed_delivery | 28 | 0 | 28 | 28 | 28 | 100.0 |
| stream | alarms | malformed | bad_timestamp | 3 | 3 | 0 | 0 | 0 | 100.0 |
| stream | alarms | malformed | truncated_json | 4 | 4 | 0 | 0 | 0 | 100.0 |
| stream | alarms | null | missing_value | 16 | 16 | 0 | 0 | 0 | 100.0 |
| stream | alarms | out_of_range | clock_skew | 7 | 7 | 0 | 0 | 0 | 100.0 |
| stream | kpis | duplicate | redelivery | 2561 | 0 | 2561 | 0 | 2561 | 100.0 |
| stream | kpis | late_arrival | delayed_delivery | 5131 | 0 | 5131 | 5131 | 5131 | 100.0 |
| stream | kpis | malformed | bad_timestamp | 344 | 344 | 0 | 0 | 0 | 100.0 |
| stream | kpis | malformed | truncated_json | 379 | 379 | 0 | 0 | 0 | 100.0 |
| stream | kpis | malformed | type_mismatch | 311 | 311 | 0 | 0 | 0 | 100.0 |
| stream | kpis | null | missing_value | 2568 | 2568 | 0 | 0 | 0 | 100.0 |
| stream | kpis | out_of_range | impossible_value | 1042 | 1042 | 0 | 0 | 0 | 100.0 |
| stream | sessions | duplicate | redelivery | 135 | 0 | 135 | 0 | 0 | NULL |
| stream | sessions | late_arrival | delayed_delivery | 235 | 0 | 235 | 235 | 0 | 100.0 |
| stream | sessions | malformed | bad_timestamp | 15 | 15 | 0 | 0 | 0 | 100.0 |
| stream | sessions | malformed | truncated_json | 15 | 15 | 0 | 0 | 0 | 100.0 |
| stream | sessions | malformed | type_mismatch | 17 | 17 | 0 | 0 | 0 | 100.0 |
| stream | sessions | null | missing_value | 119 | 119 | 0 | 0 | 0 | 100.0 |
| stream | sessions | out_of_range | impossible_value | 49 | 49 | 0 | 0 | 0 | 100.0 |

_40 row(s)_
