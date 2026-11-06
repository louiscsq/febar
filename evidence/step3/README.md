# Step 3 evidence: root-cause model, serving and Lakebase

All files are text, captured on 2026-11-05 and, after the PR #6 alarm ID fix, regenerated on 2026-11-06 (UTC) from workspace profile `febar` by
`scripts/capture_evidence_step3.py`. SQL ran on the serverless warehouse; MLflow, the UC model registry, Model
Serving and Lakebase metadata came from the Databricks SDK.

Every number comes from the final code and the final model, **v5**: the frozen v4 design (features rebuilt from
scratch, the whole-incident split embargo, GT-free evaluation) retrained once in PR #6 on corrected data. After
it, the frozen-model holdout re-score, the endpoint update, live scoring, the Lakebase sync and the latency check
were all run again.

**PR #6.** Incident alarm IDs repeated between batch runs, so silver's cross-run dedupe had dropped 5,417 of the
holdout's alarm IDs and 90 of `history_1m`'s (89 on a train day). IDs are now run-scoped; both runs were
regenerated (identical except IDs) and their alarm feeds replaced; the model was retrained once (training data was
affected) and the holdout re-scored once. Before / after counts and every old-vs-new table:
[`08_alarm_id_fix.md`](08_alarm_id_fix.md). Design, the
evaluation protocol and limits are in [`docs/rca_model.md`](../../docs/rca_model.md).

## Headline: fresh holdout `holdout_1m` (frozen design; re-scored once after the PR #6 fix; scored faults only)

`holdout_1m` was generated after the design was frozen: new seed 4242 for faults, noise and defects, same
network, 2026-10-17 … 10-18. It went through the unchanged step-2 pipeline. Every case is scored GT-free first;
ground truth is matched to the ranked outputs afterwards. The primary comparison is step 2's heuristic ranked on
the **same cases**.

| measure | n | old: model v4, alarms missing | **new: model v5, corrected** | step-2 heuristic, same cases (old / new) | step-2 localisation (`eval_incident_detection`, old / new) |
|---|---|---|---|---|---|
| **top-1 accuracy** | 337 | 93.2 % | **94.7 %** | 78.3 % / 78.3 % | |
| **top-3 accuracy** | 337 | 95.3 % | **95.5 %** | 80.7 % / 80.7 % | |
| any live alert correct at the SLA moment (non-oracle: no footprint matching, score ≥ threshold) | 337 | 81.0 % | **82.5 %** (slow backhaul 9.4 %) | | |
| localised within 5 min (signed times) | 337 | 80.4 % | **80.7 %** | 76.9 % / 78.3 % | 65.6 % / 78.6 % |
| pre-impact catches (alarm before impact start) | 337 | 35 | 42 | | |
| median time to correct localisation (signed) | 337 | 106 s | 92.5 s | 116 s / 99 s | 76 s / 46 s (clipped at 0 by step 2) |
| **slow backhaul localised within 5 min** | 53 | 0 % | **0 %** | 0 % / 0 % | 0 % / 0 % |
| **slow backhaul median time to correct localisation** | 53 | 615 s | **619 s** | 727.5 s / 727.5 s | 1,011 s / 1,011 s |
| alert-level fault precision (secondary) | 395 → 377 / 14,342 alerts | 92.4 % | **95.1 %** | | 97.6 % / 97.7 % (step-2 detections) |

- **Secondary framing:** step 2's *published*, region-wide `eval_rca_baseline` scores 27.9 % top-1 / 43.9 %
  top-3 on the holdout. Step 2's "58 % top-1" was that framing on the sparse 15-minute `history` run
  (19 incidents), so it is not a comparison point for these runs.
- **Where the model is not better** (holdout, v5):
  - Ties with the heuristic on the same cases: AMF overloads (100 %), cell outages (95.7 % vs 94.7 %), site power
    top-3 (100 %), router failures within 5 min (97.5 %).
  - Bushfire cluster (n = 1): missed at top-1 by both.
  - Early catch slower than step-2 localisation for cell outages (median 88.5 s vs 35 s), site power (150 s vs
    130.5 s) and router failures (−13.5 s vs 2 s, both 100 % within 5 min). With the alarms restored, step 2's
    alarm-driven localisation gained most (within 5 min 65.6 % → 78.6 %).
  - Alert precision: lower than step 2's.
  - Slow backhaul: never localised within 5 minutes.
