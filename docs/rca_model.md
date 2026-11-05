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
| `notebooks/06_rca_evaluate_holdout.py` | job `banksia-rca-evaluate-holdout`: frozen champion on `holdout_1m` (once) and the live run, GT-free scoring then matching |
| `notebooks/07_rca_any_alert_metric.py` | job `banksia-rca-any-alert-metric`: the non-oracle companion metric (any live alert correct at the SLA moment) on the frozen scores |
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
level in the region, or service-down alarms. An alarmed element that is itself on another case's impacted
chain (e.g. a dark cell raising its own `CELL_OUT_OF_SERVICE`) belongs to that case only. Without this rule it
was pulled into every case under its router and outranked their true roots. On the holdout, 95.8 % of the scored incidents had a matched case output at the SLA moment (the rest count as misses).

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

**Split by time**, never at random. Train on 2026-10-10 … 10-12. Validation on 10-13: calibration and the alert
threshold only. **Dev** on 10-14 … 10-15: seen during design, so not a holdout. Rows are assigned by decision
time. **Embargo:** every incident, of any class, belongs wholly to the split in which it starts (impact start,
else root-cause start). Every row matched to it in another split is dropped. So an incident starting in train
and running into validation contributes no validation rows, and one starting in validation contributes no dev
rows (tests cover both). The **held-out result** comes from a separate, later run, `holdout_1m` (see Results).

| split | candidate rows | positive rows | cases |
|---|---|---|---|
| train (10-10 … 10-12) | 1,537,924 | 50,655 | 56,307 |
| validation (10-13) | 433,028 | 21,783 | 23,493 |
| dev (10-14 … 10-15) | 845,723 | 35,869 | 39,032 |

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
metrics (validation and dev; the holdout and live run are scored by a separate frozen-model run), permutation feature importance (average precision on validation), the
threshold curve, every evaluation table, the feature list, and the model with signature and input example.
`pyfunc` returns `predict_proba`. The model is registered as
`telco_netmon_febar_catalog.netmon_rca.rca_ranker`. The job moves the alias **`champion`** to the new
version and tags it with `alert_threshold`, `train_run` and `dev_top1_pct`. The one-shot holdout evaluation
(`banksia-rca-evaluate-holdout`) adds `holdout_top1_pct` and `holdout_eval_run_id`.

## Results vs the step-2 localiser

**Final model:** `rca_ranker` **v4** (`@champion`), training MLflow run `e40edbe6f9884c23ad9313f4e41f2845`,
alert threshold **0.32** (validation F1). The design was frozen before the holdout was generated.
Every number below comes from `evidence/step3/02_evaluation.md`.

### How the evaluation is scored: GT-free first, ground truth after

1. **Score.** Every case of the run is ranked by the model. `evaluate.case_outputs` reads only the ID and
   feature columns and the score; label columns do not reach it. A test checks that removing or permuting
   them changes neither the outputs nor the evaluation. No incident ID, root list, footprint or fault type
   influences which cases or candidates are scored. Training labels, censoring filters and the split embargo
   apply to training and calibration only.
2. **Match.** The ranked outputs are then attributed to ground-truth incidents: same run and region,
   decision time in the incident window, case evidence (impacted cells, service-down-alarmed elements)
   overlapping the incident footprint. Per minute, the matched output with the largest overlap is the
   incident's *primary* output. Matching chooses which already-ranked output is judged; it never adds,
   removes or re-ranks a candidate.
3. **Top-1 / top-3.** The primary output at the first decision time at least 5 minutes after impact start
   (the SLA moment), looking up to 15 minutes. No output means a miss: 4.2 % of holdout incidents had no
   matched output in that window.
4. **Early catch.** Every 1-minute decision time from 5 minutes before impact start to impact end. An
   incident is localised at the first decision time whose primary output's top-1 is a valid root with
   calibrated score ≥ 0.32. Times are **signed** (`decision_ts − impact_start_ts`). Catches before the impact
   are negative, counted separately, and included in the median. "Within 5 min" means signed time ≤ 300 s.

