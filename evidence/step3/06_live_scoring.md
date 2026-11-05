# Live scoring: element_status and open_incidents (Delta sources of Lakebase)

Captured 2026-11-05 17:35 UTC from workspace profile `febar` by `scripts/capture_evidence_step3.py`.

## Row counts

```sql
SELECT 'element_status' AS t, count(*) AS n, max(last_updated_ts) AS data_time, max(refreshed_at) AS refreshed
        FROM telco_netmon_febar_catalog.netmon_rca.element_status
        UNION ALL SELECT 'open_incidents', count(*), max(last_scored_ts), max(refreshed_at) FROM telco_netmon_febar_catalog.netmon_rca.open_incidents
```

| t | n | data_time | refreshed |
|---|---|---|---|
| element_status | 1887 | 2026-10-09T00:56:00.000Z | 2026-11-05T17:23:35.677Z |
| open_incidents | 17 | 2026-10-09T00:56:00.000Z | 2026-11-05T17:23:35.677Z |

_2 row(s)_

## Element states

```sql
SELECT element_type, state, count(*) AS n FROM telco_netmon_febar_catalog.netmon_rca.element_status GROUP BY ALL ORDER BY 1, 2
```

| element_type | state | n |
|---|---|---|
| AGG_ROUTER | down | 1 |
| AGG_ROUTER | impacted | 9 |
| AGG_ROUTER | ok | 6 |
| AMF_MME | impacted | 4 |
| BACKHAUL_LINK | degraded | 5 |
| BACKHAUL_LINK | down | 1 |
| BACKHAUL_LINK | impacted | 13 |
| BACKHAUL_LINK | ok | 114 |
| CELL | alarm | 2 |
| CELL | degraded | 39 |
| CELL | down | 18 |
| CELL | ok | 1372 |
| SITE | alarm | 6 |
| SITE | degraded | 8 |
| SITE | down | 3 |
| SITE | impacted | 12 |
| SITE | ok | 270 |
| UPF_SGW | impacted | 4 |

_18 row(s)_

## Open incidents with top-3 suspects

```sql
SELECT incident_id, region_code, detected_ts, last_scored_ts, suspect_1_id, suspect_1_score, suspect_2_id,
               suspect_2_score, suspect_3_id, suspect_3_score, n_impacted_cells
        FROM telco_netmon_febar_catalog.netmon_rca.open_incidents ORDER BY suspect_1_score DESC LIMIT 15
```

