# Databricks App: deployment status, resources and logs

Captured 2026-11-06 12:26 UTC from workspace profile `febar` by `scripts/capture_evidence_step5.py`.

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
  "update_time": "2026-11-06T11:54:50Z",
  "creator": "louis.chen@databricks.com"
}
```

## Deployments (latest 5)

| deployment_id | create_time | mode | state | message | source_code_path |
|---|---|---|---|---|---|
| 01f1d9d8df511be4a4c671c168ae205a | 2026-11-06T11:54:50Z | SNAPSHOT | SUCCEEDED | App started successfully | /Workspace/Users/louis.chen@databricks.com/.bundle/banksia_netmon/dev/files/app |
| 01f1d9d339b71d2b903b6973593577db | 2026-11-06T11:14:25Z | SNAPSHOT | SUCCEEDED | App started successfully | /Workspace/Users/louis.chen@databricks.com/.bundle/banksia_netmon/dev/files/app |
| 01f1d9d2441312d3a6c289bc81bf717d | 2026-11-06T11:07:33Z | SNAPSHOT | SUCCEEDED | App started successfully | /Workspace/Users/louis.chen@databricks.com/.bundle/banksia_netmon/dev/files/app |
| 01f1d9d0e60b1638abcbcbf2972724bd | 2026-11-06T10:57:46Z | SNAPSHOT | SUCCEEDED | App started successfully | /Workspace/Users/louis.chen@databricks.com/.bundle/banksia_netmon/dev/files/app |

_4 row(s)_

## Live checks through the Apps proxy

`/api/health` round-trips to Lakebase as the app service principal; then 20 timed calls of the hot-path endpoints (warm):

```json
{
  "request": "GET /api/health",
  "http_status": 200,
  "latency_ms": 1115,
  "body": {
    "status": "ok",
    "lakebase": {
      "pg_user": "23923ae9-3de4-453b-b13f-b61f7ba84868",
      "server_time": "2026-11-06T12:26:51.420798+00:00",
      "open_incidents": 17
    },
    "lakebase_ms": 11.1
  }
}
```

End-to-end latency measured from the capturing laptop (includes the internet round trip and the Apps proxy):

| endpoint | n | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|
| /api/incidents?region=NSW | 20 | 1050 | 1126 | 1309 |
| /api/incidents/RCA-c7276c3238a27971 | 20 | 1056 | 1840 | 2271 |
| /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 | 20 | 1572 | 1694 | 3670 |

_3 row(s)_

Server-side time inside the app for the same calls (from the app's own request log, `noc_app ... -> 200 in N ms`): Lakebase queries plus, on a cold cache, the warehouse topology read:

| endpoint (path) | n | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|
| /api/incidents | 24 | 12 | 13 | 14 |
| /api/incidents/RCA-c7276c3238a27971 | 30 | 26 | 957 | 2498 |
| /api/me | 10 | 1 | 1 | 840 |
| /api/regions/NSW/topology | 44 | 33 | 39 | 126 |

_4 row(s)_

## App logs (last 60 lines)

```text
2026-11-06T12:27:37Z [APP] 2026-11-06 12:27:37,053 INFO noc_app GET /api/regions/NSW/topology -> 200 in 35 ms user=louis.chen@databricks.com
2026-11-06T12:27:37Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:27:37Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:27:37 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:27:38Z [APP] 2026-11-06 12:27:38,611 INFO noc_app GET /api/regions/NSW/topology -> 200 in 39 ms user=louis.chen@databricks.com
2026-11-06T12:27:38Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:27:39Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:27:38 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:27:40Z [APP] 2026-11-06 12:27:40,283 INFO noc_app GET /api/regions/NSW/topology -> 200 in 36 ms user=louis.chen@databricks.com
2026-11-06T12:27:40Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:27:41Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:27:40 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:27:41Z [APP] 2026-11-06 12:27:41,878 INFO noc_app GET /api/regions/NSW/topology -> 200 in 35 ms user=louis.chen@databricks.com
2026-11-06T12:27:41Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:27:42Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:27:41 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:27:43Z [APP] 2026-11-06 12:27:43,405 INFO noc_app GET /api/regions/NSW/topology -> 200 in 35 ms user=louis.chen@databricks.com
2026-11-06T12:27:43Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:27:44Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:27:43 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:27:44Z [APP] 2026-11-06 12:27:44,942 INFO noc_app GET /api/regions/NSW/topology -> 200 in 38 ms user=louis.chen@databricks.com
2026-11-06T12:27:44Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:27:45Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:27:44 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:27:46Z [APP] 2026-11-06 12:27:46,472 INFO noc_app GET /api/regions/NSW/topology -> 200 in 37 ms user=louis.chen@databricks.com
2026-11-06T12:27:46Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:27:47Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:27:46 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:27:48Z [APP] 2026-11-06 12:27:48,053 INFO noc_app GET /api/regions/NSW/topology -> 200 in 33 ms user=louis.chen@databricks.com
2026-11-06T12:27:48Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:27:48Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:27:48 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:27:49Z [APP] 2026-11-06 12:27:49,620 INFO noc_app GET /api/regions/NSW/topology -> 200 in 40 ms user=louis.chen@databricks.com
2026-11-06T12:27:49Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:27:50Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:27:49 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:27:51Z [APP] 2026-11-06 12:27:51,188 INFO noc_app GET /api/regions/NSW/topology -> 200 in 33 ms user=louis.chen@databricks.com
2026-11-06T12:27:51Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:27:51Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:27:51 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:27:52Z [APP] 2026-11-06 12:27:52,970 INFO noc_app GET /api/regions/NSW/topology -> 200 in 126 ms user=louis.chen@databricks.com
2026-11-06T12:27:52Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:27:53Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:27:52 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:27:56Z [APP] 2026-11-06 12:27:56,460 INFO noc_app GET /api/regions/NSW/topology -> 200 in 37 ms user=louis.chen@databricks.com
2026-11-06T12:27:56Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:27:57Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:27:56 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:27:58Z [APP] 2026-11-06 12:27:58,051 INFO noc_app GET /api/regions/NSW/topology -> 200 in 39 ms user=louis.chen@databricks.com
2026-11-06T12:27:58Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:27:58Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:27:58 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:27:59Z [APP] 2026-11-06 12:27:59,625 INFO noc_app GET /api/regions/NSW/topology -> 200 in 39 ms user=louis.chen@databricks.com
2026-11-06T12:27:59Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:28:00Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:27:59 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:28:01Z [APP] 2026-11-06 12:28:01,186 INFO noc_app GET /api/regions/NSW/topology -> 200 in 36 ms user=louis.chen@databricks.com
2026-11-06T12:28:01Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:28:01Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:28:01 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:28:02Z [APP] 2026-11-06 12:28:02,857 INFO noc_app GET /api/regions/NSW/topology -> 200 in 36 ms user=louis.chen@databricks.com
2026-11-06T12:28:02Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:28:03Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:28:02 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:28:04Z [APP] 2026-11-06 12:28:04,362 INFO noc_app GET /api/regions/NSW/topology -> 200 in 39 ms user=louis.chen@databricks.com
2026-11-06T12:28:04Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:28:05Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:28:04 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:28:05Z [APP] 2026-11-06 12:28:05,878 INFO noc_app GET /api/regions/NSW/topology -> 200 in 33 ms user=louis.chen@databricks.com
2026-11-06T12:28:05Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:28:06Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:28:05 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:28:07Z [APP] 2026-11-06 12:28:07,470 INFO noc_app GET /api/regions/NSW/topology -> 200 in 33 ms user=louis.chen@databricks.com
2026-11-06T12:28:07Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:28:08Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:28:07 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T12:28:09Z [APP] 2026-11-06 12:28:09,016 INFO noc_app GET /api/regions/NSW/topology -> 200 in 33 ms user=louis.chen@databricks.com
2026-11-06T12:28:09Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T12:28:09Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:12:28:08 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
```