The **step-2 heuristic** (`eval_rca_baseline`: ≥ 80 % of descendant cells impacted or a service-down alarm,
then most impacted cells, then higher in the tree) is ranked on **exactly the same case outputs**. That is the
primary comparison. Step 2's *published* `eval_rca_baseline` ranks a whole region in the first 15 minutes of
impact, a different and much weaker framing. It is shown only as a secondary, clearly labelled column. Step 2's
"58 % top-1" is that published figure on the sparse 15-minute `history` run (19 incidents), so it is not a
comparison point for these dense 1-minute runs.

**Why these numbers are higher than in the first PR #4 revision.** That evaluation pooled the candidates of
every case attributed to an incident (attribution done with ground truth *before* ranking), and took each
candidate's maximum score over 20 minutes. Early, briefly high scores of wrong candidates then won. Judging one
GT-free case ranking at the SLA moment removes both effects. The old numbers (top-1 81.4 % for v3) are not
comparable and are superseded.

### Held-out result: `holdout_1m`

A fresh 1-minute run, generated after the design was frozen: new seed 4242 for faults, noise and DQ defects,
same network (`topology_seed` 42, verified identical), 2026-10-17 … 10-18. It ran through the unchanged step-2
pipeline under its own run id and was evaluated **once** by `banksia-rca-evaluate-holdout` (evaluation MLflow
run `b678bdd4d2c84591bdc4e1bfec61d5c2`). n = 337 scored faults.

| holdout, n = 337 | n | **model top-1** | **heuristic, same cases top-1** | model top-3 | heuristic, same cases top-3 | *step 2 published, region-wide top-1 / top-3* |
|---|---|---|---|---|---|---|
| **all faults** | 337 | **93.2 %** | 78.3 % | **95.3 %** | 80.7 % | *27.9 % / 43.9 %* |
| CELL_OUTAGE | 187 | 95.2 % | 94.7 % | 96.3 % | 94.7 % | *7.0 % / 21.4 %* |
| BACKHAUL_DEGRADATION | 53 | **86.8 %** | 3.8 % | 86.8 % | 3.8 % | *41.5 % / 64.2 %* |
| AGG_ROUTER_FAILURE | 40 | 87.5 % | 87.5 % | 95.0 % | 92.5 % | *82.5 % / 95.0 %* |
| SITE_POWER_OUTAGE | 38 | 97.4 % | 84.2 % | 100 % | 100 % | *23.7 % / 50.0 %* |
| AMF_OVERLOAD | 17 | 100 % | 100 % | 100 % | 100 % | *100 % / 100 %* |
| BUSHFIRE_GRID_OUTAGE | 1 | 0 % | 0 % | 100 % | 0 % | *0 % / 0 %* |
| LONG_HAUL_FIBRE_CUT | 1 | 100 % | 100 % | 100 % | 100 % | *0 % / 0 %* |

| holdout early catch, n = 337 | n | model localised | **model within 5 min** | model pre-impact catches | **model median (signed)** | heuristic, same cases within 5 min / median | step-2 localisation within 5 min / median |
|---|---|---|---|---|---|---|---|
| **all faults** | 337 | 99.4 % | **80.4 %** | 35 | **106 s** | 76.9 % / 116 s | 65.6 % / 76 s |
| CELL_OUTAGE | 187 | 99.5 % | 94.7 % | 0 | 98.5 s | 93.6 % / 97 s | 100 % / 51 s |
| **BACKHAUL_DEGRADATION** | 53 | 98.1 % | **0 %** | 0 | **615 s** | 0 % / 727.5 s | 0 % / 1,011 s |
| AGG_ROUTER_FAILURE | 40 | 100 % | 97.5 % | 26 | −12 s | 85.0 % / 193 s | 30.0 % / 392.5 s |
| SITE_POWER_OUTAGE | 38 | 100 % | 97.4 % | 0 | 156 s | 84.2 % / 152.5 s | 57.9 % / 195 s |
| AMF_OVERLOAD | 17 | 100 % | 100 % | 9 | −113 s | 100 % / 204 s | 0 % / 514 s |
| BUSHFIRE_GRID_OUTAGE | 1 | 100 % | 0 % | 0 | 759 s | 0 % / 8,019 s | 0 % / 8,010 s |
| LONG_HAUL_FIBRE_CUT | 1 | 100 % | 100 % | 0 | 236 s | 100 % / 176 s | 0 % / 416 s |

