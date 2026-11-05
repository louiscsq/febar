# Step 3 evidence: root-cause model, serving and Lakebase

All files are text, captured on 2026-11-05 (UTC) from workspace profile `febar` by
`scripts/capture_evidence_step3.py`. SQL ran on the serverless warehouse; MLflow, the UC model registry, Model
Serving and Lakebase metadata came from the Databricks SDK.

Every number comes from the final code and the final model, **v4**: features rebuilt from scratch, the
whole-incident split embargo, and GT-free evaluation. After it, the frozen-model holdout evaluation, the
endpoint update, live scoring, the Lakebase sync and the latency check were all run again. Design, the
evaluation protocol and limits are in [`docs/rca_model.md`](../../docs/rca_model.md).

## Headline: fresh holdout `holdout_1m` (frozen model, evaluated once; scored faults only)

`holdout_1m` was generated after the design was frozen: new seed 4242 for faults, noise and defects, same
network, 2026-10-17 … 10-18. It went through the unchanged step-2 pipeline. Every case is scored GT-free first;
ground truth is matched to the ranked outputs afterwards. The primary comparison is step 2's heuristic ranked on
the **same cases**.

| measure | n | model v4 | step-2 heuristic, same cases | step-2 localisation (`eval_incident_detection`) |
|---|---|---|---|---|
| **top-1 accuracy** | 337 | **93.2 %** | 78.3 % | |
| **top-3 accuracy** | 337 | **95.3 %** | 80.7 % | |
| localised within 5 min (signed times) | 337 | **80.4 %** | 76.9 % | 65.6 % |
| pre-impact catches (alarm before impact start) | 337 | 35 | | |
| median time to correct localisation (signed) | 337 | 106 s | 116 s | 76 s (clipped at 0 by step 2) |
| **slow backhaul localised within 5 min** | 53 | **0 %** | 0 % | 0 % |
| **slow backhaul median time to correct localisation** | 53 | **615 s** | 727.5 s | 1,011 s |
| alert-level fault precision (secondary) | 395 / 14,028 alerts | 92.4 % | | 97.6 % (step-2 detections) |

- **Secondary framing:** step 2's *published*, region-wide `eval_rca_baseline` scores 27.9 % top-1 / 43.9 %
  top-3 on the holdout. Step 2's "58 % top-1" was that framing on the sparse 15-minute `history` run
  (19 incidents), so it is not a comparison point for these runs.
- **Where the model is not better** (holdout):
  - Ties with the heuristic on the same cases: router failures (87.5 %), AMF overloads (100 %), cell outages
    (95.2 % vs 94.7 %), site power top-3 (100 %).
  - Bushfire cluster (n = 1): missed at top-1 by both.
  - Cell outages, early catch: slower than step-2 localisation (median 98.5 s vs 51 s).
  - Alert precision: lower than step 2's.
  - Slow backhaul: never localised within 5 minutes.
- **Dev** (the old "test" days of `history_1m`, 2026-10-14 … 10-15, seen during design, so not a holdout,
  n = 355): top-1 94.1 % vs 80.8 %; top-3 96.6 % vs 83.9 %; within 5 min 83.7 %.
- **Live `stream` run** (n = 26): top-1 84.6 % vs 73.1 %.
- **Live open incidents** in Lakebase: 17, each with the true root of an in-flight fault as suspect #1.
- **Lakebase** PK lookup: p50 2.9 ms / p95 9.8 ms.

## Files

| file | content |
|---|---|
| [`01_training_run.md`](01_training_run.md) | training MLflow run ID, experiment, parameters (incl. embargo rule), all metrics (val / dev), artifacts; rows / positives / cases per split (train / val / dev); case labels per split; permutation feature importance; validation-day alert precision |
| [`02_evaluation.md`](02_evaluation.md) | evaluation protocol; **holdout** and **dev**: top-1 / top-3 by fault type with n (model vs heuristic on the same cases, step 2's published framing as a secondary column), early catch with signed times and pre-impact counts (model vs heuristic vs step-2 localisation), every slow-backhaul incident, alert-level precision; validation day; live run; step 2's published baseline per run; holdout top-1 misses |
| [`03_registered_model.md`](03_registered_model.md) | UC registered model, versions, `champion` alias (v4), version tags (threshold, dev and holdout top-1, holdout evaluation run), signature |
| [`04_serving_endpoint.md`](04_serving_endpoint.md) | endpoint state and config (serverless, scale to zero, v4); smoke test on a fresh-holdout backhaul case: request / response, endpoint vs batch scores and ground truth; client-side latency |
| [`05_lakebase.md`](05_lakebase.md) | Lakebase Provisioned instance; both synced tables (source, PK, TRIGGERED, state, last synced commit); latency check (p50 / p95 / p99 / max); row counts and sample rows read back from Postgres; PK lookup plan |
| [`06_live_scoring.md`](06_live_scoring.md) | `element_status` / `open_incidents` counts, states, open incidents with top-3 suspects, open incidents checked against the live run's ground truth (evidence only), element status sample, scored candidates per model version |
| [`07_pr3_review_notes.md`](07_pr3_review_notes.md) | the three PR #3 notes: Spark test of the late-data rule, signed evidence lag (negative lags shown), shared baseline-comparison code |

## What was run (final)

1. `banksia-rca-generate-training-history` (6 days of 1-minute history, `history_1m`) and the step-2 pipeline:
   from the first PR #4 revision, unchanged.
2. `banksia-rca-train` (`rebuild_features=true`). Training MLflow run `e40edbe6f9884c23ad9313f4e41f2845`;
   model v4 registered, `@champion`; threshold 0.32; val / dev evaluation.
3. `banksia-rca-generate-holdout` (`holdout_1m`, seed 4242, topology seed 42; topology checked identical, 1,887
   elements, 0 differences), then a `banksia-netmon-pipeline` update (COMPLETED; 4.0 M windows, 337 scored
   faults).
4. `banksia-rca-evaluate-holdout`, **once**, with the frozen v4 (evaluation MLflow run
   `b678bdd4d2c84591bdc4e1bfec61d5c2`).
5. Bundle deploy with `rca_model_version=4`: endpoint `banksia-rca-ranker` READY on v4.
6. `banksia-rca-score-live` (v4) → `MERGE` + TRIGGERED Lakebase sync; then `banksia-rca-lakebase-check`.
7. This capture (all files regenerated).

## Limitations recorded

- **No `CREATE CATALOG`** on the metastore. No Lakebase database catalog, so the synced tables are registered in
  the project catalog (`netmon_rca.lb_*`). The Postgres side is unaffected.
- **Matching picks the judged case.** Per-incident accuracy grades the matched case with the largest footprint
  overlap. Ground truth chooses *which* ranking is graded, never what is ranked.
- **Latency sources differ.** `04` latency is laptop → endpoint over the internet; `05` is from a serverless job.
- **Old live run.** The live run scored is the step-2 `stream` run (2026-10-08); no new live stream was started.
