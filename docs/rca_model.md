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

## Training data

**Run.** A dedicated labelled history at the live granularity: `history_1m` (job
`banksia-rca-generate-training-history`), 6 days (2026-10-10 … 10-15 UTC), `small` network (1,431 cells,
same seed and topology as steps 1–2), **1-minute** KPIs, fault-rate multiplier 200, DQ defects on. The step-2
`history` run has 15-minute KPIs and 16 faults, which can neither train a model nor show anything happening
inside 5 minutes. The new run goes through the unchanged step-2 pipeline as its own `source_run`. It starts
after the step-2 runs because the real-time health windows are append-only behind an event-time watermark.
It yields 12.0 M real-time 1-minute cell windows and 982 scored fault incidents (customer-impacting,
uncensored; batch runs are never censored). History and live runs stay separate everywhere: every query is
for one `source_run`, and the live `stream` run is used only for an out-of-run check and for live scoring.

**Cases** (`features.py`). A case is one impact cluster at one 1-minute decision time `t`. A cell counts as
impacted when one of its last 3 visible real-time windows is degraded (step 2's rules), or when it has had no
window for 2 minutes (dark). Impacted cells are grouped under their **highest ancestor of which at least 50 %
of the cells are impacted**. Every step uses observed data only. Two cell outages under one router are
two cases. A router failure, an AMF overload or a degraded link becomes one case. A service-down alarm with no
impacted cells nearby (a dark site that only raises `NE_UNREACHABLE`) forms its own case. Per-region cases
were tried first and ranked the root of a *different* concurrent incident too often. At this fault density a
region usually has several incidents open at once.

**Candidates**: every ancestor of the case's impacted cells (the cell, site, backhaul link, aggregation
router, UPF, AMF), plus alarmed elements nearby: active alarms under one of the case's routers, above router
level in the region, or service-down alarms. In the test split the true root is among the candidates for
**{{root_in_candidates}}** of the incidents.

**Features** (`FEATURE_COLUMNS`, 55). Everything the NOC could see at `t`:

| group | features |
|---|---|
| element | `level` (element type), `log_n_desc_cells`, `n_children` |
| hierarchy fan-out | `impacted_fraction`, `degraded_fraction`, `silent_fraction`, `n_impacted_cells`, `coverage` (share of the case's impacted cells under the element), `child_max_coverage`, `impacted_children_fraction`, `parent_impacted_fraction`, `parent_coverage` |
| KPI deviation from baseline | mean z-score over descendant cells of latency, loss, DL throughput, RRC success, drop rate (`*_now`, last 3 windows) and vs the parent (`*_vs_parent`); attach success, availability, PRB utilisation |
| trends (short look-back) | least-squares slope per minute over the last 5 and 15 windows of each z-score (`*_slope5`, `*_slope15`), of PRB utilisation and of the impacted fraction. For a backhaul link these are the link's latency and utilisation trend (the generator has no link counters, so they come from the link's cells) |
| alarms | on the element: count, CRITICAL / MAJOR, service-down, by category (link, power, unreachable, core), age of the oldest; in the subtree; on the parent; share of children alarmed |
| time | `minutes_since_first_anomaly` (first minute in the last hour with at least half the current impact) |
| context | `in_maintenance` (change calendar), case size, number of candidates |

*No ground truth, no future.* Inputs are the real-time tables only: `gold_cell_health_1m` (on-time records,
step 2's late-data rule), `silver_alarms` by arrival time (`evidence_ts`), topology and the change calendar.
A window or alarm is used at `t` only if it had **arrived** by `t`. Each row carries `feature_evidence_ts`,
the latest arrival among the records it was built from. Tests (`tests/test_rca_features.py`) check:
`FEATURE_COLUMNS` and the ID columns contain none of `LABEL_COLUMNS`; `feature_evidence_ts <= decision_ts`
on every row; a record that arrives after `t`, even with an absurd value, leaves the features at `t`
unchanged; an alarm whose RAISE has not arrived is not counted; and 15-minute input is rejected.

**Labels** (`labels.py`). A case is matched to a ground-truth incident of the same run and region when the
incident footprint contains one of the case's impacted cells (or service-down-alarmed elements), with `t` in
`[impact_start − 5 min, impact_end + 10 min]`. `is_root` = the candidate is in that incident's
`root_element_ids` (any listed site or link counts for bushfire and cyclone clusters). `case_label` uses step
2's priority: fault, censored, planned, red herring, none. **Cases overlapping a censored incident are
dropped** from training and scoring. Cases without a fault (noise, red herrings, planned work) stay in as
all-negative cases, so scores learn not to fire on them.

**Split by time**, never at random. Train on 2026-10-10 … 10-12, validation on 10-13 (calibration and
alert threshold only), test on 10-14 … 10-15 (never used for a choice). Rows are assigned by decision time,
with an embargo: a row matched to an incident that starts in a later split is dropped, so no incident is seen
in two splits.

| split | candidate rows | positive rows | cases |
|---|---|---|---|
{{split_table}}

## Model

**Choice.** scikit-learn `HistGradientBoostingClassifier`, pointwise: *is this candidate a root?* Candidates
are ranked per case by score. Why:

- It handles missing values natively. A cell with no visible window, a root with no parent, or a slope over too
  few points is common here, and imputing it would invent information.
- It trains in minutes on 1.5 M rows and adds no dependency to the serverless jobs or the serving container.
- It outputs a probability that isotonic calibration (fitted on the validation day, frozen ranker) makes
  meaningful *across* cases. The early-warning mode needs that to compare one threshold across cases. A
  LambdaRank objective (LightGBM / XGBoost `rank:ndcg`) optimises the in-case order directly, but its scores
  are only comparable within a case, so alerting would need a second model.
- Trade-off: pointwise training does not see the competing candidates directly. The case-relative features
  (`coverage`, `child_max_coverage`, `parent_coverage`, case size) give it that context.

Hyperparameters are fixed (`model.PARAMS`: 400 trees, learning rate 0.05, 31 leaves, min 40 samples per leaf,
L2 1.0) and were not tuned on any split. Class weighting was dropped: positives are about 4 % of candidates,
ranking only needs an order, calibration fixes the probabilities, and sklearn's sample-weight path made
training about 20× slower.

**Alert threshold.** A case alerts when its top-1 calibrated score is at least the threshold. The threshold is
chosen on the validation day only, by the best F1 of "the alerted top-1 is a true root" (precision over
alerting cases, recall over fault cases). The curve is logged as `evaluation/threshold_curve.csv`.

**MLflow and UC.** Experiment `/Shared/banksia_netmon/rca_ranker`. The run logs parameters, split sizes,
metrics (validation, test, live), permutation feature importance (average precision on validation), the
threshold curve, every evaluation table, the feature list, and the model with signature and input example.
`pyfunc` returns `predict_proba`. The model is registered as
`telco_netmon_febar_catalog.netmon_rca.rca_ranker`. The job moves the alias **`champion`** to the new
version and tags it with `alert_threshold`, `train_run` and `test_top1_pct`.
