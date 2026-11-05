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
level in the region, or service-down alarms. An alarmed element that is itself on another case's impacted
chain (e.g. a dark cell raising its own `CELL_OUT_OF_SERVICE`) belongs to that case only. Without this rule it
was pulled into every case under its router and outranked their true roots. In the test split the true root is among the candidates for
**97.5 %** of the incidents.

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
| train (10-10 … 10-12) | 1,537,924 | 50,655 | 56,307 |
| validation (10-13) | 538,552 | 25,547 | 27,242 |
| test (10-14 … 10-15) | 998,086 | 38,114 | 40,953 |

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

## Results vs the step-2 localiser

Final run: MLflow run `8d047e614f3941f795a2f8f638957328`, model version **3** (`@champion`), alert threshold
**0.31**. Held-out test days 2026-10-14 … 10-15, **n = 355 scored fault incidents**. Full
tables are in [`evidence/step3/02_evaluation.md`](../evidence/step3/02_evaluation.md).

Two step-2 references, both on the same incidents:

- **step-2 baseline**: `eval_rca_baseline` exactly as published. It ranks region-wide, in the first 15 minutes
  of impact, by impacted descendant cells. This is the localiser behind the "58 % top-1" figure, which was
  measured on the 19 incidents of the sparse 15-minute `history` run. On the dense 1-minute run it scores
  25.8 % over the whole run and 23.4 % on its test days top-1, because several faults are usually open in a region at once.
- **heuristic, same cases**: the same heuristic and filter applied to exactly the cases and candidates the
  model ranks. It separates the gain from the case framing (clusters instead of regions) from the gain from
  the model.

| test, n = 355 | n | model top-1 | step-2 baseline top-1 | heuristic, same cases top-1 | model top-3 | step-2 baseline top-3 | heuristic, same cases top-3 |
|---|---|---|---|---|---|---|---|
| **all faults** | 355 | **81.4 %** | 23.4 % | 76.1 % | **93.5 %** | 36.3 % | 85.1 % |
| CELL_OUTAGE | 205 | 78.5 % | 5.4 % | 74.1 % | 96.1 % | 14.6 % | 83.9 % |
| BACKHAUL_DEGRADATION | 55 | 76.4 % | 34.5 % | 67.3 % | 78.2 % | 49.1 % | 67.3 % |
| SITE_POWER_OUTAGE | 46 | 84.8 % | 21.7 % | 73.9 % | 93.5 % | 50.0 % | 95.7 % |
| AGG_ROUTER_FAILURE | 30 | 93.3 % | 83.3 % | 93.3 % | 100 % | 100 % | 100 % |
| AMF_OVERLOAD | 18 | 100 % | 100 % | 100 % | 100 % | 100 % | 100 % |
| LONG_HAUL_FIBRE_CUT | 1 | 100 % | 0 % | 100 % | 100 % | 100 % | 100 % |

The true root is among the model's candidates for 97.5 % of the test incidents (the ceiling for top-k).
Validation day (n = 158): model top-1 82.3 %, top-3 93.7 %.

**Early catch** (the model scores every 1-minute decision time; an incident counts as localised at the first
decision time whose top-1 is a valid root with calibrated score >= 0.31). Step 2 = `eval_incident_detection`
localisation (a detection or the rollup on a root):

| test, n = 355 | n | model localised | model within 5 min | model median | step 2 localised | step 2 within 5 min | step 2 median |
|---|---|---|---|---|---|---|---|
| **all faults** | 355 | 99.4 % | **83.7 %** | 92 s | 100 % | 79.2 % | 46 s |
| CELL_OUTAGE | 205 | 100 % | 97.6 % | 88 s | 100 % | 100 % | 36 s |
| **BACKHAUL_DEGRADATION** | 55 | 96.4 % | **5.5 %** | **618 s** | 100 % | 0 % | 1,020 s |
| SITE_POWER_OUTAGE | 46 | 100 % | 97.8 % | 104 s | 100 % | 97.8 % | 145 s |
| AGG_ROUTER_FAILURE | 30 | 100 % | 100 % | 0 s | 100 % | 100 % | 12 s |
| AMF_OVERLOAD | 18 | 100 % | 100 % | 0 s | 100 % | 0 % | 509 s |
| LONG_HAUL_FIBRE_CUT | 1 | 100 % | 100 % | 168 s | 100 % | 100 % | 228 s |

Model times are decision time minus impact start. The decision time is when all of a case's inputs had
arrived. Step 2's live pipeline latency (median 39 s) and the scoring time come on top. Step 2's rollup times
are a lower bound (MV refresh excluded).

