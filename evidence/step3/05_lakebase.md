# Lakebase: instance, synced tables, rows, read latency

Captured 2026-11-05 17:35 UTC from workspace profile `febar` by `scripts/capture_evidence_step3.py`.

## Instance (Lakebase Provisioned)

```json
{
  "name": "banksia-netmon-lakebase",
  "state": "DatabaseInstanceState.AVAILABLE",
  "capacity": "CU_1",
  "pg_version": "PG_VERSION_16",
  "read_write_dns": "ep-fragrant-shadow-d2yxrd90.database.us-east-1.cloud.databricks.com",
  "creator": "louis.chen@databricks.com",
  "uid": "2945acf5-6e36-4fdd-87f6-3827e9454c2c"
}
```

## Synced table `telco_netmon_febar_catalog.netmon_rca.lb_element_status`

```json
{
  "source": "telco_netmon_febar_catalog.netmon_rca.element_status",
  "primary_key": [
    "element_id"
  ],
  "scheduling_policy": "SyncedTableSchedulingPolicy.TRIGGERED",
  "database_instance": "banksia-netmon-lakebase",
  "logical_database": "netmon_serving",
  "state": "SyncedTableState.SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE",
  "message": "Synced table creation succeeded using Delta Live Tables: https://fevm-telco-netmon-febar.cloud.databricks.com#joblist/pipelines/eb85df61-12fb-4bfe-8baf-0a24254ef161/updates/27fe39b7-f99e-4139-945a-0f1cb41f8251.",
  "pipeline_id": "eb85df61-12fb-4bfe-8baf-0a24254ef161",
  "last_sync": "SyncedTableTriggeredUpdateStatus(last_processed_commit_version=10, timestamp='2026-11-05T17:24:47Z', triggered_update_progress=None)"
}
```

## Synced table `telco_netmon_febar_catalog.netmon_rca.lb_open_incidents`

```json
{
  "source": "telco_netmon_febar_catalog.netmon_rca.open_incidents",
  "primary_key": [
    "incident_id"
  ],
  "scheduling_policy": "SyncedTableSchedulingPolicy.TRIGGERED",
  "database_instance": "banksia-netmon-lakebase",
  "logical_database": "netmon_serving",
  "state": "SyncedTableState.SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE",
  "message": "Synced table creation succeeded using Delta Live Tables: https://fevm-telco-netmon-febar.cloud.databricks.com#joblist/pipelines/de1a6b07-9c92-4c50-bc8d-dd195d68e6f5/updates/70b4b4e6-29e6-48d8-9f91-e2eea913893b.",
  "pipeline_id": "de1a6b07-9c92-4c50-bc8d-dd195d68e6f5",
  "last_sync": "SyncedTableTriggeredUpdateStatus(last_processed_commit_version=11, timestamp='2026-11-05T17:24:46Z', triggered_update_progress=None)"
}
```

## Read-latency check (psycopg + OAuth token, from a serverless job; latest run)

```sql
SELECT run_at, query, n, p50_ms, p95_ms, p99_ms, max_ms, capacity, element_status_rows, open_incidents_rows
        FROM telco_netmon_febar_catalog.netmon_rca.lakebase_latency_check WHERE run_at = (SELECT max(run_at) FROM telco_netmon_febar_catalog.netmon_rca.lakebase_latency_check)
```

| run_at | query | n | p50_ms | p95_ms | p99_ms | max_ms | capacity | element_status_rows | open_incidents_rows |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-05T17:24:58.381817+00:00 | element_status by element_id (PK) | 300 | 2.94 | 9.76 | 18.63 | 24.34 | CU_1 | 1887 | 17 |
| 2026-11-05T17:24:58.381817+00:00 | open_incidents by region_code | 300 | 2.69 | 6.94 | 12.63 | 13.29 | CU_1 | 1887 | 17 |
| 2026-11-05T17:24:58.381817+00:00 | open_incident suspects joined to element_status | 300 | 2.4 | 8.57 | 17.88 | 20.96 | CU_1 | 1887 | 17 |

_3 row(s)_

## Row counts read from Postgres

```json
{
  "lb_element_status_rows": 1887,
  "lb_open_incidents_rows": 17
}
```

## Sample rows read from Postgres: netmon_rca.lb_element_status

