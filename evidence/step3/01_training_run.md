# Training run (MLflow)

Captured 2026-11-05 16:38 UTC from workspace profile `febar` by `scripts/capture_evidence_step3.py`.

## Run

- MLflow run ID: `8d047e614f3941f795a2f8f638957328`
- experiment: `/Shared/banksia_netmon/rca_ranker` (`688671173720819`)
- status: `FINISHED`, started 2026-11-05 16:13 UTC, 4.5 min
- registered model: `telco_netmon_febar_catalog.netmon_rca.rca_ranker` version `3` (alias `champion`)
- training job wall time (features + training + evaluation + registration): 15.5 min

## Parameters

```json
{
  "alert_threshold": "0.31",
  "decision_step_minutes": "1",
  "hgb_early_stopping": "False",
  "hgb_l2_regularization": "1.0",
  "hgb_learning_rate": "0.05",
  "hgb_max_iter": "400",
  "hgb_max_leaf_nodes": "31",
  "hgb_min_samples_leaf": "40",
  "hgb_random_state": "7",
  "model_type": "sklearn HistGradientBoostingClassifier + isotonic calibration (validation days)",
  "n_features": "55",
  "positives_test": "38114",
  "positives_train": "50655",
  "positives_val": "25547",
  "rows_test": "998086",
  "rows_train": "1537924",
  "rows_val": "538552",
  "test_start": "2026-10-14 00:00:00+00:00",
  "train_run": "history_1m",
  "val_start": "2026-10-13 00:00:00+00:00"
}
```

## Metrics (val = calibration / threshold day, test = held-out days; live = stream run)

```json
{
  "live_baseline_top1_pct": 53.8,
  "live_n_incidents": 26.0,
  "live_top1_pct": 80.8,
  "live_top3_pct": 84.6,
  "test_alert_precision_pct": 93.3,
  "test_backhaul_median_s": 618.0,
  "test_backhaul_n": 55.0,
  "test_backhaul_within_5min_pct": 5.5,
  "test_baseline_top1_pct": 23.4,
  "test_baseline_top3_pct": 36.3,
  "test_heuristic_same_cases_top1_pct": 76.1,
  "test_heuristic_same_cases_top3_pct": 85.1,
  "test_n_incidents": 355.0,
  "test_step2_alert_precision_pct": 96.1,
  "test_step2_backhaul_within_5min_pct": 0.0,
  "test_top1_pct": 81.4,
  "test_top3_pct": 93.5,
  "val_alert_precision_pct": 89.4,
  "val_backhaul_median_s": 564.0,
  "val_backhaul_n": 25.0,
  "val_backhaul_within_5min_pct": 4.0,
  "val_baseline_top1_pct": 23.4,
  "val_baseline_top3_pct": 35.4,
  "val_heuristic_same_cases_top1_pct": 72.2,
  "val_heuristic_same_cases_top3_pct": 81.6,
  "val_n_incidents": 158.0,
  "val_step2_alert_precision_pct": 96.3,
  "val_step2_backhaul_within_5min_pct": 0.0,
  "val_top1_pct": 82.3,
  "val_top3_pct": 93.7
}
```

## Artifacts

```text
[
  "feature_columns.json",
  "evaluation",
  "evaluation/feature_importance.csv",
  "evaluation/live_accuracy.csv",
  "evaluation/split_counts.csv",
  "evaluation/test_accuracy.csv",
  "evaluation/test_alert_precision.csv",
  "evaluation/test_early_catch.csv",
  "evaluation/test_early_catch_summary.csv",
  "evaluation/test_ranking.csv",
  "evaluation/threshold_curve.csv",
  "evaluation/val_accuracy.csv",
  "evaluation/val_alert_precision.csv",
  "evaluation/val_early_catch.csv",
  "evaluation/val_early_catch_summary.csv",
  "evaluation/val_ranking.csv"
]
```

## Rows, positives and cases per split

Censored incidents are excluded before the split; rows matched to an incident that starts in a later split are dropped (embargo).

```sql
SELECT split, count(*) AS candidate_rows, count_if(is_root) AS positive_rows,
               count(DISTINCT case_id) AS cases, min(decision_ts) AS first_decision, max(decision_ts) AS last_decision
        FROM telco_netmon_febar_catalog.netmon_rca.rca_training_labels GROUP BY split ORDER BY min(decision_ts)
```

