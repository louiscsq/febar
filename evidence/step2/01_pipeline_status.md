# Pipeline runs and update status

Captured 2026-10-08 13:53 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

## Pipeline

- name: `banksia-netmon-pipeline`
- pipeline_id: `80449004-f45a-4b32-8215-f68fdf6acfd9`
- state: `IDLE`
- serverless: `True`, continuous: `False`, channel: `CURRENT`
- catalog / default schema: `telco_netmon_febar_catalog` / `netmon_bronze`
- event log: `telco_netmon_febar_catalog.netmon_eval.netmon_pipeline_event_log`

## Updates (from the event log)

```sql
SELECT origin.update_id, min(timestamp) AS started, max(timestamp) AS last_event,
               max_by(details:update_progress:state::string, timestamp)
                 FILTER (WHERE event_type = 'update_progress') AS final_state,
               max(CASE WHEN event_type = 'create_update' THEN details:create_update:cause::string END) AS cause,
               max(CASE WHEN event_type = 'create_update' THEN details:create_update:full_refresh::string END)
                 AS full_refresh
        FROM telco_netmon_febar_catalog.netmon_eval.netmon_pipeline_event_log GROUP BY origin.update_id ORDER BY started
```

| update_id | started | last_event | final_state | cause | full_refresh |
|---|---|---|---|---|---|
| NULL | 2026-10-08T11:17:47.086Z | 2026-10-08T13:21:09.211Z | NULL | NULL | NULL |
| d0784fab-0a3a-421f-8558-1495518ad781 | 2026-10-08T11:23:14.884Z | 2026-10-08T11:24:06.823Z | FAILED | API_CALL | false |
| 81410d2e-dd4d-45ac-91bb-fd19d798ed93 | 2026-10-08T11:24:10.951Z | 2026-10-08T11:24:54.406Z | FAILED | RETRY_ON_FAILURE | false |
| d758dbad-f4e4-4d41-95f8-441ead683d07 | 2026-10-08T11:24:55.589Z | 2026-10-08T11:26:05.876Z | FAILED | RETRY_ON_FAILURE | false |
| 417cc092-5ea9-47d7-881a-51841053ebbd | 2026-10-08T11:26:08.795Z | 2026-10-08T11:28:01.367Z | FAILED | RETRY_ON_FAILURE | false |
| 6b6a681c-eb33-451d-bdc8-be2490dac510 | 2026-10-08T11:28:04.809Z | 2026-10-08T11:31:13.544Z | FAILED | RETRY_ON_FAILURE | false |
| 01b6cadd-bd30-49ac-8312-b4cd9af7aa7a | 2026-10-08T11:31:15.401Z | 2026-10-08T11:34:06.700Z | CANCELED | RETRY_ON_FAILURE | false |
| 9e999dfe-71a0-4886-abbd-44c9fab2040d | 2026-10-08T11:34:10.805Z | 2026-10-08T11:38:52.725Z | COMPLETED | API_CALL | true |
| 63ee8378-6722-4351-bb83-0e0ef601f232 | 2026-10-08T11:42:30.120Z | 2026-10-08T11:47:48.198Z | COMPLETED | API_CALL | true |
| 2cf1a92f-f903-4744-b226-f1a30b72ca55 | 2026-10-08T11:48:57.106Z | 2026-10-08T11:50:58.881Z | FAILED | API_CALL | false |
| 92aed2f2-4228-4a50-9fe1-08b835a91f28 | 2026-10-08T11:51:04.388Z | 2026-10-08T11:52:38.166Z | FAILED | RETRY_ON_FAILURE | false |
| b8bc36ef-93bb-47f2-b75e-99ab5bed4720 | 2026-10-08T11:52:41.279Z | 2026-10-08T11:54:35.639Z | FAILED | RETRY_ON_FAILURE | false |
| d4301be6-7e7d-4795-bab5-969de1b04fd6 | 2026-10-08T11:54:37.651Z | 2026-10-08T11:57:14.388Z | FAILED | RETRY_ON_FAILURE | false |
| 28242976-dedd-41a1-a19c-8635d2d918e0 | 2026-10-08T11:57:17.271Z | 2026-10-08T12:01:17.222Z | FAILED | RETRY_ON_FAILURE | false |
| 8b85060c-c921-404c-8b5e-74b3e6f1a15e | 2026-10-08T12:01:21.748Z | 2026-10-08T12:02:13.034Z | CANCELED | RETRY_ON_FAILURE | false |
| 5a2cfd30-42a7-4ff3-825a-3e28dd1ad49a | 2026-10-08T12:04:02.835Z | 2026-10-08T12:09:23.041Z | COMPLETED | API_CALL | true |
| e608ebf4-1337-4625-95fb-49c68f91917d | 2026-10-08T12:10:11.861Z | 2026-10-08T12:25:56.493Z | CANCELED | API_CALL | false |
| 8e4012da-0830-432a-aa6f-0b5d03debeec | 2026-10-08T12:27:41.220Z | 2026-10-08T12:33:20.746Z | COMPLETED | API_CALL | true |
| 35be89c6-9d7c-4339-a4ff-aba779c9545b | 2026-10-08T12:33:41.834Z | 2026-10-08T13:20:42.514Z | CANCELED | API_CALL | false |
| 07fec833-3d59-4a51-b0a3-dd1b2c3118a1 | 2026-10-08T13:21:15.214Z | 2026-10-08T13:23:44.770Z | COMPLETED | API_CALL | false |
| a5846662-11bb-4bd2-a1a6-d217f9368a7f | 2026-10-08T13:25:42.071Z | 2026-10-08T13:27:28.695Z | COMPLETED | API_CALL | false |

