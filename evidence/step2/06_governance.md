# Unity Catalog governance: masks, row filters, roles, grants, tags

Captured 2026-10-08 19:39 UTC from workspace profile `febar` (warehouse `d7fa853ab15b20a3`) by `scripts/capture_evidence.py`.

Masks and row filters are declared on the pipeline tables (`silver_sessions`, `gold_impact_detections`) and backed by `governance/sql/01_functions.sql`. Regional NOC roles read only the region-filtered views in `netmon_noc` (`02_noc_views.sql`); `noc_national` also reads gold and the operational silver tables; `pii_privileged` is granted nothing (`03_grants_*.sql`). Tags: `04_comments_tags.sql`.

**Limitation, stated plainly:** every query below runs as one principal, the capturing user. Querying as a second principal (a persona service principal via OAuth M2M or a token) was not possible: creating credentials for a service principal was blocked in this environment. So (1) row-level behaviour is proven by changing the capturing user's group membership and querying every object a regional role can read, and (2) grant-level least privilege is proven from `information_schema` for each persona and from Unity Catalog rejecting the workspace-local groups as principals. The capturing user owns the catalog, so it can always read the base tables itself; that is why grant denial is shown from the privilege tables, not by a refused query.

## Column masks

```sql
SELECT table_schema, table_name, column_name, mask_name FROM telco_netmon_febar_catalog.information_schema.column_masks
        ORDER BY ALL
```

| table_schema | table_name | column_name | mask_name |
|---|---|---|---|
| netmon_silver | silver_sessions | imsi | telco_netmon_febar_catalog.netmon_gov.mask_imsi |
| netmon_silver | silver_sessions | msisdn | telco_netmon_febar_catalog.netmon_gov.mask_msisdn |

_2 row(s)_

## Row filters

```sql
SELECT table_schema, table_name, filter_name, target_columns FROM telco_netmon_febar_catalog.information_schema.row_filters
        ORDER BY ALL
```

| table_schema | table_name | filter_name | target_columns |
|---|---|---|---|
| netmon_gold | gold_impact_detections | telco_netmon_febar_catalog.netmon_gov.region_filter | region_code |
| netmon_silver | silver_sessions | telco_netmon_febar_catalog.netmon_gov.region_filter | region_code |

_2 row(s)_

## Region-filtered serving views (netmon_noc)

```sql
SELECT table_name, left(replace(replace(view_definition, char(10), ' '), char(13), ' '), 170) AS definition
        FROM telco_netmon_febar_catalog.information_schema.views WHERE table_schema = 'netmon_noc' ORDER BY 1
```

| table_name | definition |
|---|---|
| gold_cell_baseline | SELECT b.*, n.region_code FROM `telco_netmon_febar_catalog`.`netmon_gold`.gold_cell_baseline b JOIN `telco_netmon_febar… |
| gold_cell_health_1m | SELECT * FROM `telco_netmon_febar_catalog`.`netmon_gold`.gold_cell_health_1m WHERE `telco_netmon_febar_catalog`.`netmon… |
| gold_cell_health_5m | SELECT * FROM `telco_netmon_febar_catalog`.`netmon_gold`.gold_cell_health_5m WHERE `telco_netmon_febar_catalog`.`netmon… |
| gold_cell_sessions_5m | SELECT * FROM `telco_netmon_febar_catalog`.`netmon_gold`.gold_cell_sessions_5m WHERE `telco_netmon_febar_catalog`.`netm… |
| gold_element_impact_5m | SELECT * FROM `telco_netmon_febar_catalog`.`netmon_gold`.gold_element_impact_5m WHERE `telco_netmon_febar_catalog`.`net… |
| gold_impact_detections | SELECT * FROM `telco_netmon_febar_catalog`.`netmon_gold`.gold_impact_detections WHERE `telco_netmon_febar_catalog`.`net… |
| silver_alarms | SELECT * FROM `telco_netmon_febar_catalog`.`netmon_silver`.silver_alarms WHERE `telco_netmon_febar_catalog`.`netmon_gov… |
| silver_kpis | SELECT * FROM `telco_netmon_febar_catalog`.`netmon_silver`.silver_kpis WHERE `telco_netmon_febar_catalog`.`netmon_gov`.… |
| silver_maintenance_windows | SELECT m.*, n.region_code FROM `telco_netmon_febar_catalog`.`netmon_silver`.silver_maintenance_windows m JOIN `telco_ne… |
| silver_sessions | SELECT * FROM `telco_netmon_febar_catalog`.`netmon_silver`.silver_sessions WHERE `telco_netmon_febar_catalog`.`netmon_g… |
| silver_topology_edges | SELECT e.*, n.region_code FROM `telco_netmon_febar_catalog`.`netmon_silver`.silver_topology_edges e JOIN `telco_netmon_… |
| silver_topology_nodes | SELECT * FROM `telco_netmon_febar_catalog`.`netmon_silver`.silver_topology_nodes WHERE `telco_netmon_febar_catalog`.`ne… |

_12 row(s)_

## Policy function definitions

```sql
SELECT routine_name, routine_definition FROM telco_netmon_febar_catalog.information_schema.routines
        WHERE routine_schema = 'netmon_gov' ORDER BY 1
