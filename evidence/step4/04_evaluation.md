# MLflow GenAI evaluation: dev and holdout (separately)

Captured 2026-11-06 02:27 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

`banksia-genai-evaluate` runs `mlflow.genai.evaluate` over the evaluation set: one grounded context per scored step-3
incident that had a case output at the SLA moment. **Dev** = `history_1m` 2026-10-14 … 10-15 (prompt iteration
happened here only). **Holdout** = `holdout_1m` 2026-10-17 … 10-18, run **once** with the frozen prompts (the job
refuses to re-run it). Ground truth reaches only the scorers (`expectations`). Assistant `databricks-gpt-5-4-mini`; LLM judges
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
| llm_root_agreement_pct | 97.1 |
| ranker_top1_agreement_pct | 96.5 |
| answered_pct | 99.7 |
| llm_selective_accuracy_pct | 97.4 |
| ranker_top1_on_answered_pct | 96.5 |
| changed_to_correct | 3 |
| changed_correct_to_wrong | 0 |
| changed_wrong_to_wrong | 0 |
| uncertain_on_correct | 1 |
| uncertain_on_wrong | 0 |
| fault_hypothesis_match_pct | 96.5 |
| hallucinated_root_pct | 0.0 |
| hallucinated_element_pct | 2.6 |
| evidence_field_validity_pct | 99.4 |
| fallback_pct | 0.3 |
| sms_compliant_pct | 100.0 |
| sms_llm_first_try_compliant_pct | 98.3 |
| sms_llm_compliant_after_repair_pct | 99.7 |
| judge_groundedness_pct | 81.8 |
| judge_sms_guidelines_pct | 99.7 |
| latency_p50_ms | 6411.0 |
| latency_p95_ms | 8012.0 |
| prompt_tokens_mean | 4896.0 |
| completion_tokens_mean | 772.0 |
| n_scored_incidents | 355.0 |
| ranker_top1_all_scored_pct | 94.1 |
| llm_root_agreement_all_scored_pct | 94.6 |
| mlflow_run_id | a3ec3955c745457492240515d67f929d |
| noc_prompt_version | noc_summary_v3@cfda4dd5 |
| sms_prompt_version | sms_v1@8114c121 |
| wall_minutes | 11.8 |

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
| CELL_OUTAGE | 205 | 97.6 | 97.1 | 100.0 | 97.6 | 1 | 0 | 0 | 0 | 95.1 | 0.0 | 97.6 | 79.0 | 6327.0 |
| BACKHAUL_DEGRADATION | 46 | 93.5 | 93.5 | 100.0 | 93.5 | 0 | 0 | 0 | 0 | 100.0 | 0.0 | 100.0 | 84.8 | 7117.0 |
| SITE_POWER_OUTAGE | 46 | 97.8 | 97.8 | 100.0 | 97.8 | 0 | 0 | 0 | 0 | 97.8 | 10.9 | 97.8 | 82.6 | 6211.0 |
| AGG_ROUTER_FAILURE | 30 | 100.0 | 93.3 | 100.0 | 100.0 | 2 | 0 | 0 | 0 | 100.0 | 13.3 | 100.0 | 90.0 | 6675.0 |
| AMF_OVERLOAD | 18 | 94.4 | 100.0 | 94.4 | 100.0 | 0 | 0 | 1 | 0 | 94.4 | 0.0 | 100.0 | 88.9 | 6851.0 |
| LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 100.0 | 100.0 | 100.0 | 0 | 0 | 0 | 0 | 100.0 | 0.0 | 100.0 | 100.0 | 6175.0 |

_6 row(s)_

## DEV: every case where the assistant departs from the ranker

```sql
SELECT eval_id, fault_type, root_element_ids, ranker_top1, llm_root, llm_vs_ranker, confidence,
                   fault_hypothesis FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_results_dev
            WHERE llm_vs_ranker <> 'same' ORDER BY llm_vs_ranker, fault_type, eval_id
```

