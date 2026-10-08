# Expectation pass/fail metrics (pipeline event log)

Captured 2026-10-08 18:03 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

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
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | incident_id_not_null | 367 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | on_time | 18496 | 202 | 1.080 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | event_ts_valid | 18659 | 39 | 0.209 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | event_ts_plausible | 18661 | 37 | 0.198 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | alarm_code_not_null | 18669 | 29 | 0.155 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | severity_not_null | 18675 | 23 | 0.123 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | known_element | 18677 | 21 | 0.112 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | element_id_not_null | 18677 | 21 | 0.112 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | record_id_not_null | 18698 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | alarm_id_not_null | 18698 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | on_time | 2409458 | 24361 | 1.001 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | event_ts_valid | 2430713 | 3106 | 0.128 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | latency_ms_not_null | 2431830 | 1989 | 0.082 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | dl_throughput_mbps_not_null | 2431857 | 1962 | 0.081 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | availability_pct_not_null | 2431889 | 1930 | 0.079 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | prb_util_pct_not_null | 2431925 | 1894 | 0.078 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | no_rescued_data | 2432181 | 1638 | 0.067 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | rrc_setup_success_pct_not_null | 2432288 | 1531 | 0.063 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | active_users_not_null | 2432309 | 1510 | 0.062 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | cell_id_not_null | 2432343 | 1476 | 0.061 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | known_element | 2432343 | 1476 | 0.061 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | active_users_in_range | 2432990 | 829 | 0.034 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | availability_pct_in_range | 2432992 | 827 | 0.034 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | latency_ms_in_range | 2433007 | 812 | 0.033 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | rrc_setup_success_pct_in_range | 2433010 | 809 | 0.033 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | dl_throughput_mbps_in_range | 2433012 | 807 | 0.033 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | prb_util_pct_in_range | 2433031 | 788 | 0.032 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | record_id_not_null | 2433819 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | ul_throughput_mbps_in_range | 2433819 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | attach_success_pct_in_range | 2433819 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | session_drop_rate_pct_in_range | 2433819 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | packet_loss_pct_in_range | 2433819 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | valid_window | 42 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | on_time | 1312266 | 13252 | 1.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | start_ts_valid | 1323341 | 2177 | 0.164 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | bytes_dl_not_null | 1323840 | 1678 | 0.127 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | bytes_dl_in_range | 1324189 | 1329 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | outcome_not_null | 1324191 | 1327 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | cell_id_not_null | 1324194 | 1324 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | known_element | 1324194 | 1324 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | duration_s_in_range | 1324197 | 1321 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | imsi_not_null | 1324222 | 1296 | 0.098 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | no_rescued_data | 1324628 | 890 | 0.067 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | record_id_not_null | 1325518 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | bytes_ul_in_range | 1325518 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | edge_endpoints_not_null | 22596 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | valid_level | 22644 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | element_id_not_null | 22644 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | valid_element_type | 22644 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | has_region_and_timezone | 22644 | 0 | 0.000 |

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
| telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | 0 |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | 0 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | 0 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | 149 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | 20270 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | 0 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | 11064 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | 0 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | 0 |