| incident_id | region_code | detected_ts | last_scored_ts | suspect_1_id | suspect_1_score | suspect_2_id | suspect_2_score | suspect_3_id | suspect_3_score | n_impacted_cells |
|---|---|---|---|---|---|---|---|---|---|---|
| RCA-27ed3e8af852d33a | VIC | 2026-10-08T23:56:00.000Z | 2026-10-09T00:56:00.000Z | BH-VIC-0005 | 1.0 | AGG-VIC-01 | 0.0 | CELL-VIC-00010-5G2 | 0.0 | 12 |
| RCA-1073d4d88aa7e05b | VIC | 2026-10-08T23:56:00.000Z | 2026-10-09T00:56:00.000Z | CELL-VIC-00062-5G2 | 1.0 | AGG-VIC-03 | 0.0 | AMF-VIC-01 | 0.0 | 1 |
| RCA-60fe3d71c22893d5 | NSW | 2026-10-08T23:56:00.000Z | 2026-10-09T00:56:00.000Z | CELL-NSW-00123-4G3 | 1.0 | SITE-NSW-00123 | 2.0E-4 | AGG-NSW-04 | 0.0 | 1 |
| RCA-fbd7ff66e62b0b42 | NSW | 2026-10-09T00:07:00.000Z | 2026-10-09T00:56:00.000Z | SITE-NSW-00009 | 1.0 | AGG-NSW-01 | 0.0231 | AMF-NSW-01 | 0.0 | 6 |
| RCA-9737805189832cde | VIC | 2026-10-09T00:41:00.000Z | 2026-10-09T00:56:00.000Z | CELL-VIC-00005-4G2 | 1.0 | AGG-VIC-01 | 0.0 | AMF-VIC-01 | 0.0 | 1 |
| RCA-9eb236846361cdad | VIC | 2026-10-09T00:24:00.000Z | 2026-10-09T00:56:00.000Z | CELL-VIC-00033-4G2 | 1.0 | AGG-VIC-02 | 0.0 | AMF-VIC-01 | 0.0 | 1 |
| RCA-944a68e9bf7eff9b | VIC | 2026-10-08T23:56:00.000Z | 2026-10-09T00:56:00.000Z | CELL-VIC-00107-5G1 | 1.0 | AGG-VIC-04 | 0.0 | AMF-VIC-01 | 0.0 | 1 |
| RCA-ce4e7fd28bd45261 | NSW | 2026-10-09T00:32:00.000Z | 2026-10-09T00:56:00.000Z | BH-NSW-0041 | 1.0 | SITE-NSW-00097 | 2.0E-4 | AGG-NSW-04 | 0.0 | 3 |
| RCA-cdc1224a2469350b | NSW | 2026-10-09T00:39:00.000Z | 2026-10-09T00:56:00.000Z | BH-NSW-0015 | 1.0 | SITE-NSW-00045 | 2.0E-4 | AGG-NSW-02 | 0.0 | 6 |
| RCA-4b24e8c0bfedac1a | NSW | 2026-10-08T23:56:00.000Z | 2026-10-09T00:56:00.000Z | BH-NSW-0010 | 1.0 | AGG-NSW-01 | 0.0743 | SITE-NSW-00025 | 0.0743 | 3 |
| RCA-e909709b1c6a18fb | NSW | 2026-10-08T23:59:00.000Z | 2026-10-09T00:56:00.000Z | BH-NSW-0013 | 1.0 | AGG-NSW-01 | 0.0231 | CELL-NSW-00031-4G3 | 0.0 | 9 |
| RCA-c068ecb5f659c20d | NSW | 2026-10-09T00:37:00.000Z | 2026-10-09T00:56:00.000Z | CELL-NSW-00122-4G2 | 1.0 | AGG-NSW-04 | 0.0 | AMF-NSW-01 | 0.0 | 1 |
| RCA-55424701801c7330 | NSW | 2026-10-09T00:19:00.000Z | 2026-10-09T00:56:00.000Z | CELL-NSW-00051-4G3 | 1.0 | SITE-NSW-00045 | 2.0E-4 | AGG-NSW-02 | 0.0 | 1 |
| RCA-399fe9bb03f3b4cb | VIC | 2026-10-09T00:34:00.000Z | 2026-10-09T00:56:00.000Z | CELL-VIC-00022-5G3 | 1.0 | AGG-VIC-02 | 0.0 | AMF-VIC-01 | 0.0 | 1 |
| RCA-c69d3bab90ca811f | VIC | 2026-10-08T23:58:00.000Z | 2026-10-09T00:56:00.000Z | CELL-VIC-00090-4G3 | 1.0 | AGG-VIC-04 | 0.0 | AMF-VIC-01 | 0.0 | 1 |

_15 row(s)_

## Open incidents vs the live run's ground truth (incidents still in flight at the end = censored)

Ground truth is joined here for the evidence only; the scoring job never reads it.

```sql
SELECT o.incident_id, o.suspect_1_id, g.incident_id AS gt_incident, g.fault_type, g.root_element_ids,
               array_contains(g.root_element_ids, o.suspect_1_id) AS top1_is_root,
               array_contains(g.root_element_ids, o.suspect_1_id) OR array_contains(g.root_element_ids, o.suspect_2_id)
                 OR array_contains(g.root_element_ids, o.suspect_3_id) AS root_in_top3, g.is_censored
        FROM telco_netmon_febar_catalog.netmon_rca.open_incidents o
        LEFT JOIN telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents g ON g.source_run = o.source_run AND g.event_class = 'fault'
         AND (array_contains(g.root_element_ids, o.suspect_1_id) OR array_contains(g.affected_element_ids, o.suspect_1_id)
              OR array_contains(g.affected_cell_ids, o.suspect_1_id))
         AND o.last_scored_ts BETWEEN g.start_ts - INTERVAL 5 MINUTES AND coalesce(g.end_ts, g.impact_end_ts) + INTERVAL 10 MINUTES
        ORDER BY o.suspect_1_score DESC LIMIT 20
```

