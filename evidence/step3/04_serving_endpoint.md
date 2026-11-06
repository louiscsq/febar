# Model Serving endpoint

Captured 2026-11-06 08:03 UTC from workspace profile `febar` by `scripts/capture_evidence_step3.py`.

## Endpoint

```json
{
  "name": "banksia-rca-ranker",
  "state": {
    "ready": "EndpointStateReady.READY",
    "config_update": "EndpointStateConfigUpdate.NOT_UPDATING"
  },
  "served_entities": [
    {
      "name": "rca-ranker",
      "entity_name": "telco_netmon_febar_catalog.netmon_rca.rca_ranker",
      "entity_version": "5",
      "workload_size": "Small",
      "scale_to_zero_enabled": true,
      "state": "ServedModelStateDeployment.DEPLOYMENT_READY"
    }
  ]
}
```

## Smoke test

Case `holdout_1m|NSW|20261017T0102|CELL-NSW-00086-4G1` (a fresh-holdout backhaul case, 6 candidates) sent as `dataframe_records` with the model's 55 feature columns. The endpoint returns `predict_proba` `[p(not root), p(root)]` per candidate; ranking by `p(root)` gives the suspects.

## Request (first 2 of the records)

```json
{
  "dataframe_records": [
    {
      "level": 2.0,
      "log_n_desc_cells": 4.4426513,
      "n_children": 10.0,
      "n_impacted_cells": 11.0,
      "impacted_fraction": 0.13095239,
      "degraded_fraction": 0.13095239,
      "silent_fraction": 0.0,
      "coverage": 1.0,
      "child_max_coverage": 1.0,
      "impacted_children_fraction": 0.2,
      "parent_impacted_fraction": 0.040257648,
      "parent_coverage": 1.0,
      "lat_now": 5.6470084,
      "lat_slope5": 0.52606535,
      "lat_slope15": 0.05861181,
      "lat_vs_parent": 4.59729,
      "loss_now": 14.029293,
      "loss_slope5": 1.558054,
      "loss_slope15": 0.16091599,
      "loss_vs_parent": 10.356172,
      "thr_now": -0.68513376,
      "thr_slope5": -0.08231131,
      "thr_slope15": -0.00666,
      "thr_vs_parent": -0.44686007,
      "rrc_now": -2.3430777,
      "rrc_slope5": -0.2883121,
      "rrc_slope15": -0.029388348,
      "rrc_vs_parent": -0.12285447,
      "drop_now": 3.4960415,
      "drop_slope5": 0.41126487,
      "drop_slope15": 0.041733798,
      "drop_vs_parent": 2.5809758,
      "attach_now": 99.8014,
      "attach_vs_parent": 0.32123566,
      "avail_now": 100.0,
      "prb_now": 41.51006,
      "prb_slope15": 0.03740508,
      "impacted_fraction_slope15": 0.0002976192,
      "minutes_since_first_anomaly": 31.0,
      "n_alarms": 0.0,
      "n_critical_alarms": 0.0,
      "n_major_alarms": 0.0,
      "n_service_down_alarms": 0.0,
      "n_alarms_link": 0.0,
      "n_alarms_power": 0.0,
      "n_alarms_unreach": 0.0,
      "n_alarms_core": 0.0,
      "alarm_age_min": 0.0,
      "n_subtree_alarms": 8.0,
      "n_subtree_service_down_alarms": 0.0,
      "alarmed_children_fraction": 0.2,
      "parent_n_alarms": 0.0,
      "in_maintenance": 0.0,
      "log_case_impacted_cells": 0.6931472,
      "n_case_candidates": 6.0
    },
    {
      "level": 0.0,
      "log_n_desc_cells": 6.43294,
      "n_children": 1.0,
      "n_impacted_cells": 25.0,
      "impacted_fraction": 0.040257648,
      "degraded_fraction": 0.040257648,
      "silent_fraction": 0.0,
      "coverage": 1.0,
      "child_max_coverage": 1.0,
      "impacted_children_fraction": 1.0,
      "parent_impacted_fraction": null,
      "parent_coverage": null,
      "lat_now": 1.0497185,
      "lat_slope5": 0.05990091,
      "lat_slope15": 0.01291831,
      "lat_vs_parent": null,
      "loss_now": 3.6731212,
      "loss_slope5": 0.23040321,
      "loss_slope15": 0.028569024,
      "loss_vs_parent": null,
      "thr_now": -0.23827368,
      "thr_slope5": 0.017580738,
      "thr_slope15": -0.0007318775,
      "thr_vs_parent": null,
      "rrc_now": -2.2202232,
      "rrc_slope5": -0.030755615,
      "rrc_slope15": -0.028253645,
      "rrc_vs_parent": null,
      "drop_now": 0.9150657,
      "drop_slope5": 0.061935045,
      "drop_slope15": 0.00717562,
      "drop_vs_parent": null,
      "attach_now": 99.48016,
      "attach_vs_parent": null,
      "avail_now": 99.67196,
      "prb_now": 42.86568,
      "prb_slope15": 0.028457683,
      "impacted_fraction_slope15": 0.00012077285,
      "minutes_since_first_anomaly": 32.0,
      "n_alarms": 0.0,
      "n_critical_alarms": 0.0,
      "n_major_alarms": 0.0,
      "n_service_down_alarms": 0.0,
      "n_alarms_link": 0.0,
      "n_alarms_power": 0.0,
      "n_alarms_unreach": 0.0,
      "n_alarms_core": 0.0,
      "alarm_age_min": 0.0,
      "n_subtree_alarms": 18.0,
      "n_subtree_service_down_alarms": 2.0,
      "alarmed_children_fraction": 0.0,
      "parent_n_alarms": 0.0,
      "in_maintenance": 0.0,
      "log_case_impacted_cells": 0.6931472,
      "n_case_candidates": 6.0
    }
  ]
}
```