_34 row(s)_

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
| alarms | stream | severity_not_null | 5 |
| alarms | stream | event_ts_plausible | 4 |
| alarms | stream | alarm_code_not_null | 4 |
| alarms | stream | event_ts_valid | 3 |
| alarms | stream | parseable_record | 3 |
| alarms | stream | known_element | 1 |
| alarms | stream | element_id_not_null | 1 |
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
| kpis | stream | event_ts_valid | 664 |
| kpis | stream | latency_ms_not_null | 428 |
| kpis | stream | dl_throughput_mbps_not_null | 421 |
| kpis | stream | prb_util_pct_not_null | 404 |
| kpis | stream | parseable_record | 383 |
| kpis | stream | availability_pct_not_null | 378 |
| kpis | stream | rrc_setup_success_pct_not_null | 344 |
| kpis | stream | no_rescued_data | 318 |
| kpis | stream | known_element | 299 |
| kpis | stream | cell_id_not_null | 299 |
| kpis | stream | active_users_not_null | 291 |
| kpis | stream | availability_pct_in_range | 179 |
| kpis | stream | dl_throughput_mbps_in_range | 178 |
| kpis | stream | active_users_in_range | 176 |
| kpis | stream | latency_ms_in_range | 169 |
| kpis | stream | prb_util_pct_in_range | 165 |
| kpis | stream | rrc_setup_success_pct_in_range | 165 |
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
| sessions | stream | start_ts_valid | 32 |
| sessions | stream | bytes_dl_not_null | 29 |
| sessions | stream | bytes_dl_in_range | 24 |
| sessions | stream | cell_id_not_null | 21 |
| sessions | stream | known_element | 21 |
| sessions | stream | no_rescued_data | 14 |
| sessions | stream | duration_s_in_range | 13 |
| sessions | stream | outcome_not_null | 12 |
| sessions | stream | parseable_record | 10 |
| sessions | stream | imsi_not_null | 10 |

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
| kpis | K-CELL-NQL-00001-4G2-202610050845 | ["cell_id_not_null","known_element"] | 2026-10-05T08:45:00Z | {"event_ts_raw":"2026-10-05T08:45:00Z","granularity_s":900,"availability_pct":100.0,"active_users":10,"prb_uti | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610031315 | ["prb_util_pct_not_null"] | 2026-10-03T13:15:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-03T13:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610082257 | ["parseable_record"] | NULL | NULL | NULL | {"record_id":"K-CELL-NQL-00001-4G1-202610082257","event_ts":"2026-10-0 |
| kpis | K-CELL-NQL-00001-4G2-202610081744 | ["rrc_setup_success_pct_in_range"] | 2026-10-08T17:44:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-10-08T17:44:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202609241415 | ["latency_ms_not_null"] | 2026-09-24T14:15:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-09-24T14:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202609240015 | ["dl_throughput_mbps_in_range"] | 2026-09-24T00:15:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-09-24T00:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610081809 | ["active_users_in_range"] | 2026-10-08T18:09:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-08T18:09:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202609281900 | ["availability_pct_not_null"] | 2026-09-28T19:00:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-09-28T19:00:00Z","granularity_s":900,"active_users":9,"pr | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202609240215 | ["no_rescued_data","dl_throughput_mbps_not_null"] | 2026-09-24T02:15:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-09-24T02:15:00Z","granularity_s":900,"availability_pct":1 | {"dl_throughput_mbps":"ERR","_file_path":"/Volumes/telco_net | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610051145 | ["latency_ms_in_range"] | 2026-10-05T11:45:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-05T11:45:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202610082133 | ["rrc_setup_success_pct_not_null"] | 2026-10-08T21:33:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-10-08T21:33:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202610040315 | ["availability_pct_in_range"] | 2026-10-04T03:15:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-10-04T03:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202609292215 | ["active_users_not_null"] | 2026-09-29T22:15:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-09-29T22:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00002-4G3-202609241400 | ["prb_util_pct_in_range"] | 2026-09-24T14:00:00Z | {"cell_id":"CELL-NQL-00002-4G3","event_ts_raw":"2026-09-24T14:00:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
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
| stream | alarms | duplicate | redelivery | 12 | 0 | 12 | 0 | 12 | 100.0 |
| stream | alarms | late_arrival | delayed_delivery | 20 | 0 | 20 | 20 | 20 | 100.0 |
| stream | alarms | malformed | bad_timestamp | 1 | 1 | 0 | 0 | 0 | 100.0 |
| stream | alarms | malformed | truncated_json | 3 | 3 | 0 | 0 | 0 | 100.0 |
| stream | alarms | null | missing_value | 12 | 12 | 0 | 0 | 0 | 100.0 |
| stream | alarms | out_of_range | clock_skew | 4 | 4 | 0 | 0 | 0 | 100.0 |
| stream | kpis | duplicate | redelivery | 2556 | 0 | 2556 | 0 | 2556 | 100.0 |
| stream | kpis | late_arrival | delayed_delivery | 5133 | 0 | 5133 | 5133 | 5133 | 100.0 |
| stream | kpis | malformed | bad_timestamp | 339 | 339 | 0 | 0 | 0 | 100.0 |
| stream | kpis | malformed | truncated_json | 383 | 383 | 0 | 0 | 0 | 100.0 |
| stream | kpis | malformed | type_mismatch | 318 | 318 | 0 | 0 | 0 | 100.0 |
| stream | kpis | null | missing_value | 2572 | 2572 | 0 | 0 | 0 | 100.0 |
| stream | kpis | out_of_range | impossible_value | 1032 | 1032 | 0 | 0 | 0 | 100.0 |
| stream | sessions | duplicate | redelivery | 103 | 0 | 103 | 0 | 0 | NULL |
| stream | sessions | late_arrival | delayed_delivery | 173 | 0 | 173 | 173 | 0 | 100.0 |
| stream | sessions | malformed | bad_timestamp | 10 | 10 | 0 | 0 | 0 | 100.0 |
| stream | sessions | malformed | truncated_json | 10 | 10 | 0 | 0 | 0 | 100.0 |
| stream | sessions | malformed | type_mismatch | 14 | 14 | 0 | 0 | 0 | 100.0 |
| stream | sessions | null | missing_value | 88 | 88 | 0 | 0 | 0 | 100.0 |
| stream | sessions | out_of_range | impossible_value | 37 | 37 | 0 | 0 | 0 | 100.0 |

_40 row(s)_
