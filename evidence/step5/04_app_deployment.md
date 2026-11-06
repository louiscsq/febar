# Databricks App: deployment status, resources and logs

Captured 2026-11-06 13:49 UTC from workspace profile `febar` by `scripts/capture_evidence_step5.py`.

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
  "update_time": "2026-11-06T13:19:02Z",
  "creator": "louis.chen@databricks.com"
}
```

## Deployments (latest 5)

| deployment_id | create_time | mode | state | message | source_code_path |
|---|---|---|---|---|---|
| 01f1d9e4a21b1266bd7ce8f97e38e813 | 2026-11-06T13:19:02Z | SNAPSHOT | SUCCEEDED | App started successfully | /Workspace/Users/louis.chen@databricks.com/.bundle/banksia_netmon/dev/files/app |
| 01f1d9d8df511be4a4c671c168ae205a | 2026-11-06T11:54:50Z | SNAPSHOT | SUCCEEDED | App started successfully | /Workspace/Users/louis.chen@databricks.com/.bundle/banksia_netmon/dev/files/app |
| 01f1d9d339b71d2b903b6973593577db | 2026-11-06T11:14:25Z | SNAPSHOT | SUCCEEDED | App started successfully | /Workspace/Users/louis.chen@databricks.com/.bundle/banksia_netmon/dev/files/app |
| 01f1d9d2441312d3a6c289bc81bf717d | 2026-11-06T11:07:33Z | SNAPSHOT | SUCCEEDED | App started successfully | /Workspace/Users/louis.chen@databricks.com/.bundle/banksia_netmon/dev/files/app |
| 01f1d9d0e60b1638abcbcbf2972724bd | 2026-11-06T10:57:46Z | SNAPSHOT | SUCCEEDED | App started successfully | /Workspace/Users/louis.chen@databricks.com/.bundle/banksia_netmon/dev/files/app |

_5 row(s)_

## Live checks through the Apps proxy

`/api/health` round-trips to Lakebase as the app service principal; then 20 timed calls of the hot-path endpoints (warm):

```json
{
  "request": "GET /api/health",
  "http_status": 200,
  "latency_ms": 2004,
  "body": {
    "status": "ok",
    "lakebase": {
      "pg_user": "23923ae9-3de4-453b-b13f-b61f7ba84868",
      "server_time": "2026-11-06T13:49:59.439019+00:00"
    },
    "lakebase_ms": 10.2
  }
}
```

## Forwarded-header trust boundary (spoofing attempt)

The app takes the user's identity from `x-forwarded-email` / `x-forwarded-access-token`, set by the Databricks Apps proxy. Here the client sends its own (spoofed) values for both headers through the proxy, with a valid login token for the capturing user; `/api/me` reports which identity the backend actually received:

```json
{
  "request": "GET /api/me with spoofed x-forwarded-* headers",
  "sent_headers": {
    "x-forwarded-email": "spoofed.attacker@banksia.example",
    "x-forwarded-preferred-username": "spoofed.attacker",
    "x-forwarded-access-token": "spoofed-token"
  },
  "http_status": 200,
  "body": {
    "user": "louis.chen@databricks.com",
    "name": "Louis Chen",
    "regions": [
      "NQL",
      "NSW",
      "VIC",
      "WA"
    ],
    "on_behalf_of_user": true,
    "identities": {
      "lakebase": "app service principal (23923ae9-3de4-453b-b13f-b61f7ba84868)",
      "sql_warehouse": "signed-in user (on-behalf-of token)",
      "genie": "signed-in user (on-behalf-of token)"
    }
  }
}
```

Backend saw user `louis.chen@databricks.com`: the spoofed email was **overwritten by the proxy**; the region scope ['NQL', 'NSW', 'VIC', 'WA'] came from Unity Catalog with the proxy-forwarded token (a spoofed token would have failed the UC query).

End-to-end latency measured from the capturing laptop (includes the internet round trip and the Apps proxy):

| endpoint | n | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|
| /api/incidents?region=NSW | 20 | 1084 | 1260 | 1269 |
| /api/incidents/RCA-c7276c3238a27971 | 20 | 1150 | 1582 | 2809 |
| /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 | 20 | 1759 | 2199 | 2627 |

_3 row(s)_

Server-side time inside the app for the same calls (from the app's own request log, `noc_app ... -> 200 in N ms`): Lakebase queries plus, on a cold cache, the warehouse topology read:

| endpoint (path) | n | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|
| /api/incidents | 23 | 12 | 14 | 16 |
| /api/incidents/RCA-c7276c3238a27971 | 24 | 27 | 33 | 5930 |
| /api/me | 14 | 1 | 818 | 868 |
| /api/regions/NSW/topology | 42 | 36 | 44 | 126 |

_4 row(s)_

## App logs (last 60 lines)

```text
2026-11-06T13:50:48Z [APP] 2026-11-06 13:50:48,983 INFO noc_app GET /api/regions/NSW/topology -> 200 in 36 ms user=louis.chen@databricks.com
2026-11-06T13:50:48Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:50:49Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:50:48 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:50:50Z [APP] 2026-11-06 13:50:50,715 INFO noc_app GET /api/regions/NSW/topology -> 200 in 35 ms user=louis.chen@databricks.com
2026-11-06T13:50:50Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:50:51Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:50:50 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:50:52Z [APP] 2026-11-06 13:50:52,717 INFO noc_app GET /api/regions/NSW/topology -> 200 in 34 ms user=louis.chen@databricks.com
2026-11-06T13:50:52Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:50:53Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:50:52 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:50:54Z [APP] 2026-11-06 13:50:54,263 INFO noc_app GET /api/regions/NSW/topology -> 200 in 45 ms user=louis.chen@databricks.com
2026-11-06T13:50:54Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:50:55Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:50:54 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:50:56Z [APP] 2026-11-06 13:50:56,096 INFO noc_app GET /api/regions/NSW/topology -> 200 in 42 ms user=louis.chen@databricks.com
2026-11-06T13:50:56Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:50:56Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:50:56 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:50:57Z [APP] 2026-11-06 13:50:57,757 INFO noc_app GET /api/regions/NSW/topology -> 200 in 32 ms user=louis.chen@databricks.com
2026-11-06T13:50:57Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:50:58Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:50:57 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:50:59Z [APP] 2026-11-06 13:50:59,520 INFO noc_app GET /api/regions/NSW/topology -> 200 in 37 ms user=louis.chen@databricks.com
2026-11-06T13:50:59Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:51:00Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:50:59 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:51:01Z [APP] 2026-11-06 13:51:01,377 INFO noc_app GET /api/regions/NSW/topology -> 200 in 44 ms user=louis.chen@databricks.com
2026-11-06T13:51:01Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:51:02Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:51:01 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:51:02Z [APP] 2026-11-06 13:51:02,920 INFO noc_app GET /api/regions/NSW/topology -> 200 in 33 ms user=louis.chen@databricks.com
2026-11-06T13:51:02Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:51:03Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:51:02 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:51:04Z [APP] 2026-11-06 13:51:04,849 INFO noc_app GET /api/regions/NSW/topology -> 200 in 37 ms user=louis.chen@databricks.com
2026-11-06T13:51:04Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:51:05Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:51:04 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:51:06Z [APP] 2026-11-06 13:51:06,635 INFO noc_app GET /api/regions/NSW/topology -> 200 in 32 ms user=louis.chen@databricks.com
2026-11-06T13:51:06Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:51:07Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:51:06 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:51:08Z [APP] 2026-11-06 13:51:08,410 INFO noc_app GET /api/regions/NSW/topology -> 200 in 34 ms user=louis.chen@databricks.com
2026-11-06T13:51:08Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:51:09Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:51:08 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:51:10Z [APP] 2026-11-06 13:51:10,024 INFO noc_app GET /api/regions/NSW/topology -> 200 in 33 ms user=louis.chen@databricks.com
2026-11-06T13:51:10Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:51:10Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:51:09 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:51:11Z [APP] 2026-11-06 13:51:11,934 INFO noc_app GET /api/regions/NSW/topology -> 200 in 32 ms user=louis.chen@databricks.com
2026-11-06T13:51:11Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:51:12Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:51:11 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:51:13Z [APP] 2026-11-06 13:51:13,647 INFO noc_app GET /api/regions/NSW/topology -> 200 in 33 ms user=louis.chen@databricks.com
2026-11-06T13:51:13Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:51:14Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:51:13 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:51:15Z [APP] 2026-11-06 13:51:15,222 INFO noc_app GET /api/regions/NSW/topology -> 200 in 34 ms user=louis.chen@databricks.com
2026-11-06T13:51:15Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:51:16Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:51:15 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:51:16Z [APP] 2026-11-06 13:51:16,779 INFO noc_app GET /api/regions/NSW/topology -> 200 in 32 ms user=louis.chen@databricks.com
2026-11-06T13:51:16Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:51:17Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:51:16 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:51:18Z [APP] 2026-11-06 13:51:18,606 INFO noc_app GET /api/regions/NSW/topology -> 200 in 33 ms user=louis.chen@databricks.com
2026-11-06T13:51:18Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:51:19Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:51:18 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:51:20Z [APP] 2026-11-06 13:51:20,262 INFO noc_app GET /api/regions/NSW/topology -> 200 in 61 ms user=louis.chen@databricks.com
2026-11-06T13:51:20Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:51:21Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:51:20 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
2026-11-06T13:51:23Z [APP] 2026-11-06 13:51:23,111 INFO noc_app GET /api/regions/NSW/topology -> 200 in 38 ms user=louis.chen@databricks.com
2026-11-06T13:51:23Z [APP] INFO:     <ip>:0 - "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971 HTTP/1.1" 200 OK
2026-11-06T13:51:23Z [HTTP] <ip> - 6016306480479573@7474648429104135 [06/Nov/2026:13:51:23 +0000] "GET /api/regions/NSW/topology HTTP/1.1" 200 41736 "-" "python-httpx/0.28.1"
```
