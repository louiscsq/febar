# Step 3 evidence: root-cause model, serving and Lakebase

All files are text, captured on 2026-11-05 (UTC) from workspace profile `febar` by
`scripts/capture_evidence_step3.py`. SQL ran on the serverless warehouse; MLflow, the UC model registry,
Model Serving and Lakebase metadata came from the Databricks SDK. Every number comes from the final code
(model version 3): features were rebuilt from scratch in the final training run, then the endpoint, live
scoring, Lakebase sync and latency check were run again. Design and limits: [`docs/rca_model.md`](../../docs/rca_model.md).

## Headline (held-out test days 2026-10-14 … 10-15 of `history_1m`, scored faults only)

| measure | n | model (v3) | step-2 localiser |
|---|---|---|---|
| **top-1 accuracy** | 355 | **81.4 %** | 23.4 % as published (`eval_rca_baseline`); 76.1 % with its heuristic on the model's own cases |
| **top-3 accuracy** | 355 | **93.5 %** | 36.3 %; 85.1 % on the same cases |
| **slow backhaul: localised within 5 min** | 55 | **5.5 %** (3 of 55) | 0 % |
| **slow backhaul: median time to correct localisation** | 55 | **618 s** | 1,020 s |
| all faults localised within 5 min (early-catch mode) | 355 | 83.7 % | 79.2 % |
| alert-level fault precision (secondary) | 442 / 12,827 alerts | 93.3 % | 96.1 % |
| live `stream` run, top-1 (out-of-run check) | 26 | 80.8 % | 53.8 % |
| live open incidents whose suspect #1 is the true root | 17 | 17 | |
| Lakebase PK lookup p50 / p95 | 300 | 3.4 ms / 10.3 ms | |

- The step-2 "58 % top-1" was measured on the sparse 15-minute `history` run (19 incidents). On this dense
  1-minute run, with several faults usually open per region, the same heuristic scores 23.4 %. Run on the
  model's clustered cases instead of whole regions, it reaches 76.1 %. So most of the gain comes from the case
  framing, and the model adds +5.3 points top-1 and +8.4 points top-3 on top.
- **Where the model is not better**:
  - Router failures and AMF overloads: it only ties the heuristic on the same cases.
  - Site power outages, top-3: slightly below it (93.5 % vs 95.7 %).
  - Cell outages, early catch: slower than step 2 (median 88 s vs 36 s).
  - Alert precision: lower than step 2's (93.3 % vs 96.1 %).
  - Slow backhaul: still almost never localised within 5 minutes.
- Test-set hygiene: design iterations looked at WA's test days, and the final candidate fix came from
  inspecting a held-out smoke-test case. Both are disclosed in docs/rca_model.md ("How clean the test split is").

## Files

| file | content |
|---|---|
| [`01_training_run.md`](01_training_run.md) | MLflow run ID, experiment, parameters, all metrics, artifacts; rows / positives / cases per split; case labels per split; permutation feature importance; validation alert precision |
| [`02_evaluation.md`](02_evaluation.md) | top-1 / top-3 vs step 2 overall and by fault type with n; early catch vs step-2 localisation by fault type; every held-out backhaul incident; alert-level precision (model vs step-2 detections, same code); validation day; live run; step 2's published baseline per run; sample of top-1 misses |
| [`03_registered_model.md`](03_registered_model.md) | UC registered model, versions, `champion` alias, version tags (threshold), signature |
| [`04_serving_endpoint.md`](04_serving_endpoint.md) | endpoint state and config (serverless, scale to zero, version 3); smoke-test request / response for a held-out backhaul case; endpoint vs batch scores and ground truth; client-side latency |
| [`05_lakebase.md`](05_lakebase.md) | Lakebase Provisioned instance; both synced tables (source, PK, TRIGGERED, state, last synced commit); latency check (p50 / p95 / p99 / max); row counts and sample rows read back from Postgres; PK lookup plan |
| [`06_live_scoring.md`](06_live_scoring.md) | `element_status` / `open_incidents` row counts, states, open incidents with top-3 suspects, open incidents checked against the live run's ground truth (evidence only), element status sample, scored candidates per run |
| [`07_pr3_review_notes.md`](07_pr3_review_notes.md) | the three PR #3 notes: Spark test of the late-data rule, signed evidence lag (negative lags shown), shared baseline-comparison code |

## What was run

1. `banksia-rca-generate-training-history`: 6 days of 1-minute labelled history (`history_1m`, 12.0 M real-time
   windows, 982 scored faults), then `banksia-netmon-pipeline` (incremental update, COMPLETED), with the PR #3
   changes deployed.
2. `banksia-rca-train` (run with `rebuild_features=true`): features from scratch, train / calibrate /
   threshold, evaluation, MLflow run `8d047e614f3941f795a2f8f638957328`, model version 3, alias `champion`.
3. Bundle deploy with `rca_model_version=3`: endpoint `banksia-rca-ranker` READY on version 3.
4. `banksia-rca-score-live` on the live `stream` run: `MERGE` into `element_status` / `open_incidents`, then
   a TRIGGERED sync of both Lakebase synced tables.
5. `banksia-rca-lakebase-check`: psycopg + OAuth token, row counts, samples, 300 point lookups per query.
6. This capture.

## Limitations recorded

- **No `CREATE CATALOG`** on the metastore. No Lakebase database catalog could be created, so the synced tables
  are registered in the project catalog (`netmon_rca.lb_*`). The Postgres side is unaffected.
- Latency figures in `04` are from a laptop over the internet; the Lakebase figures in `05` are from a
  serverless job in the workspace.
- The live run scored is the step-2 `stream` run (2026-10-08); no new live stream was started for step 3.
