# Expectation pass/fail metrics (pipeline event log)

Captured 2026-10-08 13:53 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

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
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | incident_id_not_null | 512 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | on_time | 19323 | 214 | 1.095 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | event_ts_valid | 19495 | 42 | 0.215 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | event_ts_plausible | 19499 | 38 | 0.195 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | alarm_code_not_null | 19510 | 27 | 0.138 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | severity_not_null | 19513 | 24 | 0.123 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | known_element | 19514 | 23 | 0.118 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | element_id_not_null | 19514 | 23 | 0.118 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | record_id_not_null | 19537 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | alarm_id_not_null | 19537 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | on_time | 2237538 | 22621 | 1.001 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | event_ts_valid | 2257256 | 2903 | 0.128 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | dl_throughput_mbps_not_null | 2258326 | 1833 | 0.081 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | availability_pct_not_null | 2258340 | 1819 | 0.080 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | latency_ms_not_null | 2258350 | 1809 | 0.080 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | prb_util_pct_not_null | 2258392 | 1767 | 0.078 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | no_rescued_data | 2258620 | 1539 | 0.068 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | active_users_not_null | 2258754 | 1405 | 0.062 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | rrc_setup_success_pct_not_null | 2258766 | 1393 | 0.062 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | cell_id_not_null | 2258778 | 1381 | 0.061 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | known_element | 2258778 | 1381 | 0.061 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | active_users_in_range | 2259386 | 773 | 0.034 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | dl_throughput_mbps_in_range | 2259401 | 758 | 0.034 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | availability_pct_in_range | 2259401 | 758 | 0.034 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | prb_util_pct_in_range | 2259413 | 746 | 0.033 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | latency_ms_in_range | 2259415 | 744 | 0.033 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | rrc_setup_success_pct_in_range | 2259417 | 742 | 0.033 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | record_id_not_null | 2260159 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | ul_throughput_mbps_in_range | 2260159 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | attach_success_pct_in_range | 2260159 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | session_drop_rate_pct_in_range | 2260159 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | packet_loss_pct_in_range | 2260159 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | valid_window | 116 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | on_time | 1299430 | 13129 | 1.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | start_ts_valid | 1310400 | 2159 | 0.164 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | bytes_dl_not_null | 1310907 | 1652 | 0.126 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | outcome_not_null | 1311240 | 1319 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | duration_s_in_range | 1311244 | 1315 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | bytes_dl_in_range | 1311249 | 1310 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | cell_id_not_null | 1311250 | 1309 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | known_element | 1311250 | 1309 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | imsi_not_null | 1311264 | 1295 | 0.099 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | no_rescued_data | 1311682 | 877 | 0.067 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | record_id_not_null | 1312559 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | bytes_ul_in_range | 1312559 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | edge_endpoints_not_null | 37660 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | valid_level | 37740 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | element_id_not_null | 37740 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | valid_element_type | 37740 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | has_region_and_timezone | 37740 | 0 | 0.000 |

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
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | 154 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | 18831 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | 0 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | 10964 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | 0 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | 0 |