| eval_id | fault_type | root_element_ids | ranker_top1 | llm_root | llm_vs_ranker | confidence | fault_hypothesis |
|---|---|---|---|---|---|---|---|
| EVAL-dev-12b06e69dd60 | AGG_ROUTER_FAILURE | ["AGG-NQL-03"] | AGG-NQL-01 | AGG-NQL-03 | changed_to_correct | high | AGG_ROUTER_FAILURE |
| EVAL-dev-6504aedbe281 | AGG_ROUTER_FAILURE | ["AGG-NQL-04"] | AGG-NQL-01 | AGG-NQL-04 | changed_to_correct | high | AGG_ROUTER_FAILURE |
| EVAL-dev-683a5e038146 | CELL_OUTAGE | ["CELL-NSW-00091-4G3"] | CELL-NSW-00091-4G2 | CELL-NSW-00091-4G3 | changed_to_correct | medium | CELL_OUTAGE |
| EVAL-dev-0277797bad6f | AMF_OVERLOAD | ["AMF-VIC-01"] | AMF-VIC-01 | uncertain | uncertain_on_correct | low | UNCERTAIN |

_4 row(s)_

## HOLDOUT: overall

| metric | value |
|---|---|
| n | 323 |
| llm_root_agreement_pct | 82.0 |
| ranker_top1_agreement_pct | 97.2 |
| answered_pct | 89.5 |
| llm_selective_accuracy_pct | 91.7 |
| ranker_top1_on_answered_pct | 97.2 |
| changed_to_correct | 2 |
| changed_correct_to_wrong | 18 |
| changed_wrong_to_wrong | 0 |
| uncertain_on_correct | 33 |
| uncertain_on_wrong | 1 |
| fault_hypothesis_match_pct | 69.0 |
| hallucinated_root_pct | 1.9 |
| hallucinated_element_pct | 3.1 |
| evidence_field_validity_pct | 99.5 |
| fallback_pct | 1.9 |
| sms_compliant_pct | 100.0 |
| sms_llm_first_try_compliant_pct | 98.5 |
| sms_llm_compliant_after_repair_pct | 99.4 |
| judge_groundedness_pct | 78.6 |
| judge_sms_guidelines_pct | 98.8 |
| latency_p50_ms | 6606.0 |
| latency_p95_ms | 7925.0 |
| prompt_tokens_mean | 4705.0 |
| completion_tokens_mean | 791.0 |
| n_scored_incidents | 337.0 |
| ranker_top1_all_scored_pct | 93.2 |
| llm_root_agreement_all_scored_pct | 78.6 |
| mlflow_run_id | c403ff94c1c7436eabd43e026231035c |
| noc_prompt_version | noc_summary_v3@cfda4dd5 |
| sms_prompt_version | sms_v1@8114c121 |
| wall_minutes | 9.0 |

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
| CELL_OUTAGE | 181 | 76.8 | 98.3 | 86.2 | 89.1 | 0 | 14 | 25 | 0 | 75.1 | 1.7 | 98.3 | 79.0 | 6445.0 |
| BACKHAUL_DEGRADATION | 46 | 100.0 | 100.0 | 100.0 | 100.0 | 0 | 0 | 0 | 0 | 95.7 | 0.0 | 97.8 | 84.8 | 6862.0 |
| AGG_ROUTER_FAILURE | 39 | 82.1 | 89.7 | 92.3 | 88.9 | 1 | 2 | 2 | 1 | 46.2 | 12.8 | 100.0 | 61.5 | 7108.0 |
| SITE_POWER_OUTAGE | 38 | 89.5 | 97.4 | 97.4 | 91.9 | 0 | 2 | 1 | 0 | 34.2 | 5.3 | 97.4 | 86.8 | 6628.0 |
| AMF_OVERLOAD | 17 | 70.6 | 100.0 | 70.6 | 100.0 | 0 | 0 | 5 | 0 | 70.6 | 0.0 | 100.0 | 76.5 | 7082.0 |
| BUSHFIRE_GRID_OUTAGE | 1 | 100.0 | 0.0 | 100.0 | 100.0 | 1 | 0 | 0 | 0 | 0.0 | 0.0 | 100.0 | 100.0 | 6584.0 |
| LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 100.0 | 100.0 | 100.0 | 0 | 0 | 0 | 0 | 0.0 | 0.0 | 100.0 | 100.0 | 7033.0 |