- Pre-impact catches are real. Router failures raise `NODE_DOWN` and AMF overloads raise core alarms before
  the generator's `impact_start_ts` (cells degrade 1–3 min after the root fails). The model names the root from
  those alarms. They are counted, not clipped.
- Step-2 times are step 2's own `localisation_ttd_s`, which step 2 clips at 0 and which is a lower bound for the
  rollup path (MV refresh excluded). The heuristic on the same cases has no score threshold; its top-1 counts as
  soon as it is a root. Step 2's median live pipeline latency of 39 s comes on top of every system's time.
- **Slow backhaul degradation** (n = 53): **no system localises any within 5 minutes.** The model's median time
  to correct localisation is 615 s, against 1,011 s for step 2 and 727.5 s for the heuristic on the same cases.
  Top-1 accuracy at the SLA moment is 86.8 % (heuristic on the same cases: 3.8 %). The heuristic's filter needs
  ≥ 80 % of a link's cells impacted, and a degrading link flags about 30 %.
- **Non-oracle companion: any live alert correct at the SLA moment** (`evaluate.any_alert_at_sla`, job
  `banksia-rca-any-alert-metric` on the frozen v4 scores). Top-1 above judges the case output that ground truth
  picked by footprint overlap, with no score threshold. The companion uses no footprint: at the same fixed
  decision time (first decision time ≥ impact start + 5 min), is **any** live alert of the incident's region (a
  case whose top-1 score ≥ 0.32) naming a valid root? **Holdout 81.0 %** (top-1 93.2 % on the same 337
  incidents), **dev 83.9 %** (94.1 %). It matches top-1 for cell outages (95.2 %), site power (97.4 %), router
  failures (87.5 %) and AMF overloads (100 %). The whole gap is **slow backhaul: 9.4 %** (top-1 86.8 %): at 5
  minutes the right link is ranked first in its case but has not cleared the alert threshold yet, which is the
  early-catch result again (0 % within 5 min). A region has a median of 5 live alerts at that minute.