- **Dev** (the old "test" days of `history_1m`, 2026-10-14 … 10-15, seen during design, so not a holdout,
  n = 355): top-1 94.1 % vs 80.8 %; top-3 96.3 % vs 83.9 % (v4: 96.6 %); within 5 min 83.7 %; any live alert
  correct at the SLA moment 83.9 %. Validation top-1 92.4 % for both v4 and v5.
- **Live `stream` run** (n = 26): top-1 84.6 % vs 73.1 %.
- **Live open incidents** in Lakebase (re-scored with v5): 17, each with the true root of an in-flight fault as
  suspect #1.
- **Lakebase** PK lookup: p50 3.1 ms / p95 11.9 ms (v4 capture: 2.9 / 9.8 ms).

## Files

| file | content |
|---|---|
| [`01_training_run.md`](01_training_run.md) | training MLflow run ID, experiment, parameters (incl. embargo rule), all metrics (val / dev), artifacts; rows / positives / cases per split (train / val / dev); case labels per split; permutation feature importance; validation-day alert precision |
| [`02_evaluation.md`](02_evaluation.md) | evaluation protocol; **holdout** and **dev**: top-1 / top-3 by fault type with n (model vs heuristic on the same cases, step 2's published framing as a secondary column), the non-oracle "any live alert correct at the SLA moment" companion next to the matched top-1, early catch with signed times and pre-impact counts (model vs heuristic vs step-2 localisation), every slow-backhaul incident, alert-level precision; validation day; live run; step 2's published baseline per run; holdout top-1 misses |
| [`03_registered_model.md`](03_registered_model.md) | UC registered model, versions, `champion` alias (v5), version tags (threshold, dev and holdout top-1, holdout evaluation run), signature |
| [`04_serving_endpoint.md`](04_serving_endpoint.md) | endpoint state and config (serverless, scale to zero, v5); smoke test on a fresh-holdout backhaul case: request / response, endpoint vs batch scores and ground truth; client-side latency |
| [`05_lakebase.md`](05_lakebase.md) | Lakebase Provisioned instance; both synced tables (source, PK, TRIGGERED, state, last synced commit); latency check (p50 / p95 / p99 / max); row counts and sample rows read back from Postgres; PK lookup plan |
| [`06_live_scoring.md`](06_live_scoring.md) | `element_status` / `open_incidents` counts, states, open incidents with top-3 suspects, open incidents checked against the live run's ground truth (evidence only), element status sample, scored candidates per model version |
| [`08_alarm_id_fix.md`](08_alarm_id_fix.md) | PR #6: the defect, retraining decision, alarms per run before / after (bronze, silver, quarantine, injected duplicates, missing IDs), and old (v4, alarms missing) vs new (v5, corrected) for holdout, dev and validation: top-1 / top-3, any-alert, early catch, alert precision; step-2 TTD and baseline old vs new |
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
8. Step 4 (PR #5) follow-up to the PR #4 review: job `banksia-rca-any-alert-metric` computed the non-oracle
   companion metric on the frozen v4 scores (nothing retrained), and `02_evaluation.md` was regenerated
   (`--only evaluation`, 2026-11-05 23:47 UTC). The other files are unchanged.

9. **PR #6** (2026-11-06): generator fix (run-unique alarm / change IDs); `banksia-rca-generate-training-history`
   and `banksia-rca-generate-holdout` re-run into the `staging` volume (same seeds and windows);
   `banksia-netmon-replace-run-feeds` (verify, then swap + delete superseded rows + incremental pipeline update);
   `banksia-rca-train` (v5, `@champion`, threshold 0.27, training MLflow run `24cf7981a0304b0f8e51eb7b0a2943fc`);
   `banksia-rca-evaluate-holdout` **once** with v5 (evaluation MLflow run `d58a5f8893df4d37b7835be9877811df`);
   `banksia-rca-any-alert-metric`; bundle deploy with `rca_model_version=5`; `banksia-rca-score-live` (v5);
   `banksia-rca-lakebase-check`. Files 01–06 and 08 regenerated; 07 unchanged.

## Limitations recorded

- **No `CREATE CATALOG`** on the metastore. No Lakebase database catalog, so the synced tables are registered in
  the project catalog (`netmon_rca.lb_*`). The Postgres side is unaffected.
- **Matching picks the judged case.** Per-incident accuracy grades the matched case with the largest footprint
  overlap. Ground truth chooses *which* ranking is graded, never what is ranked.
- **Latency sources differ.** `04` latency is laptop → endpoint over the internet; `05` is from a serverless job.
- **Old live run.** The live run scored is the step-2 `stream` run (2026-10-08); no new live stream was started.
