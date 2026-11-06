# Training run (MLflow)

Captured 2026-11-06 08:01 UTC from workspace profile `febar` by `scripts/capture_evidence_step3.py`.

## Run

- MLflow run ID: `24cf7981a0304b0f8e51eb7b0a2943fc`
- experiment: `/Shared/banksia_netmon/rca_ranker` (`688671173720819`)
- status: `FINISHED`, started 2026-11-06 07:20 UTC, 4.9 min
- registered model: `telco_netmon_febar_catalog.netmon_rca.rca_ranker` version `5` (alias `champion`)
- training job wall time (features + training + evaluation + registration): 15.5 min

## Parameters

```json
{
  "alert_threshold": "0.27",
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
  "positives_train": "50660",
  "positives_val": "21783",
  "rows_dev": "845733",
  "rows_train": "1538108",
  "rows_val": "433029",
  "split_embargo": "each incident wholly in the split of its start; its rows elsewhere dropped",
  "train_run": "history_1m",
  "val_start": "2026-10-13 00:00:00+00:00"
}
```

## Metrics (val = calibration / threshold day, dev = last two training-run days, seen during design; the held-out holdout_1m result is in 02_evaluation.md)

```json
{
  "dev_alert_precision_pct": 93.8,
  "dev_any_alert_correct_pct": 83.9,
  "dev_backhaul_median_signed_s": 618.0,
  "dev_backhaul_n": 55.0,
  "dev_backhaul_within_5min_pct": 5.5,
  "dev_baseline_top1_pct": 23.4,
  "dev_heuristic_same_cases_top1_pct": 80.8,
  "dev_heuristic_same_cases_top3_pct": 83.9,
  "dev_n_incidents": 355.0,
  "dev_top1_pct": 94.1,
  "dev_top3_pct": 96.3,
  "dev_within_5min_pct": 83.7,
  "val_alert_precision_pct": 91.8,
  "val_any_alert_correct_pct": 82.9,
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
  "evaluation/dev_any_alert.csv",
  "evaluation/dev_any_alert_summary.csv",
  "evaluation/dev_early_catch.csv",
  "evaluation/dev_early_catch_summary.csv",
  "evaluation/dev_ranking.csv",
  "evaluation/feature_importance.csv",
  "evaluation/split_counts.csv",
  "evaluation/threshold_curve.csv",
  "evaluation/val_accuracy.csv",
  "evaluation/val_alert_precision.csv",
  "evaluation/val_any_alert.csv",
  "evaluation/val_any_alert_summary.csv",
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
| train | 1538108 | 50660 | 56307 | 2026-10-10T01:02:00.000Z | 2026-10-12T23:59:00.000Z |
| val | 433029 | 21783 | 23493 | 2026-10-13T00:00:00.000Z | 2026-10-13T23:59:00.000Z |
| dev | 845733 | 35869 | 39032 | 2026-10-14T00:00:00.000Z | 2026-10-16T00:01:00.000Z |

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
| coverage | 0.04567 | 0.00135 |
| level | 0.02618 | 5.5E-4 |
| parent_impacted_fraction | 0.02438 | 7.8E-4 |
| impacted_children_fraction | 0.02325 | 2.1E-4 |
| n_subtree_service_down_alarms | 0.02261 | 5.7E-4 |
| impacted_fraction | 0.01983 | 9.0E-5 |
| n_children | 0.01267 | 1.8E-4 |
| attach_now | 0.01212 | 1.1E-4 |
| n_critical_alarms | 0.00905 | 4.5E-4 |
| n_impacted_cells | 0.00858 | 2.5E-4 |
| prb_now | 0.00815 | 4.1E-4 |
| degraded_fraction | 0.00776 | 9.0E-5 |
| thr_vs_parent | 0.00759 | 3.4E-4 |
| drop_now | 0.00723 | 1.5E-4 |
| n_alarms | 0.0069 | 2.7E-4 |
| minutes_since_first_anomaly | 0.00634 | 4.2E-4 |
| in_maintenance | 0.00599 | 1.8E-4 |
| n_service_down_alarms | 0.00554 | 0.00126 |
| loss_now | 0.00543 | 2.5E-4 |
| lat_now | 0.0052 | 1.3E-4 |
| n_alarms_core | 0.00513 | 4.0E-5 |
| alarmed_children_fraction | 0.00464 | 3.0E-4 |
| n_alarms_unreach | 0.0041 | 1.3E-4 |
| prb_slope15 | 0.00405 | 2.0E-5 |
| child_max_coverage | 0.00397 | 1.5E-4 |

_25 row(s)_

## Validation-day alert-level precision at the chosen threshold

The threshold itself was chosen by validation F1 on case top-1 (threshold_curve.csv artifact); this is the validation alert-level precision at that threshold.

```sql
SELECT * FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_val_alert_precision
```

| system | fault | censored | planned_suppressed | planned_fp | red_herring | unexplained | fault_precision_pct | maintenance_suppression_pct | n_alerts | mlflow_run_id | model_version | threshold |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rca_model (top-1 >= threshold) | 202 | 0 | 6 | 0 | 0 | 18 | 91.8 | 100.0 | 226 | 24cf7981a0304b0f8e51eb7b0a2943fc | 5 | 0.27 |
| step2 detections | 5873 | 0 | 580 | 0 | 0 | 224 | 96.3 | 100.0 | 6677 | 24cf7981a0304b0f8e51eb7b0a2943fc | 5 | 0.27 |

_2 row(s)_
