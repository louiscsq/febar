# Step 6: nothing existing changed

Generated 2026-11-07 03:01 UTC by `scripts/collective_backhaul_experiment.py`.

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


## Every published step 2-5 result table: content hash and last change

All 89 result / summary tables of netmon_eval, netmon_rca and netmon_genai (the published scorecards,
including the `_pr5` copies of the pre-PR-6 results). `sha2` over the sorted JSON of every row is a deterministic content
hash, recorded here so that any later change is detectable. **No pre-step-6 hash snapshot exists**, so the before/after
check for this step is (a) `last_altered` (no table was changed since 2026-11-07T00:00:00Z) and (b) the replay of the committed
evidence below.

| table | type | last_altered | rows | sha2 (first 16 hex) | altered since 2026-11-07T00:00:00Z |
|---|---|---|---|---|---|
| netmon_eval.alarm_counts_pr5 | MANAGED | 2026-11-06 05:55:40.921000+00:00 | 4 | f2e33eb6d728c14e | no |
| netmon_eval.eval_alert_precision | MATERIALIZED_VIEW | 2026-11-06 09:45:48.638000+00:00 | 12 | ab1b496b54397907 | no |
| netmon_eval.eval_alert_precision_pr5 | MANAGED | 2026-11-06 05:54:35.684000+00:00 | 12 | b105e099d87a1ad7 | no |
| netmon_eval.eval_detection_precision | MATERIALIZED_VIEW | 2026-11-06 09:45:48.701000+00:00 | 12 | cdfced544625eb59 | no |
| netmon_eval.eval_detection_precision_pr5 | MANAGED | 2026-11-06 05:54:39.550000+00:00 | 12 | 367d7f2642426a02 | no |
| netmon_eval.eval_dq_capture | MATERIALIZED_VIEW | 2026-11-06 09:45:36.995000+00:00 | 80 | 1b745a1c8d37336e | no |
| netmon_eval.eval_dq_capture_pr5 | MANAGED | 2026-11-06 05:54:27.432000+00:00 | 80 | 34f9b3f78bc8428b | no |
| netmon_eval.eval_incident_detection | MATERIALIZED_VIEW | 2026-11-06 09:45:52.972000+00:00 | 1494 | 1881c9c63ca1e6ed | no |
| netmon_eval.eval_incident_detection_pr5 | MANAGED | 2026-11-06 05:54:32.160000+00:00 | 1494 | a4ab8c5927df0d01 | no |
| netmon_eval.eval_rca_baseline | MATERIALIZED_VIEW | 2026-11-06 09:45:52.903000+00:00 | 1494 | 1e38178c2fff4c65 | no |
| netmon_eval.eval_rca_baseline_pr5 | MANAGED | 2026-11-06 05:54:23.463000+00:00 | 1494 | e357037864d5710b | no |
| netmon_eval.eval_ttd_summary | MATERIALIZED_VIEW | 2026-11-06 09:45:55.585000+00:00 | 44 | b1c058e523740869 | no |
| netmon_eval.eval_ttd_summary_pr5 | MANAGED | 2026-11-06 05:54:18.968000+00:00 | 44 | f8077c73d0953b54 | no |
| netmon_genai.genai_eval_results_dev | MANAGED | 2026-11-06 07:59:07.591000+00:00 | 346 | d49c71b0c986cd93 | no |
| netmon_genai.genai_eval_results_dev_pr5 | MANAGED | 2026-11-06 05:53:48.823000+00:00 | 346 | 4b35350e8c1e344a | no |
| netmon_genai.genai_eval_results_holdout | MANAGED | 2026-11-06 08:10:25.422000+00:00 | 323 | e8d9911948c672c3 | no |
| netmon_genai.genai_eval_results_holdout_pr5 | MANAGED | 2026-11-06 05:53:53.212000+00:00 | 323 | 0dfe239ecf29f609 | no |
| netmon_genai.genai_eval_summary_dev | MANAGED | 2026-11-06 07:59:12.525000+00:00 | 7 | 96b511d2721a88fc | no |
| netmon_genai.genai_eval_summary_dev_pr5 | MANAGED | 2026-11-06 05:53:57.715000+00:00 | 7 | 6a5ff6cefaec10e8 | no |
| netmon_genai.genai_eval_summary_holdout | MANAGED | 2026-11-06 08:10:31.596000+00:00 | 8 | f0d24e05db9261cc | no |
| netmon_genai.genai_eval_summary_holdout_pr5 | MANAGED | 2026-11-06 05:54:02.004000+00:00 | 8 | f935d52533c35015 | no |
| netmon_rca.rca_eval_dev_accuracy | MANAGED | 2026-11-06 07:26:02.286000+00:00 | 7 | daba4cb5e32d7e81 | no |
| netmon_rca.rca_eval_dev_accuracy_pr5 | MANAGED | 2026-11-06 05:51:43.601000+00:00 | 7 | 04ab1da5ad9578c8 | no |
| netmon_rca.rca_eval_dev_alert_precision | MANAGED | 2026-11-06 07:26:11.035000+00:00 | 2 | d3bc0663039516dc | no |
| netmon_rca.rca_eval_dev_alert_precision_pr5 | MANAGED | 2026-11-06 05:51:47.928000+00:00 | 2 | b2da737fa2f0658f | no |
| netmon_rca.rca_eval_dev_any_alert | MANAGED | 2026-11-06 07:41:54.815000+00:00 | 355 | e37c5135468bf531 | no |
| netmon_rca.rca_eval_dev_any_alert_pr5 | MANAGED | 2026-11-06 05:53:04.963000+00:00 | 355 | 673394dcec026723 | no |
| netmon_rca.rca_eval_dev_any_alert_summary | MANAGED | 2026-11-06 07:41:59.490000+00:00 | 7 | 773e9894f42cc0ac | no |
| netmon_rca.rca_eval_dev_any_alert_summary_pr5 | MANAGED | 2026-11-06 05:53:08.876000+00:00 | 7 | 6aa70057228e9c61 | no |
| netmon_rca.rca_eval_dev_early_catch | MANAGED | 2026-11-06 07:26:05.199000+00:00 | 355 | e77958f6268c1f53 | no |
| netmon_rca.rca_eval_dev_early_catch_pr5 | MANAGED | 2026-11-06 05:51:51.990000+00:00 | 355 | 74ebcb509e34b216 | no |
| netmon_rca.rca_eval_dev_early_catch_summary | MANAGED | 2026-11-06 07:26:08.144000+00:00 | 7 | d9ad7e19e52617aa | no |
| netmon_rca.rca_eval_dev_early_catch_summary_pr5 | MANAGED | 2026-11-06 05:51:56.356000+00:00 | 7 | acd1ffb5f633902e | no |
| netmon_rca.rca_eval_dev_ranking | MANAGED | 2026-11-06 07:25:59.182000+00:00 | 355 | 75bbf04906e1d9c3 | no |
| netmon_rca.rca_eval_dev_ranking_pr5 | MANAGED | 2026-11-06 05:51:59.935000+00:00 | 355 | 1c80d033503e1deb | no |
| netmon_rca.rca_eval_holdout_accuracy | MANAGED | 2026-11-06 07:35:02.412000+00:00 | 8 | fa1e71473a57900f | no |
| netmon_rca.rca_eval_holdout_accuracy_pr5 | MANAGED | 2026-11-06 05:52:24.469000+00:00 | 8 | 76375873cfdfff7a | no |
| netmon_rca.rca_eval_holdout_alert_precision | MANAGED | 2026-11-06 07:35:13.294000+00:00 | 2 | 5342717ae7d348a5 | no |
| netmon_rca.rca_eval_holdout_alert_precision_pr5 | MANAGED | 2026-11-06 05:52:28.633000+00:00 | 2 | 088019e3e45ff72a | no |
| netmon_rca.rca_eval_holdout_any_alert | MANAGED | 2026-11-06 07:41:38.809000+00:00 | 337 | 5d67646995e419d2 | no |
| netmon_rca.rca_eval_holdout_any_alert_pr5 | MANAGED | 2026-11-06 05:53:13.169000+00:00 | 337 | ec281a85ccd0e411 | no |
| netmon_rca.rca_eval_holdout_any_alert_summary | MANAGED | 2026-11-06 07:41:43.343000+00:00 | 8 | 8d976f5c81f0c26e | no |
| netmon_rca.rca_eval_holdout_any_alert_summary_pr5 | MANAGED | 2026-11-06 05:53:17.849000+00:00 | 8 | dfe0aca11f9d6402 | no |
| netmon_rca.rca_eval_holdout_early_catch | MANAGED | 2026-11-06 07:35:05.958000+00:00 | 337 | f208eb5019f77bea | no |
| netmon_rca.rca_eval_holdout_early_catch_pr5 | MANAGED | 2026-11-06 05:52:32.645000+00:00 | 337 | 6f6821aa9837cb71 | no |
| netmon_rca.rca_eval_holdout_early_catch_summary | MANAGED | 2026-11-06 07:35:09.268000+00:00 | 8 | 233ae99aae601677 | no |
| netmon_rca.rca_eval_holdout_early_catch_summary_pr5 | MANAGED | 2026-11-06 05:52:36.756000+00:00 | 8 | 05df3257165e345b | no |
| netmon_rca.rca_eval_holdout_ranking | MANAGED | 2026-11-06 07:34:59.414000+00:00 | 337 | 928e7a61a504b955 | no |
| netmon_rca.rca_eval_holdout_ranking_pr5 | MANAGED | 2026-11-06 05:52:40.695000+00:00 | 337 | 8a5609a247d54f59 | no |
| netmon_rca.rca_eval_live_accuracy | MANAGED | 2026-11-06 07:35:30.297000+00:00 | 5 | 1ae9214648c09453 | no |
| netmon_rca.rca_eval_live_accuracy_pr5 | MANAGED | 2026-11-06 05:52:44.827000+00:00 | 5 | cb672381252fd5ec | no |
| netmon_rca.rca_eval_live_alert_precision | MANAGED | 2026-11-06 07:35:40.623000+00:00 | 2 | 1dd9689bc55a4071 | no |
| netmon_rca.rca_eval_live_alert_precision_pr5 | MANAGED | 2026-11-06 05:52:48.908000+00:00 | 2 | 1c1366fb4a6c4313 | no |
| netmon_rca.rca_eval_live_any_alert | MANAGED | 2026-11-06 07:35:46.243000+00:00 | 26 | ad563247b3d12645 | no |
| netmon_rca.rca_eval_live_any_alert_summary | MANAGED | 2026-11-06 07:35:51.087000+00:00 | 5 | 3088e0bfae1f2d95 | no |
| netmon_rca.rca_eval_live_early_catch | MANAGED | 2026-11-06 07:35:33.711000+00:00 | 26 | c067709c5e521d36 | no |
| netmon_rca.rca_eval_live_early_catch_pr5 | MANAGED | 2026-11-06 05:52:52.956000+00:00 | 26 | f75f31c95a98dc36 | no |
| netmon_rca.rca_eval_live_early_catch_summary | MANAGED | 2026-11-06 07:35:36.651000+00:00 | 5 | a4796d2d04cd59e0 | no |
| netmon_rca.rca_eval_live_early_catch_summary_pr5 | MANAGED | 2026-11-06 05:52:56.658000+00:00 | 5 | 19389b4e3cb06ced | no |
| netmon_rca.rca_eval_live_ranking | MANAGED | 2026-11-06 07:35:27.384000+00:00 | 26 | 21c087f3d852ceff | no |
| netmon_rca.rca_eval_live_ranking_pr5 | MANAGED | 2026-11-06 05:53:00.978000+00:00 | 26 | 57d9c2e2e99f5324 | no |
| netmon_rca.rca_eval_test_accuracy | MANAGED | 2026-11-05 16:18:26.093000+00:00 | 7 | 44712054d24f40d5 | no |
| netmon_rca.rca_eval_test_accuracy_pr5 | MANAGED | 2026-11-06 05:52:04.161000+00:00 | 7 | 44712054d24f40d5 | no |
| netmon_rca.rca_eval_test_alert_precision | MANAGED | 2026-11-05 16:18:34.445000+00:00 | 2 | 9818a7939a860f5d | no |
| netmon_rca.rca_eval_test_alert_precision_pr5 | MANAGED | 2026-11-06 05:52:08.266000+00:00 | 2 | 9818a7939a860f5d | no |
| netmon_rca.rca_eval_test_early_catch | MANAGED | 2026-11-05 16:18:28.790000+00:00 | 355 | bb66acffd68750e5 | no |
| netmon_rca.rca_eval_test_early_catch_pr5 | MANAGED | 2026-11-06 05:52:12.642000+00:00 | 355 | bb66acffd68750e5 | no |
| netmon_rca.rca_eval_test_early_catch_summary | MANAGED | 2026-11-05 16:18:31.669000+00:00 | 7 | 8f7a3265148bb977 | no |
| netmon_rca.rca_eval_test_early_catch_summary_pr5 | MANAGED | 2026-11-06 05:52:16.487000+00:00 | 7 | 8f7a3265148bb977 | no |
| netmon_rca.rca_eval_test_ranking | MANAGED | 2026-11-05 16:18:23.181000+00:00 | 355 | 07fb9d0a73ce2980 | no |
| netmon_rca.rca_eval_test_ranking_pr5 | MANAGED | 2026-11-06 05:52:20.641000+00:00 | 355 | 07fb9d0a73ce2980 | no |
| netmon_rca.rca_eval_val_accuracy | MANAGED | 2026-11-06 07:25:38.220000+00:00 | 7 | dd3aeb8171b06a2c | no |
| netmon_rca.rca_eval_val_accuracy_pr5 | MANAGED | 2026-11-06 05:51:20.719000+00:00 | 7 | ffa188ede0a1ae48 | no |
| netmon_rca.rca_eval_val_alert_precision | MANAGED | 2026-11-06 07:25:47.542000+00:00 | 2 | 4bcd5d471cb401f3 | no |
| netmon_rca.rca_eval_val_alert_precision_pr5 | MANAGED | 2026-11-06 05:51:25.015000+00:00 | 2 | 1b7102393c4a2491 | no |
| netmon_rca.rca_eval_val_any_alert | MANAGED | 2026-11-06 07:25:52.516000+00:00 | 158 | 521653527071111f | no |
| netmon_rca.rca_eval_val_any_alert_summary | MANAGED | 2026-11-06 07:25:56.233000+00:00 | 7 | 2e70fc888744d3eb | no |
| netmon_rca.rca_eval_val_early_catch | MANAGED | 2026-11-06 07:25:41.341000+00:00 | 158 | a884dfb02520bfbc | no |
| netmon_rca.rca_eval_val_early_catch_pr5 | MANAGED | 2026-11-06 05:51:31+00:00 | 158 | b7f7f403402cc891 | no |
| netmon_rca.rca_eval_val_early_catch_summary | MANAGED | 2026-11-06 07:25:44.429000+00:00 | 7 | b2e6fde2e5cd259f | no |
| netmon_rca.rca_eval_val_early_catch_summary_pr5 | MANAGED | 2026-11-06 05:51:35.189000+00:00 | 7 | effbc22308259d9a | no |
| netmon_rca.rca_eval_val_ranking | MANAGED | 2026-11-06 07:25:34.908000+00:00 | 158 | dc137c6f126fd423 | no |
| netmon_rca.rca_eval_val_ranking_pr5 | MANAGED | 2026-11-06 05:51:39.629000+00:00 | 158 | 3129f89048ce0878 | no |
| netmon_rca.rca_feature_importance | MANAGED | 2026-11-06 07:26:21.835000+00:00 | 55 | b25f3cc6fe81041c | no |
| netmon_rca.rca_feature_importance_pr5 | MANAGED | 2026-11-06 05:53:29.705000+00:00 | 55 | 0a4986dd2704f834 | no |
| netmon_rca.rca_holdout_runs | MANAGED | 2026-11-06 07:35:56.640000+00:00 | 1 | dba5358100300ca5 | no |
| netmon_rca.rca_holdout_runs_pr5 | MANAGED | 2026-11-06 05:53:21.801000+00:00 | 1 | e282233fac818b22 | no |
| netmon_rca.rca_training_runs | MANAGED | 2026-11-06 07:26:25.665000+00:00 | 1 | 70cf00e7cc65a624 | no |
| netmon_rca.rca_training_runs_pr5 | MANAGED | 2026-11-06 05:53:25.665000+00:00 | 1 | 9aa6e20fab2df523 | no |

