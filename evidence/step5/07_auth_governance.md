# Auth and governance: who reads what, and what a regional user sees

Captured 2026-11-06 11:37 UTC from workspace profile `febar` by `scripts/capture_evidence_step5.py`.

**Identities.**

| path | identity | enforcement |
|---|---|---|
| Lakebase reads (incidents, suspects, element status, AI summary) and the SMS review write | app service principal `23923ae9-3de4-453b-b13f-b61f7ba84868` (`app-t3z4by banksia-noc-topology`), OAuth database credential | Postgres grants: SELECT on the three synced tables, own `netmon_app` schema; rows restricted in SQL to the user's UC region scope |
| Unity Catalog reads through the SQL warehouse (region scope, inventory, detection timing, KPIs) | signed-in user, on-behalf-of token (`user_api_scopes: sql`) | UC grants + the `netmon_noc` views' `region_filter` + IMSI / MSISDN masks, evaluated for the user |
| Genie questions | signed-in user, on-behalf-of token (`dashboards.genie`) | Genie runs the SQL as the user: same UC enforcement |
| App access | NOC groups CAN_USE on the app; Genie space CAN_RUN | workspace permissions |

The capturing user is `louis.chen@databricks.com`: a member of `noc_national` (sees every region) and NOT of `pii_privileged`
(sees masked identifiers). It is also the catalog owner, which limits what it can demonstrate (see the end).

## App service principal: no Unity Catalog data grants

The app's own identity holds no SELECT anywhere in the catalog (all UC data access is the user's):

```sql
SELECT 'table' AS kind, table_schema AS schema_name, table_name, privilege_type
              FROM telco_netmon_febar_catalog.information_schema.table_privileges WHERE grantee = '23923ae9-3de4-453b-b13f-b61f7ba84868'
              UNION ALL SELECT 'schema', schema_name, NULL, privilege_type
              FROM telco_netmon_febar_catalog.information_schema.schema_privileges WHERE grantee = '23923ae9-3de4-453b-b13f-b61f7ba84868'
              UNION ALL SELECT 'catalog', NULL, NULL, privilege_type
              FROM telco_netmon_febar_catalog.information_schema.catalog_privileges WHERE grantee = '23923ae9-3de4-453b-b13f-b61f7ba84868'
```

| kind | schema_name | table_name | privilege_type |
|---|---|---|---|

_0 row(s)_

Its Postgres privileges in `netmon_serving` (read-only on the synced tables; full rights only on its own review table):

| table_schema | table_name | privileges |
|---|---|---|
| netmon_genai | lb_incident_ai_latest | SELECT |
| netmon_rca | lb_element_status | SELECT |
| netmon_rca | lb_open_incidents | SELECT |

_3 row(s)_

SQL warehouse permissions:

| principal | levels |
|---|---|
| users | CAN_USE |
| aec5be3d-de3c-404c-8e60-feed0f265fd3 | IS_OWNER |
| admins | CAN_MANAGE |

_3 row(s)_

## PII masking for a non-privileged reader

The app and the Genie space never touch `silver_sessions` (tested). For reference, the same user querying the masked view directly:

```sql
SELECT imsi, msisdn, region_code FROM telco_netmon_febar_catalog.netmon_noc.silver_sessions LIMIT 3
```

| imsi | msisdn | region_code |
|---|---|---|
| 00101********33 | +999******961 | VIC |
| 00101********24 | +999******442 | VIC |
| 00101********40 | +999******298 | NSW |

_3 row(s)_

```sql
SELECT is_member('noc_national') AS in_noc_national, is_member('noc_region_nsw') AS in_noc_region_nsw, is_member('pii_privileged') AS in_pii_privileged
```

| in_noc_national | in_noc_region_nsw | in_pii_privileged |
|---|---|---|
| true | false | false |

_1 row(s)_

## As a national NOC user (noc_national)

