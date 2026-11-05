# Root-cause ranking model, serving and Lakebase

Step 3 of the Banksia Mobile NOC build. Given what the NOC can see when customer impact is detected, a
trained gradient-boosted model (not an LLM) ranks the candidate network elements by how likely each one is the
root cause. The model is tracked in MLflow, registered in Unity Catalog with a `champion` alias, and served on
a serverless Model Serving endpoint. The live element status and the open incidents with their top-3
suspects are written to Lakebase for the step-5 topology app. Proof that all of this ran on the workspace is in
[`evidence/step3/`](../evidence/step3/).

- [Overview](#overview)
- [Training data](#training-data): run, cases, candidates, features, labels, split
- [Model](#model): choice and trade-offs, calibration, alert threshold
- [Results vs the step-2 localiser](#results-vs-the-step-2-localiser)
- [Serving](#serving)
- [Lakebase](#lakebase)
- [Deploy and run](#deploy-and-run)
- [Known limits](#known-limits)
- [Workspace limitations](#workspace-limitations)

## Overview

```
 gold_cell_health_1m (on-time windows) ┐
 silver_alarms (by arrival time)       ├─► netmon_pipeline.rca.features ─► rca_candidate_features
 silver_topology_nodes, maintenance    ┘     (cases x candidates, decision time t)        │
 eval_gt_incidents ──► rca.labels (is_root, case_label) ──► rca_training_labels ◄──────────┤
                                                                                          ▼
              rca.model: HistGradientBoostingClassifier + isotonic calibration ─► MLflow run ─► UC model
                                                         telco_netmon_febar_catalog.netmon_rca.rca_ranker@champion
                                                                         │                     │
            notebooks/04_rca_score_live.py (batch, in job) ◄─────────────┘                     ▼
              │  element_status, open_incidents (Delta, CDF)              Model Serving: banksia-rca-ranker
              ▼  synced tables (TRIGGERED)                                (serverless, scale to zero)
 Lakebase Provisioned banksia-netmon-lakebase / database netmon_serving / schema netmon_rca
```

| code | what |
|---|---|
| `src/netmon_pipeline/rca/features.py` | cases, candidate generation, detection-time features (`FEATURE_COLUMNS`), `LABEL_COLUMNS` that may never be features |
| `src/netmon_pipeline/rca/labels.py` | ground-truth matching, `case_label`, `is_root` |
| `src/netmon_pipeline/rca/model.py` | time split with embargo, training, calibration, alert threshold, permutation importance |
| `src/netmon_pipeline/rca/evaluate.py` | top-1 / top-3, early catch, alert-level precision with step 2's `scoring` code |
| `src/netmon_pipeline/rca/train.py` | end-to-end training + evaluation (job and local) |
| `src/netmon_pipeline/rca/live.py` | `open_incidents`, `element_status` |
| `src/netmon_pipeline/rca/sources.py` | the SQL for every input (one run, one region) |
| `notebooks/03_rca_train.py` | job `banksia-rca-train`: features, labels, MLflow, UC registration, evaluation tables |
| `notebooks/04_rca_score_live.py` | job `banksia-rca-score-live`: batch scoring of the live run, Delta MERGE, Lakebase sync trigger |
| `notebooks/05_lakebase_check.py` | job `banksia-rca-lakebase-check`: Postgres database setup, psycopg + OAuth read-latency check |
| `resources/rca.*.yml` | jobs, Lakebase instance, synced tables, serving endpoint (bundle) |
| `tests/test_rca_features.py`, `tests/test_rca_live.py` | leakage, timing, candidates, labels, split, evaluation, live outputs |