```json
[
  {
    "element_id": "AGG-NQL-01",
    "element_type": "AGG_ROUTER",
    "parent_id": "UPF-NQL-01",
    "region_code": "NQL",
    "n_desc_cells": "None",
    "n_impacted_cells": "0.0",
    "impacted_fraction": "0.0",
    "silent_fraction": "0.0",
    "n_alarms": "0.0",
    "n_service_down_alarms": "0.0",
    "rca_score": "None",
    "state": "ok",
    "open_incident_id": "None",
    "suspect_rank": "None",
    "last_updated_ts": "2026-10-09 00:56:00+00:00",
    "refreshed_at": "2026-11-05 17:23:35.677210+00:00",
    "model_version": "4"
  },
  {
    "element_id": "AGG-NQL-02",
    "element_type": "AGG_ROUTER",
    "parent_id": "UPF-NQL-01",
    "region_code": "NQL",
    "n_desc_cells": "3.0",
    "n_impacted_cells": "3.0",
    "impacted_fraction": "1.0",
    "silent_fraction": "1.0",
    "n_alarms": "2.0",
    "n_service_down_alarms": "1.0",
    "rca_score": "1.0",
    "state": "down",
    "open_incident_id": "RCA-d28473ab1bd7b846",
    "suspect_rank": "1.0",
    "last_updated_ts": "2026-10-09 00:56:00+00:00",
    "refreshed_at": "2026-11-05 17:23:35.677210+00:00",
    "model_version": "4"
  },
  {
    "element_id": "AGG-NQL-03",
    "element_type": "AGG_ROUTER",
    "parent_id": "UPF-NQL-01",
    "region_code": "NQL",
    "n_desc_cells": "None",
    "n_impacted_cells": "0.0",
    "impacted_fraction": "0.0",
    "silent_fraction": "0.0",
    "n_alarms": "0.0",
    "n_service_down_alarms": "0.0",
    "rca_score": "None",
    "state": "ok",
    "open_incident_id": "None",
    "suspect_rank": "None",
    "last_updated_ts": "2026-10-09 00:56:00+00:00",
    "refreshed_at": "2026-11-05 17:23:35.677210+00:00",
    "model_version": "4"
  },
  {
    "element_id": "AGG-NQL-04",
    "element_type": "AGG_ROUTER",
    "parent_id": "UPF-NQL-01",
    "region_code": "NQL",
    "n_desc_cells": "None",
    "n_impacted_cells": "0.0",
    "impacted_fraction": "0.0",
    "silent_fraction": "0.0",
    "n_alarms": "0.0",
    "n_service_down_alarms": "0.0",
    "rca_score": "None",
    "state": "ok",
    "open_incident_id": "None",
    "suspect_rank": "None",
    "last_updated_ts": "2026-10-09 00:56:00+00:00",
    "refreshed_at": "2026-11-05 17:23:35.677210+00:00",
    "model_version": "4"
  },
  {
    "element_id": "AGG-NSW-01",
    "element_type": "AGG_ROUTER",
    "parent_id": "UPF-NSW-01",
    "region_code": "NSW",
    "n_desc_cells": "167.99996948242188",
    "n_impacted_cells": "18.0",
    "impacted_fraction": "0.1071428582072258",
    "silent_fraction": "0.0357142873108387",
    "n_alarms": "1.0",
    "n_service_down_alarms": "0.0",
    "rca_score": "0.07429145516074451",
    "state": "impacted",
    "open_incident_id": "RCA-fbd7ff66e62b0b42",
    "suspect_rank": "2.0",
    "last_updated_ts": "2026-10-09 00:56:00+00:00",
    "refreshed_at": "2026-11-05 17:23:35.677210+00:00",
    "model_version": "4"
  }
]
```

## Sample rows read from Postgres: netmon_rca.lb_open_incidents