```

| routine_name | routine_definition |
|---|---|
| is_pii_privileged | is_account_group_member('pii_privileged') OR is_member('pii_privileged') |
| mask_imsi | CASE   WHEN imsi IS NULL THEN NULL   WHEN `telco_netmon_febar_catalog`.`netmon_gov`.is_pii_privileged() THEN imsi   ELS… |
| mask_msisdn | CASE   WHEN msisdn IS NULL THEN NULL   WHEN `telco_netmon_febar_catalog`.`netmon_gov`.is_pii_privileged() THEN msisdn  … |
| region_filter | is_account_group_member('noc_national') OR is_member('noc_national')   OR is_account_group_member(concat('noc_region_',… |

_4 row(s)_

## Workspace-local groups, roles and members

| group | role | members |
|---|---|---|
| `noc_national` | national NOC | netmon-pii-officer, netmon-noc-national, Louis Chen |
| `noc_region_act` | regional NOC | — |
| `noc_region_nql` | regional NOC | — |
| `noc_region_nsw` | regional NOC | netmon-noc-nsw-analyst |
| `noc_region_nt` | regional NOC | — |
| `noc_region_pil` | regional NOC | — |
| `noc_region_qld` | regional NOC | — |
| `noc_region_sa` | regional NOC | — |
| `noc_region_tas` | regional NOC | — |
| `noc_region_vic` | regional NOC | — |
| `noc_region_wa` | regional NOC | netmon-noc-wa-analyst |
| `pii_privileged` | unmask only (no grants) | netmon-pii-officer, netmon-pii-only |

## Privileges held by each persona (grantees; every netmon securable)

`netmon-pii-only` (member of `pii_privileged` only) has no privileges at all; the regional analysts hold only the `netmon_noc` schema (plus USE CATALOG and the filter function).

```sql
WITH p AS (
          SELECT grantee, 'CATALOG' AS kind, catalog_name AS object, privilege_type
          FROM telco_netmon_febar_catalog.information_schema.catalog_privileges
          UNION ALL SELECT grantee, 'SCHEMA', schema_name, privilege_type FROM telco_netmon_febar_catalog.information_schema.schema_privileges
          UNION ALL SELECT grantee, 'TABLE', concat(table_schema, '.', table_name), privilege_type
            FROM telco_netmon_febar_catalog.information_schema.table_privileges
          UNION ALL SELECT grantee, 'FUNCTION', concat(routine_schema, '.', routine_name), privilege_type
            FROM telco_netmon_febar_catalog.information_schema.routine_privileges)
        SELECT persona, kind, object, array_sort(collect_set(privilege_type)) AS privileges FROM (
          SELECT CASE a.id WHEN '8855855c-202f-4260-bf4f-85f2ac215524' THEN 'netmon-pii-officer' WHEN 'fd43c8c6-65f4-433d-962f-6abb3e5bd88b' THEN 'netmon-pii-only' WHEN 'bb41b303-d6b4-4dd0-b524-b25e2f3a3433' THEN 'netmon-noc-nsw-analyst' WHEN '227a0d30-fe32-47f9-867f-9c91c13db70a' THEN 'netmon-noc-national' WHEN '2ee944da-a522-49e2-8600-6c72e454ce2c' THEN 'netmon-noc-wa-analyst' END AS persona, p.* FROM (SELECT explode(array('8855855c-202f-4260-bf4f-85f2ac215524', 'fd43c8c6-65f4-433d-962f-6abb3e5bd88b', 'bb41b303-d6b4-4dd0-b524-b25e2f3a3433', '227a0d30-fe32-47f9-867f-9c91c13db70a', '2ee944da-a522-49e2-8600-6c72e454ce2c')) AS id) a
          LEFT JOIN p ON p.grantee = a.id)
        GROUP BY ALL ORDER BY persona, kind, object
```

| persona | kind | object | privileges |
|---|---|---|---|
| netmon-noc-national | CATALOG | telco_netmon_febar_catalog | ["USE_CATALOG"] |
| netmon-noc-national | FUNCTION | netmon_gov.region_filter | ["EXECUTE"] |
| netmon-noc-national | SCHEMA | netmon_gold | ["SELECT","USE_SCHEMA"] |
| netmon-noc-national | SCHEMA | netmon_gov | ["USE_SCHEMA"] |
| netmon-noc-national | SCHEMA | netmon_noc | ["SELECT","USE_SCHEMA"] |
| netmon-noc-national | SCHEMA | netmon_silver | ["USE_SCHEMA"] |
| netmon-noc-national | TABLE | netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_baseline_1 | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_health_1m_1 | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_health_5m_1 | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_health_5m_retrospective_1 | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_sessions_5m_1 | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_element_impact_5m_1 | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_impact_detections_1 | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_gold.gold_cell_baseline | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_gold.gold_cell_health_1m | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_gold.gold_cell_health_5m | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_gold.gold_cell_health_5m_retrospective | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_gold.gold_cell_sessions_5m | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_gold.gold_element_impact_5m | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_gold.gold_impact_detections | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_noc.gold_cell_baseline | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_noc.gold_cell_health_1m | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_noc.gold_cell_health_5m | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_noc.gold_cell_sessions_5m | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_noc.gold_element_impact_5m | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_noc.gold_impact_detections | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_noc.silver_alarms | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_noc.silver_kpis | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_noc.silver_maintenance_windows | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_noc.silver_sessions | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_noc.silver_topology_edges | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_noc.silver_topology_nodes | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_silver.silver_alarms | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_silver.silver_kpis | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_silver.silver_maintenance_windows | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_silver.silver_sessions | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_silver.silver_topology_edges | ["SELECT"] |
| netmon-noc-national | TABLE | netmon_silver.silver_topology_nodes | ["SELECT"] |
| netmon-noc-nsw-analyst | CATALOG | telco_netmon_febar_catalog | ["USE_CATALOG"] |
| netmon-noc-nsw-analyst | FUNCTION | netmon_gov.region_filter | ["EXECUTE"] |
| netmon-noc-nsw-analyst | SCHEMA | netmon_gov | ["USE_SCHEMA"] |
| netmon-noc-nsw-analyst | SCHEMA | netmon_noc | ["SELECT","USE_SCHEMA"] |
| netmon-noc-nsw-analyst | TABLE | netmon_noc.gold_cell_baseline | ["SELECT"] |
| netmon-noc-nsw-analyst | TABLE | netmon_noc.gold_cell_health_1m | ["SELECT"] |
| netmon-noc-nsw-analyst | TABLE | netmon_noc.gold_cell_health_5m | ["SELECT"] |
| netmon-noc-nsw-analyst | TABLE | netmon_noc.gold_cell_sessions_5m | ["SELECT"] |
| netmon-noc-nsw-analyst | TABLE | netmon_noc.gold_element_impact_5m | ["SELECT"] |
| netmon-noc-nsw-analyst | TABLE | netmon_noc.gold_impact_detections | ["SELECT"] |
| netmon-noc-nsw-analyst | TABLE | netmon_noc.silver_alarms | ["SELECT"] |
| netmon-noc-nsw-analyst | TABLE | netmon_noc.silver_kpis | ["SELECT"] |
| netmon-noc-nsw-analyst | TABLE | netmon_noc.silver_maintenance_windows | ["SELECT"] |
| netmon-noc-nsw-analyst | TABLE | netmon_noc.silver_sessions | ["SELECT"] |
| netmon-noc-nsw-analyst | TABLE | netmon_noc.silver_topology_edges | ["SELECT"] |
| netmon-noc-nsw-analyst | TABLE | netmon_noc.silver_topology_nodes | ["SELECT"] |
| netmon-noc-wa-analyst | CATALOG | telco_netmon_febar_catalog | ["USE_CATALOG"] |
| netmon-noc-wa-analyst | FUNCTION | netmon_gov.region_filter | ["EXECUTE"] |
| netmon-noc-wa-analyst | SCHEMA | netmon_gov | ["USE_SCHEMA"] |
| netmon-noc-wa-analyst | SCHEMA | netmon_noc | ["SELECT","USE_SCHEMA"] |
| netmon-noc-wa-analyst | TABLE | netmon_noc.gold_cell_baseline | ["SELECT"] |
| netmon-noc-wa-analyst | TABLE | netmon_noc.gold_cell_health_1m | ["SELECT"] |
| netmon-noc-wa-analyst | TABLE | netmon_noc.gold_cell_health_5m | ["SELECT"] |
| netmon-noc-wa-analyst | TABLE | netmon_noc.gold_cell_sessions_5m | ["SELECT"] |
| netmon-noc-wa-analyst | TABLE | netmon_noc.gold_element_impact_5m | ["SELECT"] |
| netmon-noc-wa-analyst | TABLE | netmon_noc.gold_impact_detections | ["SELECT"] |
| netmon-noc-wa-analyst | TABLE | netmon_noc.silver_alarms | ["SELECT"] |
| netmon-noc-wa-analyst | TABLE | netmon_noc.silver_kpis | ["SELECT"] |
| netmon-noc-wa-analyst | TABLE | netmon_noc.silver_maintenance_windows | ["SELECT"] |
| netmon-noc-wa-analyst | TABLE | netmon_noc.silver_sessions | ["SELECT"] |
| netmon-noc-wa-analyst | TABLE | netmon_noc.silver_topology_edges | ["SELECT"] |
| netmon-noc-wa-analyst | TABLE | netmon_noc.silver_topology_nodes | ["SELECT"] |
| netmon-pii-officer | CATALOG | telco_netmon_febar_catalog | ["USE_CATALOG"] |
| netmon-pii-officer | FUNCTION | netmon_gov.region_filter | ["EXECUTE"] |
| netmon-pii-officer | SCHEMA | netmon_gold | ["SELECT","USE_SCHEMA"] |
| netmon-pii-officer | SCHEMA | netmon_gov | ["USE_SCHEMA"] |
| netmon-pii-officer | SCHEMA | netmon_noc | ["SELECT","USE_SCHEMA"] |
| netmon-pii-officer | SCHEMA | netmon_silver | ["USE_SCHEMA"] |
| netmon-pii-officer | TABLE | netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_baseline_1 | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_health_1m_1 | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_health_5m_1 | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_health_5m_retrospective_1 | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_sessions_5m_1 | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_element_impact_5m_1 | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_impact_detections_1 | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_gold.gold_cell_baseline | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_gold.gold_cell_health_1m | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_gold.gold_cell_health_5m | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_gold.gold_cell_health_5m_retrospective | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_gold.gold_cell_sessions_5m | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_gold.gold_element_impact_5m | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_gold.gold_impact_detections | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_noc.gold_cell_baseline | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_noc.gold_cell_health_1m | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_noc.gold_cell_health_5m | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_noc.gold_cell_sessions_5m | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_noc.gold_element_impact_5m | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_noc.gold_impact_detections | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_noc.silver_alarms | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_noc.silver_kpis | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_noc.silver_maintenance_windows | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_noc.silver_sessions | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_noc.silver_topology_edges | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_noc.silver_topology_nodes | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_silver.silver_alarms | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_silver.silver_kpis | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_silver.silver_maintenance_windows | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_silver.silver_sessions | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_silver.silver_topology_edges | ["SELECT"] |
| netmon-pii-officer | TABLE | netmon_silver.silver_topology_nodes | ["SELECT"] |
| netmon-pii-only | NULL | NULL | [] |

_109 row(s)_

## Base-table privileges held by regional / pii-only principals (expected: no rows)

Covers the regional analyst personas, the pii-only persona, and every `noc_region_*` group and `pii_privileged` by name. Zero rows: nobody but the national role can read a silver / gold table directly; regional access is only through `netmon_noc`.

```sql
SELECT grantee, 'SCHEMA' AS kind, schema_name AS object, privilege_type
        FROM telco_netmon_febar_catalog.information_schema.schema_privileges
        WHERE schema_name IN ('netmon_bronze', 'netmon_silver', 'netmon_gold', 'netmon_eval') AND grantee IN ('fd43c8c6-65f4-433d-962f-6abb3e5bd88b', 'bb41b303-d6b4-4dd0-b524-b25e2f3a3433', '2ee944da-a522-49e2-8600-6c72e454ce2c', 'noc_region_act', 'noc_region_nql', 'noc_region_pil', 'pii_privileged', 'noc_region_nt', 'noc_region_qld', 'noc_region_vic', 'noc_region_nsw', 'noc_region_tas', 'noc_region_wa', 'noc_region_sa')
        UNION ALL
        SELECT grantee, 'TABLE', concat(table_schema, '.', table_name), privilege_type
        FROM telco_netmon_febar_catalog.information_schema.table_privileges
        WHERE table_schema IN ('netmon_bronze', 'netmon_silver', 'netmon_gold', 'netmon_eval') AND grantee IN ('fd43c8c6-65f4-433d-962f-6abb3e5bd88b', 'bb41b303-d6b4-4dd0-b524-b25e2f3a3433', '2ee944da-a522-49e2-8600-6c72e454ce2c', 'noc_region_act', 'noc_region_nql', 'noc_region_pil', 'pii_privileged', 'noc_region_nt', 'noc_region_qld', 'noc_region_vic', 'noc_region_nsw', 'noc_region_tas', 'noc_region_wa', 'noc_region_sa')
