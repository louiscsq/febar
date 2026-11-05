# Registered model in Unity Catalog

Captured 2026-11-05 16:33 UTC from workspace profile `febar` by `scripts/capture_evidence_step3.py`.

## Registered model

```json
{
  "full_name": "telco_netmon_febar_catalog.netmon_rca.rca_ranker",
  "owner": "louis.chen@databricks.com",
  "description": "Banksia NOC root-cause ranker: scores every candidate element of a customer-impact case (an impact cluster at a 1-minute decision time) as the likely root cause. Input: the detection-time features in feature_columns.json; output: predict_proba [p(not root), p(root)], calibrated. Rank candidates of a case by p(root). See docs/rca_model.md.",
  "aliases": [
    {
      "alias": "champion",
      "version": 3
    }
  ]
}
```

## Versions

```json
[
  {
    "version": 3,
    "status": "ModelVersionInfoStatus.READY",
    "run_id": "8d047e614f3941f795a2f8f638957328",
    "created": "2026-11-05T16:18:00.157000+00:00",
    "storage_location": "s3://telco-netmon-febar-ext-s3-049629455384-rs1bkj/models/7af9e89c-d6dc-466e-9e62-64d6afd9db38/versions/2a5c59ee-7cbe-4a19-93d1-08967f1ccde9"
  },
  {
    "version": 2,
    "status": "ModelVersionInfoStatus.READY",
    "run_id": "c27218685b0f44169533d72e9ebd334d",
    "created": "2026-11-05T15:37:51.042000+00:00",
    "storage_location": "s3://telco-netmon-febar-ext-s3-049629455384-rs1bkj/models/7af9e89c-d6dc-466e-9e62-64d6afd9db38/versions/c358c39c-2052-4491-99c1-ad5f796493d1"
  },
  {
    "version": 1,
    "status": "ModelVersionInfoStatus.READY",
    "run_id": "8b6f31176b1249c4b89107ef1045fdfd",
    "created": "2026-11-05T14:54:38.152000+00:00",
    "storage_location": "s3://telco-netmon-febar-ext-s3-049629455384-rs1bkj/models/7af9e89c-d6dc-466e-9e62-64d6afd9db38/versions/86c776a8-c8a6-42be-ab72-58a06b9a9418"
  }
]
```

## champion version tags

```json
{
  "alert_threshold": "0.31",
  "test_top1_pct": "81.4",
  "train_run": "history_1m"
}
```

## Signature (inputs -> outputs)

```text
inputs: 
  ['level': double (required), 'log_n_desc_cells': double (required), 'n_children': double (required), 'n_impacted_cells': double (required), 'impacted_fraction': double (required), 'degraded_fraction': double (required), 'silent_fraction': double (required), 'coverage': double (required), 'child_max_coverage': double (required), 'impacted_children_fraction': double (required), 'parent_impacted_fraction': double (optional), 'parent_coverage': double (optional), 'lat_now': double (required), 'lat_slope5': double (required), 'lat_slope15': double (required), 'lat_vs_parent': double (optional), 'loss_now': double (required), 'loss_slope5': double (required), 'loss_slope15': double (required), 'loss_vs_parent': double (optional), 'thr_now': double (required), 'thr_slope5': double (required), 'thr_slope15': double (required), 'thr_vs_parent': double (optional), 'rrc_now': double (required), 'rrc_slope5': double (required), 'rrc_slope15': double (required), 'rrc_vs_parent': double (optional), 'drop_now': double (required), 'drop_slope5': double (required), 'drop_slope15': double (required), 'drop_vs_parent': double (optional), 'attach_now': double (required), 'attach_vs_parent': double (optional), 'avail_now': double (required), 'prb_now': double (required), 'prb_slope15': double (required), 'impacted_fraction_slope15': double (required), 'minutes_since_first_anomaly': double (required), 'n_alarms': double (required), 'n_critical_alarms': double (required), 'n_major_alarms': double (required), 'n_service_down_alarms': double (required), 'n_alarms_link': double (required), 'n_alarms_power': double (required), 'n_alarms_unreach': double (required), 'n_alarms_core': double (required), 'alarm_age_min': double (required), 'n_subtree_alarms': double (required), 'n_subtree_service_down_alarms': double (required), 'alarmed_children_fraction': double (required), 'parent_n_alarms': double (required), 'in_maintenance': double (required), 'log_case_impacted_cells': double (required), 'n_case_candidates': double (required)]
outputs: 
  [Tensor('float64', (-1, 2))]
params: 
  None

```
