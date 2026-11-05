# Training run (MLflow)

Captured 2026-11-05 17:33 UTC from workspace profile `febar` by `scripts/capture_evidence_step3.py`.

## Run

- MLflow run ID: `e40edbe6f9884c23ad9313f4e41f2845`
- experiment: `/Shared/banksia_netmon/rca_ranker` (`688671173720819`)
- status: `FINISHED`, started 2026-11-05 17:15 UTC, 4.6 min
- registered model: `telco_netmon_febar_catalog.netmon_rca.rca_ranker` version `4` (alias `champion`)
- training job wall time (features + training + evaluation + registration): 16.3 min

## Parameters

```json
{
  "alert_threshold": "0.32",
  "decision_step_minutes": "1",
  "dev_start": "2026-10-14 00:00:00+00:00",
  "hgb_early_stopping": "False",
  "hgb_l2_regularization": "1.0",
  "hgb_learning_rate": "0.05",
  "hgb_max_iter": "400",
  "hgb_max_leaf_nodes": "31",
  "hgb_min_samples_leaf": "40",
  "hgb_random_state": "7",
  "model_type": "sklearn HistGradientBoostingClassifier + isotonic calibration (validation days)",
  "n_features": "55",
  "positives_dev": "35869",
  "positives_train": "50655",
  "positives_val": "21783",
  "rows_dev": "845723",
  "rows_train": "1537924",
  "rows_val": "433028",
  "split_embargo": "each incident wholly in the split of its start; its rows elsewhere dropped",
  "train_run": "history_1m",
  "val_start": "2026-10-13 00:00:00+00:00"
}
```

## Metrics (val = calibration / threshold day, dev = last two training-run days, seen during design; the held-out holdout_1m result is in 02_evaluation.md)

```json
{
  "dev_alert_precision_pct": 93.3,
  "dev_backhaul_median_signed_s": 618.0,
  "dev_backhaul_n": 55.0,
  "dev_backhaul_within_5min_pct": 5.5,
  "dev_baseline_top1_pct": 23.4,
  "dev_heuristic_same_cases_top1_pct": 80.8,
  "dev_heuristic_same_cases_top3_pct": 83.9,
  "dev_n_incidents": 355.0,
  "dev_top1_pct": 94.1,
  "dev_top3_pct": 96.6,
  "dev_within_5min_pct": 83.7,
  "val_alert_precision_pct": 89.4,
  "val_backhaul_median_signed_s": 564.0,
  "val_backhaul_n": 25.0,
  "val_backhaul_within_5min_pct": 4.0,
  "val_baseline_top1_pct": 23.4,
  "val_heuristic_same_cases_top1_pct": 75.9,
  "val_heuristic_same_cases_top3_pct": 82.3,
  "val_n_incidents": 158.0,
  "val_top1_pct": 92.4,
  "val_top3_pct": 94.9,
  "val_within_5min_pct": 82.3
}
```

## Artifacts

```text
[
  "feature_columns.json",
  "evaluation",
  "evaluation/dev_accuracy.csv",
  "evaluation/dev_alert_precision.csv",
  "evaluation/dev_early_catch.csv",
  "evaluation/dev_early_catch_summary.csv",
  "evaluation/dev_ranking.csv",
  "evaluation/feature_importance.csv",
  "evaluation/split_counts.csv",
  "evaluation/threshold_curve.csv",
  "evaluation/val_accuracy.csv",
  "evaluation/val_alert_precision.csv",
  "evaluation/val_early_catch.csv",
  "evaluation/val_early_catch_summary.csv",
  "evaluation/val_ranking.csv"
]
```

## Rows, positives and cases per split

Censored incidents are excluded from training before the split. Embargo: every incident (any class) belongs wholly to the split it starts in; its rows in any other split are dropped. These labels are for training and calibration only; the evaluation scores every case GT-free.

```sql
SELECT split, count(*) AS candidate_rows, count_if(is_root) AS positive_rows,
               count(DISTINCT case_id) AS cases, min(decision_ts) AS first_decision, max(decision_ts) AS last_decision
        FROM telco_netmon_febar_catalog.netmon_rca.rca_training_labels GROUP BY split ORDER BY min(decision_ts)
```