```

| grantee | kind | object | privilege_type |
|---|---|---|---|

_0 row(s)_

## All grantees on the base schemas and their tables (who can read silver / gold directly)

Besides the catalog owner (excluded: a user) and the FEVM platform service principal, only the national personas appear.

```sql
SELECT kind, grantee_name, array_sort(collect_set(object)) AS objects, array_sort(collect_set(privilege_type))
               AS privileges FROM (
          SELECT 'SCHEMA' AS kind, coalesce(CASE grantee WHEN '8855855c-202f-4260-bf4f-85f2ac215524' THEN 'netmon-pii-officer' WHEN 'fd43c8c6-65f4-433d-962f-6abb3e5bd88b' THEN 'netmon-pii-only' WHEN 'bb41b303-d6b4-4dd0-b524-b25e2f3a3433' THEN 'netmon-noc-nsw-analyst' WHEN '227a0d30-fe32-47f9-867f-9c91c13db70a' THEN 'netmon-noc-national' WHEN '2ee944da-a522-49e2-8600-6c72e454ce2c' THEN 'netmon-noc-wa-analyst' END, grantee) AS grantee_name, schema_name AS object,
                 privilege_type FROM telco_netmon_febar_catalog.information_schema.schema_privileges WHERE schema_name IN ('netmon_bronze', 'netmon_silver', 'netmon_gold', 'netmon_eval')
          UNION ALL
          SELECT 'TABLE', coalesce(CASE grantee WHEN '8855855c-202f-4260-bf4f-85f2ac215524' THEN 'netmon-pii-officer' WHEN 'fd43c8c6-65f4-433d-962f-6abb3e5bd88b' THEN 'netmon-pii-only' WHEN 'bb41b303-d6b4-4dd0-b524-b25e2f3a3433' THEN 'netmon-noc-nsw-analyst' WHEN '227a0d30-fe32-47f9-867f-9c91c13db70a' THEN 'netmon-noc-national' WHEN '2ee944da-a522-49e2-8600-6c72e454ce2c' THEN 'netmon-noc-wa-analyst' END, grantee), concat(table_schema, '.', table_name),
                 privilege_type FROM telco_netmon_febar_catalog.information_schema.table_privileges WHERE table_schema IN ('netmon_bronze', 'netmon_silver', 'netmon_gold', 'netmon_eval'))
        WHERE grantee_name NOT LIKE '%@%' GROUP BY kind, grantee_name ORDER BY kind, grantee_name