_7 row(s)_

## HOLDOUT: every case where the assistant departs from the ranker

```sql
SELECT eval_id, fault_type, root_element_ids, ranker_top1, llm_root, llm_vs_ranker, confidence,
                   fault_hypothesis FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_results_holdout
            WHERE llm_vs_ranker <> 'same' ORDER BY llm_vs_ranker, fault_type, eval_id
```

| eval_id | fault_type | root_element_ids | ranker_top1 | llm_root | llm_vs_ranker | confidence | fault_hypothesis |
|---|---|---|---|---|---|---|---|
| EVAL-holdout-494a62841c49 | AGG_ROUTER_FAILURE | ["AGG-NSW-02"] | AGG-NSW-02 | BH-NSW-0015 | changed_correct_to_wrong | medium | BACKHAUL_CUT |
| EVAL-holdout-b36df816351a | AGG_ROUTER_FAILURE | ["AGG-NQL-02"] | AGG-NQL-02 | BH-NQL-0004 | changed_correct_to_wrong | high | BACKHAUL_CUT |
| EVAL-holdout-0017af2502fe | CELL_OUTAGE | ["CELL-WA-00014-4G2"] | CELL-WA-00014-4G2 | SITE-WA-00014 | changed_correct_to_wrong | medium | CELL_OUTAGE |
| EVAL-holdout-0329c140c893 | CELL_OUTAGE | ["CELL-VIC-00064-5G1"] | CELL-VIC-00064-5G1 | BH-VIC-0028 | changed_correct_to_wrong | medium | BACKHAUL_DEGRADATION |
| EVAL-holdout-1a111d8902c6 | CELL_OUTAGE | ["CELL-NSW-00034-5G3"] | CELL-NSW-00034-5G3 | BH-NSW-0014 | changed_correct_to_wrong | medium | BACKHAUL_CUT |
| EVAL-holdout-3a2b8090ebeb | CELL_OUTAGE | ["CELL-NQL-00019-4G1"] | CELL-NQL-00019-4G1 | BH-NQL-0012 | changed_correct_to_wrong | medium | BACKHAUL_DEGRADATION |
| EVAL-holdout-452e29b96d1c | CELL_OUTAGE | ["CELL-VIC-00055-5G2"] | CELL-VIC-00055-5G2 | BH-VIC-0024 | changed_correct_to_wrong | medium | BACKHAUL_DEGRADATION |
| EVAL-holdout-5acd4ddea57a | CELL_OUTAGE | ["CELL-NSW-00019-4G3"] | CELL-NSW-00019-4G3 | BH-NSW-0007 | changed_correct_to_wrong | medium | BACKHAUL_DEGRADATION |
| EVAL-holdout-64f43c163f79 | CELL_OUTAGE | ["CELL-VIC-00060-4G2"] | CELL-VIC-00060-4G2 | BH-VIC-0027 | changed_correct_to_wrong | medium | BACKHAUL_DEGRADATION |
| EVAL-holdout-91672e4f973c | CELL_OUTAGE | ["CELL-NSW-00022-4G3"] | CELL-NSW-00022-4G3 | SITE-NSW-00021 | changed_correct_to_wrong | medium | BACKHAUL_DEGRADATION |
| EVAL-holdout-91ef571bbbe8 | CELL_OUTAGE | ["CELL-NSW-00024-4G2"] | CELL-NSW-00024-4G2 | BH-NSW-0009 | changed_correct_to_wrong | medium | BACKHAUL_DEGRADATION |
| EVAL-holdout-9db78edab91b | CELL_OUTAGE | ["CELL-VIC-00020-4G1"] | CELL-VIC-00020-4G1 | BH-VIC-0009 | changed_correct_to_wrong | medium | BACKHAUL_CUT |
| EVAL-holdout-9e9fb3773802 | CELL_OUTAGE | ["CELL-VIC-00045-4G1"] | CELL-VIC-00045-4G1 | BH-VIC-0021 | changed_correct_to_wrong | medium | BACKHAUL_DEGRADATION |
| EVAL-holdout-aaea8bb9a605 | CELL_OUTAGE | ["CELL-NSW-00080-5G2"] | CELL-NSW-00080-5G2 | AGG-NSW-03 | changed_correct_to_wrong | low | UNCERTAIN |
| EVAL-holdout-dbdb10d8314b | CELL_OUTAGE | ["CELL-VIC-00035-5G3"] | CELL-VIC-00035-5G3 | BH-VIC-0017 | changed_correct_to_wrong | medium | BACKHAUL_DEGRADATION |
| EVAL-holdout-e9e2e5d39fbd | CELL_OUTAGE | ["CELL-NSW-00030-4G1"] | CELL-NSW-00030-4G1 | AGG-NSW-01 | changed_correct_to_wrong | medium | AGG_ROUTER_FAILURE |
| EVAL-holdout-927e82b07a00 | SITE_POWER_OUTAGE | ["SITE-VIC-00084"] | SITE-VIC-00084 | BH-VIC-0038 | changed_correct_to_wrong | medium | BACKHAUL_DEGRADATION |
| EVAL-holdout-fac760d8d94c | SITE_POWER_OUTAGE | ["SITE-WA-00007"] | SITE-WA-00007 | AGG-WA-01 | changed_correct_to_wrong | high | AGG_ROUTER_FAILURE |
| EVAL-holdout-48f71ff12df0 | AGG_ROUTER_FAILURE | ["AGG-NQL-04"] | CELL-NQL-00004-5G3 | AGG-NQL-04 | changed_to_correct | high | BACKHAUL_CUT |
| EVAL-holdout-26712a467795 | BUSHFIRE_GRID_OUTAGE | ["SITE-NSW-00087", "SITE-NSW-00089"] | BH-NSW-0037 | SITE-NSW-00089 | changed_to_correct | high | SITE_POWER_OUTAGE |
| EVAL-holdout-574e4debaf4c | AGG_ROUTER_FAILURE | ["AGG-WA-01"] | AGG-WA-01 | uncertain | uncertain_on_correct | low | BACKHAUL_CUT |
| EVAL-holdout-e9ae980b342a | AGG_ROUTER_FAILURE | ["AGG-VIC-04"] | AGG-VIC-04 | uncertain | uncertain_on_correct | low | BACKHAUL_CUT |
| EVAL-holdout-2a12111cb73c | AMF_OVERLOAD | ["AMF-NQL-01"] | AMF-NQL-01 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-569f061ae8db | AMF_OVERLOAD | ["AMF-VIC-01"] | AMF-VIC-01 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-8bba0e300b72 | AMF_OVERLOAD | ["AMF-WA-01"] | AMF-WA-01 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-91473b901e62 | AMF_OVERLOAD | ["AMF-NQL-01"] | AMF-NQL-01 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-f9e3aa739d70 | AMF_OVERLOAD | ["AMF-WA-01"] | AMF-WA-01 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-007a5d927b1d | CELL_OUTAGE | ["CELL-NSW-00087-4G3"] | CELL-NSW-00087-4G3 | uncertain | uncertain_on_correct | low | CELL_OUTAGE |
| EVAL-holdout-02c1c9dab3ae | CELL_OUTAGE | ["CELL-NSW-00095-5G3"] | CELL-NSW-00095-5G3 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-0f397b61c96f | CELL_OUTAGE | ["CELL-WA-00015-5G1"] | CELL-WA-00015-5G1 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-1a8627549a69 | CELL_OUTAGE | ["CELL-NSW-00004-5G1"] | CELL-NSW-00004-5G1 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-1f3571c3717c | CELL_OUTAGE | ["CELL-VIC-00051-5G2"] | CELL-VIC-00051-5G2 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-259b13f0f171 | CELL_OUTAGE | ["CELL-WA-00026-5G2"] | CELL-WA-00026-5G2 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-26b6a1b0f9c4 | CELL_OUTAGE | ["CELL-NSW-00083-4G1"] | CELL-NSW-00083-4G1 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-27856386e465 | CELL_OUTAGE | ["CELL-VIC-00098-4G3"] | CELL-VIC-00098-4G3 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-28fe266ffd8a | CELL_OUTAGE | ["CELL-VIC-00091-4G3"] | CELL-VIC-00091-4G3 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-2eeb4d627363 | CELL_OUTAGE | ["CELL-NSW-00085-4G3"] | CELL-NSW-00085-4G3 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-363e639687f2 | CELL_OUTAGE | ["CELL-VIC-00033-4G2"] | CELL-VIC-00033-4G2 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-52e7ac5667f4 | CELL_OUTAGE | ["CELL-NSW-00091-4G3"] | CELL-NSW-00091-4G3 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-572f6d552f4c | CELL_OUTAGE | ["CELL-VIC-00060-5G1"] | CELL-VIC-00060-5G1 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-57d8417b0d32 | CELL_OUTAGE | ["CELL-WA-00028-4G3"] | CELL-WA-00028-4G3 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-5d208278c2c9 | CELL_OUTAGE | ["CELL-VIC-00084-5G2"] | CELL-VIC-00084-5G2 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-72ec004558b9 | CELL_OUTAGE | ["CELL-NSW-00010-4G3"] | CELL-NSW-00010-4G3 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-8aa03cd094cc | CELL_OUTAGE | ["CELL-NSW-00098-4G2"] | CELL-NSW-00098-4G2 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-9ba62145f0a3 | CELL_OUTAGE | ["CELL-VIC-00007-4G1"] | CELL-VIC-00007-4G1 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-9f7032c7eaca | CELL_OUTAGE | ["CELL-NSW-00080-4G1"] | CELL-NSW-00080-4G1 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-a1809c2273b4 | CELL_OUTAGE | ["CELL-NSW-00082-4G1"] | CELL-NSW-00082-4G1 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-a961e2c613a3 | CELL_OUTAGE | ["CELL-NSW-00113-5G3"] | CELL-NSW-00113-5G3 | uncertain | uncertain_on_correct | low | AGG_ROUTER_FAILURE |
| EVAL-holdout-b87838f1c943 | CELL_OUTAGE | ["CELL-NSW-00102-4G1"] | CELL-NSW-00102-4G1 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-c1d7370cadd4 | CELL_OUTAGE | ["CELL-VIC-00077-5G1"] | CELL-VIC-00077-5G1 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-d52bbb3ed7da | CELL_OUTAGE | ["CELL-NSW-00118-5G2"] | CELL-NSW-00118-5G2 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-ea53a7652c2b | CELL_OUTAGE | ["CELL-WA-00033-5G3"] | CELL-WA-00033-5G3 | uncertain | uncertain_on_correct | low | UNCERTAIN |
| EVAL-holdout-762069696c4a | SITE_POWER_OUTAGE | ["SITE-NSW-00096"] | SITE-NSW-00096 | uncertain | uncertain_on_correct | low | BACKHAUL_DEGRADATION |
| EVAL-holdout-1f432fc0991e | AGG_ROUTER_FAILURE | ["AGG-WA-03"] | AGG-WA-01 | uncertain | uncertain_on_wrong | low | UNCERTAIN |

_54 row(s)_
