# PR #6: run-unique alarm IDs, re-ingest, retrain and one holdout re-score

Captured 2026-11-06 08:04 UTC from workspace profile `febar` by `scripts/capture_evidence_step3.py`.

**Defect** (found in step 4, `evidence/step4/09_holdout_alarm_gap.md`): incident alarm IDs hashed only the per-run
incident ID (`INC-00001`, ...), so a later batch run reused an earlier run's alarm IDs and silver's cross-run dedupe
on `record_id` dropped them. **Fix**: alarm and change IDs hash a run key (`docs/data_model.md`, "IDs across runs").
`history_1m` and `holdout_1m` were regenerated with the same seeds and windows (`run_id` = run name). The
regeneration was verified to differ from the ingested files **only in IDs** (KPIs, sessions, topology and incident
ground truth byte-identical; alarms, DQ log and change calendar identical without `record_id` / `alarm_id` /
`change_id`), and the three changed feeds were swapped in by `banksia-netmon-replace-run-feeds`
(`notebooks/12_replace_run_feeds.py`; no full refresh, step-2 `history` / `stream` untouched).

**Retraining decision.** The training data was affected: `history_1m` had lost 90 alarm IDs, 89 of them on
2026-10-10, the first **train** day (to the step-2 `history` run's IDs). The contract says: if training data was
affected, retrain. The model was retrained once with the **frozen design** (same code, features, hyperparameters,
split dates and threshold rule; job `banksia-rca-train` with its defaults): old champion v4 (MLflow run
`e40edbe6f9884c23ad9313f4e41f2845`, threshold 0.32) -> new champion v5 (MLflow run
`24cf7981a0304b0f8e51eb7b0a2943fc`, threshold 0.27). The holdout was then re-scored **once** with the same
evaluation code (`banksia-rca-evaluate-holdout`, then `banksia-rca-any-alert-metric`): old evaluation v4
run `b678bdd4d2c84591bdc4e1bfec61d5c2`, new evaluation v5 run `d58a5f8893df4d37b7835be9877811df`. Old numbers are the `*_pr5` snapshots
taken before anything was changed. Both the model and the data changed between old and new, so the holdout
difference is not attributable to either alone; the dev and validation rows show the model change on unchanged data
(dev days lost no alarms).

## Alarms per run BEFORE the fix (snapshot netmon_eval.alarm_counts_pr5)

`removed_by_dedupe` = bronze rows - silver rows - quarantined rows. It should equal `injected_duplicates`. `missing_ids_held_by_other_run` = distinct IDs of the run absent from silver (and not quarantined) whose ID is in silver under another run.

```sql
SELECT * FROM telco_netmon_febar_catalog.netmon_eval.alarm_counts_pr5 ORDER BY run
```

| run | bronze_rows | bronze_distinct_ids | injected_duplicates | quarantined_rows | silver_rows | silver_distinct_ids | removed_by_dedupe | distinct_ids_missing_from_silver | missing_ids_held_by_other_run |
|---|---|---|---|---|---|---|---|---|---|
| history | 16730 | 16626 | 85 | 151 | 16494 | 16494 | 85 | 0 | 0 |
| history_1m | 96599 | 96024 | 480 | 864 | 95165 | 95165 | 570 | 90 | 89 |
| holdout_1m | 29109 | 28933 | 145 | 226 | 23321 | 23321 | 5562 | 5417 | 5380 |
| stream | 3154 | 3132 | 18 | 30 | 3106 | 3106 | 18 | 0 | 0 |

_4 row(s)_

## Alarms per run AFTER the fix (same query, live)

Every run: `removed_by_dedupe` = `injected_duplicates`, nothing missing. Only the intended DQ duplicates are removed. (Quarantine counts rise slightly: rows that were dropped by the dedupe before their expectations ran now reach the quarantine.)

```sql
WITH b AS (SELECT _source_run run, count(*) bronze_rows, count(DISTINCT record_id) bronze_distinct_ids FROM telco_netmon_febar_catalog.netmon_bronze.bronze_alarms GROUP BY 1),
bid AS (SELECT DISTINCT _source_run run, record_id FROM telco_netmon_febar_catalog.netmon_bronze.bronze_alarms WHERE record_id IS NOT NULL),
s AS (SELECT source_run run, count(*) silver_rows, count(DISTINCT record_id) silver_distinct_ids FROM telco_netmon_febar_catalog.netmon_silver.silver_alarms GROUP BY 1),
sid AS (SELECT DISTINCT source_run run, record_id FROM telco_netmon_febar_catalog.netmon_silver.silver_alarms),
q AS (SELECT DISTINCT _source_run run, record_id FROM telco_netmon_febar_catalog.netmon_silver.silver_quarantine WHERE feed = 'alarms' AND record_id IS NOT NULL),
qn AS (SELECT _source_run run, count(*) quarantined_rows FROM telco_netmon_febar_catalog.netmon_silver.silver_quarantine WHERE feed = 'alarms' GROUP BY 1),
dup AS (SELECT _source_run run, count(*) injected_duplicates FROM telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections WHERE feed = 'alarms' AND defect_type = 'duplicate' GROUP BY 1),
miss AS (SELECT m.run, m.record_id, EXISTS (SELECT 1 FROM sid o WHERE o.record_id = m.record_id AND o.run <> m.run) AS in_other_run
         FROM (SELECT * FROM bid LEFT ANTI JOIN sid USING (run, record_id) LEFT ANTI JOIN q USING (run, record_id)) m),
mc AS (SELECT run, count(*) missing_ids, count_if(in_other_run) missing_ids_held_by_other_run FROM miss GROUP BY 1)
SELECT b.run, b.bronze_rows, b.bronze_distinct_ids, coalesce(dup.injected_duplicates, 0) injected_duplicates,
       coalesce(qn.quarantined_rows, 0) quarantined_rows, s.silver_rows, s.silver_distinct_ids,
       b.bronze_rows - s.silver_rows - coalesce(qn.quarantined_rows, 0) AS removed_by_dedupe,
       coalesce(mc.missing_ids, 0) distinct_ids_missing_from_silver, coalesce(mc.missing_ids_held_by_other_run, 0) missing_ids_held_by_other_run
FROM b LEFT JOIN s USING (run) LEFT JOIN qn USING (run) LEFT JOIN dup USING (run) LEFT JOIN mc USING (run)
 ORDER BY run
```

| run | bronze_rows | bronze_distinct_ids | injected_duplicates | quarantined_rows | silver_rows | silver_distinct_ids | removed_by_dedupe | distinct_ids_missing_from_silver | missing_ids_held_by_other_run |
|---|---|---|---|---|---|---|---|---|---|
| history | 16730 | 16626 | 85 | 151 | 16494 | 16494 | 85 | 0 | 0 |
| history_1m | 96599 | 96024 | 480 | 865 | 95254 | 95254 | 480 | 0 | 0 |
| holdout_1m | 29109 | 28933 | 145 | 259 | 28705 | 28705 | 145 | 0 | 0 |
| stream | 3154 | 3132 | 18 | 30 | 3106 | 3106 | 18 | 0 | 0 |

_4 row(s)_

## Before vs after, side by side

```sql
SELECT n.run, o.silver_rows AS silver_before, n.silver_rows AS silver_after, n.silver_rows - o.silver_rows AS gained,
               o.removed_by_dedupe AS dedupe_removed_before, n.removed_by_dedupe AS dedupe_removed_after,
               n.injected_duplicates, o.distinct_ids_missing_from_silver AS missing_before,
               n.distinct_ids_missing_from_silver AS missing_after
        FROM (
WITH b AS (SELECT _source_run run, count(*) bronze_rows, count(DISTINCT record_id) bronze_distinct_ids FROM telco_netmon_febar_catalog.netmon_bronze.bronze_alarms GROUP BY 1),
bid AS (SELECT DISTINCT _source_run run, record_id FROM telco_netmon_febar_catalog.netmon_bronze.bronze_alarms WHERE record_id IS NOT NULL),
s AS (SELECT source_run run, count(*) silver_rows, count(DISTINCT record_id) silver_distinct_ids FROM telco_netmon_febar_catalog.netmon_silver.silver_alarms GROUP BY 1),
sid AS (SELECT DISTINCT source_run run, record_id FROM telco_netmon_febar_catalog.netmon_silver.silver_alarms),
q AS (SELECT DISTINCT _source_run run, record_id FROM telco_netmon_febar_catalog.netmon_silver.silver_quarantine WHERE feed = 'alarms' AND record_id IS NOT NULL),
qn AS (SELECT _source_run run, count(*) quarantined_rows FROM telco_netmon_febar_catalog.netmon_silver.silver_quarantine WHERE feed = 'alarms' GROUP BY 1),
dup AS (SELECT _source_run run, count(*) injected_duplicates FROM telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections WHERE feed = 'alarms' AND defect_type = 'duplicate' GROUP BY 1),
miss AS (SELECT m.run, m.record_id, EXISTS (SELECT 1 FROM sid o WHERE o.record_id = m.record_id AND o.run <> m.run) AS in_other_run
         FROM (SELECT * FROM bid LEFT ANTI JOIN sid USING (run, record_id) LEFT ANTI JOIN q USING (run, record_id)) m),
mc AS (SELECT run, count(*) missing_ids, count_if(in_other_run) missing_ids_held_by_other_run FROM miss GROUP BY 1)
SELECT b.run, b.bronze_rows, b.bronze_distinct_ids, coalesce(dup.injected_duplicates, 0) injected_duplicates,
       coalesce(qn.quarantined_rows, 0) quarantined_rows, s.silver_rows, s.silver_distinct_ids,
       b.bronze_rows - s.silver_rows - coalesce(qn.quarantined_rows, 0) AS removed_by_dedupe,
       coalesce(mc.missing_ids, 0) distinct_ids_missing_from_silver, coalesce(mc.missing_ids_held_by_other_run, 0) missing_ids_held_by_other_run
FROM b LEFT JOIN s USING (run) LEFT JOIN qn USING (run) LEFT JOIN dup USING (run) LEFT JOIN mc USING (run)
) n JOIN telco_netmon_febar_catalog.netmon_eval.alarm_counts_pr5 o USING (run) ORDER BY n.run
```

| run | silver_before | silver_after | gained | dedupe_removed_before | dedupe_removed_after | injected_duplicates | missing_before | missing_after |
|---|---|---|---|---|---|---|---|---|
| history | 16494 | 16494 | 0 | 85 | 85 | 85 | 0 | 0 |
| history_1m | 95165 | 95254 | 89 | 570 | 480 | 480 | 90 | 0 |
| holdout_1m | 23321 | 28705 | 5384 | 5562 | 145 | 145 | 5417 | 0 |
| stream | 3106 | 3106 | 0 | 18 | 18 | 18 | 0 | 0 |

_4 row(s)_

## HOLDOUT (holdout_1m): top-1 / top-3 old vs new

`baseline_top1_pct` = step 2's region-wide `eval_rca_baseline` on the same incidents.

```sql
SELECT coalesce(n.fault_type, o.fault_type) AS fault_type, o.n AS old_n, n.n AS new_n, o.model_top1_pct AS old_model_top1_pct, n.model_top1_pct AS new_model_top1_pct, o.heuristic_same_cases_top1_pct AS old_heuristic_same_cases_top1_pct, n.heuristic_same_cases_top1_pct AS new_heuristic_same_cases_top1_pct, o.model_top3_pct AS old_model_top3_pct, n.model_top3_pct AS new_model_top3_pct, o.baseline_top1_pct AS old_baseline_top1_pct, n.baseline_top1_pct AS new_baseline_top1_pct FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_holdout_accuracy_pr5 o FULL OUTER JOIN telco_netmon_febar_catalog.netmon_rca.rca_eval_holdout_accuracy n ON n.fault_type = o.fault_type ORDER BY fault_type = 'ALL' DESC, new_n DESC
```

| fault_type | old_n | new_n | old_model_top1_pct | new_model_top1_pct | old_heuristic_same_cases_top1_pct | new_heuristic_same_cases_top1_pct | old_model_top3_pct | new_model_top3_pct | old_baseline_top1_pct | new_baseline_top1_pct |
|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 337.0 | 337.0 | 93.2 | 94.7 | 78.3 | 78.3 | 95.3 | 95.5 | 27.9 | 27.9 |
| CELL_OUTAGE | 187.0 | 187.0 | 95.2 | 95.7 | 94.7 | 94.7 | 96.3 | 96.3 | 7.0 | 7.0 |
| BACKHAUL_DEGRADATION | 53.0 | 53.0 | 86.8 | 86.8 | 3.8 | 3.8 | 86.8 | 86.8 | 41.5 | 41.5 |
| AGG_ROUTER_FAILURE | 40.0 | 40.0 | 87.5 | 95.0 | 87.5 | 87.5 | 95.0 | 97.5 | 82.5 | 82.5 |
| SITE_POWER_OUTAGE | 38.0 | 38.0 | 97.4 | 100.0 | 84.2 | 84.2 | 100.0 | 100.0 | 23.7 | 23.7 |
| AMF_OVERLOAD | 17.0 | 17.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| BUSHFIRE_GRID_OUTAGE | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 100.0 | 100.0 | 0.0 | 0.0 |
| LONG_HAUL_FIBRE_CUT | 1.0 | 1.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 0.0 |

_8 row(s)_

## HOLDOUT (holdout_1m): non-oracle any-alert metric old vs new

```sql
SELECT coalesce(n.fault_type, o.fault_type) AS fault_type, o.n AS old_n, n.n AS new_n, o.any_alert_correct_pct AS old_any_alert_correct_pct, n.any_alert_correct_pct AS new_any_alert_correct_pct, o.matched_top1_pct AS old_matched_top1_pct, n.matched_top1_pct AS new_matched_top1_pct, o.median_region_alerts AS old_median_region_alerts, n.median_region_alerts AS new_median_region_alerts FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_holdout_any_alert_summary_pr5 o FULL OUTER JOIN telco_netmon_febar_catalog.netmon_rca.rca_eval_holdout_any_alert_summary n ON n.fault_type = o.fault_type ORDER BY fault_type = 'ALL' DESC, new_n DESC
```

| fault_type | old_n | new_n | old_any_alert_correct_pct | new_any_alert_correct_pct | old_matched_top1_pct | new_matched_top1_pct | old_median_region_alerts | new_median_region_alerts |
|---|---|---|---|---|---|---|---|---|
| ALL | 337 | 337 | 81.0 | 82.5 | 93.2 | 94.7 | 5.0 | 5.0 |
| CELL_OUTAGE | 187 | 187 | 95.2 | 95.7 | 95.2 | 95.7 | 5.0 | 5.0 |
| BACKHAUL_DEGRADATION | 53 | 53 | 9.4 | 9.4 | 86.8 | 86.8 | 5.0 | 5.0 |
| AGG_ROUTER_FAILURE | 40 | 40 | 87.5 | 95.0 | 87.5 | 95.0 | 3.0 | 3.0 |
| SITE_POWER_OUTAGE | 38 | 38 | 97.4 | 100.0 | 97.4 | 100.0 | 5.0 | 5.0 |
| AMF_OVERLOAD | 17 | 17 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 1.0 |
| BUSHFIRE_GRID_OUTAGE | 1 | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 5.0 | 5.0 |
| LONG_HAUL_FIBRE_CUT | 1 | 1 | 100.0 | 100.0 | 100.0 | 100.0 | 5.0 | 5.0 |

_8 row(s)_

## HOLDOUT (holdout_1m): early catch old vs new (signed seconds; step-2 localisation on the same incidents)

```sql
SELECT coalesce(n.fault_type, o.fault_type) AS fault_type, o.n AS old_n, n.n AS new_n, o.model_within_5min_pct AS old_model_within_5min_pct, n.model_within_5min_pct AS new_model_within_5min_pct, o.model_median_signed_s AS old_model_median_signed_s, n.model_median_signed_s AS new_model_median_signed_s, o.heuristic_same_cases_within_5min_pct AS old_heuristic_same_cases_within_5min_pct, n.heuristic_same_cases_within_5min_pct AS new_heuristic_same_cases_within_5min_pct, o.step2_within_5min_pct AS old_step2_within_5min_pct, n.step2_within_5min_pct AS new_step2_within_5min_pct, o.step2_median_s AS old_step2_median_s, n.step2_median_s AS new_step2_median_s FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_holdout_early_catch_summary_pr5 o FULL OUTER JOIN telco_netmon_febar_catalog.netmon_rca.rca_eval_holdout_early_catch_summary n ON n.fault_type = o.fault_type ORDER BY fault_type = 'ALL' DESC, new_n DESC
```

| fault_type | old_n | new_n | old_model_within_5min_pct | new_model_within_5min_pct | old_model_median_signed_s | new_model_median_signed_s | old_heuristic_same_cases_within_5min_pct | new_heuristic_same_cases_within_5min_pct | old_step2_within_5min_pct | new_step2_within_5min_pct | old_step2_median_s | new_step2_median_s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 337 | 337 | 80.4 | 80.7 | 106.0 | 92.5 | 76.9 | 78.3 | 65.6 | 78.6 | 76.0 | 46.0 |
| CELL_OUTAGE | 187 | 187 | 94.7 | 94.7 | 98.5 | 88.5 | 93.6 | 93.6 | 100.0 | 100.0 | 51.0 | 35.0 |
| BACKHAUL_DEGRADATION | 53 | 53 | 0.0 | 0.0 | 615.0 | 619.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1011.0 | 1011.0 |
| AGG_ROUTER_FAILURE | 40 | 40 | 97.5 | 97.5 | -12.0 | -13.5 | 85.0 | 97.5 | 30.0 | 100.0 | 392.5 | 2.0 |
| SITE_POWER_OUTAGE | 38 | 38 | 97.4 | 100.0 | 156.0 | 150.0 | 84.2 | 84.2 | 57.9 | 97.4 | 195.0 | 130.5 |
| AMF_OVERLOAD | 17 | 17 | 100.0 | 100.0 | -113.0 | -113.0 | 100.0 | 100.0 | 0.0 | 0.0 | 514.0 | 514.0 |
| BUSHFIRE_GRID_OUTAGE | 1 | 1 | 0.0 | 0.0 | 759.0 | 1419.0 | 0.0 | 0.0 | 0.0 | 0.0 | 8010.0 | 8010.0 |
| LONG_HAUL_FIBRE_CUT | 1 | 1 | 100.0 | 100.0 | 236.0 | 116.0 | 100.0 | 100.0 | 0.0 | 100.0 | 416.0 | 69.0 |

_8 row(s)_

## HOLDOUT (holdout_1m): alert-level fault precision old vs new

```sql
SELECT coalesce(n.system, o.system) AS system, o.n_alerts AS old_n_alerts, n.n_alerts AS new_n_alerts, o.fault AS old_fault, n.fault AS new_fault, o.unexplained AS old_unexplained, n.unexplained AS new_unexplained, o.fault_precision_pct AS old_fault_precision_pct, n.fault_precision_pct AS new_fault_precision_pct FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_holdout_alert_precision_pr5 o FULL OUTER JOIN telco_netmon_febar_catalog.netmon_rca.rca_eval_holdout_alert_precision n ON n.system = o.system ORDER BY system
```

| system | old_n_alerts | new_n_alerts | old_fault | new_fault | old_unexplained | new_unexplained | old_fault_precision_pct | new_fault_precision_pct |
|---|---|---|---|---|---|---|---|---|
| rca_model (top-1 >= threshold) | 395 | 377 | 353 | 353 | 29 | 18 | 92.4 | 95.1 |
| step2 detections | 14028 | 14342 | 12600 | 12885 | 309 | 309 | 97.6 | 97.7 |

_2 row(s)_

## DEV (history_1m 10-14 … 10-15): top-1 / top-3 old vs new

`baseline_top1_pct` = step 2's region-wide `eval_rca_baseline` on the same incidents.

```sql
SELECT coalesce(n.fault_type, o.fault_type) AS fault_type, o.n AS old_n, n.n AS new_n, o.model_top1_pct AS old_model_top1_pct, n.model_top1_pct AS new_model_top1_pct, o.heuristic_same_cases_top1_pct AS old_heuristic_same_cases_top1_pct, n.heuristic_same_cases_top1_pct AS new_heuristic_same_cases_top1_pct, o.model_top3_pct AS old_model_top3_pct, n.model_top3_pct AS new_model_top3_pct, o.baseline_top1_pct AS old_baseline_top1_pct, n.baseline_top1_pct AS new_baseline_top1_pct FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_dev_accuracy_pr5 o FULL OUTER JOIN telco_netmon_febar_catalog.netmon_rca.rca_eval_dev_accuracy n ON n.fault_type = o.fault_type ORDER BY fault_type = 'ALL' DESC, new_n DESC
```

| fault_type | old_n | new_n | old_model_top1_pct | new_model_top1_pct | old_heuristic_same_cases_top1_pct | new_heuristic_same_cases_top1_pct | old_model_top3_pct | new_model_top3_pct | old_baseline_top1_pct | new_baseline_top1_pct |
|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 355.0 | 355.0 | 94.1 | 94.1 | 80.8 | 80.8 | 96.6 | 96.3 | 23.4 | 23.4 |
| CELL_OUTAGE | 205.0 | 205.0 | 97.1 | 97.1 | 96.6 | 96.6 | 100.0 | 99.5 | 5.4 | 5.4 |
| BACKHAUL_DEGRADATION | 55.0 | 55.0 | 78.2 | 78.2 | 5.5 | 5.5 | 78.2 | 78.2 | 34.5 | 34.5 |
| SITE_POWER_OUTAGE | 46.0 | 46.0 | 97.8 | 97.8 | 82.6 | 82.6 | 100.0 | 100.0 | 21.7 | 21.7 |
| AGG_ROUTER_FAILURE | 30.0 | 30.0 | 93.3 | 93.3 | 96.7 | 96.7 | 100.0 | 100.0 | 83.3 | 83.3 |
| AMF_OVERLOAD | 18.0 | 18.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| LONG_HAUL_FIBRE_CUT | 1.0 | 1.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 0.0 |

_7 row(s)_

## DEV (history_1m 10-14 … 10-15): non-oracle any-alert metric old vs new

```sql
SELECT coalesce(n.fault_type, o.fault_type) AS fault_type, o.n AS old_n, n.n AS new_n, o.any_alert_correct_pct AS old_any_alert_correct_pct, n.any_alert_correct_pct AS new_any_alert_correct_pct, o.matched_top1_pct AS old_matched_top1_pct, n.matched_top1_pct AS new_matched_top1_pct, o.median_region_alerts AS old_median_region_alerts, n.median_region_alerts AS new_median_region_alerts FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_dev_any_alert_summary_pr5 o FULL OUTER JOIN telco_netmon_febar_catalog.netmon_rca.rca_eval_dev_any_alert_summary n ON n.fault_type = o.fault_type ORDER BY fault_type = 'ALL' DESC, new_n DESC
```

| fault_type | old_n | new_n | old_any_alert_correct_pct | new_any_alert_correct_pct | old_matched_top1_pct | new_matched_top1_pct | old_median_region_alerts | new_median_region_alerts |
|---|---|---|---|---|---|---|---|---|
| ALL | 355 | 355 | 83.9 | 83.9 | 94.1 | 94.1 | 6.0 | 6.0 |
| CELL_OUTAGE | 205 | 205 | 97.1 | 97.1 | 97.1 | 97.1 | 7.0 | 7.0 |
| BACKHAUL_DEGRADATION | 55 | 55 | 12.7 | 12.7 | 78.2 | 78.2 | 5.0 | 5.0 |
| SITE_POWER_OUTAGE | 46 | 46 | 97.8 | 97.8 | 97.8 | 97.8 | 6.0 | 6.0 |
| AGG_ROUTER_FAILURE | 30 | 30 | 93.3 | 93.3 | 93.3 | 93.3 | 2.0 | 2.0 |
| AMF_OVERLOAD | 18 | 18 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 1.0 |
| LONG_HAUL_FIBRE_CUT | 1 | 1 | 100.0 | 100.0 | 100.0 | 100.0 | 2.0 | 2.0 |

_7 row(s)_

## DEV (history_1m 10-14 … 10-15): early catch old vs new (signed seconds; step-2 localisation on the same incidents)

```sql
SELECT coalesce(n.fault_type, o.fault_type) AS fault_type, o.n AS old_n, n.n AS new_n, o.model_within_5min_pct AS old_model_within_5min_pct, n.model_within_5min_pct AS new_model_within_5min_pct, o.model_median_signed_s AS old_model_median_signed_s, n.model_median_signed_s AS new_model_median_signed_s, o.heuristic_same_cases_within_5min_pct AS old_heuristic_same_cases_within_5min_pct, n.heuristic_same_cases_within_5min_pct AS new_heuristic_same_cases_within_5min_pct, o.step2_within_5min_pct AS old_step2_within_5min_pct, n.step2_within_5min_pct AS new_step2_within_5min_pct, o.step2_median_s AS old_step2_median_s, n.step2_median_s AS new_step2_median_s FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_dev_early_catch_summary_pr5 o FULL OUTER JOIN telco_netmon_febar_catalog.netmon_rca.rca_eval_dev_early_catch_summary n ON n.fault_type = o.fault_type ORDER BY fault_type = 'ALL' DESC, new_n DESC
```

| fault_type | old_n | new_n | old_model_within_5min_pct | new_model_within_5min_pct | old_model_median_signed_s | new_model_median_signed_s | old_heuristic_same_cases_within_5min_pct | new_heuristic_same_cases_within_5min_pct | old_step2_within_5min_pct | new_step2_within_5min_pct | old_step2_median_s | new_step2_median_s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 355 | 355 | 83.7 | 83.7 | 93.0 | 92.0 | 80.6 | 80.6 | 79.2 | 79.2 | 46.0 | 46.0 |
| CELL_OUTAGE | 205 | 205 | 97.6 | 97.6 | 89.0 | 88.0 | 97.1 | 97.1 | 100.0 | 100.0 | 36.0 | 36.0 |
| BACKHAUL_DEGRADATION | 55 | 55 | 5.5 | 5.5 | 618.0 | 618.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1020.0 | 1020.0 |
| SITE_POWER_OUTAGE | 46 | 46 | 97.8 | 97.8 | 114.0 | 114.0 | 82.6 | 82.6 | 97.8 | 97.8 | 145.0 | 145.0 |
| AGG_ROUTER_FAILURE | 30 | 30 | 100.0 | 100.0 | -11.0 | -11.0 | 100.0 | 100.0 | 100.0 | 100.0 | 11.5 | 11.5 |
| AMF_OVERLOAD | 18 | 18 | 100.0 | 100.0 | -57.0 | -58.5 | 100.0 | 100.0 | 0.0 | 0.0 | 508.5 | 508.5 |
| LONG_HAUL_FIBRE_CUT | 1 | 1 | 100.0 | 100.0 | 168.0 | 168.0 | 100.0 | 100.0 | 100.0 | 100.0 | 228.0 | 228.0 |

_7 row(s)_

## DEV (history_1m 10-14 … 10-15): alert-level fault precision old vs new

```sql
SELECT coalesce(n.system, o.system) AS system, o.n_alerts AS old_n_alerts, n.n_alerts AS new_n_alerts, o.fault AS old_fault, n.fault AS new_fault, o.unexplained AS old_unexplained, n.unexplained AS new_unexplained, o.fault_precision_pct AS old_fault_precision_pct, n.fault_precision_pct AS new_fault_precision_pct FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_dev_alert_precision_pr5 o FULL OUTER JOIN telco_netmon_febar_catalog.netmon_rca.rca_eval_dev_alert_precision n ON n.system = o.system ORDER BY system
```

| system | old_n_alerts | new_n_alerts | old_fault | new_fault | old_unexplained | new_unexplained | old_fault_precision_pct | new_fault_precision_pct |
|---|---|---|---|---|---|---|---|---|
| rca_model (top-1 >= threshold) | 442 | 434 | 393 | 390 | 28 | 26 | 93.3 | 93.8 |
| step2 detections | 12827 | 12827 | 10558 | 10558 | 430 | 430 | 96.1 | 96.1 |

_2 row(s)_

## VALIDATION (history_1m 10-13): top-1 / top-3 old vs new

`baseline_top1_pct` = step 2's region-wide `eval_rca_baseline` on the same incidents.

```sql
SELECT coalesce(n.fault_type, o.fault_type) AS fault_type, o.n AS old_n, n.n AS new_n, o.model_top1_pct AS old_model_top1_pct, n.model_top1_pct AS new_model_top1_pct, o.heuristic_same_cases_top1_pct AS old_heuristic_same_cases_top1_pct, n.heuristic_same_cases_top1_pct AS new_heuristic_same_cases_top1_pct, o.model_top3_pct AS old_model_top3_pct, n.model_top3_pct AS new_model_top3_pct, o.baseline_top1_pct AS old_baseline_top1_pct, n.baseline_top1_pct AS new_baseline_top1_pct FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_val_accuracy_pr5 o FULL OUTER JOIN telco_netmon_febar_catalog.netmon_rca.rca_eval_val_accuracy n ON n.fault_type = o.fault_type ORDER BY fault_type = 'ALL' DESC, new_n DESC
```

| fault_type | old_n | new_n | old_model_top1_pct | new_model_top1_pct | old_heuristic_same_cases_top1_pct | new_heuristic_same_cases_top1_pct | old_model_top3_pct | new_model_top3_pct | old_baseline_top1_pct | new_baseline_top1_pct |
|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 158.0 | 158.0 | 92.4 | 92.4 | 75.9 | 75.9 | 94.9 | 94.9 | 23.4 | 23.4 |
| CELL_OUTAGE | 87.0 | 87.0 | 96.6 | 96.6 | 95.4 | 95.4 | 97.7 | 97.7 | 4.6 | 4.6 |
| BACKHAUL_DEGRADATION | 25.0 | 25.0 | 76.0 | 76.0 | 0.0 | 0.0 | 80.0 | 80.0 | 36.0 | 36.0 |
| SITE_POWER_OUTAGE | 23.0 | 23.0 | 91.3 | 91.3 | 69.6 | 69.6 | 100.0 | 100.0 | 21.7 | 21.7 |
| AGG_ROUTER_FAILURE | 14.0 | 14.0 | 100.0 | 100.0 | 92.9 | 92.9 | 100.0 | 100.0 | 78.6 | 78.6 |
| AMF_OVERLOAD | 8.0 | 8.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| CORE_CONGESTION | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

_7 row(s)_

## VALIDATION (history_1m 10-13): early catch old vs new (signed seconds; step-2 localisation on the same incidents)

```sql
SELECT coalesce(n.fault_type, o.fault_type) AS fault_type, o.n AS old_n, n.n AS new_n, o.model_within_5min_pct AS old_model_within_5min_pct, n.model_within_5min_pct AS new_model_within_5min_pct, o.model_median_signed_s AS old_model_median_signed_s, n.model_median_signed_s AS new_model_median_signed_s, o.heuristic_same_cases_within_5min_pct AS old_heuristic_same_cases_within_5min_pct, n.heuristic_same_cases_within_5min_pct AS new_heuristic_same_cases_within_5min_pct, o.step2_within_5min_pct AS old_step2_within_5min_pct, n.step2_within_5min_pct AS new_step2_within_5min_pct, o.step2_median_s AS old_step2_median_s, n.step2_median_s AS new_step2_median_s FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_val_early_catch_summary_pr5 o FULL OUTER JOIN telco_netmon_febar_catalog.netmon_rca.rca_eval_val_early_catch_summary n ON n.fault_type = o.fault_type ORDER BY fault_type = 'ALL' DESC, new_n DESC
```

| fault_type | old_n | new_n | old_model_within_5min_pct | new_model_within_5min_pct | old_model_median_signed_s | new_model_median_signed_s | old_heuristic_same_cases_within_5min_pct | new_heuristic_same_cases_within_5min_pct | old_step2_within_5min_pct | new_step2_within_5min_pct | old_step2_median_s | new_step2_median_s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 158 | 158 | 82.3 | 82.3 | 82.5 | 82.5 | 77.8 | 77.8 | 78.5 | 78.5 | 40.0 | 40.0 |
| CELL_OUTAGE | 87 | 87 | 98.9 | 98.9 | 82.0 | 80.0 | 97.7 | 97.7 | 100.0 | 100.0 | 33.0 | 33.0 |
| BACKHAUL_DEGRADATION | 25 | 25 | 4.0 | 4.0 | 564.0 | 564.0 | 0.0 | 0.0 | 0.0 | 0.0 | 999.0 | 999.0 |
| SITE_POWER_OUTAGE | 23 | 23 | 91.3 | 91.3 | 82.0 | 82.0 | 69.6 | 69.6 | 100.0 | 100.0 | 159.0 | 159.0 |
| AGG_ROUTER_FAILURE | 14 | 14 | 100.0 | 100.0 | -19.0 | -14.5 | 100.0 | 100.0 | 100.0 | 100.0 | 7.0 | 7.0 |
| AMF_OVERLOAD | 8 | 8 | 100.0 | 100.0 | -106.5 | -21.5 | 100.0 | 100.0 | 0.0 | 0.0 | 436.0 | 436.0 |
| CORE_CONGESTION | 1 | 1 | 0.0 | 0.0 | 494.0 | 494.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

_7 row(s)_

## VALIDATION (history_1m 10-13): alert-level fault precision old vs new

```sql
SELECT coalesce(n.system, o.system) AS system, o.n_alerts AS old_n_alerts, n.n_alerts AS new_n_alerts, o.fault AS old_fault, n.fault AS new_fault, o.unexplained AS old_unexplained, n.unexplained AS new_unexplained, o.fault_precision_pct AS old_fault_precision_pct, n.fault_precision_pct AS new_fault_precision_pct FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_val_alert_precision_pr5 o FULL OUTER JOIN telco_netmon_febar_catalog.netmon_rca.rca_eval_val_alert_precision n ON n.system = o.system ORDER BY system
```

| system | old_n_alerts | new_n_alerts | old_fault | new_fault | old_unexplained | new_unexplained | old_fault_precision_pct | new_fault_precision_pct |
|---|---|---|---|---|---|---|---|---|
| rca_model (top-1 >= threshold) | 233 | 226 | 203 | 202 | 24 | 18 | 89.4 | 91.8 |
| step2 detections | 6677 | 6677 | 5873 | 5873 | 224 | 224 | 96.3 | 96.3 |

_2 row(s)_

## Step 2 (rule-based) on the holdout run, old vs new: time to detect / localise

```sql
SELECT coalesce(n.event_class, o.event_class) AS event_class, o.n_incidents AS old_n_incidents, n.n_incidents AS new_n_incidents, o.impact_within_5min_pct AS old_impact_within_5min_pct, n.impact_within_5min_pct AS new_impact_within_5min_pct, o.root_localised_pct AS old_root_localised_pct, n.root_localised_pct AS new_root_localised_pct, o.localised_within_5min_pct AS old_localised_within_5min_pct, n.localised_within_5min_pct AS new_localised_within_5min_pct, o.localisation_median_ttd_s AS old_localisation_median_ttd_s, n.localisation_median_ttd_s AS new_localisation_median_ttd_s FROM (SELECT * FROM telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary_pr5 WHERE source_run = 'holdout_1m' AND fault_type = 'ALL') o FULL OUTER JOIN (SELECT * FROM telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary WHERE source_run = 'holdout_1m' AND fault_type = 'ALL') n ON n.event_class = o.event_class ORDER BY 1
```

| event_class | old_n_incidents | new_n_incidents | old_impact_within_5min_pct | new_impact_within_5min_pct | old_root_localised_pct | new_root_localised_pct | old_localised_within_5min_pct | new_localised_within_5min_pct | old_localisation_median_ttd_s | new_localisation_median_ttd_s |
|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 366 | 366 | 83.1 | 86.3 | 99.5 | 99.5 | 63.4 | 80.3 | 81.0 | 45.0 |
| fault | 337 | 337 | 81.6 | 85.2 | 99.4 | 99.4 | 65.6 | 78.6 | 76.0 | 46.0 |
| planned | 29 | 29 | 100.0 | 100.0 | 100.0 | 100.0 | 37.9 | 100.0 | 334.0 | 33.0 |

_3 row(s)_

## Step 2 region-wide RCA baseline per run, old vs new

`history` and `stream` are untouched and must be equal old vs new.

```sql
SELECT coalesce(n.source_run, o.source_run) AS source_run, o.n AS old_n, n.n AS new_n, o.hit_at_1_pct AS old_hit_at_1_pct, n.hit_at_1_pct AS new_hit_at_1_pct, o.hit_at_3_pct AS old_hit_at_3_pct, n.hit_at_3_pct AS new_hit_at_3_pct FROM (SELECT source_run, count(*) AS n, round(100 * avg(CAST(hit_at_1 AS INT)), 1) AS hit_at_1_pct, round(100 * avg(CAST(hit_at_3 AS INT)), 1) AS hit_at_3_pct FROM telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline_pr5 GROUP BY 1) o FULL OUTER JOIN (SELECT source_run, count(*) AS n, round(100 * avg(CAST(hit_at_1 AS INT)), 1) AS hit_at_1_pct, round(100 * avg(CAST(hit_at_3 AS INT)), 1) AS hit_at_3_pct FROM telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline GROUP BY 1) n ON n.source_run = o.source_run ORDER BY 1
```

| source_run | old_n | new_n | old_hit_at_1_pct | new_hit_at_1_pct | old_hit_at_3_pct | new_hit_at_3_pct |
|---|---|---|---|---|---|---|
| history | 19 | 19 | 57.9 | 57.9 | 68.4 | 68.4 |
| history_1m | 1083 | 1083 | 25.8 | 25.8 | 39.5 | 39.5 |
| holdout_1m | 366 | 366 | 28.7 | 28.7 | 45.9 | 45.9 |
| stream | 26 | 26 | 53.8 | 53.8 | 73.1 | 73.1 |

_4 row(s)_