```

| kind | grantee_name | objects | privileges |
|---|---|---|---|
| SCHEMA | aec5be3d-de3c-404c-8e60-feed0f265fd3 | ["netmon_bronze","netmon_eval","netmon_gold","netmon_silver"] | ["ALL_PRIVILEGES","MANAGE"] |
| SCHEMA | netmon-noc-national | ["netmon_gold","netmon_silver"] | ["SELECT","USE_SCHEMA"] |
| SCHEMA | netmon-pii-officer | ["netmon_gold","netmon_silver"] | ["SELECT","USE_SCHEMA"] |
| TABLE | aec5be3d-de3c-404c-8e60-feed0f265fd3 | ["netmon_bronze.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_bronze_alarms_1","netmon_bronze.__materializ… | ["ALL_PRIVILEGES","MANAGE"] |
| TABLE | netmon-noc-national | ["netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_baseline_1","netmon_gold.__materiali… | ["SELECT"] |
| TABLE | netmon-pii-officer | ["netmon_gold.__materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_baseline_1","netmon_gold.__materiali… | ["SELECT"] |

_6 row(s)_

## SHOW GRANTS for a regional group (Unity Catalog view of the group)

Workspace-local groups are not UC principals, so they cannot hold, or keep, any grant; the governance job also issues REVOKE ALL for every group and records this.

```sql
SHOW GRANTS `noc_region_nsw` ON SCHEMA telco_netmon_febar_catalog.netmon_silver
```

Error returned by Unity Catalog:

```
FAILED: [RequestId=07e1f5ce-53af-4713-b49d-dc5f3469bf16 ErrorClass=PRINCIPAL_DOES_NOT_EXIST.PRINCIPAL_DOES_NOT_EXIST] Could not find principal with name noc_region_nsw.
```

## Tags: schemas and tables

```sql
SELECT 'schema' AS level, schema_name AS object, tag_name, tag_value FROM telco_netmon_febar_catalog.information_schema.schema_tags
        UNION ALL
        SELECT 'table', concat(schema_name, '.', table_name), tag_name, tag_value
        FROM telco_netmon_febar_catalog.information_schema.table_tags WHERE schema_name LIKE 'netmon%'
        ORDER BY 1, 2, 3
```

| level | object | tag_name | tag_value |
|---|---|---|---|
| schema | netmon_bronze | contains_pii | true |
| schema | netmon_bronze | domain | operations |
| schema | netmon_bronze | layer | bronze |
| schema | netmon_eval | domain | operations |
| schema | netmon_eval | ground_truth | true |
| schema | netmon_eval | netmon_layer | evaluation |
| schema | netmon_gold | contains_pii | false |
| schema | netmon_gold | domain | operations |
| schema | netmon_gold | layer | gold |
| schema | netmon_noc | consumer | regional_noc |
| schema | netmon_noc | domain | operations |
| schema | netmon_noc | netmon_layer | serving |
| schema | netmon_noc | row_filter | by_region |
| schema | netmon_raw | domain | operations |
| schema | netmon_raw | netmon_layer | landing |
| schema | netmon_silver | contains_pii | true |
| schema | netmon_silver | domain | operations |
| schema | netmon_silver | layer | silver |
| table | netmon_bronze.bronze_sessions | access | engineering_only |
| table | netmon_bronze.bronze_sessions | classification | restricted |
| table | netmon_bronze.bronze_sessions | contains_pii | true |
| table | netmon_bronze.bronze_sessions | domain | operations |
| table | netmon_bronze.bronze_sessions | netmon_domain | customer_experience |
| table | netmon_eval.eval_gt_incidents | ground_truth | true |
| table | netmon_eval.eval_gt_incidents | use | evaluation_only |
| table | netmon_eval.eval_incident_detection | ground_truth | true |
| table | netmon_eval.eval_incident_detection | use | evaluation_only |
| table | netmon_gold.gold_cell_baseline | domain | operations |
| table | netmon_gold.gold_cell_baseline | grain | cell_hour_daytype |
| table | netmon_gold.gold_cell_baseline | netmon_domain | network_performance |
| table | netmon_gold.gold_cell_health_1m | domain | operations |
| table | netmon_gold.gold_cell_health_1m | grain | cell_1m |
| table | netmon_gold.gold_cell_health_1m | netmon_domain | network_performance |
| table | netmon_gold.gold_cell_health_5m | domain | operations |
| table | netmon_gold.gold_cell_health_5m | grain | cell_5m |
| table | netmon_gold.gold_cell_health_5m | netmon_domain | network_performance |
| table | netmon_gold.gold_cell_health_5m_retrospective | domain | operations |
| table | netmon_gold.gold_cell_health_5m_retrospective | grain | cell_5m |
| table | netmon_gold.gold_cell_health_5m_retrospective | netmon_domain | network_performance |
| table | netmon_gold.gold_cell_health_5m_retrospective | use | retrospective_only |
| table | netmon_gold.gold_cell_sessions_5m | contains_pii | false |
| table | netmon_gold.gold_cell_sessions_5m | domain | operations |
| table | netmon_gold.gold_cell_sessions_5m | grain | cell_5m |
| table | netmon_gold.gold_cell_sessions_5m | netmon_domain | customer_experience |
| table | netmon_gold.gold_element_impact_5m | consumer | ml_rca_model |
| table | netmon_gold.gold_element_impact_5m | domain | operations |
| table | netmon_gold.gold_element_impact_5m | grain | element_5m |
| table | netmon_gold.gold_element_impact_5m | netmon_domain | root_cause_analysis |
| table | netmon_gold.gold_impact_detections | consumer | noc,lakebase,app |
| table | netmon_gold.gold_impact_detections | domain | operations |
| table | netmon_gold.gold_impact_detections | netmon_domain | service_assurance |
| table | netmon_gold.gold_impact_detections | row_filter | by_region |
| table | netmon_gold.gold_impact_detections | sla | 5min |
| table | netmon_silver.silver_alarms | contains_pii | false |
| table | netmon_silver.silver_alarms | domain | operations |
| table | netmon_silver.silver_alarms | netmon_domain | fault_management |
| table | netmon_silver.silver_kpis | contains_pii | false |
| table | netmon_silver.silver_kpis | domain | operations |
| table | netmon_silver.silver_kpis | netmon_domain | network_performance |
| table | netmon_silver.silver_quarantine | access | engineering_only |
| table | netmon_silver.silver_quarantine | classification | restricted |
| table | netmon_silver.silver_quarantine | domain | quality |
| table | netmon_silver.silver_sessions | classification | confidential |
| table | netmon_silver.silver_sessions | contains_pii | true |
| table | netmon_silver.silver_sessions | domain | operations |
| table | netmon_silver.silver_sessions | masked | imsi,msisdn |
| table | netmon_silver.silver_sessions | netmon_domain | customer_experience |
| table | netmon_silver.silver_sessions | row_filter | by_region |
| table | netmon_silver.silver_topology_nodes | domain | operations |
| table | netmon_silver.silver_topology_nodes | netmon_domain | network_inventory |

_70 row(s)_

## Tags: PII columns

```sql
SELECT schema_name, table_name, column_name, tag_name, tag_value FROM telco_netmon_febar_catalog.information_schema.column_tags
        WHERE schema_name LIKE 'netmon%' ORDER BY ALL
