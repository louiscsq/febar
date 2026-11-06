# Step 4 evidence: Gen AI NOC assistant, customer SMS drafts, AI Gateway

All files are text (no MLflow store or trace files are committed: traces live in the workspace experiment `/Shared/banksia_netmon/noc_assistant`, referenced by run ID), captured on 2026-11-06 (UTC) from workspace profile `febar` from the final code (prompts
`noc_summary_v3`, `sms_v1`, context `ctx-v1`): `scripts/capture_evidence_step4.py` (01, 02, 03, 04, 05, 07, 08, 09, 10; 02–05 and 07–10 regenerated after the
PR #6 alarm ID fix),
`scripts/genai_early_example.py` (03b) and `scripts/genai_guardrail_tests.py` (06). The last two call the live
endpoint. System tables on this workspace are account-wide, so every system-table query is filtered to this
workspace's ID and the assistant endpoint. Design, protocol and limits: [`docs/genai_assistant.md`](../../docs/genai_assistant.md).

## Headline

PR #6 fixed an upstream defect (incident alarm IDs repeated across batch runs, so silver's dedupe had dropped about
20 % of the holdout's alarms, `09`). The data was re-ingested, the ranker retrained once (v5), the evaluation set
rebuilt, dev re-run and the holdout re-run **once** with the same frozen prompts (`force=true`, reason recorded).
Old = PR #5 (published), new = PR #6 (`10_holdout_rerun.md`).

| | dev old (n = 346) | **dev new** | holdout old (n = 323) | **holdout new** |
|---|---|---|---|---|
| assistant root-cause agreement | 97.1 % | **96.8 %** | 82.0 % | **97.5 %** |
| ranker's top-1 alone, same contexts | 96.5 % | 96.5 % | 97.2 % | 98.8 % |
| ranker misses fixed / correct answers turned wrong / turned uncertain | 3 / 0 / 1 | 3 / 2 / 0 | 2 / 18 / 33 | 0 / 2 / 2 |
| hallucinated root before the guard (repaired) | 0.0 % | 0.0 % | 1.9 % | 0.0 % |
| unknown element ID in raw output (scrubbed) | 2.6 % | 5.2 % | 3.1 % | 5.0 % |
| groundedness (judge) / SMS guidelines (judge) | 81.8 % / 99.7 % | 80.9 % / 99.4 % | 78.6 % / 98.8 % | 79.6 % / 99.1 % |
| SMS final drafts compliant / LLM drafts compliant at first try | 100 % / 98.3 % | 100 % / 97.4 % | 100 % / 98.5 % | 100 % / 99.7 % |
| latency per incident p50 / p95 | 6.4 s / 8.0 s | 6.0 s / 7.3 s | 6.6 s / 7.9 s | 6.3 s / 7.4 s |
| tokens per incident in / out | 4,896 / 772 | 4,887 / 776 | 4,705 / 791 | 4,824 / 759 |

With the alarms restored, the holdout contexts carrying an active alarm go from 159 to 315 of 323 and the assistant
recovers to near the ranker, but stays **below** it on the holdout (97.5 % vs 98.8 %, fixes none). Some measures got
worse: dev agreement −0.3 pt with 2 correct answers turned wrong (dev contexts practically unchanged), and the
unknown-element rate doubled on both splits. Guardrail tests (`06`, unchanged): 6 / 6 blocked or neutralised.
Lakebase: 17 / 17 open incidents (re-scored with v5) have a summary, PK read p50 3.8 ms.

## Files

| file | content |
|---|---|
| [`01_gateway_config.md`](01_gateway_config.md) | live AI Gateway config of `databricks-gpt-5-4-mini` (no secrets), what the code requests, per-feature status, the inference-table failure (error + request ID) and the input-safety false positive |
| [`02_inference_log.md`](02_inference_log.md) | request / response log (in place of the inference table): volume by purpose / status, sample rows (request and response heads), guardrail-block rows; gateway usage tracking (`system.serving.endpoint_usage`) by day and sample rows; the log joined to usage rows on `client_request_id` (calls since fix round 1; earlier usage rows have it NULL) |
| [`03_worked_examples.md`](03_worked_examples.md) | full examples from the final dev run, each with context → validated NOC summary → guard report → SMS drafts: slow backhaul degradation, an `uncertain` answer, site power outage, aggregation router failure, cell outage; plus one live open incident (no ground truth) |
| [`03b_early_and_ambiguous_examples.md`](03b_early_and_ambiguous_examples.md) | below the alert threshold (dev): a slow backhaul 2 min before the SLA moment, where the assistant picks the link (#2) from its alarms; a cluster with no fault behind it, where it answers `uncertain` |
| [`04_evaluation.md`](04_evaluation.md) | MLflow GenAI evaluation, **dev and holdout separately**: overall metrics, by fault type, every case where the assistant departs from the ranker; MLflow run IDs and prompt versions |
| [`05_outputs_and_lakebase.md`](05_outputs_and_lakebase.md) | `netmon_genai` tables, `incident_ai_summaries` and `customer_notice_drafts` (all `status = draft`, 0 approved, 0 sent), `incident_ai_latest`, the synced table, the psycopg read-back (rows from Postgres) and its latency |
| [`06_guardrail_tests.md`](06_guardrail_tests.md) | live: prompt injection in alarm text (sanitiser on, and bypassed on purpose); PII leak attempts (redaction, AI Gateway input PII block, pre-send block, phone numbers asked into an SMS) |
| [`07_latency_cost.md`](07_latency_cost.md) | latency p50 / p95 and tokens per incident (dev, holdout), per call type; billing query for the endpoint (rows not yet posted at capture); gateway token totals |
| [`08_jobs_and_runs.md`](08_jobs_and_runs.md) | deployed jobs, their latest runs and the trigger config; each assistant run's own output (open / processed / skipped_unchanged / llm_calls / tokens), incl. the table-triggered run `147398191171624`: 17 open, 0 processed, 17 skipped, 0 LLM calls |
| [`09_holdout_alarm_gap.md`](09_holdout_alarm_gap.md) | the holdout finding, rebuilt from the pre-fix `*_pr5` snapshots: alarm counts per run, assistant vs ranker stratified by whether the context has an active alarm (`NULL` fault type = all types); **resolution** (PR #6) with the after counts and the new holdout stratification |
| [`10_holdout_rerun.md`](10_holdout_rerun.md) | PR #6: dev and holdout old vs new, overall and by fault type; the recorded holdout re-run reason; every new holdout case where the assistant departs from the ranker |

## What was run (final)

1. `scripts/genai_configure_gateway.py --no-inference-table` (guardrails, rate limits, usage tracking).
2. `banksia-genai-build-evalset`: contexts (dev 346, holdout 323) and labels.
3. Dev iteration (`scripts/genai_eval_local.py`, dev only): random 40, the 12 ranker misses; below-threshold examples
   → prompt v2; full dev run with judges → v3.
4. `banksia-genai-evaluate split=dev` (final dev), then `split=holdout` **once**.
5. `banksia-genai-assistant` (17 open incidents, v3), the Lakebase synced table, `banksia-genai-lakebase-check`;
   `banksia-rca-score-live` to exercise the table-update trigger.
6. Guardrail tests, early / ambiguous examples, this capture.
7. **PR #6** (2026-11-06): after the alarm ID fix and re-ingest (`evidence/step3/08_alarm_id_fix.md`) and the v5
   retrain: `banksia-rca-score-live` (v5; its MERGE triggered `banksia-genai-assistant` run `584238101020942`:
   17 processed, 34 LLM calls, Lakebase synced), `banksia-genai-build-evalset`, `banksia-genai-evaluate split=dev`,
   then `split=holdout force=true` **once** with `force_reason` (MLflow run `fb0197f68d634db68b6b6757a6705517`),
   `banksia-genai-lakebase-check`. 03b and 06 were not re-run (they call the live endpoint on hand-built inputs
   that the fix does not touch).

## Limitations recorded

- **Inference tables cannot be enabled** on the endpoint (server-side 500), so request / response logging is done in
  code (`noc_assistant_request_log`), alongside the gateway's usage tracking.
- **Input safety guardrail off**: false positives on benign NOC prompts.
- **Gateway PII detector false positives** on numbers (mitigated by rounding; 8 of 2,123 logged calls were blocked).
- **Billing not yet posted** for the endpoint's tokens at capture time.
- **The holdout's alarms were partly missing** upstream (`09`); fixed in PR #6 (`10`).