_21 row(s)_

## Flows of the latest completed update

```sql
WITH u AS (SELECT origin.update_id AS id FROM telco_netmon_febar_catalog.netmon_eval.netmon_pipeline_event_log
                   WHERE event_type = 'update_progress' AND details:update_progress:state::string = 'COMPLETED'
                   ORDER BY timestamp DESC LIMIT 1)
        SELECT origin.flow_name, max_by(details:flow_progress:status::string, timestamp) AS final_status,
               sum(details:flow_progress:metrics:num_output_rows::bigint) AS output_rows
        FROM telco_netmon_febar_catalog.netmon_eval.netmon_pipeline_event_log WHERE event_type = 'flow_progress' AND origin.update_id = (SELECT id FROM u)
        GROUP BY origin.flow_name ORDER BY origin.flow_name
```

| flow_name | final_status | output_rows |
|---|---|---|
| pipelines.flowTimeMetrics.missingFlowName | NULL | NULL |
| telco_netmon_febar_catalog.netmon_bronze.bronze_alarms | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_bronze.bronze_maintenance_windows | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_bronze.bronze_sessions | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_bronze.bronze_topology_edges | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_bronze.bronze_topology_nodes | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_bronze.quarantine_alarms | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_bronze.quarantine_alarms_corrupt | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_bronze.quarantine_kpis | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_bronze.quarantine_kpis_corrupt | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_bronze.quarantine_sessions | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_bronze.quarantine_sessions_corrupt | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_eval.bronze_gt_incidents | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_log | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_eval.eval_detection_precision | COMPLETED | 4 |
| telco_netmon_febar_catalog.netmon_eval.eval_dq_capture | COMPLETED | 40 |
| telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents | COMPLETED | 58 |
| telco_netmon_febar_catalog.netmon_eval.eval_incident_detection | COMPLETED | 35 |
| telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline | COMPLETED | 35 |
| telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary | NULL | 22 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_baseline | COMPLETED | 975575 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_5m | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | COMPLETED | 88787 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_silver.silver_alarms | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows | COMPLETED | 11 |
| telco_netmon_febar_catalog.netmon_silver.silver_sessions | COMPLETED | NULL |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_edges | COMPLETED | 1883 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | COMPLETED | 1887 |

_34 row(s)_

## Pipeline errors, if any (last 10)

Errors from the first deploy-and-fix iterations are kept here deliberately.

```sql
SELECT timestamp, origin.update_id, origin.flow_name, left(message, 200) AS message
        FROM telco_netmon_febar_catalog.netmon_eval.netmon_pipeline_event_log WHERE level = 'ERROR' ORDER BY timestamp DESC LIMIT 10
```

| timestamp | update_id | flow_name | message |
|---|---|---|---|
| 2026-10-08T12:01:17.222Z | 28242976-dedd-41a1-a19c-8635d2d918e0 | NULL | Update 282429 is FAILED since flow 'telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m' has failed more than … |
| 2026-10-08T12:01:15.612Z | 28242976-dedd-41a1-a19c-8635d2d918e0 | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | Flow 'telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m' has FAILED more than 2 times and will not be restar… |
| 2026-10-08T11:57:14.388Z | d4301be6-7e7d-4795-bab5-969de1b04fd6 | NULL | Update d4301b is FAILED since flow 'telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m' has failed more than … |
| 2026-10-08T11:57:11.557Z | d4301be6-7e7d-4795-bab5-969de1b04fd6 | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | Flow 'telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m' has FAILED more than 2 times and will not be restar… |
| 2026-10-08T11:54:35.540Z | b8bc36ef-93bb-47f2-b75e-99ab5bed4720 | NULL | Update b8bc36 is FAILED since flow 'telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m' has failed more than … |
| 2026-10-08T11:54:34.647Z | b8bc36ef-93bb-47f2-b75e-99ab5bed4720 | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | Flow 'telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m' has FAILED more than 2 times and will not be restar… |
| 2026-10-08T11:52:38.166Z | 92aed2f2-4228-4a50-9fe1-08b835a91f28 | NULL | Update 92aed2 is FAILED since flow 'telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m' has failed more than … |
| 2026-10-08T11:52:37.043Z | 92aed2f2-4228-4a50-9fe1-08b835a91f28 | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | Flow 'telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m' has FAILED more than 2 times and will not be restar… |
| 2026-10-08T11:50:58.881Z | 2cf1a92f-f903-4744-b226-f1a30b72ca55 | NULL | Update 2cf1a9 is FAILED since flow 'telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m' has failed more than … |
| 2026-10-08T11:50:57.162Z | 2cf1a92f-f903-4744-b226-f1a30b72ca55 | telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m | Flow 'telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m' has FAILED more than 2 times and will not be restar… |

_10 row(s)_