| split | candidate_rows | positive_rows | cases | first_decision | last_decision |
|---|---|---|---|---|---|
| train | 1537924 | 50655 | 56307 | 2026-10-10T01:02:00.000Z | 2026-10-12T23:59:00.000Z |
| val | 538552 | 25547 | 27242 | 2026-10-13T00:00:00.000Z | 2026-10-13T23:59:00.000Z |
| test | 998086 | 38114 | 40953 | 2026-10-14T00:00:00.000Z | 2026-10-15T23:58:00.000Z |

_3 row(s)_

## Case labels per split

```sql
SELECT split, case_label, count(DISTINCT case_id) AS cases FROM telco_netmon_febar_catalog.netmon_rca.rca_training_labels
        GROUP BY ALL ORDER BY 1, 2
```

| split | case_label | cases |
|---|---|---|
| test | fault | 36460 |
| test | none | 3053 |
| test | planned | 1439 |
| test | red_herring | 1 |
| train | fault | 49736 |
| train | none | 4235 |
| train | planned | 2319 |
| train | red_herring | 17 |
| val | fault | 25087 |
| val | none | 1461 |
| val | planned | 693 |
| val | red_herring | 1 |

_12 row(s)_

## Feature importance (permutation, average precision, validation sample)

```sql
SELECT feature, round(importance_mean, 5) AS importance_mean, round(importance_std, 5) AS importance_std
        FROM telco_netmon_febar_catalog.netmon_rca.rca_feature_importance ORDER BY importance_mean DESC LIMIT 25
```

| feature | importance_mean | importance_std |
|---|---|---|
| coverage | 0.05477 | 0.00127 |
| level | 0.03069 | 0.00156 |
| impacted_children_fraction | 0.02877 | 0.00169 |
| parent_impacted_fraction | 0.02242 | 8.8E-4 |
| impacted_fraction | 0.02076 | 4.9E-4 |
| n_subtree_service_down_alarms | 0.01851 | 0.00104 |
| drop_now | 0.01033 | 4.1E-4 |
| n_children | 0.00851 | 3.9E-4 |
| attach_now | 0.00828 | 3.1E-4 |
| minutes_since_first_anomaly | 0.00706 | 2.1E-4 |
| degraded_fraction | 0.00631 | 1.5E-4 |
| n_critical_alarms | 0.00622 | 1.4E-4 |
| avail_now | 0.00563 | 2.9E-4 |
| in_maintenance | 0.00548 | 4.0E-4 |
| thr_vs_parent | 0.00533 | 3.4E-4 |
| prb_now | 0.00528 | 5.2E-4 |
| loss_now | 0.00511 | 9.0E-5 |
| n_alarms_core | 0.00503 | 1.5E-4 |
| alarm_age_min | 0.00468 | 2.2E-4 |
| alarmed_children_fraction | 0.00425 | 3.5E-4 |
| n_alarms | 0.00377 | 2.7E-4 |
| n_impacted_cells | 0.0037 | 1.1E-4 |
| n_service_down_alarms | 0.00359 | 3.2E-4 |
| lat_now | 0.00358 | 7.0E-5 |
| prb_slope15 | 0.00338 | 3.2E-4 |

_25 row(s)_

## Validation-day alert-level precision at the chosen threshold

The threshold itself was chosen by validation F1 on case top-1 (threshold_curve.csv artifact); this is the validation alert-level precision at that threshold.

```sql
SELECT * FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_val_alert_precision
```

| system | fault | censored | planned_suppressed | planned_fp | red_herring | unexplained | fault_precision_pct | maintenance_suppression_pct | n_alerts | mlflow_run_id | model_version | threshold |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rca_model (top-1 >= threshold) | 203 | 0 | 6 | 0 | 0 | 24 | 89.4 | 100.0 | 233 | 8d047e614f3941f795a2f8f638957328 | 3 | 0.31 |
| step2 detections | 5873 | 0 | 580 | 0 | 0 | 224 | 96.3 | 100.0 | 6677 | 8d047e614f3941f795a2f8f638957328 | 3 | 0.31 |

_2 row(s)_