| incident_id | suspect_1_id | gt_incident | fault_type | root_element_ids | top1_is_root | root_in_top3 | is_censored |
|---|---|---|---|---|---|---|---|
| RCA-9eb236846361cdad | CELL-VIC-00033-4G2 | INC-2026100900-00004 | CELL_OUTAGE | ["CELL-VIC-00033-4G2"] | true | true | true |
| RCA-1073d4d88aa7e05b | CELL-VIC-00062-5G2 | INC-2026100823-00006 | CELL_OUTAGE | ["CELL-VIC-00062-5G2"] | true | true | true |
| RCA-d28473ab1bd7b846 | AGG-NQL-02 | INC-2026100900-00011 | LONG_HAUL_FIBRE_CUT | ["AGG-NQL-02"] | true | true | true |
| RCA-c068ecb5f659c20d | CELL-NSW-00122-4G2 | INC-2026100900-00008 | CELL_OUTAGE | ["CELL-NSW-00122-4G2"] | true | true | true |
| RCA-9737805189832cde | CELL-VIC-00005-4G2 | INC-2026100900-00010 | CELL_OUTAGE | ["CELL-VIC-00005-4G2"] | true | true | true |
| RCA-cdc1224a2469350b | BH-NSW-0015 | INC-2026100900-00006 | BACKHAUL_DEGRADATION | ["BH-NSW-0015"] | true | true | true |
| RCA-55424701801c7330 | CELL-NSW-00051-4G3 | INC-2026100900-00003 | CELL_OUTAGE | ["CELL-NSW-00051-4G3"] | true | true | true |
| RCA-c69d3bab90ca811f | CELL-VIC-00090-4G3 | INC-2026100823-00011 | CELL_OUTAGE | ["CELL-VIC-00090-4G3"] | true | true | true |
| RCA-c7276c3238a27971 | SITE-NSW-00105 | INC-2026100823-00002 | SITE_POWER_OUTAGE | ["SITE-NSW-00105"] | true | true | true |
| RCA-399fe9bb03f3b4cb | CELL-VIC-00022-5G3 | INC-2026100900-00007 | CELL_OUTAGE | ["CELL-VIC-00022-5G3"] | true | true | true |
| RCA-944a68e9bf7eff9b | CELL-VIC-00107-5G1 | INC-2026100823-00003 | CELL_OUTAGE | ["CELL-VIC-00107-5G1"] | true | true | true |
| RCA-4b24e8c0bfedac1a | BH-NSW-0010 | INC-2026100823-00005 | BACKHAUL_DEGRADATION | ["BH-NSW-0010"] | true | true | true |
| RCA-fbd7ff66e62b0b42 | SITE-NSW-00009 | INC-2026100823-00009 | SITE_POWER_OUTAGE | ["SITE-NSW-00009"] | true | true | true |
| RCA-ce4e7fd28bd45261 | BH-NSW-0041 | INC-2026100900-00005 | BACKHAUL_DEGRADATION | ["BH-NSW-0041"] | true | true | true |
| RCA-60fe3d71c22893d5 | CELL-NSW-00123-4G3 | INC-2026100823-00001 | CELL_OUTAGE | ["CELL-NSW-00123-4G3"] | true | true | true |
| RCA-e909709b1c6a18fb | BH-NSW-0013 | INC-2026100823-00010 | BACKHAUL_DEGRADATION | ["BH-NSW-0013"] | true | true | true |
| RCA-27ed3e8af852d33a | BH-VIC-0005 | INC-2026100822-00008 | BACKHAUL_DEGRADATION | ["BH-VIC-0005"] | true | true | true |

_17 row(s)_

## Element status sample (non-ok first)

```sql
SELECT element_id, element_type, region_code, state, n_impacted_cells, impacted_fraction, n_alarms,
               round(rca_score, 3) AS rca_score, open_incident_id, suspect_rank, last_updated_ts
        FROM telco_netmon_febar_catalog.netmon_rca.element_status ORDER BY state = 'ok', rca_score DESC NULLS LAST LIMIT 15
```

