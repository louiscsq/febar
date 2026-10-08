# Expectation pass/fail metrics (pipeline event log)

Captured 2026-10-08 15:30 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

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
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | incident_id_not_null | 325 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | on_time | 20098 | 219 | 1.078 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | event_ts_valid | 20270 | 47 | 0.231 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | event_ts_plausible | 20278 | 39 | 0.192 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | alarm_code_not_null | 20287 | 30 | 0.148 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | known_element | 20294 | 23 | 0.113 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | element_id_not_null | 20294 | 23 | 0.113 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | severity_not_null | 20294 | 23 | 0.113 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | record_id_not_null | 20317 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | alarm_id_not_null | 20317 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | on_time | 2406906 | 24340 | 1.001 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | event_ts_valid | 2428111 | 3135 | 0.129 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | dl_throughput_mbps_not_null | 2429283 | 1963 | 0.081 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | latency_ms_not_null | 2429284 | 1962 | 0.081 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | availability_pct_not_null | 2429312 | 1934 | 0.080 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | prb_util_pct_not_null | 2429341 | 1905 | 0.078 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | no_rescued_data | 2429597 | 1649 | 0.068 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | rrc_setup_success_pct_not_null | 2429732 | 1514 | 0.062 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | active_users_not_null | 2429737 | 1509 | 0.062 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | cell_id_not_null | 2429782 | 1464 | 0.060 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | known_element | 2429782 | 1464 | 0.060 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | dl_throughput_mbps_in_range | 2430422 | 824 | 0.034 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | rrc_setup_success_pct_in_range | 2430427 | 819 | 0.034 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | availability_pct_in_range | 2430429 | 817 | 0.034 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | prb_util_pct_in_range | 2430437 | 809 | 0.033 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | active_users_in_range | 2430446 | 800 | 0.033 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | latency_ms_in_range | 2430448 | 798 | 0.033 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | record_id_not_null | 2431246 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | ul_throughput_mbps_in_range | 2431246 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | attach_success_pct_in_range | 2431246 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | session_drop_rate_pct_in_range | 2431246 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | packet_loss_pct_in_range | 2431246 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | valid_window | 43 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | on_time | 1302549 | 13151 | 1.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | start_ts_valid | 1313540 | 2160 | 0.164 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | bytes_dl_not_null | 1314039 | 1661 | 0.126 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | outcome_not_null | 1314379 | 1321 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | duration_s_in_range | 1314382 | 1318 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | cell_id_not_null | 1314385 | 1315 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | known_element | 1314385 | 1315 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | bytes_dl_in_range | 1314387 | 1313 | 0.100 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | imsi_not_null | 1314409 | 1291 | 0.098 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | no_rescued_data | 1314817 | 883 | 0.067 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | record_id_not_null | 1315700 | 0 | 0.000 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | bytes_ul_in_range | 1315700 | 0 | 0.000 |
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
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | 162 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | 20253 |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | 0 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | 10988 |
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
| alarms | stream | event_ts_valid | 11 |
| alarms | stream | event_ts_plausible | 6 |
| alarms | stream | severity_not_null | 5 |
| alarms | stream | alarm_code_not_null | 5 |
| alarms | stream | known_element | 3 |
| alarms | stream | element_id_not_null | 3 |
| alarms | stream | parseable_record | 1 |
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
| kpis | stream | event_ts_valid | 693 |
| kpis | stream | dl_throughput_mbps_not_null | 422 |
| kpis | stream | prb_util_pct_not_null | 415 |
| kpis | stream | latency_ms_not_null | 401 |
| kpis | stream | availability_pct_not_null | 382 |
| kpis | stream | parseable_record | 353 |
| kpis | stream | no_rescued_data | 329 |
| kpis | stream | rrc_setup_success_pct_not_null | 327 |
| kpis | stream | active_users_not_null | 290 |
| kpis | stream | known_element | 287 |
| kpis | stream | cell_id_not_null | 287 |
| kpis | stream | dl_throughput_mbps_in_range | 195 |
| kpis | stream | prb_util_pct_in_range | 186 |
| kpis | stream | rrc_setup_success_pct_in_range | 175 |
| kpis | stream | availability_pct_in_range | 169 |
| kpis | stream | latency_ms_in_range | 155 |
| kpis | stream | active_users_in_range | 147 |
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
| sessions | stream | start_ts_valid | 15 |
| sessions | stream | cell_id_not_null | 12 |
| sessions | stream | known_element | 12 |
| sessions | stream | bytes_dl_not_null | 12 |
| sessions | stream | duration_s_in_range | 10 |
| sessions | stream | bytes_dl_in_range | 8 |
| sessions | stream | no_rescued_data | 7 |
| sessions | stream | outcome_not_null | 6 |
| sessions | stream | parseable_record | 6 |
| sessions | stream | imsi_not_null | 5 |

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
| kpis | K-CELL-NQL-00001-4G3-202610081931 | ["dl_throughput_mbps_not_null"] | 2026-10-08T19:31:00Z | {"cell_id":"CELL-NQL-00001-4G3","event_ts_raw":"2026-10-08T19:31:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202609260530 | ["event_ts_valid"] | NULL | {"cell_id":"CELL-NQL-00001-4G1","granularity_s":900,"availability_pct":100.0,"active_users":15,"prb_util_pct": | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202610050845 | ["cell_id_not_null","known_element"] | 2026-10-05T08:45:00Z | {"event_ts_raw":"2026-10-05T08:45:00Z","granularity_s":900,"availability_pct":100.0,"active_users":10,"prb_uti | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610031315 | ["prb_util_pct_not_null"] | 2026-10-03T13:15:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-03T13:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610081622 | ["parseable_record"] | NULL | NULL | NULL | {"record_id":"K-CELL-NQL-00001-4G1-202610081622","event_ts":"2026-10-0 |
| kpis | K-CELL-NQL-00001-4G3-202610061415 | ["rrc_setup_success_pct_in_range"] | 2026-10-06T14:15:00Z | {"cell_id":"CELL-NQL-00001-4G3","event_ts_raw":"2026-10-06T14:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202609241415 | ["latency_ms_not_null"] | 2026-09-24T14:15:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-09-24T14:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202609240015 | ["dl_throughput_mbps_in_range"] | 2026-09-24T00:15:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-09-24T00:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610082004 | ["active_users_in_range"] | 2026-10-08T20:04:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-08T20:04:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202609281900 | ["availability_pct_not_null"] | 2026-09-28T19:00:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-09-28T19:00:00Z","granularity_s":900,"active_users":9,"pr | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202609240215 | ["no_rescued_data","dl_throughput_mbps_not_null"] | 2026-09-24T02:15:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-09-24T02:15:00Z","granularity_s":900,"availability_pct":1 | {"dl_throughput_mbps":"ERR","_file_path":"/Volumes/telco_net | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610051145 | ["latency_ms_in_range"] | 2026-10-05T11:45:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-05T11:45:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610081943 | ["rrc_setup_success_pct_not_null"] | 2026-10-08T19:43:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-08T19:43:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
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
| stream | alarms | duplicate | redelivery | 19 | 0 | 19 | 0 | 19 | 100.0 |
| stream | alarms | late_arrival | delayed_delivery | 35 | 0 | 35 | 35 | 35 | 100.0 |
| stream | alarms | malformed | bad_timestamp | 7 | 7 | 0 | 0 | 0 | 100.0 |
| stream | alarms | malformed | truncated_json | 1 | 1 | 0 | 0 | 0 | 100.0 |
| stream | alarms | null | missing_value | 17 | 17 | 0 | 0 | 0 | 100.0 |
| stream | alarms | out_of_range | clock_skew | 6 | 6 | 0 | 0 | 0 | 100.0 |
| stream | kpis | duplicate | redelivery | 2543 | 0 | 2543 | 0 | 2543 | 100.0 |
| stream | kpis | late_arrival | delayed_delivery | 5112 | 0 | 5112 | 5112 | 5112 | 100.0 |
| stream | kpis | malformed | bad_timestamp | 340 | 340 | 0 | 0 | 0 | 100.0 |
| stream | kpis | malformed | truncated_json | 353 | 353 | 0 | 0 | 0 | 100.0 |
| stream | kpis | malformed | type_mismatch | 329 | 329 | 0 | 0 | 0 | 100.0 |
| stream | kpis | null | missing_value | 2548 | 2548 | 0 | 0 | 0 | 100.0 |
| stream | kpis | out_of_range | impossible_value | 1027 | 1027 | 0 | 0 | 0 | 100.0 |
| stream | sessions | duplicate | redelivery | 51 | 0 | 51 | 0 | 0 | NULL |
| stream | sessions | late_arrival | delayed_delivery | 72 | 0 | 72 | 72 | 0 | 100.0 |
| stream | sessions | malformed | bad_timestamp | 6 | 6 | 0 | 0 | 0 | 100.0 |
| stream | sessions | malformed | truncated_json | 6 | 6 | 0 | 0 | 0 | 100.0 |
| stream | sessions | malformed | type_mismatch | 7 | 7 | 0 | 0 | 0 | 100.0 |
| stream | sessions | null | missing_value | 42 | 42 | 0 | 0 | 0 | 100.0 |
| stream | sessions | out_of_range | impossible_value | 18 | 18 | 0 | 0 | 0 | 100.0 |

_40 row(s)_
