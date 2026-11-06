# PR #6: step-4 evaluation re-run after the alarm ID fix (old vs new)

Captured 2026-11-06 08:14 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

Prompts frozen at `noc_summary_v3` / `sms_v1`, same scorers, judges and code. The evaluation set was rebuilt
(`banksia-genai-build-evalset`) from the corrected data and the retrained ranker v5, then dev was re-run and the
holdout re-run **once** with `force=true`. Re-run reason recorded on the MLflow run (tag `holdout_rerun_reason`) and in
the result tables (`rerun_reason`): "PR #6: run-unique alarm IDs. The holdout's fault alarms had been dropped upstream by a cross-run ID collision (09_holdout_alarm_gap.md); holdout_1m was re-ingested with corrected alarms and the ranker retrained (v5) on corrected training data. Prompts frozen at noc_summary_v3 / sms_v1; nothing tuned."

Old = the published PR #5 results (snapshots `genai_eval_summary_<split>_pr5`, ranker v4, alarms missing on the
holdout); new = this run. Both the inputs (alarms) and the ranker changed, so a difference is not attributable to the
assistant alone. Nothing was tuned on either result.

## HOLDOUT: overall, old vs new

| metric | old (PR #5) | new (PR #6) |
|---|---|---|
| n | 323 | 323 |
| llm_root_agreement_pct | 82.0 | 97.5 |
| ranker_top1_agreement_pct | 97.2 | 98.8 |
| answered_pct | 89.5 | 99.1 |
| llm_selective_accuracy_pct | 91.7 | 98.4 |
| ranker_top1_on_answered_pct | 97.2 | 99.1 |
| changed_to_correct | 2 | 0 |
| changed_correct_to_wrong | 18 | 2 |
| changed_wrong_to_wrong | 0 | 0 |
| uncertain_on_correct | 33 | 2 |
| uncertain_on_wrong | 1 | 1 |
| fault_hypothesis_match_pct | 69.0 | 95.7 |
| hallucinated_root_pct | 1.9 | 0.0 |
| hallucinated_element_pct | 3.1 | 5.0 |
| evidence_field_validity_pct | 99.5 | 99.4 |
| fallback_pct | 1.9 | 1.9 |
| sms_compliant_pct | 100.0 | 100.0 |
| sms_llm_first_try_compliant_pct | 98.5 | 99.7 |
| sms_llm_compliant_after_repair_pct | 99.4 | 99.7 |
| judge_groundedness_pct | 78.6 | 79.6 |
| judge_sms_guidelines_pct | 98.8 | 99.1 |
| latency_p50_ms | 6606.0 | 6307.0 |
| latency_p95_ms | 7925.0 | 7406.0 |
| prompt_tokens_mean | 4705.0 | 4824.0 |
| completion_tokens_mean | 791.0 | 759.0 |
| n_scored_incidents | 337.0 | 337.0 |
| ranker_top1_all_scored_pct | 93.2 | 94.7 |
| llm_root_agreement_all_scored_pct | 78.6 | 93.5 |
| mlflow_run_id | c403ff94c1c7436eabd43e026231035c | fb0197f68d634db68b6b6757a6705517 |
| noc_prompt_version | noc_summary_v3@cfda4dd5 | noc_summary_v3@cfda4dd5 |
| sms_prompt_version | sms_v1@8114c121 | sms_v1@8114c121 |
| rerun_reason |  | PR #6: run-unique alarm IDs. The holdout's fault alarms had been dropped upstream by a cross-run ID collision (09_holdout_alarm_gap.md); holdout_1m was re-ingested with corrected alarms and the ranker retrained (v5) on corrected training data. Prompts frozen at noc_summary_v3 / sms_v1; nothing tuned. |

## HOLDOUT: by fault type, old vs new

```sql
SELECT coalesce(n.`group`, o.`group`) AS fault_type, o.n AS old_n, n.n AS new_n, o.llm_root_agreement_pct AS old_llm_root_agreement_pct, n.llm_root_agreement_pct AS new_llm_root_agreement_pct, o.ranker_top1_agreement_pct AS old_ranker_top1_agreement_pct, n.ranker_top1_agreement_pct AS new_ranker_top1_agreement_pct, o.answered_pct AS old_answered_pct, n.answered_pct AS new_answered_pct, o.changed_correct_to_wrong AS old_changed_correct_to_wrong, n.changed_correct_to_wrong AS new_changed_correct_to_wrong, o.uncertain_on_correct AS old_uncertain_on_correct, n.uncertain_on_correct AS new_uncertain_on_correct
            FROM (SELECT * FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_summary_holdout_pr5 WHERE `group` <> 'ALL_WITH_CASE') o
            FULL OUTER JOIN (SELECT * FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_summary_holdout WHERE `group` <> 'ALL_WITH_CASE') n
              ON n.`group` = o.`group` ORDER BY CAST(coalesce(n.n, o.n) AS INT) DESC
```

| fault_type | old_n | new_n | old_llm_root_agreement_pct | new_llm_root_agreement_pct | old_ranker_top1_agreement_pct | new_ranker_top1_agreement_pct | old_answered_pct | new_answered_pct | old_changed_correct_to_wrong | new_changed_correct_to_wrong | old_uncertain_on_correct | new_uncertain_on_correct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CELL_OUTAGE | 181 | 181 | 76.8 | 98.3 | 98.3 | 98.9 | 86.2 | 100.0 | 14 | 1 | 25 | 0 |
| BACKHAUL_DEGRADATION | 46 | 46 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0 | 0 | 0 | 0 |
| AGG_ROUTER_FAILURE | 39 | 39 | 82.1 | 94.9 | 89.7 | 97.4 | 92.3 | 100.0 | 2 | 1 | 2 | 0 |
| SITE_POWER_OUTAGE | 38 | 38 | 89.5 | 100.0 | 97.4 | 100.0 | 97.4 | 100.0 | 2 | 0 | 1 | 0 |
| AMF_OVERLOAD | 17 | 17 | 70.6 | 88.2 | 100.0 | 100.0 | 70.6 | 88.2 | 0 | 0 | 5 | 2 |
| BUSHFIRE_GRID_OUTAGE | 1 | 1 | 100.0 | 0.0 | 0.0 | 0.0 | 100.0 | 0.0 | 0 | 0 | 0 | 0 |
| LONG_HAUL_FIBRE_CUT | 1 | 1 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0 | 0 | 0 | 0 |

_7 row(s)_

## DEV: overall, old vs new

| metric | old (PR #5) | new (PR #6) |
|---|---|---|
| n | 346 | 346 |
| llm_root_agreement_pct | 97.1 | 96.8 |
| ranker_top1_agreement_pct | 96.5 | 96.5 |
| answered_pct | 99.7 | 100.0 |
| llm_selective_accuracy_pct | 97.4 | 96.8 |
| ranker_top1_on_answered_pct | 96.5 | 96.5 |
| changed_to_correct | 3 | 3 |
| changed_correct_to_wrong | 0 | 2 |
| changed_wrong_to_wrong | 0 | 2 |
| uncertain_on_correct | 1 | 0 |
| uncertain_on_wrong | 0 | 0 |
| fault_hypothesis_match_pct | 96.5 | 93.9 |
| hallucinated_root_pct | 0.0 | 0.0 |
| hallucinated_element_pct | 2.6 | 5.2 |
| evidence_field_validity_pct | 99.4 | 99.7 |
| fallback_pct | 0.3 | 0.6 |
| sms_compliant_pct | 100.0 | 100.0 |
| sms_llm_first_try_compliant_pct | 98.3 | 97.4 |
| sms_llm_compliant_after_repair_pct | 99.7 | 99.1 |
| judge_groundedness_pct | 81.8 | 80.9 |
| judge_sms_guidelines_pct | 99.7 | 99.4 |
| latency_p50_ms | 6411.0 | 6014.0 |
| latency_p95_ms | 8012.0 | 7289.0 |
| prompt_tokens_mean | 4896.0 | 4887.0 |
| completion_tokens_mean | 772.0 | 776.0 |
| n_scored_incidents | 355.0 | 355.0 |
| ranker_top1_all_scored_pct | 94.1 | 94.1 |
| llm_root_agreement_all_scored_pct | 94.6 | 94.4 |
| mlflow_run_id | a3ec3955c745457492240515d67f929d | cae6c002bb9144df8944f82458769eca |
| noc_prompt_version | noc_summary_v3@cfda4dd5 | noc_summary_v3@cfda4dd5 |
| sms_prompt_version | sms_v1@8114c121 | sms_v1@8114c121 |
| rerun_reason |  |  |

## DEV: by fault type, old vs new

```sql
SELECT coalesce(n.`group`, o.`group`) AS fault_type, o.n AS old_n, n.n AS new_n, o.llm_root_agreement_pct AS old_llm_root_agreement_pct, n.llm_root_agreement_pct AS new_llm_root_agreement_pct, o.ranker_top1_agreement_pct AS old_ranker_top1_agreement_pct, n.ranker_top1_agreement_pct AS new_ranker_top1_agreement_pct, o.answered_pct AS old_answered_pct, n.answered_pct AS new_answered_pct, o.changed_correct_to_wrong AS old_changed_correct_to_wrong, n.changed_correct_to_wrong AS new_changed_correct_to_wrong, o.uncertain_on_correct AS old_uncertain_on_correct, n.uncertain_on_correct AS new_uncertain_on_correct
            FROM (SELECT * FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_summary_dev_pr5 WHERE `group` <> 'ALL_WITH_CASE') o
            FULL OUTER JOIN (SELECT * FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_summary_dev WHERE `group` <> 'ALL_WITH_CASE') n
              ON n.`group` = o.`group` ORDER BY CAST(coalesce(n.n, o.n) AS INT) DESC
```

| fault_type | old_n | new_n | old_llm_root_agreement_pct | new_llm_root_agreement_pct | old_ranker_top1_agreement_pct | new_ranker_top1_agreement_pct | old_answered_pct | new_answered_pct | old_changed_correct_to_wrong | new_changed_correct_to_wrong | old_uncertain_on_correct | new_uncertain_on_correct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CELL_OUTAGE | 205 | 205 | 97.6 | 97.1 | 97.1 | 97.1 | 100.0 | 100.0 | 0 | 1 | 0 | 0 |
| BACKHAUL_DEGRADATION | 46 | 46 | 93.5 | 93.5 | 93.5 | 93.5 | 100.0 | 100.0 | 0 | 0 | 0 | 0 |
| SITE_POWER_OUTAGE | 46 | 46 | 97.8 | 97.8 | 97.8 | 97.8 | 100.0 | 100.0 | 0 | 0 | 0 | 0 |
| AGG_ROUTER_FAILURE | 30 | 30 | 100.0 | 100.0 | 93.3 | 93.3 | 100.0 | 100.0 | 0 | 0 | 0 | 0 |
| AMF_OVERLOAD | 18 | 18 | 94.4 | 94.4 | 100.0 | 100.0 | 94.4 | 100.0 | 0 | 1 | 1 | 0 |
| LONG_HAUL_FIBRE_CUT | 1 | 1 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0 | 0 | 0 | 0 |

_6 row(s)_

## HOLDOUT (new): every case where the assistant departs from the ranker

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