- **Secondary, alert-level fault precision** (step 2's definitions and code): model 395 alerts, **92.4 %** real
  faults. Step-2 detections over the same days: 14,028 alerts, 97.6 %. The model pages about once per incident,
  not once per impacted element, at lower precision.

**Where the model does not beat the heuristic on the same cases (holdout).**
- Router failures: equal top-1 (87.5 %).
- AMF overloads: equal (100 %).
- Site power outages: equal top-3 (100 %).
- Cell outages: practically equal (95.2 % vs 94.7 %).
- The single bushfire cluster is a top-1 miss for both.
- Early-catch median time for site power outages: slightly slower (156 s vs 152.5 s).
- Against step-2 localisation, the model is slower for cell outages (median 98.5 s vs 51 s; 94.7 % vs 100 %
  within 5 min). Step 2 localises a cell outage the moment the cell's own detection lands. The model waits for
  its windows to become visible and the score to clear the threshold.
- Alert precision is lower than step 2's (92.4 % vs 97.6 %).

### Dev set (seen during design: not a holdout)

The last two days of `history_1m` (2026-10-14 … 10-15, n = 355). These were the "test" days of the first PR #4
revision. They were inspected while the design was iterated: the cluster cases, the heuristic's filter,
dropping class weights, and the nearby-alarm candidate fix, found on one of their cases. They are therefore
reported only as **dev**. Model v4: top-1 94.1 % (heuristic, same cases 80.8 %), top-3 96.6 % (83.9 %); within
5 min 83.7 %, median 93 s signed. Slow backhaul: 5.5 % within 5 min, median 618 s. Alert precision 93.3 %.
The validation day (n = 158) chose the calibration and the threshold: top-1 92.4 % (75.9 %).

**Live stream run** (2026-10-08, out-of-run check, n = 26, censored incidents not scored): model top-1 84.6 %,
heuristic on the same cases 73.1 %, step 2 published 53.8 %.

## Serving

| path | what | why |
|---|---|---|
| **batch, in job** (`banksia-rca-score-live`) | builds the candidates of the live run, loads `models:/…rca_ranker@champion`, scores every candidate, writes `element_status` / `open_incidents`, triggers the Lakebase sync | the job already holds every candidate's features. Scoring a decision time takes milliseconds in-process, with no network hop, endpoint cold start or payload limits |
| **Model Serving endpoint** `banksia-rca-ranker` | serverless, `Small`, **scale to zero**, serves the same UC version | on-demand scoring by the step-5 app or other tools (re-rank one case's candidates, what-if). Idle costs nothing; the first call after idle pays a cold start |

The endpoint takes `dataframe_records` with the 55 feature columns (signature in UC) and returns
`predict_proba` `[p(not root), p(root)]`. Rank a case's candidates by `p(root)`. A smoke test with a fresh-holdout
backhaul case and its request / response is in `evidence/step3/04_serving_endpoint.md`. The endpoint pins a
version (`rca_model_version` in `databricks.yml`, since served entities take a version, not an alias). After
retraining, set it to the new `champion` version and redeploy.

**Open incidents** (`live.open_incidents`). A case alerts when its top-1 score is at least the threshold.
Alerts on one element are grouped with step 2's alert rule (a new alert after a 10-minute gap). An incident is
open while its alert is active at the latest decision time. `detected_ts` is when that alert started; the
suspects are the top-3 candidates of the case at the latest decision time.
**Element status** (`live.element_status`): per element, `down` (≥ 80 % of descendant cells silent or a
service-down alarm), `degraded` (≥ 50 % impacted), `impacted`, `alarm` or `ok`, with counts, the highest
root-cause score and the open incident the element is a suspect of.

## Lakebase

- **Flavour: Lakebase Provisioned** (`resources/rca.lakebase.yml`, instance `banksia-netmon-lakebase`,
  `CU_1`, Postgres 16). Both Provisioned and Autoscaling APIs respond on this workspace. Provisioned was
  chosen because the bundle declares its **synced tables** natively (`synced_database_tables`), so the whole
  Delta → Postgres path is code. Autoscaling's scale-to-zero would suit an idle demo better and is the
  natural next step once its synced tables are bundle-managed.
- **Synced tables** (`resources/rca.synced_tables.yml`). `netmon_rca.element_status` (PK `element_id`) and
  `netmon_rca.open_incidents` (PK `incident_id`) are Delta tables with Change Data Feed. They are written by
  `MERGE`, deleting rows that are no longer current (cleared incidents). They sync in **TRIGGERED** mode into
  Postgres database `netmon_serving`, schema `netmon_rca`, tables `lb_element_status` / `lb_open_incidents`.
  The scoring job starts a sync after every `MERGE`. Triggered rather than continuous: the source changes
  once per scoring run, and continuous sync would run (and bill) a pipeline all the time.
- **No secrets.** `notebooks/05_lakebase_check.py` connects with **psycopg** using a one-hour OAuth token from
  `generate_database_credential` and the job's own identity. It creates the database (`stage=setup`) and runs
  the read-latency check (`stage=check`). Nothing in the repo holds a password, token or connection string.
- **Read latency** (from a serverless job, warm connection, 300 lookups each): PK lookup of `lb_element_status` p50 **2.9 ms**, p95 **9.8 ms**, p99 18.6 ms; open incidents of a region p50 2.7 ms / p95 6.9 ms; suspects joined to their status p50 2.4 ms / p95 8.6 ms (CU_1, 1,887 + 17 rows; `evidence/step3/05_lakebase.md`).

## Deploy and run

```bash
databricks bundle validate -t dev -p febar
databricks bundle deploy -t dev -p febar

databricks bundle run -p febar rca_generate_training_history   # 6 days of 1-minute labelled history
databricks bundle run -p febar netmon_pipeline                  # step-2 pipeline over the new run
databricks bundle run -p febar rca_train                        # features, MLflow, UC model, @champion, val/dev eval
databricks bundle run -p febar rca_generate_holdout             # fresh holdout (new seed, same network, later days)
databricks bundle run -p febar netmon_pipeline                  # step-2 pipeline over the holdout
databricks bundle run -p febar rca_evaluate_holdout             # frozen champion on the holdout, once
databricks bundle run -p febar rca_any_alert_metric             # non-oracle companion metric (frozen scores)
databricks bundle run -p febar rca_lakebase_check --params stage=setup
databricks bundle run -p febar rca_score_live                   # element_status / open_incidents (+ sync)
# set rca_model_version to the champion version, then deploy again (endpoint + synced tables)
databricks bundle deploy -t dev -p febar
databricks bundle run -p febar rca_score_live                   # first sync into Lakebase
databricks bundle run -p febar rca_lakebase_check               # read-latency check
python scripts/capture_evidence_step3.py --profile febar --warehouse <id>
```

`scripts/rca_fetch_local.py` downloads one run / region of inputs to Parquet so you can iterate on features
offline (`train.build_features` / `train.train_and_evaluate` run unchanged on a laptop).

## Known limits

- **One synthetic network, one fault density.** Train and test come from the same generator at 200× fault
  rates. Real networks need retraining on their own incident history, with real link counters (the link trend
  features here come from the link's cells).
- **Slow backhaul ramps stay hard.** Over the first minutes, a link ramping over 10–30 minutes looks like
  normal variation at the cell level. The model localises them much earlier than step 2 but rarely within 5
  minutes. Link-level telemetry (interface errors, RSL, utilisation) would be the real fix.
- **Pointwise ranking.** Top-3 is high but top-1 confuses a root with its own descendant or ancestor
  (a dark site against one of its cells, a cell outage against its site). A pairwise / listwise ranker or
  explicit parent / child contrast features would help.
- **Concurrency.** Cases are clusters, but faults that overlap in one cluster (e.g. two outages under one
  partly-impacted link) share one ranking.
- **Live scoring is a job, not a stream.** `banksia-rca-score-live` scores the latest state when it runs. For
  a 1-minute cadence, schedule it every minute against the continuous pipeline or move the scoring into a
  streaming `foreachBatch`. The live run scored here is the step-2 `stream` run (2026-10-08). No new live
  stream was started for step 3.
- **Watermark tail.** The real-time 1-minute windows are append-only behind a 2-minute event-time watermark,
  so a run's last minutes only appear once a later run's data moves the watermark. `history_1m` gained its last
  4.2 k windows when the holdout was ingested; the holdout's own last minutes are still pending.
- **Matching picks the judged case.** The per-incident numbers judge the matched case with the largest overlap
  with the footprint. That is ground truth deciding *which* ranking to grade, never what is ranked. A NOC
  seeing several clusters for one fault would still have to pick, and alert precision measures the pages it gets.
- **Threshold choice.** F1 on validation picked 0.32 for v4. A NOC that wants fewer pages would
  choose by a precision target instead and accept later early catches. The curve is logged.

## Workspace limitations

- **No `CREATE CATALOG`.** The workspace denies `CREATE CATALOG` on the metastore, so no Lakebase *database
  catalog* could be registered. The synced tables are registered in the project catalog instead
  (`telco_netmon_febar_catalog.netmon_rca.lb_*`), which Lakebase supports by naming the instance and logical
  database explicitly. Postgres access is unchanged.
- **Serving pins a version.** Bundle served entities take a model version, not an alias.