**Slow backhaul degradation.** Of 55 held-out slowly worsening links, the model localises 3 (5.5 %) within 5 minutes of impact start; step 2 localises none. The median time to correct localisation is **618 s against 1,020 s** (about 6.7 minutes earlier), and 96.4 % are localised at all before the impact ends. Top-1 accuracy on them is 76.4 % (step 2: 34.5 %). The 5-minute target is still missed for almost all of them: in the first minutes of a 10-30 minute ramp the link's cells sit inside normal variation (see Known limits).

**Secondary: alert-level fault precision** (step 2's definitions and code, test days). Model alerts (case top-1 >= threshold, grouped per element with the 10-minute gap): **442 alerts, 93.3 % real faults** (393 TP, 28 unexplained, 21 planned work suppressed by the change calendar). Step 2's detections on the same days: 12,827 alerts, 96.1 %. The model pages far less often, about one page per incident instead of one per impacted element, at slightly lower precision.

**Live stream run** (2026-10-08, a different run, n = 26, censored excluded; out-of-run check, not
used for any choice): model top-1 80.8 % vs step-2 baseline 53.8 %, top-3 84.6 % vs
73.1 %.

**Where the model does not beat the baseline.** Top-1: no fault type is worse. For router failures (93.3 %) and AMF overloads (100 %), where the heuristic is already right, the model only equals the heuristic on the same cases. Top-3 for site power outages is slightly below it (93.5 % vs 95.7 %). In the early-catch mode the model is **slower than step 2 for cell outages** (median 88 s vs 36 s; 97.6 % vs 100 % within 5 minutes). Step 2 localises a cell outage the moment the cell's own detection lands, while the model waits for its windows to become visible and for the calibrated score to clear the threshold. Alert-level precision is lower than step 2's (93.3 % vs 96.1 %). Most of the gain over the published baseline comes from the case framing: the heuristic on the same cases already reaches 76.1 %. The model adds +5.3 points top-1 and +8.4 points top-3 on top of it.

**How clean the test split is.** The design was iterated locally on one region (WA) over all six days, with
WA's validation and test metrics visible. That led to the cluster cases, the heuristic's filter and
dropping class weights. After a first full run (model v2: top-1 50.4 %, top-3 84.8 % on the same test set),
the endpoint smoke test, run on a held-out case, showed the nearby-alarm attachment bug described under
*Candidates*. Fixing it gave the final v3. That fix came from reading one test case, not from tuning against
test metrics, but it is a design change made after seeing test data, and it is disclosed here. Hyperparameters, features and the threshold rule were not tuned against any test
number, and NSW, VIC and NQL test days (about 85 % of the test incidents) were not looked at before the final
run. The WA share of the test set is therefore not fully pristine.

## Serving

| path | what | why |
|---|---|---|
| **batch, in job** (`banksia-rca-score-live`) | builds the candidates of the live run, loads `models:/…rca_ranker@champion`, scores every candidate, writes `element_status` / `open_incidents`, triggers the Lakebase sync | the job already holds every candidate's features. Scoring a decision time takes milliseconds in-process, with no network hop, endpoint cold start or payload limits |
| **Model Serving endpoint** `banksia-rca-ranker` | serverless, `Small`, **scale to zero**, serves the same UC version | on-demand scoring by the step-5 app or other tools (re-rank one case's candidates, what-if). Idle costs nothing; the first call after idle pays a cold start |

The endpoint takes `dataframe_records` with the 55 feature columns (signature in UC) and returns
`predict_proba` `[p(not root), p(root)]`. Rank a case's candidates by `p(root)`. A smoke test with a held-out
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
- **Read latency** (from a serverless job, warm connection, 300 lookups each): PK lookup of `lb_element_status` p50 **3.4 ms**, p95 **10.3 ms**, p99 19.8 ms; open incidents of a region p50 3.1 ms / p95 8.8 ms; suspects joined to their status p50 3.1 ms / p95 6.9 ms (CU_1, 1,887 + 17 rows; `evidence/step3/05_lakebase.md`).

## Deploy and run

```bash
databricks bundle validate -t dev -p febar
databricks bundle deploy -t dev -p febar

databricks bundle run -p febar rca_generate_training_history   # 6 days of 1-minute labelled history
databricks bundle run -p febar netmon_pipeline                  # step-2 pipeline over the new run
databricks bundle run -p febar rca_train                        # features, MLflow, UC model, @champion, eval
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
- **Threshold choice.** F1 on validation picked 0.31 (v2 picked 0.18). A NOC that wants fewer pages would
  choose by a precision target instead and accept later early catches. The curve is logged.

## Workspace limitations

- **No `CREATE CATALOG`.** The workspace denies `CREATE CATALOG` on the metastore, so no Lakebase *database
  catalog* could be registered. The synced tables are registered in the project catalog instead
  (`telco_netmon_febar_catalog.netmon_rca.lb_*`), which Lakebase supports by naming the instance and logical
  database explicitly. Postgres access is unchanged.
- **Serving pins a version.** Bundle served entities take a model version, not an alias.