| split | candidate_rows | positive_rows | cases | first_decision | last_decision |
|---|---|---|---|---|---|
| train | 1537924 | 50655 | 56307 | 2026-10-10T01:02:00.000Z | 2026-10-12T23:59:00.000Z |
| val | 433028 | 21783 | 23493 | 2026-10-13T00:00:00.000Z | 2026-10-13T23:59:00.000Z |
| dev | 845723 | 35869 | 39032 | 2026-10-14T00:00:00.000Z | 2026-10-16T00:01:00.000Z |

_3 row(s)_

## Case labels per split

```sql
SELECT split, case_label, count(DISTINCT case_id) AS cases FROM telco_netmon_febar_catalog.netmon_rca.rca_training_labels
        GROUP BY ALL ORDER BY 1, 2
```

| split | case_label | cases |
|---|---|---|
| dev | fault | 34531 |
| dev | none | 3062 |
| dev | planned | 1439 |
| train | fault | 49736 |
| train | none | 4235 |
| train | planned | 2319 |
| train | red_herring | 17 |
| val | fault | 21339 |
| val | none | 1461 |
| val | planned | 693 |

_10 row(s)_

## Feature importance (permutation, average precision, validation sample)

```sql
SELECT feature, round(importance_mean, 5) AS importance_mean, round(importance_std, 5) AS importance_std
        FROM telco_netmon_febar_catalog.netmon_rca.rca_feature_importance ORDER BY importance_mean DESC LIMIT 25
```

| feature | importance_mean | importance_std |
|---|---|---|
| coverage | 0.06208 | 6.8E-4 |
| level | 0.03688 | 1.1E-4 |
| impacted_children_fraction | 0.03304 | 9.3E-4 |
| parent_impacted_fraction | 0.02326 | 0.00127 |
| impacted_fraction | 0.02298 | 4.8E-4 |
| n_subtree_service_down_alarms | 0.02042 | 9.3E-4 |
| n_children | 0.01098 | 4.4E-4 |
| drop_now | 0.01038 | 6.5E-4 |
| attach_now | 0.01032 | 5.5E-4 |
| in_maintenance | 0.00805 | 1.8E-4 |
| degraded_fraction | 0.00728 | 9.0E-5 |
| n_critical_alarms | 0.00722 | 4.9E-4 |
| minutes_since_first_anomaly | 0.00706 | 8.1E-4 |
| n_alarms_core | 0.0064 | 1.3E-4 |
| thr_vs_parent | 0.00607 | 3.1E-4 |
| avail_now | 0.00603 | 4.8E-4 |
| loss_now | 0.00559 | 1.1E-4 |
| n_alarms | 0.00541 | 6.2E-4 |
| prb_now | 0.00531 | 2.5E-4 |
| alarm_age_min | 0.00527 | 6.7E-4 |
| alarmed_children_fraction | 0.00496 | 3.2E-4 |
| n_impacted_cells | 0.00434 | 1.9E-4 |
| prb_slope15 | 0.00423 | 3.2E-4 |
| child_max_coverage | 0.00414 | 1.2E-4 |
| lat_now | 0.00397 | 1.7E-4 |

_25 row(s)_

## Validation-day alert-level precision at the chosen threshold

The threshold itself was chosen by validation F1 on case top-1 (threshold_curve.csv artifact); this is the validation alert-level precision at that threshold.

```sql
SELECT * FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_val_alert_precision
```

| system | fault | censored | planned_suppressed | planned_fp | red_herring | unexplained | fault_precision_pct | maintenance_suppression_pct | n_alerts | mlflow_run_id | model_version | threshold |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rca_model (top-1 >= threshold) | 203 | 0 | 6 | 0 | 0 | 24 | 89.4 | 100.0 | 233 | e40edbe6f9884c23ad9313f4e41f2845 | 4 | 0.32 |
| step2 detections | 5873 | 0 | 580 | 0 | 0 | 224 | 96.3 | 100.0 | 6677 | e40edbe6f9884c23ad9313f4e41f2845 | 4 | 0.32 |

_2 row(s)_