| element_id | element_type | region_code | state | n_impacted_cells | impacted_fraction | n_alarms | rca_score | open_incident_id | suspect_rank | last_updated_ts |
|---|---|---|---|---|---|---|---|---|---|---|
| CELL-NSW-00051-4G3 | CELL | NSW | down | 1.0 | 1.0 | 2.0 | 1.0 | RCA-55424701801c7330 | 1.0 | 2026-10-09T00:56:00.000Z |
| BH-NSW-0041 | BACKHAUL_LINK | NSW | degraded | 3.0 | 1.0 | 2.0 | 1.0 | RCA-ce4e7fd28bd45261 | 1.0 | 2026-10-09T00:56:00.000Z |
| CELL-NSW-00122-4G2 | CELL | NSW | down | 1.0 | 1.0 | 2.0 | 1.0 | RCA-c068ecb5f659c20d | 1.0 | 2026-10-09T00:56:00.000Z |
| CELL-NSW-00123-4G3 | CELL | NSW | degraded | 1.0 | 1.0 | 0.0 | 1.0 | RCA-60fe3d71c22893d5 | 1.0 | 2026-10-09T00:56:00.000Z |
| CELL-VIC-00022-5G3 | CELL | VIC | down | 1.0 | 1.0 | 1.0 | 1.0 | RCA-399fe9bb03f3b4cb | 1.0 | 2026-10-09T00:56:00.000Z |
| BH-NSW-0015 | BACKHAUL_LINK | NSW | degraded | 6.0 | 1.0 | 2.0 | 1.0 | RCA-cdc1224a2469350b | 1.0 | 2026-10-09T00:56:00.000Z |
| SITE-NSW-00105 | SITE | NSW | down | 3.0 | 1.0 | 2.0 | 1.0 | RCA-c7276c3238a27971 | 1.0 | 2026-10-09T00:56:00.000Z |
| SITE-NSW-00009 | SITE | NSW | down | 6.0 | 1.0 | 2.0 | 1.0 | RCA-fbd7ff66e62b0b42 | 1.0 | 2026-10-09T00:56:00.000Z |
| CELL-VIC-00090-4G3 | CELL | VIC | down | 1.0 | 1.0 | 1.0 | 1.0 | RCA-c69d3bab90ca811f | 1.0 | 2026-10-09T00:56:00.000Z |
| CELL-VIC-00107-5G1 | CELL | VIC | degraded | 1.0 | 1.0 | 0.0 | 1.0 | RCA-944a68e9bf7eff9b | 1.0 | 2026-10-09T00:56:00.000Z |
| CELL-VIC-00062-5G2 | CELL | VIC | degraded | 1.0 | 1.0 | 0.0 | 1.0 | RCA-1073d4d88aa7e05b | 1.0 | 2026-10-09T00:56:00.000Z |
| CELL-VIC-00033-4G2 | CELL | VIC | down | 1.0 | 1.0 | 1.0 | 1.0 | RCA-9eb236846361cdad | 1.0 | 2026-10-09T00:56:00.000Z |
| CELL-VIC-00005-4G2 | CELL | VIC | down | 1.0 | 1.0 | 2.0 | 1.0 | RCA-9737805189832cde | 1.0 | 2026-10-09T00:56:00.000Z |
| BH-VIC-0005 | BACKHAUL_LINK | VIC | degraded | 12.0 | 1.0 | 0.0 | 1.0 | RCA-27ed3e8af852d33a | 1.0 | 2026-10-09T00:56:00.000Z |
| BH-NSW-0013 | BACKHAUL_LINK | NSW | degraded | 9.0 | 1.0 | 0.0 | 1.0 | RCA-e909709b1c6a18fb | 1.0 | 2026-10-09T00:56:00.000Z |

_15 row(s)_

## Scored candidates appended per scoring run

```sql
SELECT model_version, count(*) AS rows, count(DISTINCT case_id) AS cases, min(decision_ts), max(decision_ts)
        FROM telco_netmon_febar_catalog.netmon_rca.rca_live_scores GROUP BY 1
```

| model_version | rows | cases | min(decision_ts) | max(decision_ts) |
|---|---|---|---|---|
| 1 | 11996 | 1104 | 2026-10-08T23:56:00.000Z | 2026-10-09T00:56:00.000Z |
| 2 | 11996 | 1104 | 2026-10-08T23:56:00.000Z | 2026-10-09T00:56:00.000Z |
| 4 | 10603 | 1104 | 2026-10-08T23:56:00.000Z | 2026-10-09T00:56:00.000Z |
| 3 | 10603 | 1104 | 2026-10-08T23:56:00.000Z | 2026-10-09T00:56:00.000Z |

_4 row(s)_