_33 row(s)_

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
| alarms | stream | event_ts_valid | 6 |
| alarms | stream | severity_not_null | 6 |
| alarms | stream | event_ts_plausible | 5 |
| alarms | stream | known_element | 3 |
| alarms | stream | element_id_not_null | 3 |
| alarms | stream | parseable_record | 3 |
| alarms | stream | alarm_code_not_null | 2 |
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
| kpis | stream | event_ts_valid | 461 |
| kpis | stream | dl_throughput_mbps_not_null | 292 |
| kpis | stream | prb_util_pct_not_null | 277 |
| kpis | stream | availability_pct_not_null | 267 |
| kpis | stream | latency_ms_not_null | 248 |
| kpis | stream | parseable_record | 228 |
| kpis | stream | no_rescued_data | 219 |
| kpis | stream | rrc_setup_success_pct_not_null | 206 |
| kpis | stream | known_element | 204 |
| kpis | stream | cell_id_not_null | 204 |
| kpis | stream | active_users_not_null | 186 |
| kpis | stream | dl_throughput_mbps_in_range | 129 |
| kpis | stream | prb_util_pct_in_range | 123 |
| kpis | stream | active_users_in_range | 120 |
| kpis | stream | availability_pct_in_range | 110 |
| kpis | stream | latency_ms_in_range | 101 |
| kpis | stream | rrc_setup_success_pct_in_range | 98 |
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
| sessions | stream | start_ts_valid | 14 |
| sessions | stream | imsi_not_null | 9 |
| sessions | stream | duration_s_in_range | 7 |
| sessions | stream | cell_id_not_null | 6 |
| sessions | stream | known_element | 6 |
| sessions | stream | bytes_dl_in_range | 5 |
| sessions | stream | outcome_not_null | 4 |
| sessions | stream | bytes_dl_not_null | 3 |
| sessions | stream | parseable_record | 2 |
| sessions | stream | no_rescued_data | 1 |

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
| kpis | K-CELL-NQL-00001-4G1-202610081459 | ["dl_throughput_mbps_not_null"] | 2026-10-08T14:59:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-08T14:59:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202609260530 | ["event_ts_valid"] | NULL | {"cell_id":"CELL-NQL-00001-4G1","granularity_s":900,"availability_pct":100.0,"active_users":15,"prb_util_pct": | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202610050845 | ["cell_id_not_null","known_element"] | 2026-10-05T08:45:00Z | {"event_ts_raw":"2026-10-05T08:45:00Z","granularity_s":900,"availability_pct":100.0,"active_users":10,"prb_uti | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610031315 | ["prb_util_pct_not_null"] | 2026-10-03T13:15:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-03T13:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202609251130 | ["parseable_record"] | NULL | NULL | NULL | {"record_id":"K-CELL-NQL-00001-4G2-202609251130","event_ts":"2026-09-2 |
| kpis | K-CELL-NQL-00001-4G3-202610061415 | ["rrc_setup_success_pct_in_range"] | 2026-10-06T14:15:00Z | {"cell_id":"CELL-NQL-00001-4G3","event_ts_raw":"2026-10-06T14:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202609241415 | ["latency_ms_not_null"] | 2026-09-24T14:15:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-09-24T14:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202609240015 | ["dl_throughput_mbps_in_range"] | 2026-09-24T00:15:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-09-24T00:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610081238 | ["active_users_in_range"] | 2026-10-08T12:38:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-08T12:38:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202609281900 | ["availability_pct_not_null"] | 2026-09-28T19:00:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-09-28T19:00:00Z","granularity_s":900,"active_users":9,"pr | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202609240215 | ["no_rescued_data","dl_throughput_mbps_not_null"] | 2026-09-24T02:15:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-09-24T02:15:00Z","granularity_s":900,"availability_pct":1 | {"dl_throughput_mbps":"ERR","_file_path":"/Volumes/telco_net | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610051145 | ["latency_ms_in_range"] | 2026-10-05T11:45:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-05T11:45:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00003-4G1-202609300530 | ["rrc_setup_success_pct_not_null"] | 2026-09-30T05:30:00Z | {"cell_id":"CELL-NQL-00003-4G1","event_ts_raw":"2026-09-30T05:30:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610081606 | ["availability_pct_in_range"] | 2026-10-08T16:06:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-08T16:06:00Z","granularity_s":60,"availability_pct":16 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202609292215 | ["active_users_not_null"] | 2026-09-29T22:15:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-09-29T22:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00002-4G1-202610081458 | ["prb_util_pct_in_range"] | 2026-10-08T14:58:00Z | {"cell_id":"CELL-NQL-00002-4G1","event_ts_raw":"2026-10-08T14:58:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
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
| stream | alarms | duplicate | redelivery | 15 | 0 | 15 | 0 | 15 | 100.0 |
| stream | alarms | late_arrival | delayed_delivery | 30 | 0 | 30 | 30 | 30 | 100.0 |
| stream | alarms | malformed | bad_timestamp | 4 | 4 | 0 | 0 | 0 | 100.0 |
| stream | alarms | malformed | truncated_json | 3 | 3 | 0 | 0 | 0 | 100.0 |
| stream | alarms | null | missing_value | 13 | 13 | 0 | 0 | 0 | 100.0 |
| stream | alarms | out_of_range | clock_skew | 5 | 5 | 0 | 0 | 0 | 100.0 |
| stream | kpis | duplicate | redelivery | 1692 | 0 | 1692 | 0 | 1692 | 100.0 |
| stream | kpis | late_arrival | delayed_delivery | 3393 | 0 | 3393 | 3393 | 3393 | 100.0 |
| stream | kpis | malformed | bad_timestamp | 229 | 229 | 0 | 0 | 0 | 100.0 |
| stream | kpis | malformed | truncated_json | 228 | 228 | 0 | 0 | 0 | 100.0 |
| stream | kpis | malformed | type_mismatch | 219 | 219 | 0 | 0 | 0 | 100.0 |
| stream | kpis | null | missing_value | 1693 | 1693 | 0 | 0 | 0 | 100.0 |
| stream | kpis | out_of_range | impossible_value | 681 | 681 | 0 | 0 | 0 | 100.0 |
| stream | sessions | duplicate | redelivery | 24 | 0 | 24 | 0 | 0 | NULL |
| stream | sessions | late_arrival | delayed_delivery | 50 | 0 | 50 | 50 | 0 | 100.0 |
| stream | sessions | malformed | bad_timestamp | 4 | 4 | 0 | 0 | 0 | 100.0 |
| stream | sessions | malformed | truncated_json | 2 | 2 | 0 | 0 | 0 | 100.0 |
| stream | sessions | malformed | type_mismatch | 1 | 1 | 0 | 0 | 0 | 100.0 |
| stream | sessions | null | missing_value | 32 | 32 | 0 | 0 | 0 | 100.0 |
| stream | sessions | out_of_range | impossible_value | 12 | 12 | 0 | 0 | 0 | 100.0 |

_40 row(s)_