```

| schema_name | table_name | column_name | tag_name | tag_value |
|---|---|---|---|---|
| netmon_bronze | bronze_sessions | imsi | classification | restricted |
| netmon_bronze | bronze_sessions | imsi | netmon_pii | imsi |
| netmon_bronze | bronze_sessions | msisdn | class.phone_number |  |
| netmon_bronze | bronze_sessions | msisdn | classification | restricted |
| netmon_bronze | bronze_sessions | msisdn | netmon_pii | msisdn |
| netmon_silver | silver_sessions | imsi | classification | confidential |
| netmon_silver | silver_sessions | imsi | masked | mask_imsi |
| netmon_silver | silver_sessions | imsi | netmon_pii | imsi |
| netmon_silver | silver_sessions | msisdn | class.phone_number |  |
| netmon_silver | silver_sessions | msisdn | classification | confidential |
| netmon_silver | silver_sessions | msisdn | masked | mask_msisdn |
| netmon_silver | silver_sessions | msisdn | netmon_pii | msisdn |
| netmon_silver | silver_sessions | subscriber_key | netmon_pii | pseudonymous |

_13 row(s)_

## Table comments (key tables)

```sql
SELECT table_schema, table_name, left(comment, 150) AS comment FROM telco_netmon_febar_catalog.information_schema.tables
        WHERE table_schema IN ('netmon_silver', 'netmon_gold', 'netmon_eval', 'netmon_noc') ORDER BY 1, 2
```

| table_schema | table_name | comment |
|---|---|---|
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_bronze_gt_dq_injections_1 | GROUND TRUTH audit log of every injected data-quality defect. Evaluation only. |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_bronze_gt_incidents_1 | GROUND TRUTH incident labels as written by the generator. Evaluation only: never a feature source. |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_eval_alert_precision_1 | Alert-level fault precision: detections grouped per (source_run, element_id) into episodes (starting more than 10 min a… |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_eval_detection_log_1 | Unfiltered copy of the impact detections for offline scoring (gold_impact_detections is row-filtered for NOC users). Sa… |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_eval_detection_precision_1 | Detection-ROW fault precision per source run and signal source (one row per detection, i.e. per degraded cell-minute or… |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_eval_dq_capture_1 | Data-quality defects injected by the generator (ground truth) vs how the pipeline handled them: quarantined (malformed/… |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_eval_gt_incidents_1 | GROUND TRUTH incidents, typed (UTC), one row per (source_run, incident_id). Labels only. |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_eval_incident_detection_1 | Per scored incident (customer-impacting, not censored), two separate metrics. (a) impact detection: first detection on … |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_eval_rca_baseline_1 | Topology-heuristic RCA baseline for the later ML model: in the incident's region and first 15 minutes of impact, rank g… |
| netmon_eval | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_eval_ttd_summary_1 | Per source run (history = 15-min ROP backfill, stream = 1-min live feed), per event class (fault first) and fault type:… |
| netmon_eval | bronze_gt_dq_injections | GROUND TRUTH audit log of every injected data-quality defect. Evaluation only. |
| netmon_eval | bronze_gt_incidents | GROUND TRUTH incident labels as written by the generator. Evaluation only: never a feature source. |
| netmon_eval | eval_alert_precision | Alert-level fault precision: detections grouped per (source_run, element_id) into episodes (starting more than 10 min a… |
| netmon_eval | eval_detection_log | Unfiltered copy of the impact detections for offline scoring (gold_impact_detections is row-filtered for NOC users). Sa… |
| netmon_eval | eval_detection_precision | Detection-ROW fault precision per source run and signal source (one row per detection, i.e. per degraded cell-minute or… |
| netmon_eval | eval_dq_capture | Data-quality defects injected by the generator (ground truth) vs how the pipeline handled them: quarantined (malformed/… |
| netmon_eval | eval_gt_incidents | GROUND TRUTH incidents, typed (UTC), one row per (source_run, incident_id). Labels only. |
| netmon_eval | eval_incident_detection | Per scored incident (customer-impacting, not censored), two separate metrics. (a) impact detection: first detection on … |
| netmon_eval | eval_rca_baseline | Topology-heuristic RCA baseline for the later ML model: in the incident's region and first 15 minutes of impact, rank g… |
| netmon_eval | eval_ttd_summary | Per source run (history = 15-min ROP backfill, stream = 1-min live feed), per event class (fault first) and fault type:… |
| netmon_eval | netmon_pipeline_event_log | NULL |
| netmon_gold | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_baseline_1 | Per cell x local hour x day type (weekday/weekend) KPI mean and std over the 14 local days strictly before valid_date. … |
| netmon_gold | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_health_1m_1 | Real-time per-cell 1-minute KPI windows (event time, UTC) built from ON-TIME records only, with baseline means, z-score… |
| netmon_gold | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_health_5m_1 | Real-time per-cell 5-minute KPI windows with baseline deviation, ON-TIME records only (qualification and evidence_ts us… |
| netmon_gold | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_health_5m_retrospective_1 | RETROSPECTIVE per-cell 5-minute windows over ALL silver KPI records, late arrivals included (n_late_reports). For after… |
| netmon_gold | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_cell_sessions_5m_1 | Per-cell 5-minute session outcomes by session end time: setup failures, drops, no-service and approximate distinct subs… |
| netmon_gold | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_element_impact_5m_1 | Topology rollup per element per 5-min window: impacted (degraded or silent) descendant cells, impacted children, parent… |
| netmon_gold | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_gold_impact_detections_1 | Customer-impact detections per cell (KPI rules vs baseline) or element (element-down alarms), with detected_ts (wall cl… |
| netmon_gold | gold_cell_baseline | Per cell x local hour x day type (weekday/weekend) KPI mean and std over the 14 local days strictly before valid_date. … |
| netmon_gold | gold_cell_health_1m | Real-time per-cell 1-minute KPI windows (event time, UTC) built from ON-TIME records only, with baseline means, z-score… |
| netmon_gold | gold_cell_health_5m | Real-time per-cell 5-minute KPI windows with baseline deviation, ON-TIME records only (qualification and evidence_ts us… |
| netmon_gold | gold_cell_health_5m_retrospective | RETROSPECTIVE per-cell 5-minute windows over ALL silver KPI records, late arrivals included (n_late_reports). For after… |
| netmon_gold | gold_cell_sessions_5m | Per-cell 5-minute session outcomes by session end time: setup failures, drops, no-service and approximate distinct subs… |
| netmon_gold | gold_element_impact_5m | Topology rollup per element per 5-min window: impacted (degraded or silent) descendant cells, impacted children, parent… |
| netmon_gold | gold_impact_detections | Customer-impact detections per cell (KPI rules vs baseline) or element (element-down alarms), with detected_ts (wall cl… |
| netmon_noc | gold_cell_baseline | Region-filtered cell baseline |
| netmon_noc | gold_cell_health_1m | Region-filtered 1-minute cell health |
| netmon_noc | gold_cell_health_5m | Region-filtered 5-minute cell health |
| netmon_noc | gold_cell_sessions_5m | Region-filtered per-cell session outcomes |
| netmon_noc | gold_element_impact_5m | Region-filtered topology rollup |
| netmon_noc | gold_impact_detections | gold_impact_detections: row filter of the table applies |
| netmon_noc | silver_alarms | Region-filtered silver_alarms |
| netmon_noc | silver_kpis | Region-filtered silver_kpis |
| netmon_noc | silver_maintenance_windows | Region-filtered change calendar |
| netmon_noc | silver_sessions | silver_sessions: row filter and IMSI/MSISDN masks of the table apply |
| netmon_noc | silver_topology_edges | Region-filtered topology edges (region of the child element) |
| netmon_noc | silver_topology_nodes | Region-filtered network inventory |
| netmon_silver | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_alarms_1 | Validated alarm RAISE/CLEAR events with the element's region and ancestors. is_service_down marks element-down alarms t… |
| netmon_silver | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_kpis_1 | Validated per-cell KPI records: typed, UTC timestamps plus local time / local date from the cell's IANA zone, deduplica… |
| netmon_silver | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_maintenance_windows_1 | Approved change windows (UTC). Operational data the NOC uses to suppress planned work. |
| netmon_silver | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_quarantine_1 | Rows rejected by silver expectations (malformed, null, out-of-range, unknown element) and unparseable JSON lines, with … |
| netmon_silver | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_sessions_1 | Validated sampled xDR sessions. IMSI/MSISDN are column-masked and rows are filtered by the reader's regional NOC group.… |
| netmon_silver | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_topology_edges_1 | Directed topology edges, upstream -> downstream. |
| netmon_silver | __materialization_mat_80449004_f45a_4b32_8215_f68fdf6acfd9_silver_topology_nodes_1 | Network inventory (one row per element, latest snapshot). Ancestor columns (amf_id .. site_id) include the element itse… |
| netmon_silver | silver_alarms | Validated alarm RAISE/CLEAR events with the element's region and ancestors. is_service_down marks element-down alarms t… |
| netmon_silver | silver_kpis | Validated per-cell KPI records: typed, UTC timestamps plus local time / local date from the cell's IANA zone, deduplica… |
| netmon_silver | silver_maintenance_windows | Approved change windows (UTC). Operational data the NOC uses to suppress planned work. |
| netmon_silver | silver_quarantine | Rows rejected by silver expectations (malformed, null, out-of-range, unknown element) and unparseable JSON lines, with … |
| netmon_silver | silver_sessions | Validated sampled xDR sessions. IMSI/MSISDN are column-masked and rows are filtered by the reader's regional NOC group.… |
| netmon_silver | silver_topology_edges | Directed topology edges, upstream -> downstream. |
| netmon_silver | silver_topology_nodes | Network inventory (one row per element, latest snapshot). Ancestor columns (amf_id .. site_id) include the element itse… |

_61 row(s)_

## Column comments on silver_sessions

```sql
SELECT column_name, data_type, comment FROM telco_netmon_febar_catalog.information_schema.columns
        WHERE table_schema = 'netmon_silver' AND table_name = 'silver_sessions' AND comment IS NOT NULL
        ORDER BY ordinal_position