_89 row(s)_


## Committed step 2-4 headline evidence replayed against the current tables

Before = the tables committed in evidence/step2..4 (the published numbers; no separate pre-step-6 snapshot was
taken, so the committed evidence is the reference). After = the same SQL re-run now, rendered by the same function. Step 5's
headline is the Genie benchmark (evidence/step5/02*): answers of a live LLM, not a table, so it cannot be replayed
deterministically; the serving views it reads sit on the tables hashed above.

| file | section | status | committed rows | current rows |
|---|---|---|---|---|
| evidence/step2/02_expectations.md | Per dataset and rule | skipped (not replayable: system / time-dependent / non-SELECT) |  |  |
| evidence/step2/02_expectations.md | Dropped rows per silver flow | skipped (not replayable: system / time-dependent / non-SELECT) |  |  |
| evidence/step2/02_expectations.md | Quarantine by feed and failed rule | every committed row unchanged; +68 rows (first column: alarms, kpis, sessions) | 68 | 136 |
| evidence/step2/02_expectations.md | Quarantine sample (PII redacted) | DIFFERENT | 25 | 25 |
| evidence/step2/02_expectations.md | Injected defects (ground truth) vs pipeline handling — eval_dq_capture | every committed row unchanged; +40 rows (first column: history_1m, holdout_1m) | 40 | 80 |
| evidence/step2/03_row_counts.md | All pipeline tables | DIFFERENT | 25 | 25 |
| evidence/step2/03_row_counts.md | Bronze and silver by generator run | every committed row unchanged; +6 rows (first column: alarms, kpis, sessions) | 6 | 12 |
| evidence/step2/03_row_counts.md | Silver by generator run | every committed row unchanged; +6 rows (first column: alarms, kpis, sessions) | 6 | 12 |
| evidence/step2/05_time_to_detect.md | Headline: faults only | every committed row unchanged; +2 rows (first column: history_1m, holdout_1m) | 2 | 4 |
| evidence/step2/05_time_to_detect.md | All event classes | every committed row unchanged; +6 rows (first column: history_1m, holdout_1m) | 6 | 12 |
| evidence/step2/05_time_to_detect.md | Per fault type | every committed row unchanged; +17 rows (first column: history_1m, holdout_1m) | 15 | 32 |
| evidence/step2/05_time_to_detect.md | Live-stream fault incidents | identical | 26 | 26 |
| evidence/step2/05_time_to_detect.md | Ground-truth incidents in the live stream (incl. censored and non-impa | identical | 11 | 11 |
| evidence/step2/05_time_to_detect.md | Alert-level fault precision (detections grouped per element per episod | every committed row unchanged; +6 rows (first column: history_1m, holdout_1m) | 6 | 12 |
| evidence/step2/05_time_to_detect.md | Detection-row fault precision and maintenance suppression | every committed row unchanged; +6 rows (first column: history_1m, holdout_1m) | 6 | 12 |
| evidence/step2/05_time_to_detect.md | History AMF_OVERLOAD INC-00016: localisation and the inputs it was qua | identical | 1 | 1 |
| evidence/step2/05_time_to_detect.md | INC-00016: qualifying rollup windows of the root (real-time, on-time r | identical | 1 | 1 |
| evidence/step2/05_time_to_detect.md | INC-00016: the root's descendant cell windows behind that rollup (late | identical | 2 | 2 |
| evidence/step2/05_time_to_detect.md | Real-time vs retrospective 5-minute windows: late records | DIFFERENT | 2 | 2 |
| evidence/step2/05_time_to_detect.md | RCA topology-heuristic baseline (hit@1 / hit@3 vs root_element_ids) | every committed row unchanged; +19 rows (first column: history_1m, holdout_1m) | 17 | 36 |
| evidence/step3/01_training_run.md | Rows, positives and cases per split | identical | 3 | 3 |
| evidence/step3/01_training_run.md | Case labels per split | identical | 10 | 10 |
| evidence/step3/01_training_run.md | Feature importance (permutation, average precision, validation sample) | identical | 25 | 25 |
| evidence/step3/01_training_run.md | Validation-day alert-level precision at the chosen threshold | identical | 2 | 2 |
| evidence/step3/02_evaluation.md | HOLDOUT (holdout_1m, untouched): top-1 / top-3, model vs the step-2 he | identical | 8 | 8 |
| evidence/step3/02_evaluation.md | HOLDOUT (holdout_1m, untouched): non-oracle companion, any live alert  | identical | 8 | 8 |
| evidence/step3/02_evaluation.md | HOLDOUT (holdout_1m, untouched): early catch (signed times), model vs  | identical | 8 | 8 |
| evidence/step3/02_evaluation.md | HOLDOUT (holdout_1m, untouched): slow backhaul degradation, per incide | identical | 53 | 53 |
| evidence/step3/02_evaluation.md | HOLDOUT (holdout_1m, untouched): secondary, alert-level fault precisio | identical | 2 | 2 |
| evidence/step3/02_evaluation.md | DEV (history_1m 10-14 … 10-15, seen during design): top-1 / top-3, mod | identical | 7 | 7 |
| evidence/step3/02_evaluation.md | DEV (history_1m 10-14 … 10-15, seen during design): non-oracle compani | identical | 7 | 7 |
| evidence/step3/02_evaluation.md | DEV (history_1m 10-14 … 10-15, seen during design): early catch (signe | identical | 7 | 7 |
| evidence/step3/02_evaluation.md | DEV (history_1m 10-14 … 10-15, seen during design): slow backhaul degr | identical | 55 | 55 |
| evidence/step3/02_evaluation.md | DEV (history_1m 10-14 … 10-15, seen during design): secondary, alert-l | identical | 2 | 2 |
| evidence/step3/02_evaluation.md | Validation day (calibration and threshold were chosen here) | identical | 7 | 7 |
| evidence/step3/02_evaluation.md | Live stream run (2026-10-08, out-of-run check; censored incidents not  | identical | 5 | 5 |
| evidence/step3/02_evaluation.md | Step 2's published RCA baseline per run (eval_rca_baseline, region-wid | identical | 4 | 4 |
| evidence/step3/02_evaluation.md | Holdout incidents the model missed at top-1 (sample) | identical | 18 | 18 |
| evidence/step3/07_pr3_review_notes.md | b. Real (signed) evidence lag: alarms that arrive before the impact st | DIFFERENT from now; identical to the pre-PR-6 snapshot (`_pr5` tables) | 28 | 28 |
| evidence/step3/07_pr3_review_notes.md | b. Incidents whose first evidence predates impact (sample) | DIFFERENT from now; identical to the pre-PR-6 snapshot (`_pr5` tables) | 10 | 10 |
| evidence/step3/08_alarm_id_fix.md | Alarms per run BEFORE the fix (snapshot netmon_eval.alarm_counts_pr5) | identical | 4 | 4 |
| evidence/step3/08_alarm_id_fix.md | Alarms per run AFTER the fix (same query, live) | identical | 4 | 4 |
| evidence/step3/08_alarm_id_fix.md | Before vs after, side by side | identical | 4 | 4 |
| evidence/step3/08_alarm_id_fix.md | HOLDOUT (holdout_1m): top-1 / top-3 old vs new | identical | 8 | 8 |
| evidence/step3/08_alarm_id_fix.md | HOLDOUT (holdout_1m): non-oracle any-alert metric old vs new | identical | 8 | 8 |
| evidence/step3/08_alarm_id_fix.md | HOLDOUT (holdout_1m): early catch old vs new (signed seconds; step-2 l | identical | 8 | 8 |
| evidence/step3/08_alarm_id_fix.md | HOLDOUT (holdout_1m): alert-level fault precision old vs new | identical | 2 | 2 |
| evidence/step3/08_alarm_id_fix.md | DEV (history_1m 10-14 … 10-15): top-1 / top-3 old vs new | identical | 7 | 7 |
| evidence/step3/08_alarm_id_fix.md | DEV (history_1m 10-14 … 10-15): non-oracle any-alert metric old vs new | identical | 7 | 7 |
| evidence/step3/08_alarm_id_fix.md | DEV (history_1m 10-14 … 10-15): early catch old vs new (signed seconds | identical | 7 | 7 |
| evidence/step3/08_alarm_id_fix.md | DEV (history_1m 10-14 … 10-15): alert-level fault precision old vs new | identical | 2 | 2 |
| evidence/step3/08_alarm_id_fix.md | VALIDATION (history_1m 10-13): top-1 / top-3 old vs new | identical | 7 | 7 |
| evidence/step3/08_alarm_id_fix.md | VALIDATION (history_1m 10-13): early catch old vs new (signed seconds; | identical | 7 | 7 |
| evidence/step3/08_alarm_id_fix.md | VALIDATION (history_1m 10-13): alert-level fault precision old vs new | identical | 2 | 2 |
| evidence/step3/08_alarm_id_fix.md | Step 2 (rule-based) on the holdout run, old vs new: time to detect / l | identical | 3 | 3 |
| evidence/step3/08_alarm_id_fix.md | Step 2 region-wide RCA baseline per run, old vs new | identical | 4 | 4 |
| evidence/step4/04_evaluation.md | DEV: by fault type | identical | 6 | 6 |
| evidence/step4/04_evaluation.md | DEV: every case where the assistant departs from the ranker | identical | 7 | 7 |
| evidence/step4/04_evaluation.md | HOLDOUT: by fault type | identical | 7 | 7 |
| evidence/step4/04_evaluation.md | HOLDOUT: every case where the assistant departs from the ranker | identical | 5 | 5 |
| evidence/step4/07_latency_cost.md | DEV: latency and tokens per incident | identical | 1 | 1 |
| evidence/step4/07_latency_cost.md | HOLDOUT: latency and tokens per incident | identical | 1 | 1 |
| evidence/step4/07_latency_cost.md | Request log: latency per call type | identical | 2 | 2 |
| evidence/step4/07_latency_cost.md | Billing: DBUs attributed to the assistant endpoint (this workspace) | skipped (not replayable: system / time-dependent / non-SELECT) |  |  |
| evidence/step4/07_latency_cost.md | Gateway usage tracking: tokens on the endpoint (this workspace) | skipped (not replayable: system / time-dependent / non-SELECT) |  |  |
| evidence/step4/09_holdout_alarm_gap.md | Alarms per run before the fix (snapshot) | identical | 4 | 4 |
| evidence/step4/09_holdout_alarm_gap.md | DEV (before the fix): assistant vs ranker by whether the context has a | identical | 10 | 10 |
| evidence/step4/09_holdout_alarm_gap.md | HOLDOUT (before the fix): assistant vs ranker by whether the context h | identical | 14 | 14 |
| evidence/step4/09_holdout_alarm_gap.md | Alarms per run after the fix (live) | identical | 4 | 4 |
| evidence/step4/09_holdout_alarm_gap.md | HOLDOUT (after the fix): assistant vs ranker by whether the context ha | identical | 12 | 12 |
| evidence/step4/10_holdout_rerun.md | HOLDOUT: by fault type, old vs new | identical | 7 | 7 |
| evidence/step4/10_holdout_rerun.md | DEV: by fault type, old vs new | identical | 6 | 6 |
| evidence/step4/10_holdout_rerun.md | HOLDOUT (new): every case where the assistant departs from the ranker | identical | 5 | 5 |

_73 row(s)_


**Replayed: 54 identical, 10 with every committed row unchanged plus rows of runs added after that file was captured, 5 different** (listed below; see the README for why each one differs).

## Differences (explained in the README)

### evidence/step2/02_expectations.md: Quarantine sample (PII redacted)

committed rows not in the current output:

| feed | record_id | failed_rules | event_ts_raw | payload | rescued | corrupt |
|---|---|---|---|---|---|---|
| alarms | ALM-041fbe27f3bc060c-R | ["severity_not_null"] | 2026-09-30T10:42:37Z | {"alarm_id":"ALM-041fbe27f3bc060c","event_type":"RAISE","element_id":"UPF-VIC-01","element_type":"UPF_SGW","al | NULL | NULL |
| alarms | ALM-064d759e08d8b5a6-R | ["event_ts_valid"] |  | {"alarm_id":"ALM-064d759e08d8b5a6","event_type":"RAISE","element_id":"UPF-VIC-01","element_type":"UPF_SGW","al | NULL | NULL |
| alarms | ALM-074954cc4f576814-C | ["element_id_not_null","known_element"] | 2026-09-29T09:31:33Z | {"alarm_id":"ALM-074954cc4f576814","event_type":"CLEAR","element_type":"CELL","alarm_code":"SYNC_LOSS","severi | NULL | NULL |
| alarms | ALM-024596b036819e61-R | ["parseable_record"] | NULL | NULL | NULL | {"record_id":"ALM-024596b036819e61-R","alarm_id":"ALM-024596b036819e61 |
| alarms | ALM-00d0a46f80156c2c-R | ["event_ts_plausible"] | 2099-01-01T00:00:00Z | {"alarm_id":"ALM-00d0a46f80156c2c","event_type":"RAISE","element_id":"SITE-VIC-00098","element_type":"SITE","a | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202610082243 | ["dl_throughput_mbps_not_null"] | 2026-10-08T22:43:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-10-08T22:43:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G3-202610061415 | ["rrc_setup_success_pct_in_range"] | 2026-10-06T14:15:00Z | {"cell_id":"CELL-NQL-00001-4G3","event_ts_raw":"2026-10-06T14:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202609240015 | ["dl_throughput_mbps_in_range"] | 2026-09-24T00:15:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-09-24T00:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202610082233 | ["active_users_in_range"] | 2026-10-08T22:33:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-10-08T22:33:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202609240215 | ["no_rescued_data","dl_throughput_mbps_not_null"] | 2026-09-24T02:15:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-09-24T02:15:00Z","granularity_s":900,"availability_pct":1 | {"dl_throughput_mbps":"ERR","_file_path":"/Volumes/telco_net | NULL |
| kpis | K-CELL-NQL-00001-4G2-202610082323 | ["rrc_setup_success_pct_not_null"] | 2026-10-08T23:23:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-10-08T23:23:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G2-202610040315 | ["availability_pct_in_range"] | 2026-10-04T03:15:00Z | {"cell_id":"CELL-NQL-00001-4G2","event_ts_raw":"2026-10-04T03:15:00Z","granularity_s":900,"availability_pct":1 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G3-202610081918 | ["prb_util_pct_in_range"] | 2026-10-08T19:18:00Z | {"cell_id":"CELL-NQL-00001-4G3","event_ts_raw":"2026-10-08T19:18:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |

current rows not in the committed table:

| feed | record_id | failed_rules | event_ts_raw | payload | rescued | corrupt |
|---|---|---|---|---|---|---|
| alarms | ALM-0296922b41b0c033-C | ["severity_not_null"] | 2026-10-14T15:35:15Z | {"alarm_id":"ALM-0296922b41b0c033","event_type":"CLEAR","element_id":"AGG-WA-04","element_type":"AGG_ROUTER"," | NULL | NULL |
| alarms | ALM-001d694297365e65-C | ["event_ts_valid"] | NULL | {"alarm_id":"ALM-001d694297365e65","event_type":"CLEAR","element_id":"CELL-VIC-00040-4G1","element_type":"CELL | NULL | NULL |
| alarms | ALM-05622e0a4ce40960-C | ["element_id_not_null","known_element"] | 2026-10-10T23:58:52Z | {"alarm_id":"ALM-05622e0a4ce40960","event_type":"CLEAR","element_type":"SITE","alarm_code":"TEMPERATURE_HIGH", | NULL | NULL |
| alarms | ALM-0073047f95f1cf05-C | ["parseable_record"] | NULL | NULL | NULL | {"record_id":"ALM-0073047f95f1cf05-C","alarm_id":"ALM-0073047f95f1cf05 |
| alarms | ALM-009998562a9bbef3-C | ["event_ts_plausible"] | 2099-01-01T00:00:00Z | {"alarm_id":"ALM-009998562a9bbef3","event_type":"CLEAR","element_id":"AGG-NSW-02","element_type":"AGG_ROUTER", | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610110130 | ["dl_throughput_mbps_not_null"] | 2026-10-11T01:30:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-11T01:30:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610100426 | ["rrc_setup_success_pct_in_range"] | 2026-10-10T04:26:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-10T04:26:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610100204 | ["dl_throughput_mbps_in_range"] | 2026-10-10T02:04:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-10T02:04:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610122245 | ["active_users_in_range"] | 2026-10-12T22:45:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-12T22:45:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610111515 | ["no_rescued_data","prb_util_pct_not_null"] | 2026-10-11T15:15:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-11T15:15:00Z","granularity_s":60,"availability_pct":10 | {"prb_util_pct":"ERR","_file_path":"/Volumes/telco_netmon_fe | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610111749 | ["rrc_setup_success_pct_not_null"] | 2026-10-11T17:49:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-11T17:49:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610101957 | ["availability_pct_in_range"] | 2026-10-10T19:57:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-10T19:57:00Z","granularity_s":60,"availability_pct":13 | NULL | NULL |
| kpis | K-CELL-NQL-00001-4G1-202610112148 | ["prb_util_pct_in_range"] | 2026-10-11T21:48:00Z | {"cell_id":"CELL-NQL-00001-4G1","event_ts_raw":"2026-10-11T21:48:00Z","granularity_s":60,"availability_pct":10 | NULL | NULL |

### evidence/step2/03_row_counts.md: All pipeline tables

committed rows not in the current output:

| table_name | n_rows |
|---|---|
| netmon_silver.silver_sessions | 1320796 |
| netmon_silver.silver_maintenance_windows | 2 |
| netmon_gold.gold_impact_detections | 12074 |
| netmon_eval.eval_gt_incidents | 76 |
| netmon_bronze.bronze_kpis | 2447940 |
| netmon_bronze.bronze_alarms | 19884 |
| netmon_bronze.bronze_sessions | 1339456 |
| netmon_bronze.bronze_topology_nodes | 3774 |
| netmon_bronze.bronze_topology_edges | 3766 |
| netmon_bronze.bronze_maintenance_windows | 2 |
| netmon_silver.silver_kpis | 2413825 |
| netmon_silver.silver_alarms | 19600 |
| netmon_silver.silver_quarantine | 34108 |
| netmon_gold.gold_cell_baseline | 1016375 |
| netmon_gold.gold_cell_health_1m | 2385288 |
| netmon_gold.gold_cell_health_5m | 1987413 |
| netmon_gold.gold_element_impact_5m | 141461 |
| netmon_gold.gold_cell_sessions_5m | 1107259 |
| netmon_eval.bronze_gt_incidents | 76 |
| netmon_eval.bronze_gt_dq_injections | 90926 |
| netmon_eval.eval_detection_log | 12074 |
| netmon_eval.eval_incident_detection | 45 |
| netmon_eval.eval_rca_baseline | 45 |

current rows not in the committed table:

| table_name | n_rows |
|---|---|
| netmon_silver.silver_sessions | 2062199 |
| netmon_silver.silver_maintenance_windows | 132 |
| netmon_gold.gold_impact_detections | 2280744 |
| netmon_eval.eval_gt_incidents | 1670 |
| netmon_bronze.bronze_kpis | 18896842 |
| netmon_bronze.bronze_alarms | 145592 |
| netmon_bronze.bronze_sessions | 2091335 |
| netmon_bronze.bronze_topology_nodes | 7548 |
| netmon_bronze.bronze_topology_edges | 7532 |
| netmon_bronze.bronze_maintenance_windows | 132 |
| netmon_silver.silver_kpis | 18633589 |
| netmon_silver.silver_alarms | 143559 |
| netmon_silver.silver_quarantine | 189274 |
| netmon_gold.gold_cell_baseline | 1703242 |
| netmon_gold.gold_cell_health_1m | 18441342 |
| netmon_gold.gold_cell_health_5m | 5261420 |
| netmon_gold.gold_element_impact_5m | 856652 |
| netmon_gold.gold_cell_sessions_5m | 1729506 |
| netmon_eval.bronze_gt_incidents | 1670 |
| netmon_eval.bronze_gt_dq_injections | 504687 |
| netmon_eval.eval_detection_log | 2280744 |
| netmon_eval.eval_incident_detection | 1494 |
| netmon_eval.eval_rca_baseline | 1494 |

### evidence/step2/05_time_to_detect.md: Real-time vs retrospective 5-minute windows: late records

committed rows not in the current output:

| table_name | windows | records | late_records |
|---|---|---|---|
| gold_cell_health_5m (real-time, scored) | 1987413 | 2382505 | 0 |
| gold_cell_health_5m_retrospective (never scored) | 2008061 | 2413825 | 24359 |

current rows not in the committed table:

| table_name | windows | records | late_records |
|---|---|---|---|
| gold_cell_health_5m (real-time, scored) | 5261420 | 18438527 | 0 |
| gold_cell_health_5m_retrospective (never scored) | 5282082 | 18633589 | 188027 |

### evidence/step3/07_pr3_review_notes.md: b. Real (signed) evidence lag: alarms that arrive before the impact starts

committed rows not in the current output:

| source_run | fault_type | n_incidents | median_evidence_lag_s | median_signed_evidence_lag_s | min_signed_evidence_lag_s | n_evidence_before_impact |
|---|---|---|---|---|---|---|
| holdout_1m | AGG_ROUTER_FAILURE | 40 | 0.0 | -45.0 | -53 | 33 |
| holdout_1m | CELL_OUTAGE | 187 | 51.0 | 51.0 | 12 | 0 |
| holdout_1m | LONG_HAUL_FIBRE_CUT | 1 | 19519.0 | 19519.0 | 19519 | 0 |
| holdout_1m | SITE_POWER_OUTAGE | 38 | 69.5 | 107.5 | 15 | 0 |

current rows not in the committed table:

| source_run | fault_type | n_incidents | median_evidence_lag_s | median_signed_evidence_lag_s | min_signed_evidence_lag_s | n_evidence_before_impact |
|---|---|---|---|---|---|---|
| holdout_1m | AGG_ROUTER_FAILURE | 40 | 0.0 | -46.0 | -56 | 40 |
| holdout_1m | CELL_OUTAGE | 187 | 35.0 | 35.0 | 9 | 0 |
| holdout_1m | LONG_HAUL_FIBRE_CUT | 1 | 69.0 | 69.0 | 69 | 0 |
| holdout_1m | SITE_POWER_OUTAGE | 38 | 87.0 | 87.0 | 15 | 0 |

### evidence/step3/07_pr3_review_notes.md: b. Incidents whose first evidence predates impact (sample)

committed rows not in the current output:

| source_run | incident_id | fault_type | first_signal_source | first_flags | signed_evidence_lag_s | evidence_lag_s | impact_ttd_s |
|---|---|---|---|---|---|---|---|
| history_1m | INC-00748 | AGG_ROUTER_FAILURE | alarm | ["LINK_DOWN"] | -53 | 0 | 0.000000 |

current rows not in the committed table:

| source_run | incident_id | fault_type | first_signal_source | first_flags | signed_evidence_lag_s | evidence_lag_s | impact_ttd_s |
|---|---|---|---|---|---|---|---|
| holdout_1m | INC-00358 | AGG_ROUTER_FAILURE | alarm | ["LINK_DOWN"] | -56 | 0 | 0.000000 |