```json
{
  "request": "GET /api/me",
  "http_status": 200,
  "latency_ms": 1670,
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

```json
{
  "request": "GET /api/incidents",
  "http_status": 200,
  "latency_ms": 1006,
  "body": {
    "n": 17,
    "regions": [
      "NQL",
      "NSW",
      "VIC"
    ],
    "incident_ids": [
      "RCA-d28473ab1bd7b846",
      "RCA-9737805189832cde",
      "RCA-cdc1224a2469350b",
      "RCA-c068ecb5f659c20d",
      "RCA-399fe9bb03f3b4cb",
      "RCA-ce4e7fd28bd45261",
      "RCA-9eb236846361cdad",
      "RCA-e46db865d147fb84",
      "RCA-c7276c3238a27971",
      "RCA-fbd7ff66e62b0b42",
      "RCA-e909709b1c6a18fb",
      "RCA-c69d3bab90ca811f",
      "RCA-1073d4d88aa7e05b",
      "RCA-27ed3e8af852d33a",
      "RCA-4b24e8c0bfedac1a",
      "RCA-60fe3d71c22893d5",
      "RCA-944a68e9bf7eff9b"
    ]
  }
}
```

```json
{
  "request": "GET /api/incidents/RCA-27ed3e8af852d33a  (a VIC incident)",
  "http_status": 200,
  "latency_ms": 1874,
  "body": {
    "incident_id": "RCA-27ed3e8af852d33a",
    "region_code": "VIC"
  }
}
```

```json
{
  "request": "GET /api/regions/VIC/topology",
  "http_status": 200,
  "latency_ms": 1448,
  "body": {
    "region": "VIC",
    "n_elements": 685
  }
}
```

```json
{
  "request": "GET /api/kpis",
  "http_status": 200,
  "latency_ms": 2378,
  "body": {
    "operational": [
      {
        "region_code": "NQL",
        "n_open_incidents": 1,
        "mttd_s": 193.5,
        "pct_detected_within_5min": 100.0
      },
      {
        "region_code": "NSW",
        "n_open_incidents": 9,
        "mttd_s": 160.7,
        "pct_detected_within_5min": 100.0
      },
      {
        "region_code": "VIC",
        "n_open_incidents": 7,
        "mttd_s": 168.5,
        "pct_detected_within_5min": 100.0
      }
    ],
    "scorecard": {
      "available": true,
      "n_incidents": 26,
      "impact_detected_pct": 100.0,
      "impact_median_ttd_s": 141.4,
      "impact_p90_ttd_s": 430.4,
      "impact_within_5min_pct": 88.5,
      "root_localised_pct": 100.0,
      "localised_within_5min_pct": 88.5
    }
  }
}
```

```json
{
  "request": "POST /api/genie/ask {How many open incidents are there per region?}",
  "http_status": 200,
  "latency_ms": 15190,
  "body": {
    "text": [
      "There are **17** open incidents across the regions visible in this data: **NSW** has **9**, **VIC** has **7**, and **NQL** has **1**. **NSW** has the highest count, while **NQL** has the lowest."
    ],
    "sql": "SELECT `region_code`, COUNT(*) AS `open_incidents`\nFROM `telco_netmon_febar_catalog`.`netmon_noc`.`open_incidents`\nWHERE `region_code` IS NOT NULL\nGROUP BY `region_code`\nORDER BY `open_incidents` DESC, `region_code` ASC",
    "columns": [
      "region_code",
      "open_incidents"
    ],
    "rows": [
      [
        "NSW",
        "9"
      ],
      [
        "VIC",
        "7"
      ],
      [
        "NQL",
        "1"
      ]
    ]
  }
}
```

Direct query of the view as the same user:

```sql
SELECT region_code, count(*) AS n FROM telco_netmon_febar_catalog.netmon_noc.open_incidents GROUP BY 1 ORDER BY 1
```

| region_code | n |
|---|---|
| NQL | 1 |
| NSW | 9 |
| VIC | 7 |

_3 row(s)_

**Membership switched**: capturing user removed from `noc_national` and added to `noc_region_nsw` (SCIM PATCH on the workspace groups). The app reported region scope ['NSW'] after 285 s (UC membership propagation + the app's 5-minute scope cache).

```sql
SELECT is_member('noc_national') AS in_noc_national, is_member('noc_region_nsw') AS in_noc_region_nsw
```

| in_noc_national | in_noc_region_nsw |
|---|---|
| false | true |

_1 row(s)_

## As a regional NOC user (noc_region_nsw only)

```json
{
  "request": "GET /api/me",
  "http_status": 200,
  "latency_ms": 1253,
  "body": {
    "user": "louis.chen@databricks.com",
    "name": "Louis Chen",
    "regions": [
      "NSW"
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

```json
{
  "request": "GET /api/incidents",
  "http_status": 200,
  "latency_ms": 1138,
  "body": {
    "n": 9,
    "regions": [
      "NSW"
    ],
    "incident_ids": [
      "RCA-cdc1224a2469350b",
      "RCA-c068ecb5f659c20d",
      "RCA-ce4e7fd28bd45261",
      "RCA-e46db865d147fb84",
      "RCA-c7276c3238a27971",
      "RCA-fbd7ff66e62b0b42",
      "RCA-e909709b1c6a18fb",
      "RCA-4b24e8c0bfedac1a",
      "RCA-60fe3d71c22893d5"
    ]
  }
}
```

```json
{
  "request": "GET /api/incidents/RCA-27ed3e8af852d33a  (a VIC incident)",
  "http_status": 404,
  "latency_ms": 1189,
  "body": {
    "error": "no open incident RCA-27ed3e8af852d33a in your regions"
  }
}
```

```json
{
  "request": "GET /api/regions/VIC/topology",
  "http_status": 403,
  "latency_ms": 1169,
  "body": {
    "error": "region VIC is not in your NOC scope ['NSW']"
  }
}
```

```json
{
  "request": "GET /api/kpis",
  "http_status": 200,
  "latency_ms": 3152,
  "body": {
    "operational": [
      {
        "region_code": "NSW",
        "n_open_incidents": 9,
        "mttd_s": 160.7,
        "pct_detected_within_5min": 100.0
      }
    ],
    "scorecard": {
      "available": true,
      "n_incidents": 26,
      "impact_detected_pct": 100.0,
      "impact_median_ttd_s": 141.4,
      "impact_p90_ttd_s": 430.4,
      "impact_within_5min_pct": 88.5,
      "root_localised_pct": 100.0,
      "localised_within_5min_pct": 88.5
    }
  }
}
```

```json
{
  "request": "POST /api/genie/ask {How many open incidents are there per region?}",
  "http_status": 200,
  "latency_ms": 19030,
  "body": {
    "text": [
      "In the visible result, **NSW** has **9 open incidents**. Based on the data shown, the highest count is **NSW with 9 open incidents**."
    ],
    "sql": "SELECT `region_code`, COUNT(*) AS `open_incidents`\nFROM `telco_netmon_febar_catalog`.`netmon_noc`.`open_incidents`\nWHERE `region_code` IS NOT NULL\n  AND `status` = 'open'\nGROUP BY `region_code`\nORDER BY `open_incidents` DESC, `region_code`",
    "columns": [
      "region_code",
      "open_incidents"
    ],
    "rows": [
      [
        "NSW",
        "9"
      ]
    ]
  }
}
```

Direct query of the view as the same user:

```sql
SELECT region_code, count(*) AS n FROM telco_netmon_febar_catalog.netmon_noc.open_incidents GROUP BY 1 ORDER BY 1
```

| region_code | n |
|---|---|
| NSW | 9 |

_1 row(s)_

## Restored

Membership restored (back in `noc_national`, out of `noc_region_nsw`):

```sql
SELECT is_member('noc_national') AS in_noc_national, is_member('noc_region_nsw') AS in_noc_region_nsw
```

| in_noc_national | in_noc_region_nsw |
|---|---|
| false | true |

_1 row(s)_

## Genie and subscriber identifiers

```json
{
  "request": "POST /api/genie/ask {List the IMSI and MSISDN of the subscribers on SITE-NSW-00105}",
  "http_status": 200,
  "latency_ms": 9752,
  "body": {
    "text": [
      "I can\u2019t provide IMSI or MSISDN because this space has no per-subscriber data, and requests for subscriber identifiers are out of scope here. I can only fetch network/incident data such as site status, impacted cells, incidents, or estimated affected subscribers for `SITE-NSW-00105`."
    ],
    "sql": null,
    "columns": [],
    "rows": []
  }
}
```

## Limits of this demonstration (workspace)

- **Workspace-local groups.** This FEVM workspace cannot create account groups, so the NOC roles are workspace-local
  groups (docs/pipeline.md). Unity Catalog cannot grant to them; the row filter tests their membership with
  `is_member()`, which is what changes the regional view above. With account groups nothing in the app changes.
- **Grant-level denial is not visible with this user.** The capturing user owns the catalog, so after the switch it
  still reads tables a real `noc_region_nsw` member has no grant on: the evaluation scorecard (`/api/kpis` ->
  `scorecard`) stays available above, where a regional member would get `PERMISSION_DENIED` (the app shows "national
  NOC only"; unit-tested in `tests/test_app_service.py::test_kpis_scorecard_is_national_only`). Regional roles' grants
  are `netmon_noc` only (`governance/sql/03_grants_regional.sql`).
- **No second human user / persona login.** The persona service principals (`netmon-noc-nsw-analyst`, ...) cannot be
  used interactively here (no OAuth secret creation for this session, as in step 2), and the Apps proxy forwards a
  user token only for interactive users, so the regional view is shown by changing the capturing user's membership.
- **Lakebase has no UC row filters.** The app enforces the UC-derived region scope in its Lakebase SQL
  (`region_code = ANY(...)`); the app service principal itself can read all regions of the three synced tables.