## Response (first 3 predictions)

```json
{
  "predictions": [
    [
      0.9998764669549104,
      0.00012353304508956145
    ],
    [
      1.0,
      0.0
    ],
    [
      0.20588235294117652,
      0.7941176470588235
    ]
  ]
}
```

## Candidates ranked by endpoint p(root), with the ground truth and the holdout job's batch score

The endpoint and the batch scoring in the job give the same calibrated scores (same UC version). True roots among this case's candidates: ['BH-NSW-0037']; endpoint top-1: `BH-NSW-0037`.

```json
[
  {
    "element_id": "BH-NSW-0037",
    "element_type": "BACKHAUL_LINK",
    "p_root": 0.7941,
    "is_root (ground truth)": true,
    "batch_score (holdout job)": 0.7941
  },
  {
    "element_id": "CELL-NSW-00086-4G1",
    "element_type": "CELL",
    "p_root": 0.0719,
    "is_root (ground truth)": false,
    "batch_score (holdout job)": 0.0719
  },
  {
    "element_id": "SITE-NSW-00086",
    "element_type": "SITE",
    "p_root": 0.0719,
    "is_root (ground truth)": false,
    "batch_score (holdout job)": 0.0719
  },
  {
    "element_id": "AGG-NSW-03",
    "element_type": "AGG_ROUTER",
    "p_root": 0.0001,
    "is_root (ground truth)": false,
    "batch_score (holdout job)": 0.0001
  },
  {
    "element_id": "AMF-NSW-01",
    "element_type": "AMF_MME",
    "p_root": 0.0,
    "is_root (ground truth)": false,
    "batch_score (holdout job)": 0.0
  },
  {
    "element_id": "UPF-NSW-01",
    "element_type": "UPF_SGW",
    "p_root": 0.0,
    "is_root (ground truth)": false,
    "batch_score (holdout job)": 0.0
  }
]
```

## Latency from this laptop (client side, includes internet round trip)

- first call: 355 ms (may include a scale-from-zero start)
- 20 warm single-record calls: p50 344 ms, max 610 ms