```

| column_name | data_type | comment |
|---|---|---|
| record_id | STRING | xDR session id (dedupe key) |
| imsi | STRING | PII: subscriber IMSI (masked unless pii_privileged) |
| msisdn | STRING | PII: subscriber MSISDN (masked unless pii_privileged) |
| subscriber_key | STRING | Pseudonymous SHA-256 subscriber key for distinct counts |
| region_code | STRING | Region of the serving cell (row-filter key) |
| start_ts | TIMESTAMP | UTC |
| end_ts | TIMESTAMP | UTC |
| emitted_ts | TIMESTAMP | UTC |
| start_ts_local | TIMESTAMP | Session start in the cell local time zone |

_9 row(s)_

## State 1 - noc_national (capturing user): principal

```sql
SELECT current_user() AS user, is_member('noc_national') AS in_noc_national,
               is_member('noc_region_nsw') AS in_noc_region_nsw, is_member('pii_privileged') AS in_pii_privileged,
               telco_netmon_febar_catalog.netmon_gov.is_pii_privileged() AS pii_privileged_fn
```

| user | in_noc_national | in_noc_region_nsw | in_pii_privileged | pii_privileged_fn |
|---|---|---|---|---|
| louis.chen@databricks.com | true | false | false | false |

_1 row(s)_

## State 1 - noc_national (capturing user): rows visible in every object a regional role is granted

```sql
SELECT 'silver_kpis' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_kpis
UNION ALL SELECT 'silver_alarms' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_alarms
UNION ALL SELECT 'silver_sessions' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_sessions
UNION ALL SELECT 'silver_topology_nodes' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_topology_nodes
UNION ALL SELECT 'silver_topology_edges' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_topology_edges
UNION ALL SELECT 'silver_maintenance_windows' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_maintenance_windows
UNION ALL SELECT 'gold_cell_baseline' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_baseline
UNION ALL SELECT 'gold_cell_health_1m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_health_1m
UNION ALL SELECT 'gold_cell_health_5m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_health_5m
UNION ALL SELECT 'gold_impact_detections' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_impact_detections
UNION ALL SELECT 'gold_element_impact_5m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_element_impact_5m
UNION ALL SELECT 'gold_cell_sessions_5m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_sessions_5m
```

| netmon_noc_view | visible_rows | regions |
|---|---|---|
| silver_kpis | 2413825 | NQL,NSW,VIC,WA |
| silver_alarms | 19600 | NQL,NSW,VIC,WA |
| silver_sessions | 1320796 | NQL,NSW,VIC,WA |
| silver_topology_nodes | 1887 | NQL,NSW,VIC,WA |
| silver_topology_edges | 1883 | NQL,NSW,VIC,WA |
| silver_maintenance_windows | 2 | NSW,VIC |
| gold_cell_baseline | 1016375 | NQL,NSW,VIC,WA |
| gold_cell_health_1m | 2385288 | NQL,NSW,VIC,WA |
| gold_cell_health_5m | 1987413 | NQL,NSW,VIC,WA |
| gold_impact_detections | 12074 | NQL,NSW,VIC,WA |
| gold_element_impact_5m | 141461 | NQL,NSW,VIC,WA |
| gold_cell_sessions_5m | 1107259 | NQL,NSW,VIC,WA |

_12 row(s)_

## State 1 - noc_national (capturing user): IMSI / MSISDN shape (values never printed in full)

```sql
SELECT count(*) AS n_rows,
               count_if(imsi RLIKE '^00101[0-9]{10}$') AS imsi_full_value,
               count_if(imsi RLIKE '^00101[*]{8}[0-9]{2}$') AS imsi_masked,
               count_if(msisdn RLIKE '^[+]999[0-9]{9}$') AS msisdn_full_value,
               count_if(msisdn RLIKE '^[+]999[*]{6}[0-9]{3}$') AS msisdn_masked
        FROM telco_netmon_febar_catalog.netmon_noc.silver_sessions
