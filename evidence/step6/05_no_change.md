# Step 6: nothing existing changed

Generated 2026-11-07 02:19 UTC by `scripts/collective_backhaul_experiment.py`.

Checks after the three readings. `since` = 2026-11-07T00:00:00Z (before this step's first query).

## Tables / views in the netmon_* schemas altered since the step began

```sql
SELECT table_schema, table_name, table_type, last_altered FROM telco_netmon_febar_catalog.information_schema.tables WHERE table_schema LIKE 'netmon%' AND last_altered >= '2026-11-07T00:00:00Z' ORDER BY 1, 2
```

| table_schema | table_name | table_type | last_altered |
|---|---|---|---|
| netmon_eval | eval_collective_backhaul_experiment | MANAGED | 2026-11-07 01:39:47.497000+00:00 |

_1 row(s)_


## Published step-2 BACKHAUL_DEGRADATION figures (eval_ttd_summary), unchanged

```sql
SELECT source_run, n_incidents, impact_median_ttd_s, impact_p90_ttd_s, impact_within_5min_pct, median_evidence_lag_s FROM telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary WHERE fault_type = 'BACKHAUL_DEGRADATION' ORDER BY 1
```

| source_run | n_incidents | impact_median_ttd_s | impact_p90_ttd_s | impact_within_5min_pct | median_evidence_lag_s |
|---|---|---|---|---|---|
| history | 1 | 1724.0 | 1724.0 | 0.0 | 1724.0 |
| history_1m | 158 | 509.5 | 895.8 | 5.1 | 509.5 |
| holdout_1m | 53 | 559.0 | 807.6 | 7.5 | 559.0 |
| stream | 3 | 807.9 | 826.5 | 0.0 | 746.0 |

_4 row(s)_


## Experiment table: one row set per reading, all from the frozen rule

```sql
SELECT reading, freeze_sha, count(*) AS n_detections, count(DISTINCT detection_id) AS n_ids, min(scored_at) AS first_scored, max(scored_at) AS last_scored FROM telco_netmon_febar_catalog.netmon_eval.eval_collective_backhaul_experiment GROUP BY 1, 2 ORDER BY 1
```

| reading | freeze_sha | n_detections | n_ids | first_scored | last_scored |
|---|---|---|---|---|---|
| dev | e866511994f49fcf0084c994228221f6eb52af9a | 5495 | 5495 | 2026-11-07 02:12:11.409948+00:00 | 2026-11-07 02:12:11.409948+00:00 |
| holdout | e866511994f49fcf0084c994228221f6eb52af9a | 5421 | 5421 | 2026-11-07 01:49:18.197465+00:00 | 2026-11-07 01:49:18.197465+00:00 |
| stream | e866511994f49fcf0084c994228221f6eb52af9a | 532 | 532 | 2026-11-07 02:08:12.662759+00:00 | 2026-11-07 02:08:12.662759+00:00 |

_3 row(s)_


## Experiment table history (every write; the holdout was written once)

```sql
SELECT version, timestamp, operation, operationMetrics.numOutputRows AS rows_written, operationMetrics.numDeletedRows AS rows_deleted, operationMetrics.numTargetRowsInserted AS rows_merged, operationParameters.predicate AS predicate FROM (DESCRIBE HISTORY telco_netmon_febar_catalog.netmon_eval.eval_collective_backhaul_experiment) ORDER BY version
```

| version | timestamp | operation | rows_written | rows_deleted | rows_merged | predicate |
|---|---|---|---|---|---|---|
| 0 | 2026-11-07 01:39:47+00:00 | CREATE TABLE AS SELECT | 0 | NULL | NULL | NULL |
| 1 | 2026-11-07 01:39:57+00:00 | WRITE | 5495 | NULL | NULL | NULL |
| 2 | 2026-11-07 01:44:10+00:00 | DELETE | NULL | 5495 | NULL | ["(reading#31982 = dev)"] |
| 3 | 2026-11-07 01:44:16+00:00 | WRITE | 5495 | NULL | NULL | NULL |
| 4 | 2026-11-07 01:47:12+00:00 | WRITE | 532 | NULL | NULL | NULL |
| 5 | 2026-11-07 01:49:22+00:00 | WRITE | 5421 | NULL | NULL | NULL |
| 6 | 2026-11-07 02:04:42+00:00 | DELETE | NULL | 5495 | NULL | ["(reading#57272 = dev)"] |
| 7 | 2026-11-07 02:04:48+00:00 | WRITE | 5495 | NULL | NULL | NULL |
| 8 | 2026-11-07 02:04:51+00:00 | WRITE | 5495 | NULL | NULL | NULL |
| 9 | 2026-11-07 02:08:11+00:00 | DELETE | NULL | 532 | NULL | ["(reading#68420 = stream)"] |
| 10 | 2026-11-07 02:08:15+00:00 | WRITE | 532 | NULL | NULL | NULL |
| 11 | 2026-11-07 02:12:10+00:00 | DELETE | NULL | 10990 | NULL | ["(reading#74639 = dev)"] |
| 12 | 2026-11-07 02:12:16+00:00 | MERGE | 5495 | NULL | 5495 | ["((reading#75157 = reading#75041) AND (detection_id#75161 = detection_id#74994))"] |

_13 row(s)_

