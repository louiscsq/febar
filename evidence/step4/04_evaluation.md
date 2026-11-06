# MLflow GenAI evaluation: dev and holdout (separately)

Captured 2026-11-06 08:19 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

`banksia-genai-evaluate` runs `mlflow.genai.evaluate` over the evaluation set: one grounded context per scored step-3
incident that had a case output at the SLA moment. **Dev** = `history_1m` 2026-10-14 … 10-15 (prompt iteration
happened here only). **Holdout** = `holdout_1m` 2026-10-17 … 10-18, run **once** with the frozen prompts (the job
refuses to re-run it without `force=true` and a recorded reason). These are the PR #6 runs: after the alarm ID fix the
evaluation set was rebuilt and the holdout re-run once (reason in `rerun_reason`; old vs new in `10_holdout_rerun.md`). Ground truth reaches only the scorers (`expectations`). Assistant `databricks-gpt-5-4-mini`; LLM judges
`databricks-claude-sonnet-5-5` (another model family). Definitions: `netmon_pipeline.genai.scorers`.

- `llm_root_agreement_pct`: the assistant's root is in the valid root list; "uncertain" counts as a miss.
- `ranker_top1_agreement_pct`: the ranker's suspect #1 on the same contexts (step 3's top-1 at the SLA moment).
- `llm_selective_accuracy_pct` / `ranker_top1_on_answered_pct`: agreement on the cases the assistant answered.
- `changed_*` / `uncertain_*`: counts of cases where the assistant departs from the ranker.
- `hallucinated_*`: the raw output named a root that is not a suspect / any element ID not in the context
  (before the guard repaired it). `evidence_field_validity_pct`: cited context paths that exist.
- `sms_*`: final drafts compliant (always, by construction: non-compliant drafts are replaced by the template) /
  the LLM's own drafts compliant at the first try / after one repair round.
- latency = sum of the summary and SMS calls per incident (client side, job -> endpoint); tokens per incident.

## DEV: overall

| metric | value |
|---|---|
| n | 346 |
| llm_root_agreement_pct | 96.8 |
| ranker_top1_agreement_pct | 96.5 |
| answered_pct | 100.0 |
| llm_selective_accuracy_pct | 96.8 |
| ranker_top1_on_answered_pct | 96.5 |
| changed_to_correct | 3 |
| changed_correct_to_wrong | 2 |
| changed_wrong_to_wrong | 2 |
| uncertain_on_correct | 0 |
| uncertain_on_wrong | 0 |
| fault_hypothesis_match_pct | 93.9 |
| hallucinated_root_pct | 0.0 |
| hallucinated_element_pct | 5.2 |
| evidence_field_validity_pct | 99.7 |
| fallback_pct | 0.6 |
| sms_compliant_pct | 100.0 |
| sms_llm_first_try_compliant_pct | 97.4 |
| sms_llm_compliant_after_repair_pct | 99.1 |
| judge_groundedness_pct | 80.9 |
| judge_sms_guidelines_pct | 99.4 |
| latency_p50_ms | 6014.0 |
| latency_p95_ms | 7289.0 |
| prompt_tokens_mean | 4887.0 |
| completion_tokens_mean | 776.0 |
| n_scored_incidents | 355.0 |
| ranker_top1_all_scored_pct | 94.1 |
| llm_root_agreement_all_scored_pct | 94.4 |
| mlflow_run_id | cae6c002bb9144df8944f82458769eca |
| noc_prompt_version | noc_summary_v3@cfda4dd5 |
| sms_prompt_version | sms_v1@8114c121 |
| wall_minutes | 10.9 |

## DEV: by fault type

```sql
SELECT `group` AS fault_type, n, llm_root_agreement_pct, ranker_top1_agreement_pct, answered_pct,
                   llm_selective_accuracy_pct, changed_to_correct, changed_correct_to_wrong, uncertain_on_correct,
                   uncertain_on_wrong, fault_hypothesis_match_pct, hallucinated_element_pct, sms_llm_first_try_compliant_pct,
                   judge_groundedness_pct, latency_p50_ms
            FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_summary_dev WHERE `group` <> 'ALL_WITH_CASE' ORDER BY CAST(n AS INT) DESC
```