```

| n_rows | imsi_full_value | imsi_masked | msisdn_full_value | msisdn_masked |
|---|---|---|---|---|
| 1320796 | 0 | 1320796 | 0 | 1320796 |

_1 row(s)_

## State 1: masked sample for a NOC user outside pii_privileged

```sql
SELECT record_id, imsi, msisdn, region_code, outcome FROM telco_netmon_febar_catalog.netmon_noc.silver_sessions ORDER BY record_id LIMIT 5
```

| record_id | imsi | msisdn | region_code | outcome |
|---|---|---|---|---|
| S-20260924T0000-0000000 | 00101********76 | +999******374 | NSW | COMPLETED |
| S-20260924T0000-0000001 | 00101********87 | +999******875 | NSW | COMPLETED |
| S-20260924T0000-0000002 | 00101********15 | +999******623 | NSW | COMPLETED |
| S-20260924T0000-0000003 | 00101********42 | +999******580 | NSW | COMPLETED |
| S-20260924T0000-0000004 | 00101********05 | +999******813 | NSW | COMPLETED |

_5 row(s)_

## State 2 - noc_region_nsw only: principal

```sql
SELECT current_user() AS user, is_member('noc_national') AS in_noc_national,
               is_member('noc_region_nsw') AS in_noc_region_nsw, is_member('pii_privileged') AS in_pii_privileged,
               telco_netmon_febar_catalog.netmon_gov.is_pii_privileged() AS pii_privileged_fn
```

| user | in_noc_national | in_noc_region_nsw | in_pii_privileged | pii_privileged_fn |
|---|---|---|---|---|
| louis.chen@databricks.com | false | true | false | false |

_1 row(s)_

## State 2 - noc_region_nsw only: rows visible in every object a regional role is granted

Only NSW rows remain in every object.

```sql
SELECT 'silver_kpis' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_kpis
UNION ALL SELECT 'silver_alarms' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_alarms
UNION ALL SELECT 'silver_sessions' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_sessions
UNION ALL SELECT 'silver_topology_nodes' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_topology_nodes
UNION ALL SELECT 'silver_topology_edges' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_topology_edges
UNION ALL SELECT 'silver_maintenance_windows' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_maintenance_windows
UNION ALL SELECT 'gold_cell_baseline' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_baseline
UNION ALL SELECT 'gold_cell_health_1m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_health_1m
UNION ALL SELECT 'gold_cell_health_5m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_health_5m
UNION ALL SELECT 'gold_impact_detections' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_impact_detections
UNION ALL SELECT 'gold_element_impact_5m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_element_impact_5m
UNION ALL SELECT 'gold_cell_sessions_5m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_sessions_5m
```

| netmon_noc_view | visible_rows | regions |
|---|---|---|
| silver_kpis | 1048148 | NSW |
| silver_alarms | 7335 | NSW |
| silver_sessions | 527217 | NSW |
| silver_topology_nodes | 814 | NSW |
| silver_topology_edges | 813 | NSW |
| silver_maintenance_windows | 1 | NSW |
| gold_cell_baseline | 440910 | NSW |
| gold_cell_health_1m | 1035581 | NSW |
| gold_cell_health_5m | 862608 | NSW |
| gold_impact_detections | 4287 | NSW |
| gold_element_impact_5m | 56879 | NSW |
| gold_cell_sessions_5m | 447935 | NSW |

_12 row(s)_

## State 3 - no NOC group: principal

```sql
SELECT current_user() AS user, is_member('noc_national') AS in_noc_national,
               is_member('noc_region_nsw') AS in_noc_region_nsw, is_member('pii_privileged') AS in_pii_privileged,
               telco_netmon_febar_catalog.netmon_gov.is_pii_privileged() AS pii_privileged_fn
```

| user | in_noc_national | in_noc_region_nsw | in_pii_privileged | pii_privileged_fn |
|---|---|---|---|---|
| louis.chen@databricks.com | false | false | false | false |

_1 row(s)_

## State 3 - no NOC group: rows visible in every object a regional role is granted

No rows in any object: the filter is false for every region.

```sql
SELECT 'silver_kpis' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_kpis
UNION ALL SELECT 'silver_alarms' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_alarms
UNION ALL SELECT 'silver_sessions' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_sessions
UNION ALL SELECT 'silver_topology_nodes' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_topology_nodes
UNION ALL SELECT 'silver_topology_edges' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_topology_edges
UNION ALL SELECT 'silver_maintenance_windows' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_maintenance_windows
UNION ALL SELECT 'gold_cell_baseline' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_baseline
UNION ALL SELECT 'gold_cell_health_1m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_health_1m
UNION ALL SELECT 'gold_cell_health_5m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_health_5m
UNION ALL SELECT 'gold_impact_detections' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_impact_detections
UNION ALL SELECT 'gold_element_impact_5m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_element_impact_5m
UNION ALL SELECT 'gold_cell_sessions_5m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_sessions_5m
```

| netmon_noc_view | visible_rows | regions |
|---|---|---|
| silver_kpis | 0 |  |
| silver_alarms | 0 |  |
| silver_sessions | 0 |  |
| silver_topology_nodes | 0 |  |
| silver_topology_edges | 0 |  |
| silver_maintenance_windows | 0 |  |
| gold_cell_baseline | 0 |  |
| gold_cell_health_1m | 0 |  |
| gold_cell_health_5m | 0 |  |
| gold_impact_detections | 0 |  |
| gold_element_impact_5m | 0 |  |
| gold_cell_sessions_5m | 0 |  |

_12 row(s)_

## State 4 - pii_privileged only (no NOC role): principal

```sql
SELECT current_user() AS user, is_member('noc_national') AS in_noc_national,
               is_member('noc_region_nsw') AS in_noc_region_nsw, is_member('pii_privileged') AS in_pii_privileged,
               telco_netmon_febar_catalog.netmon_gov.is_pii_privileged() AS pii_privileged_fn
