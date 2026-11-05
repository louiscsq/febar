# Model Serving endpoint

Captured 2026-11-05 16:35 UTC from workspace profile `febar` by `scripts/capture_evidence_step3.py`.

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
      "entity_version": "3",
      "workload_size": "Small",
      "scale_to_zero_enabled": true,
      "state": "ServedModelStateDeployment.DEPLOYMENT_READY"
    }
  ]
}
```

## Smoke test

Case `history_1m|NSW|20261014T0000|BH-NSW-0030` (a held-out backhaul case, 9 candidates) sent as `dataframe_records` with the model's 55 feature columns. The endpoint returns `predict_proba` `[p(not root), p(root)]` per candidate; ranking by `p(root)` gives the suspects.

## Request (first 2 of the records)

```json
{
  "dataframe_records": [
    {
      "level": 2.0,
      "log_n_desc_cells": 4.4426513,
      "n_children": 10.0,
      "n_impacted_cells": 4.0,
      "impacted_fraction": 0.04761905,
      "degraded_fraction": 0.04761905,
      "silent_fraction": 0.0,
      "coverage": 1.0,
      "child_max_coverage": 1.0,
      "impacted_children_fraction": 0.2,
      "parent_impacted_fraction": 0.31723028,
      "parent_coverage": 1.0,
      "lat_now": 0.5223184,
      "lat_slope5": -0.04314024,
      "lat_slope15": 0.005979712,
      "lat_vs_parent": 1.0571448,
      "loss_now": 1.661468,
      "loss_slope5": 0.11080295,
      "loss_slope15": 0.006658437,
      "loss_vs_parent": 1.6443729,
      "thr_now": -0.22269851,
      "thr_slope5": 0.021449009,
      "thr_slope15": 0.0001926987,
      "thr_vs_parent": 2.3842916,
      "rrc_now": -6.3187575,
      "rrc_slope5": -0.5854875,
      "rrc_slope15": 0.08438426,
      "rrc_vs_parent": 107.52131,
      "drop_now": 0.399636,
      "drop_slope5": 0.013941759,
      "drop_slope15": 0.0017170168,
      "drop_vs_parent": -46.73441,
      "attach_now": 98.58387,
      "attach_vs_parent": 26.59613,
      "avail_now": 98.78037,
      "prb_now": 37.20947,
      "prb_slope15": 0.018998433,
      "impacted_fraction_slope15": -8.503401e-05,
      "minutes_since_first_anomaly": 59.0,
      "n_alarms": 0.0,
      "n_critical_alarms": 0.0,
      "n_major_alarms": 0.0,
      "n_service_down_alarms": 0.0,
      "n_alarms_link": 0.0,
      "n_alarms_power": 0.0,
      "n_alarms_unreach": 0.0,
      "n_alarms_core": 0.0,
      "alarm_age_min": 0.0,
      "n_subtree_alarms": 3.0,
      "n_subtree_service_down_alarms": 1.0,
      "alarmed_children_fraction": 0.1,
      "parent_n_alarms": 1.0,
      "in_maintenance": 0.0,
      "log_case_impacted_cells": 1.3862944,
      "n_case_candidates": 9.0
    },
    {
      "level": 0.0,
      "log_n_desc_cells": 6.43294,
      "n_children": 1.0,
      "n_impacted_cells": 197.0,
      "impacted_fraction": 0.31723028,
      "degraded_fraction": 0.30756843,
      "silent_fraction": 0.009661836,
      "coverage": 1.0,
      "child_max_coverage": 1.0,
      "impacted_children_fraction": 1.0,
      "parent_impacted_fraction": null,
      "parent_coverage": null,
      "lat_now": -0.53482634,
      "lat_slope5": 0.004185525,
      "lat_slope15": -0.00063954934,
      "lat_vs_parent": null,
      "loss_now": 0.017095149,
      "loss_slope5": 0.018339746,
      "loss_slope15": 0.0010487866,
      "loss_vs_parent": null,
      "thr_now": -2.60699,
      "thr_slope5": -0.0017729044,
      "thr_slope15": -0.006792245,
      "thr_vs_parent": null,
      "rrc_now": -113.840065,
      "rrc_slope5": -0.33753586,
      "rrc_slope15": -0.21584472,
      "rrc_vs_parent": null,
      "drop_now": 47.134045,
      "drop_slope5": 0.09120216,
      "drop_slope15": 0.06494764,
      "drop_vs_parent": null,
      "attach_now": 71.98774,
      "attach_vs_parent": null,
      "avail_now": 70.018776,
      "prb_now": 27.9055,
      "prb_slope15": -0.0003096853,
      "impacted_fraction_slope15": 0.0003795728,
      "minutes_since_first_anomaly": 23.0,
      "n_alarms": 0.0,
      "n_critical_alarms": 0.0,
      "n_major_alarms": 0.0,
      "n_service_down_alarms": 0.0,
      "n_alarms_link": 0.0,
      "n_alarms_power": 0.0,
      "n_alarms_unreach": 0.0,
      "n_alarms_core": 0.0,
      "alarm_age_min": 0.0,
      "n_subtree_alarms": 256.0,
      "n_subtree_service_down_alarms": 241.0,
      "alarmed_children_fraction": 1.0,
      "parent_n_alarms": 0.0,
      "in_maintenance": 0.0,
      "log_case_impacted_cells": 1.3862944,
      "n_case_candidates": 9.0
    }
  ]
}
```

## Response (first 3 predictions)

```json
{
  "predictions": [
    [
      1.0,
      0.0
    ],
    [
      1.0,
      0.0
    ],
    [
      0.0,
      1.0
    ]
  ]
}
```

## Candidates ranked by endpoint p(root), with the ground truth and the training job's batch score

The endpoint and the batch scoring in the job give the same calibrated scores (same UC version). True roots among this case's candidates: ['BH-NSW-0030']; endpoint top-1: `BH-NSW-0030`.

```json
[
  {
    "element_id": "BH-NSW-0030",
    "element_type": "BACKHAUL_LINK",
    "p_root": 1.0,
    "is_root (ground truth)": "true",
    "batch_score (training job)": "1.0"
  },
  {
    "element_id": "SITE-NSW-00076",
    "element_type": "SITE",
    "p_root": 0.0689,
    "is_root (ground truth)": "false",
    "batch_score (training job)": "0.0689"
  },
  {
    "element_id": "SITE-NSW-00087",
    "element_type": "SITE",
    "p_root": 0.0002,
    "is_root (ground truth)": "false",
    "batch_score (training job)": "2.0E-4"
  },
  {
    "element_id": "AGG-NSW-03",
    "element_type": "AGG_ROUTER",
    "p_root": 0.0,
    "is_root (ground truth)": "false",
    "batch_score (training job)": "0.0"
  },
  {
    "element_id": "AMF-NSW-01",
    "element_type": "AMF_MME",
    "p_root": 0.0,
    "is_root (ground truth)": "false",
    "batch_score (training job)": "0.0"
  },
  {
    "element_id": "CELL-NSW-00076-4G1",
    "element_type": "CELL",
    "p_root": 0.0,
    "is_root (ground truth)": "false",
    "batch_score (training job)": "0.0"
  },
  {
    "element_id": "CELL-NSW-00076-4G2",
    "element_type": "CELL",
    "p_root": 0.0,
    "is_root (ground truth)": "false",
    "batch_score (training job)": "0.0"
  },
  {
    "element_id": "CELL-NSW-00076-4G3",
    "element_type": "CELL",
    "p_root": 0.0,
    "is_root (ground truth)": "false",
    "batch_score (training job)": "0.0"
  },
  {
    "element_id": "UPF-NSW-01",
    "element_type": "UPF_SGW",
    "p_root": 0.0,
    "is_root (ground truth)": "false",
    "batch_score (training job)": "0.0"
  }
]
```

## Latency from this laptop (client side, includes internet round trip)

- first call: 362 ms (may include a scale-from-zero start)
- 20 warm single-record calls: p50 296 ms, max 384 ms
