# PR #6: replacement check (change calendar, superseded rows, duplicates)

Captured 2026-11-06 09:48 UTC from workspace profile `febar` by `scripts/capture_evidence_step3.py`.

The replacement swapped three feeds of `history_1m` and `holdout_1m`: alarms, the DQ log and the change calendar
(`maintenance_windows`, whose `change_id` hashes the run key). Every table derived from the calendar is a
materialized view recomputed from bronze (`silver_maintenance_windows`, then `gold_element_impact_5m` and the eval
views); no streaming table stores calendar rows. Streaming detections carry only the `in_maintenance` flag, and the
regenerated windows are identical to the old ones except `change_id` (verified file by file before the swap), so
the flag cannot change. Below: what the swap deleted, the counts now, and every check of
`netmon_pipeline.replace_check` (also the last task of `banksia-netmon-replace-run-feeds`, which fails on any
violation).

## BEFORE: rows deleted by the swap (job run 812068105574215, notebook output)

Superseded rows = every row ingested from a replaced file. Bronze maintenance before the swap held exactly these rows for the two runs (one calendar file each).

| run | table | deleted_rows |
|---|---|---|
| history_1m | bronze_alarms | 96599 |
| history_1m | bronze_gt_dq_injections | 310385 |
| history_1m | bronze_maintenance_windows | 101 |
| history_1m | silver_alarms | 95165 |
| history_1m | silver_quarantine | 864 |
| history_1m | gold_impact_detections | 15975 |
| history_1m | eval_detection_log | 15975 |
| holdout_1m | bronze_alarms | 29109 |
| holdout_1m | bronze_gt_dq_injections | 103376 |
| holdout_1m | bronze_maintenance_windows | 29 |
| holdout_1m | silver_alarms | 23321 |
| holdout_1m | silver_quarantine | 226 |
| holdout_1m | gold_impact_detections | 5739 |
| holdout_1m | eval_detection_log | 5739 |

_14 row(s)_

## BEFORE: files verified identical except IDs

| run | unchanged_files (byte-identical) | changed_files (identical without IDs) |
|---|---|---|
| history_1m | 55 | 33 |
| holdout_1m | 23 | 13 |

_2 row(s)_

## AFTER: change calendar per run, bronze

```sql
SELECT _source_run AS run, count(*) AS rows, count_if(_source_file RLIKE '-r2[.]json$') AS rows_from_new_files,
               count(DISTINCT change_id) AS change_ids, count(DISTINCT element_id, planned_start_ts, planned_end_ts) AS windows
        FROM telco_netmon_febar_catalog.netmon_bronze.bronze_maintenance_windows GROUP BY 1 ORDER BY 1
```

| run | rows | rows_from_new_files | change_ids | windows |
|---|---|---|---|---|
| history | 2 | 0 | 2 | 2 |
| history_1m | 101 | 101 | 101 | 101 |
| holdout_1m | 29 | 29 | 29 | 29 |

_3 row(s)_

## AFTER: change calendar per run, silver_maintenance_windows (materialized view)

rows = change_ids = windows: no duplicate window. `history` was not replaced.

```sql
SELECT source_run AS run, count(*) AS rows, count(DISTINCT change_id) AS change_ids,
               count(DISTINCT element_id, planned_start_ts, planned_end_ts) AS windows
        FROM telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows GROUP BY 1 ORDER BY 1
```

| run | rows | change_ids | windows |
|---|---|---|---|
| history | 2 | 2 | 2 |
| history_1m | 101 | 101 | 101 |
| holdout_1m | 29 | 29 | 29 |

_3 row(s)_

## AFTER: replacement checks (violations; all must be 0)

`legacy_change_ids` looks for the 124 pre-fix change IDs (`opaque_id("CHG", incident_id)`, computed from the ground-truth planned-maintenance incidents of both runs: 130 windows, but incident IDs repeat between runs, which is the original defect) in bronze and silver.

| check | history_1m | holdout_1m |
|---|---|---|
| superseded_rows_bronze_alarms | 0 | 0 |
| superseded_rows_bronze_gt_dq_injections | 0 | 0 |
| superseded_rows_bronze_maintenance_windows | 0 | 0 |
| superseded_rows_silver_alarms | 0 | 0 |
| superseded_rows_silver_quarantine_alarms | 0 | 0 |
| legacy_change_ids | 0 | 0 |
| duplicate_maintenance_windows | 0 | 0 |
| silver_vs_bronze_maintenance | 0 | 0 |
| duplicate_silver_alarm_ids | 0 | 0 |
| orphan_alarm_detections_gold_impact_detections | 0 | 0 |
| orphan_alarm_detections_eval_detection_log | 0 | 0 |
| fanout_unexplained_gold_impact_detections | 0 | 0 |

_12 row(s)_

## Repeated detection rows (informational, pre-existing)

Repeated `detection_id`s are not a replacement artefact: `fanout_unexplained_gold_impact_detections` = 0 above means every repeated detection matches exactly that many change windows (e.g. its site's and its router's overlapping windows), because the in-maintenance flag is a join. The KPI rows (never touched by the replacement, written 2026-11-05) repeat the same way. Recorded as a known limit.

```sql
SELECT source_run, signal_source, count(*) AS rows, count(DISTINCT detection_id) AS distinct_detections,
               count(*) - count(DISTINCT detection_id) AS repeated_rows
        FROM `telco_netmon_febar_catalog`.netmon_gold.gold_impact_detections WHERE source_run IN ('history_1m', 'holdout_1m') GROUP BY 1, 2 ORDER BY 1, 2
```

| source_run | signal_source | rows | distinct_detections | repeated_rows |
|---|---|---|---|---|
| history_1m | alarm | 15987 | 15968 | 19 |
| history_1m | kpi | 1632418 | 1631851 | 567 |
| holdout_1m | alarm | 7074 | 7030 | 44 |
| holdout_1m | kpi | 613191 | 611094 | 2097 |

_4 row(s)_
