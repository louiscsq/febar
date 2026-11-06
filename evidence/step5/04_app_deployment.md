# Databricks App: deployment status, resources and logs

Captured 2026-11-06 11:35 UTC from workspace profile `febar` by `scripts/capture_evidence_step5.py`.

`banksia-noc-topology` deployed by the bundle (`resources/app.yml`, source `app/`, `app/app.yaml`). Status and configuration from
`GET /api/2.0/apps/banksia-noc-topology`; deployments from `.../deployments`; logs from `databricks apps logs` (client IP addresses
removed).

```json
{
  "name": "banksia-noc-topology",
  "url": "https://banksia-noc-topology-7474648429104135.aws.databricksapps.com",
  "description": "Banksia NOC: network topology, failing-element pinpoint, incident panel, SMS draft review, Ask Genie",
  "compute_status": {
    "message": "App compute is running.",
    "state": "ACTIVE"
  },
  "app_status": {
    "message": "App has status: App is running",
    "state": "RUNNING"
  },
  "compute_size": "MEDIUM",
  "service_principal_name": "app-t3z4by banksia-noc-topology",
  "service_principal_client_id": "23923ae9-3de4-453b-b13f-b61f7ba84868",
  "user_api_scopes": [
    "sql",
    "dashboards.genie"
  ],
  "effective_user_api_scopes": [
    "dashboards.genie",
    "iam.access-control:read",
    "iam.current-user:read",
    "sql"
  ],
  "resources": [
    {
      "database": {
        "database_name": "netmon_serving",
        "instance_name": "banksia-netmon-lakebase",
        "permission": "CAN_CONNECT_AND_CREATE"
      },
      "description": "Lakebase serving database (synced incident / element-status / AI tables + SMS reviews)",
      "name": "database"
    },
    {
      "description": "Serverless SQL warehouse for UC reads (as the user) and the Genie space",
      "name": "sql-warehouse",
      "sql_warehouse": {
        "id": "d7fa853ab15b20a3",
        "permission": "CAN_USE"
      }
    },
    {
      "description": "NOC Genie space (resources/genie.yml)",
      "genie_space": {
        "name": "noc_genie",
        "permission": "CAN_RUN",
        "space_id": "01f1d9cd2ee0117c82252259a6bfd81f"
      },
      "name": "genie-space"
    }
  ],
  "default_source_code_path": "/Workspace/Users/louis.chen@databricks.com/.bundle/banksia_netmon/dev/files/app",
  "create_time": "2026-11-06T10:54:23Z",
  "update_time": "2026-11-06T11:14:25Z",
  "creator": "louis.chen@databricks.com"
}
```

## Deployments (latest 5)

| deployment_id | create_time | mode | state | message | source_code_path |
|---|---|---|---|---|---|
| 01f1d9d339b71d2b903b6973593577db | 2026-11-06T11:14:25Z | SNAPSHOT | SUCCEEDED | App started successfully | /Workspace/Users/louis.chen@databricks.com/.bundle/banksia_netmon/dev/files/app |
| 01f1d9d2441312d3a6c289bc81bf717d | 2026-11-06T11:07:33Z | SNAPSHOT | SUCCEEDED | App started successfully | /Workspace/Users/louis.chen@databricks.com/.bundle/banksia_netmon/dev/files/app |
| 01f1d9d0e60b1638abcbcbf2972724bd | 2026-11-06T10:57:46Z | SNAPSHOT | SUCCEEDED | App started successfully | /Workspace/Users/louis.chen@databricks.com/.bundle/banksia_netmon/dev/files/app |

_3 row(s)_

## Live checks through the Apps proxy

`/api/health` round-trips to Lakebase as the app service principal; then 20 timed calls of the hot-path endpoints (warm):

```json
{
  "request": "GET /api/health",
  "http_status": 200,
  "latency_ms": 1028,
  "body": {
    "status": "ok",
    "lakebase": {
      "pg_user": "23923ae9-3de4-453b-b13f-b61f7ba84868",
      "server_time": "2026-11-06T11:35:58.843621+00:00",
      "open_incidents": 17
    },
    "lakebase_ms": 7.0
  }
}
```

End-to-end latency measured from the capturing laptop (includes the internet round trip and the Apps proxy):

| endpoint | n | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|
| /api/incidents?region=NSW | 20 | 1048 | 1056 | 1057 |
| /api/incidents/RCA-c7276c3238a27971 | 20 | 1049 | 1087 | 1841 |
| /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 | 20 | 1571 | 1581 | 1582 |

_3 row(s)_