```json
[
  {
    "incident_id": "RCA-1073d4d88aa7e05b",
    "source_run": "stream",
    "region_code": "VIC",
    "case_id": "stream|VIC|20261009T0056|CELL-VIC-00062-5G2",
    "detected_ts": "2026-10-08 23:56:00+00:00",
    "last_scored_ts": "2026-10-09 00:56:00+00:00",
    "status": "open",
    "suspect_1_id": "CELL-VIC-00062-5G2",
    "suspect_1_type": "CELL",
    "suspect_1_score": "1.0",
    "suspect_2_id": "AGG-VIC-03",
    "suspect_2_type": "AGG_ROUTER",
    "suspect_2_score": "0.0",
    "suspect_3_id": "AMF-VIC-01",
    "suspect_3_type": "AMF_MME",
    "suspect_3_score": "0.0",
    "n_impacted_cells": "1",
    "n_candidates": "6",
    "model_version": "4",
    "refreshed_at": "2026-11-05 17:23:35.677210+00:00"
  },
  {
    "incident_id": "RCA-27ed3e8af852d33a",
    "source_run": "stream",
    "region_code": "VIC",
    "case_id": "stream|VIC|20261009T0056|BH-VIC-0005",
    "detected_ts": "2026-10-08 23:56:00+00:00",
    "last_scored_ts": "2026-10-09 00:56:00+00:00",
    "status": "open",
    "suspect_1_id": "BH-VIC-0005",
    "suspect_1_type": "BACKHAUL_LINK",
    "suspect_1_score": "1.0",
    "suspect_2_id": "AGG-VIC-01",
    "suspect_2_type": "AGG_ROUTER",
    "suspect_2_score": "0.0",
    "suspect_3_id": "CELL-VIC-00010-5G2",
    "suspect_3_type": "CELL",
    "suspect_3_score": "0.0",
    "n_impacted_cells": "12",
    "n_candidates": "19",
    "model_version": "4",
    "refreshed_at": "2026-11-05 17:23:35.677210+00:00"
  },
  {
    "incident_id": "RCA-399fe9bb03f3b4cb",
    "source_run": "stream",
    "region_code": "VIC",
    "case_id": "stream|VIC|20261009T0056|CELL-VIC-00022-5G3",
    "detected_ts": "2026-10-09 00:34:00+00:00",
    "last_scored_ts": "2026-10-09 00:56:00+00:00",
    "status": "open",
    "suspect_1_id": "CELL-VIC-00022-5G3",
    "suspect_1_type": "CELL",
    "suspect_1_score": "1.0",
    "suspect_2_id": "AGG-VIC-02",
    "suspect_2_type": "AGG_ROUTER",
    "suspect_2_score": "0.0",
    "suspect_3_id": "AMF-VIC-01",
    "suspect_3_type": "AMF_MME",
    "suspect_3_score": "0.0",
    "n_impacted_cells": "1",
    "n_candidates": "7",
    "model_version": "4",
    "refreshed_at": "2026-11-05 17:23:35.677210+00:00"
  },
  {
    "incident_id": "RCA-4b24e8c0bfedac1a",
    "source_run": "stream",
    "region_code": "NSW",
    "case_id": "stream|NSW|20261009T0056|BH-NSW-0010",
    "detected_ts": "2026-10-08 23:56:00+00:00",
    "last_scored_ts": "2026-10-09 00:56:00+00:00",
    "status": "open",
    "suspect_1_id": "BH-NSW-0010",
    "suspect_1_type": "BACKHAUL_LINK",
    "suspect_1_score": "1.0",
    "suspect_2_id": "AGG-NSW-01",
    "suspect_2_type": "AGG_ROUTER",
    "suspect_2_score": "0.0743",
    "suspect_3_id": "SITE-NSW-00025",
    "suspect_3_type": "SITE",
    "suspect_3_score": "0.0743",
    "n_impacted_cells": "3",
    "n_candidates": "11",
    "model_version": "4",
    "refreshed_at": "2026-11-05 17:23:35.677210+00:00"
  },
  {
    "incident_id": "RCA-55424701801c7330",
    "source_run": "stream",
    "region_code": "NSW",
    "case_id": "stream|NSW|20261009T0056|CELL-NSW-00051-4G3",
    "detected_ts": "2026-10-09 00:19:00+00:00",
    "last_scored_ts": "2026-10-09 00:56:00+00:00",
    "status": "open",
    "suspect_1_id": "CELL-NSW-00051-4G3",
    "suspect_1_type": "CELL",
    "suspect_1_score": "1.0",
    "suspect_2_id": "SITE-NSW-00045",
    "suspect_2_type": "SITE",
    "suspect_2_score": "0.0002",
    "suspect_3_id": "AGG-NSW-02",
    "suspect_3_type": "AGG_ROUTER",
    "suspect_3_score": "0.0",
    "n_impacted_cells": "1",
    "n_candidates": "9",
    "model_version": "4",
    "refreshed_at": "2026-11-05 17:23:35.677210+00:00"
  }
]
```

## Primary-key lookup plan (EXPLAIN)

```text
Index Scan using "__db_tmp_ebceee76-8c81-4ee3-aa6d-c7eb35cfa7b7_pkey" on partition_17030 lb_element_status  (cost=0.28..8.29 rows=1 width=145)
  Index Cond: (element_id = 'AGG-VIC-02'::text)
```
