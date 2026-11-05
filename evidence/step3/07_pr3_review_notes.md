# PR #3 review notes folded in

Captured 2026-11-05 16:34 UTC from workspace profile `febar` by `scripts/capture_evidence_step3.py`.

## a. Python late-data rule tied to the Spark transform

`tests/test_pipeline_windows_spark.py` runs, on a local SparkSession, the functions the pipeline itself calls:
`windows.is_late_sql` (silver `is_late`, kpis / alarms / sessions), `windows.realtime_records` and
`windows.window_health` (gold `gold_cell_health_1m` / `_5m`). It checks per record that `rules.is_late_py`
equals the Spark `is_late`, and per window that `windows.realtime_window` (the Python mirror) gives the same
report count, qualification and observable time as the Spark window, including the threshold edge
(exactly 20 min late is on time, 20 min + 1 s is late). A second test asserts gold.py / silver.py call these
shared functions and contain no private copy of the rule.

## b. Real (signed) evidence lag: alarms that arrive before the impact starts

`eval_incident_detection` now carries `signed_evidence_lag_s` (negative when the first matching evidence predates `impact_start_ts`) and `evidence_before_impact`; the clipped `evidence_lag_s` is unchanged. Router failures raise NODE_DOWN before their cells lose service, hence the negative lags.

```sql
SELECT source_run, fault_type, n_incidents, median_evidence_lag_s, median_signed_evidence_lag_s,
               min_signed_evidence_lag_s, n_evidence_before_impact
        FROM telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary WHERE event_class = 'fault' AND fault_type <> 'ALL' ORDER BY 1, 2
```

| source_run | fault_type | n_incidents | median_evidence_lag_s | median_signed_evidence_lag_s | min_signed_evidence_lag_s | n_evidence_before_impact |
|---|---|---|---|---|---|---|
| history | AGG_ROUTER_FAILURE | 2 | 0.0 | -48.5 | -52 | 2 |
| history | AMF_OVERLOAD | 1 | 390.0 | 390.0 | 390 | 0 |
| history | BACKHAUL_DEGRADATION | 1 | 1724.0 | 1724.0 | 1724 | 0 |
| history | BUSHFIRE_GRID_OUTAGE | 1 | 172.0 | 172.0 | 172 | 0 |
| history | CELL_OUTAGE | 6 | 56.5 | 56.5 | 28 | 0 |
| history | CORE_CONGESTION | 2 | 1067.0 | 2134.0 | 2134 | 0 |
| history | CYCLONE_BACKHAUL_CUT | 1 | 0.0 | -22.0 | -22 | 1 |
| history | LONG_HAUL_FIBRE_CUT | 1 | 178.0 | 178.0 | 178 | 0 |
| history | SITE_POWER_OUTAGE | 1 | 75.0 | 75.0 | 75 | 0 |
| history_1m | AGG_ROUTER_FAILURE | 93 | 0.0 | -44.0 | -56 | 93 |
| history_1m | AMF_OVERLOAD | 52 | 112.0 | 112.0 | 21 | 0 |
| history_1m | BACKHAUL_DEGRADATION | 158 | 509.5 | 517.0 | 138 | 0 |
| history_1m | BUSHFIRE_GRID_OUTAGE | 1 | 43.0 | 43.0 | 43 | 0 |
| history_1m | CELL_OUTAGE | 552 | 35.0 | 35.0 | 7 | 0 |
| history_1m | CORE_CONGESTION | 2 | 349.0 | 349.0 | 306 | 0 |
| history_1m | LONG_HAUL_FIBRE_CUT | 2 | 58.0 | 58.0 | 40 | 0 |
| history_1m | SITE_POWER_OUTAGE | 122 | 40.0 | 42.0 | 8 | 0 |
| stream | AGG_ROUTER_FAILURE | 1 | 0.0 | -34.0 | -34 | 1 |
| stream | BACKHAUL_DEGRADATION | 3 | 746.0 | 746.0 | 507 | 0 |
| stream | CELL_OUTAGE | 20 | 80.0 | 80.0 | 30 | 0 |
| stream | SITE_POWER_OUTAGE | 2 | 197.5 | 197.5 | 165 | 0 |

_21 row(s)_

## b. Incidents whose first evidence predates impact (sample)

```sql
SELECT source_run, incident_id, fault_type, first_signal_source, first_flags, signed_evidence_lag_s,
               evidence_lag_s, impact_ttd_s
        FROM telco_netmon_febar_catalog.netmon_eval.eval_incident_detection WHERE evidence_before_impact ORDER BY signed_evidence_lag_s LIMIT 10
```

| source_run | incident_id | fault_type | first_signal_source | first_flags | signed_evidence_lag_s | evidence_lag_s | impact_ttd_s |
|---|---|---|---|---|---|---|---|
| history_1m | INC-00433 | AGG_ROUTER_FAILURE | alarm | ["LINK_DOWN"] | -56 | 0 | 0.000000 |
| history_1m | INC-00694 | AGG_ROUTER_FAILURE | alarm | ["LINK_DOWN"] | -55 | 0 | 0.000000 |
| history_1m | INC-00662 | AGG_ROUTER_FAILURE | alarm | ["LINK_DOWN"] | -55 | 0 | 0.000000 |
| history_1m | INC-01088 | AGG_ROUTER_FAILURE | alarm | ["LINK_DOWN"] | -55 | 0 | 0.000000 |
| history_1m | INC-00444 | AGG_ROUTER_FAILURE | alarm | ["LINK_DOWN"] | -54 | 0 | 0.000000 |
| history_1m | INC-01107 | AGG_ROUTER_FAILURE | alarm | ["LINK_DOWN"] | -54 | 0 | 0.000000 |
| history_1m | INC-00349 | AGG_ROUTER_FAILURE | alarm | ["LINK_DOWN"] | -54 | 0 | 0.000000 |
| history_1m | INC-01175 | AGG_ROUTER_FAILURE | alarm | ["LINK_DOWN"] | -54 | 0 | 0.000000 |
| history_1m | INC-00748 | AGG_ROUTER_FAILURE | alarm | ["LINK_DOWN"] | -53 | 0 | 0.000000 |
| history_1m | INC-00165 | AGG_ROUTER_FAILURE | alarm | ["LINK_DOWN"] | -53 | 0 | 0.000000 |

_10 row(s)_

## c. One baseline-comparison code path

`windows.score_against_baseline(kpis, baseline)` (join the record's baseline row, add z-scores and the fired
rules) is used by both the real-time stream (`kpis_scored` -> `gold_cell_health_1m` / `_5m`) and the
after-the-fact `gold_cell_health_5m_retrospective`, which also share `windows.window_health`. The test above
asserts both call sites.