| fault_type | n | llm_root_agreement_pct | ranker_top1_agreement_pct | answered_pct | llm_selective_accuracy_pct | changed_to_correct | changed_correct_to_wrong | uncertain_on_correct | uncertain_on_wrong | fault_hypothesis_match_pct | hallucinated_element_pct | sms_llm_first_try_compliant_pct | judge_groundedness_pct | latency_p50_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CELL_OUTAGE | 205 | 97.1 | 97.1 | 100.0 | 97.1 | 1 | 1 | 0 | 0 | 94.6 | 2.0 | 96.1 | 76.6 | 5838.0 |
| BACKHAUL_DEGRADATION | 46 | 93.5 | 93.5 | 100.0 | 93.5 | 0 | 0 | 0 | 0 | 95.7 | 0.0 | 100.0 | 91.3 | 6327.0 |
| SITE_POWER_OUTAGE | 46 | 97.8 | 97.8 | 100.0 | 97.8 | 0 | 0 | 0 | 0 | 95.7 | 15.2 | 100.0 | 82.6 | 6010.0 |
| AGG_ROUTER_FAILURE | 30 | 100.0 | 93.3 | 100.0 | 100.0 | 2 | 0 | 0 | 0 | 86.7 | 23.3 | 96.7 | 86.7 | 6344.0 |
| AMF_OVERLOAD | 18 | 94.4 | 100.0 | 100.0 | 94.4 | 0 | 1 | 0 | 0 | 94.4 | 0.0 | 100.0 | 88.9 | 6133.0 |
| LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 100.0 | 100.0 | 100.0 | 0 | 0 | 0 | 0 | 0.0 | 0.0 | 100.0 | 100.0 | 6832.0 |

_6 row(s)_

## DEV: every case where the assistant departs from the ranker

```sql
SELECT eval_id, fault_type, root_element_ids, ranker_top1, llm_root, llm_vs_ranker, confidence,
                   fault_hypothesis FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_results_dev
            WHERE llm_vs_ranker <> 'same' ORDER BY llm_vs_ranker, fault_type, eval_id
```

| eval_id | fault_type | root_element_ids | ranker_top1 | llm_root | llm_vs_ranker | confidence | fault_hypothesis |
|---|---|---|---|---|---|---|---|
| EVAL-dev-5b521d19af76 | AMF_OVERLOAD | ["AMF-WA-01"] | AMF-WA-01 | AGG-WA-02 | changed_correct_to_wrong | medium | AGG_ROUTER_FAILURE |
| EVAL-dev-f4a12b4797ac | CELL_OUTAGE | ["CELL-VIC-00046-4G3"] | CELL-VIC-00046-4G3 | SITE-VIC-00045 | changed_correct_to_wrong | medium | SITE_POWER_OUTAGE |
| EVAL-dev-12b06e69dd60 | AGG_ROUTER_FAILURE | ["AGG-NQL-03"] | AGG-NQL-01 | AGG-NQL-03 | changed_to_correct | high | AGG_ROUTER_FAILURE |
| EVAL-dev-6504aedbe281 | AGG_ROUTER_FAILURE | ["AGG-NQL-04"] | AGG-NQL-01 | AGG-NQL-04 | changed_to_correct | high | BACKHAUL_CUT |
| EVAL-dev-683a5e038146 | CELL_OUTAGE | ["CELL-NSW-00091-4G3"] | CELL-NSW-00091-4G2 | CELL-NSW-00091-4G3 | changed_to_correct | medium | CELL_OUTAGE |
| EVAL-dev-4644637bbb24 | CELL_OUTAGE | ["CELL-VIC-00026-5G2"] | BH-VIC-0002 | BH-VIC-0009 | changed_wrong_to_wrong | medium | BACKHAUL_DEGRADATION |
| EVAL-dev-53f3bb5a020a | CELL_OUTAGE | ["CELL-NQL-00021-4G2"] | AGG-NQL-01 | AGG-NQL-03 | changed_wrong_to_wrong | high | BACKHAUL_CUT |

_7 row(s)_

## HOLDOUT: overall

| metric | value |
|---|---|
| n | 323 |
| llm_root_agreement_pct | 97.5 |
| ranker_top1_agreement_pct | 98.8 |
| answered_pct | 99.1 |
| llm_selective_accuracy_pct | 98.4 |
| ranker_top1_on_answered_pct | 99.1 |
| changed_to_correct | 0 |
| changed_correct_to_wrong | 2 |
| changed_wrong_to_wrong | 0 |
| uncertain_on_correct | 2 |
| uncertain_on_wrong | 1 |
| fault_hypothesis_match_pct | 95.7 |
| hallucinated_root_pct | 0.0 |
| hallucinated_element_pct | 5.0 |
| evidence_field_validity_pct | 99.4 |
| fallback_pct | 1.9 |
| sms_compliant_pct | 100.0 |
| sms_llm_first_try_compliant_pct | 99.7 |
| sms_llm_compliant_after_repair_pct | 99.7 |
| judge_groundedness_pct | 79.6 |
| judge_sms_guidelines_pct | 99.1 |
| latency_p50_ms | 6307.0 |
| latency_p95_ms | 7406.0 |
| prompt_tokens_mean | 4824.0 |
| completion_tokens_mean | 759.0 |
| n_scored_incidents | 337.0 |
| ranker_top1_all_scored_pct | 94.7 |
| llm_root_agreement_all_scored_pct | 93.5 |
| mlflow_run_id | fb0197f68d634db68b6b6757a6705517 |
| noc_prompt_version | noc_summary_v3@cfda4dd5 |
| sms_prompt_version | sms_v1@8114c121 |
| wall_minutes | 9.1 |