```

| user | in_noc_national | in_noc_region_nsw | in_pii_privileged | pii_privileged_fn |
|---|---|---|---|---|
| louis.chen@databricks.com | false | false | true | true |

_1 row(s)_

## State 4 - pii_privileged only (no NOC role): rows visible in every object a regional role is granted

Still no rows: pii_privileged grants no data access on its own (and holds no privileges, see the persona table above).

```sql
SELECT 'silver_kpis' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_kpis
UNION ALL SELECT 'silver_alarms' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_alarms
UNION ALL SELECT 'silver_sessions' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_sessions
UNION ALL SELECT 'silver_topology_nodes' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_topology_nodes
UNION ALL SELECT 'silver_topology_edges' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_topology_edges
UNION ALL SELECT 'silver_maintenance_windows' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_maintenance_windows
UNION ALL SELECT 'gold_cell_baseline' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_baseline
UNION ALL SELECT 'gold_cell_health_1m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_health_1m
UNION ALL SELECT 'gold_cell_health_5m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_health_5m
UNION ALL SELECT 'gold_impact_detections' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_impact_detections
UNION ALL SELECT 'gold_element_impact_5m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_element_impact_5m
UNION ALL SELECT 'gold_cell_sessions_5m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_sessions_5m
```

| netmon_noc_view | visible_rows | regions |
|---|---|---|
| silver_kpis | 0 |  |
| silver_alarms | 0 |  |
| silver_sessions | 0 |  |
| silver_topology_nodes | 0 |  |
| silver_topology_edges | 0 |  |
| silver_maintenance_windows | 0 |  |
| gold_cell_baseline | 0 |  |
| gold_cell_health_1m | 0 |  |
| gold_cell_health_5m | 0 |  |
| gold_impact_detections | 0 |  |
| gold_element_impact_5m | 0 |  |
| gold_cell_sessions_5m | 0 |  |

_12 row(s)_

## State 4 - pii_privileged only (no NOC role): IMSI / MSISDN shape (values never printed in full)

```sql
SELECT count(*) AS n_rows,
               count_if(imsi RLIKE '^00101[0-9]{10}$') AS imsi_full_value,
               count_if(imsi RLIKE '^00101[*]{8}[0-9]{2}$') AS imsi_masked,
               count_if(msisdn RLIKE '^[+]999[0-9]{9}$') AS msisdn_full_value,
               count_if(msisdn RLIKE '^[+]999[*]{6}[0-9]{3}$') AS msisdn_masked
        FROM telco_netmon_febar_catalog.netmon_noc.silver_sessions
```

| n_rows | imsi_full_value | imsi_masked | msisdn_full_value | msisdn_masked |
|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 |

_1 row(s)_

## State 5 - noc_national + pii_privileged: principal

```sql
SELECT current_user() AS user, is_member('noc_national') AS in_noc_national,
               is_member('noc_region_nsw') AS in_noc_region_nsw, is_member('pii_privileged') AS in_pii_privileged,
               telco_netmon_febar_catalog.netmon_gov.is_pii_privileged() AS pii_privileged_fn
```

| user | in_noc_national | in_noc_region_nsw | in_pii_privileged | pii_privileged_fn |
|---|---|---|---|---|
| louis.chen@databricks.com | true | false | true | true |

_1 row(s)_

## State 5 - noc_national + pii_privileged: rows visible in every object a regional role is granted

A NOC role plus pii_privileged: every region, and IMSI / MSISDN unmasked (checked by pattern).

```sql
SELECT 'silver_kpis' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_kpis
UNION ALL SELECT 'silver_alarms' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_alarms
UNION ALL SELECT 'silver_sessions' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_sessions
UNION ALL SELECT 'silver_topology_nodes' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_topology_nodes
UNION ALL SELECT 'silver_topology_edges' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_topology_edges
UNION ALL SELECT 'silver_maintenance_windows' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.silver_maintenance_windows
UNION ALL SELECT 'gold_cell_baseline' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_baseline
UNION ALL SELECT 'gold_cell_health_1m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_health_1m
UNION ALL SELECT 'gold_cell_health_5m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_health_5m
UNION ALL SELECT 'gold_impact_detections' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_impact_detections
UNION ALL SELECT 'gold_element_impact_5m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_element_impact_5m
UNION ALL SELECT 'gold_cell_sessions_5m' AS netmon_noc_view, count(*) AS visible_rows, array_join(array_sort(collect_set(region_code)), ',') AS regions FROM telco_netmon_febar_catalog.netmon_noc.gold_cell_sessions_5m
```

| netmon_noc_view | visible_rows | regions |
|---|---|---|
| silver_kpis | 2413825 | NQL,NSW,VIC,WA |
| silver_alarms | 19600 | NQL,NSW,VIC,WA |
| silver_sessions | 1320796 | NQL,NSW,VIC,WA |
| silver_topology_nodes | 1887 | NQL,NSW,VIC,WA |
| silver_topology_edges | 1883 | NQL,NSW,VIC,WA |
| silver_maintenance_windows | 2 | NSW,VIC |
| gold_cell_baseline | 1016375 | NQL,NSW,VIC,WA |
| gold_cell_health_1m | 2385288 | NQL,NSW,VIC,WA |
| gold_cell_health_5m | 1987413 | NQL,NSW,VIC,WA |
| gold_impact_detections | 12074 | NQL,NSW,VIC,WA |
| gold_element_impact_5m | 141461 | NQL,NSW,VIC,WA |
| gold_cell_sessions_5m | 1107259 | NQL,NSW,VIC,WA |

_12 row(s)_

## State 5 - noc_national + pii_privileged: IMSI / MSISDN shape (values never printed in full)

```sql
SELECT count(*) AS n_rows,
               count_if(imsi RLIKE '^00101[0-9]{10}$') AS imsi_full_value,
               count_if(imsi RLIKE '^00101[*]{8}[0-9]{2}$') AS imsi_masked,
               count_if(msisdn RLIKE '^[+]999[0-9]{9}$') AS msisdn_full_value,
               count_if(msisdn RLIKE '^[+]999[*]{6}[0-9]{3}$') AS msisdn_masked
        FROM telco_netmon_febar_catalog.netmon_noc.silver_sessions
```

| n_rows | imsi_full_value | imsi_masked | msisdn_full_value | msisdn_masked |
|---|---|---|---|---|
| 1320796 | 1320796 | 0 | 1320796 | 0 |

_1 row(s)_

## Restored membership

```sql
SELECT current_user() AS user, is_member('noc_national') AS in_noc_national,
               is_member('noc_region_nsw') AS in_noc_region_nsw, is_member('pii_privileged') AS in_pii_privileged,
               telco_netmon_febar_catalog.netmon_gov.is_pii_privileged() AS pii_privileged_fn
```

| user | in_noc_national | in_noc_region_nsw | in_pii_privileged | pii_privileged_fn |
|---|---|---|---|---|
| louis.chen@databricks.com | true | false | false | false |

_1 row(s)_