Server-side time inside the app for the same calls (from the app's own request log, `noc_app ... -> 200 in N ms`): Lakebase queries plus, on a cold cache, the warehouse topology read:

| endpoint (path) | n | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|
| /api/incidents | 38 | 10 | 13 | 47 |
| /api/incidents/RCA-c7276c3238a27971 | 43 | 21 | 26 | 1720 |
| /api/regions/NSW/topology | 43 | 29 | 33 | 36 |

_3 row(s)_

## App logs (last 60 lines)

```text
2026-11-06T11:36:42Z [APP] 2026-11-06 11:36:42,653 INFO noc_app GET /api/regions/NSW/topology -> 200 in 30 ms user=louis.chen@databricks.com
2026-11-06T11:36:42Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:36:43Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:36:42 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:36:44Z [APP] 2026-11-06 11:36:44,225 INFO noc_app GET /api/regions/NSW/topology -> 200 in 33 ms user=louis.chen@databricks.com
2026-11-06T11:36:44Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:36:45Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:36:44 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:36:45Z [APP] 2026-11-06 11:36:45,795 INFO noc_app GET /api/regions/NSW/topology -> 200 in 29 ms user=louis.chen@databricks.com
2026-11-06T11:36:45Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:36:46Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:36:45 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:36:47Z [APP] 2026-11-06 11:36:47,364 INFO noc_app GET /api/regions/NSW/topology -> 200 in 32 ms user=louis.chen@databricks.com
2026-11-06T11:36:47Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:36:48Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:36:47 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:36:48Z [APP] 2026-11-06 11:36:48,938 INFO noc_app GET /api/regions/NSW/topology -> 200 in 29 ms user=louis.chen@databricks.com
2026-11-06T11:36:48Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:36:49Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:36:48 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:36:50Z [APP] 2026-11-06 11:36:50,509 INFO noc_app GET /api/regions/NSW/topology -> 200 in 28 ms user=louis.chen@databricks.com
2026-11-06T11:36:50Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:36:51Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:36:50 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:36:52Z [APP] 2026-11-06 11:36:52,084 INFO noc_app GET /api/regions/NSW/topology -> 200 in 29 ms user=louis.chen@databricks.com
2026-11-06T11:36:52Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:36:52Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:36:52 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:36:53Z [APP] 2026-11-06 11:36:53,661 INFO noc_app GET /api/regions/NSW/topology -> 200 in 28 ms user=louis.chen@databricks.com
2026-11-06T11:36:53Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:36:54Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:36:53 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:36:55Z [APP] 2026-11-06 11:36:55,232 INFO noc_app GET /api/regions/NSW/topology -> 200 in 30 ms user=louis.chen@databricks.com
2026-11-06T11:36:55Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:36:56Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:36:55 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:36:56Z [APP] 2026-11-06 11:36:56,809 INFO noc_app GET /api/regions/NSW/topology -> 200 in 33 ms user=louis.chen@databricks.com
2026-11-06T11:36:56Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:36:57Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:36:56 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:36:58Z [APP] 2026-11-06 11:36:58,374 INFO noc_app GET /api/regions/NSW/topology -> 200 in 28 ms user=louis.chen@databricks.com
2026-11-06T11:36:58Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:36:59Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:36:58 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:36:59Z [APP] 2026-11-06 11:36:59,949 INFO noc_app GET /api/regions/NSW/topology -> 200 in 31 ms user=louis.chen@databricks.com
2026-11-06T11:36:59Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:37:00Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:36:59 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:37:01Z [APP] 2026-11-06 11:37:01,521 INFO noc_app GET /api/regions/NSW/topology -> 200 in 28 ms user=louis.chen@databricks.com
2026-11-06T11:37:01Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:37:02Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:37:01 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:37:03Z [APP] 2026-11-06 11:37:03,091 INFO noc_app GET /api/regions/NSW/topology -> 200 in 28 ms user=louis.chen@databricks.com
2026-11-06T11:37:03Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:37:03Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:37:03 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:37:04Z [APP] 2026-11-06 11:37:04,667 INFO noc_app GET /api/regions/NSW/topology -> 200 in 27 ms user=louis.chen@databricks.com
2026-11-06T11:37:04Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:37:05Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:37:04 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:37:06Z [APP] 2026-11-06 11:37:06,236 INFO noc_app GET /api/regions/NSW/topology -> 200 in 29 ms user=louis.chen@databricks.com
2026-11-06T11:37:06Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:37:07Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:37:06 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:37:07Z [APP] 2026-11-06 11:37:07,809 INFO noc_app GET /api/regions/NSW/topology -> 200 in 27 ms user=louis.chen@databricks.com
2026-11-06T11:37:07Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:37:08Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:37:07 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:37:09Z [APP] 2026-11-06 11:37:09,385 INFO noc_app GET /api/regions/NSW/topology -> 200 in 28 ms user=louis.chen@databricks.com
2026-11-06T11:37:09Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:37:10Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:37:09 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:37:10Z [APP] 2026-11-06 11:37:10,959 INFO noc_app GET /api/regions/NSW/topology -> 200 in 34 ms user=louis.chen@databricks.com
2026-11-06T11:37:10Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:37:11Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:37:10 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T11:37:12Z [APP] 2026-11-06 11:37:12,533 INFO noc_app GET /api/regions/NSW/topology -> 200 in 28 ms user=louis.chen@databricks.com
2026-11-06T11:37:12Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T11:37:13Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:11:37:12 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
```