## HOLDOUT: by fault type

```sql
SELECT `group` AS fault_type, n, llm_root_agreement_pct, ranker_top1_agreement_pct, answered_pct,
                   llm_selective_accuracy_pct, changed_to_correct, changed_correct_to_wrong, uncertain_on_correct,
                   uncertain_on_wrong, fault_hypothesis_match_pct, hallucinated_element_pct, sms_llm_first_try_compliant_pct,
                   judge_groundedness_pct, latency_p50_ms
            FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_summary_holdout WHERE `group` <> 'ALL_WITH_CASE' ORDER BY CAST(n AS INT) DESC
```

| fault_type | n | llm_root_agreement_pct | ranker_top1_agreement_pct | answered_pct | llm_selective_accuracy_pct | changed_to_correct | changed_correct_to_wrong | uncertain_on_correct | uncertain_on_wrong | fault_hypothesis_match_pct | hallucinated_element_pct | sms_llm_first_try_compliant_pct | judge_groundedness_pct | latency_p50_ms |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CELL_OUTAGE | 181 | 98.3 | 98.9 | 100.0 | 98.3 | 0 | 1 | 0 | 0 | 96.1 | 0.6 | 100.0 | 76.2 | 6152.0 |
| BACKHAUL_DEGRADATION | 46 | 100.0 | 100.0 | 100.0 | 100.0 | 0 | 0 | 0 | 0 | 97.8 | 2.2 | 100.0 | 82.6 | 6837.0 |
| AGG_ROUTER_FAILURE | 39 | 94.9 | 97.4 | 100.0 | 94.9 | 0 | 1 | 0 | 0 | 94.9 | 23.1 | 97.4 | 82.1 | 6612.0 |
| SITE_POWER_OUTAGE | 38 | 100.0 | 100.0 | 100.0 | 100.0 | 0 | 0 | 0 | 0 | 94.7 | 13.2 | 100.0 | 84.2 | 6241.0 |
| AMF_OVERLOAD | 17 | 88.2 | 100.0 | 88.2 | 100.0 | 0 | 0 | 2 | 0 | 94.1 | 0.0 | 100.0 | 94.1 | 6790.0 |
| BUSHFIRE_GRID_OUTAGE | 1 | 0.0 | 0.0 | 0.0 | None | 0 | 0 | 0 | 1 | 0.0 | 0.0 | 100.0 | 0.0 | 7044.0 |
| LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 100.0 | 100.0 | 100.0 | 0 | 0 | 0 | 0 | 100.0 | 0.0 | 100.0 | 100.0 | 6952.0 |

_7 row(s)_

## HOLDOUT: every case where the assistant departs from the ranker

```sql
SELECT eval_id, fault_type, root_element_ids, ranker_top1, llm_root, llm_vs_ranker, confidence,
                   fault_hypothesis FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_results_holdout
            WHERE llm_vs_ranker <> 'same' ORDER BY llm_vs_ranker, fault_type, eval_id
```

| eval_id | fault_type | root_element_ids | ranker_top1 | llm_root | llm_vs_ranker | confidence | fault_hypothesis |
|---|---|---|---|---|---|---|---|
| EVAL-holdout-eea4a9442b5f | AGG_ROUTER_FAILURE | ["AGG-VIC-01"] | AGG-VIC-01 | AGG-VIC-04 | changed_correct_to_wrong | high | AGG_ROUTER_FAILURE |
| EVAL-holdout-91672e4f973c | CELL_OUTAGE | ["CELL-NSW-00022-4G3"] | CELL-NSW-00022-4G3 | SITE-NSW-00021 | changed_correct_to_wrong | high | SITE_POWER_OUTAGE |
| EVAL-holdout-8bba0e300b72 | AMF_OVERLOAD | ["AMF-WA-01"] | AMF-WA-01 | uncertain | uncertain_on_correct | low | AMF_OVERLOAD |
| EVAL-holdout-f9e3aa739d70 | AMF_OVERLOAD | ["AMF-WA-01"] | AMF-WA-01 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-26712a467795 | BUSHFIRE_GRID_OUTAGE | ["SITE-NSW-00087", "SITE-NSW-00089"] | BH-NSW-0037 | uncertain | uncertain_on_wrong | low | UNCERTAIN |

_5 row(s)_
