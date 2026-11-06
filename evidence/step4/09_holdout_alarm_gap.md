# Holdout finding: incident alarms lost upstream, and what it does to the LLM

Captured 2026-11-06 02:28 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

The holdout evaluation (`04_evaluation.md`) shows the assistant **losing** accuracy against the ranker. Root cause found
afterwards (analysis only; nothing was re-run or tuned on the holdout): the generator derives incident alarm IDs from
the batch incident ID (`netmon_datagen.faults`: `opaque_id("ALM", incident_id, n)`, with `incident_id` = `INC-00001`,
`INC-00002`, … in every batch run). The holdout's fault alarms therefore reuse the alarm IDs of `history_1m` (and of
the step-2 `history` run), and the silver layer's cross-run deduplication (`dropDuplicatesWithinWatermark` on
`record_id`) drops them as redeliveries. Background alarm IDs include the run seed and survive. Result: the alarms
that corroborate a fault are missing for much of the holdout, while noise alarms on neighbouring elements remain.
The step-3 ranker's holdout features had the same gap (it still scored 93.2 % top-1 from KPIs); the dev days are
almost unaffected. This is a step-1/2 defect, recorded here and in the PR as a follow-up; it was not fixed in step 4
because fixing it means regenerating and re-ingesting the holdout, which changes step 3's published holdout result.

## Alarms per run: bronze (delivered) vs silver (after dedupe)

```sql
SELECT b._source_run AS run, count(*) AS bronze_rows, count(DISTINCT b.record_id) AS bronze_distinct_ids,
               count(DISTINCT s.record_id) AS in_silver
        FROM telco_netmon_febar_catalog.netmon_bronze.bronze_alarms b LEFT JOIN telco_netmon_febar_catalog.netmon_silver.silver_alarms s ON s.record_id = b.record_id AND s.source_run = b._source_run
        WHERE b._source_run IN ('history_1m', 'holdout_1m') GROUP BY 1 ORDER BY 1
```

| run | bronze_rows | bronze_distinct_ids | in_silver |
|---|---|---|---|
| history_1m | 96599 | 96024 | 95165 |
| holdout_1m | 29109 | 28933 | 23321 |

_2 row(s)_

## Holdout alarm IDs that already exist in silver under an earlier run

```sql
SELECT s.source_run AS earlier_run, count(*) AS holdout_rows_with_same_record_id
        FROM telco_netmon_febar_catalog.netmon_bronze.bronze_alarms b JOIN telco_netmon_febar_catalog.netmon_silver.silver_alarms s ON s.record_id = b.record_id AND s.source_run <> 'holdout_1m'
        WHERE b._source_run = 'holdout_1m' GROUP BY 1 ORDER BY 1
```

| earlier_run | holdout_rows_with_same_record_id |
|---|---|
| history | 538 |
| history_1m | 5405 |

_2 row(s)_

## DEV: assistant vs ranker by whether the context has an active alarm

```sql
SELECT CAST(get_json_object(c.context_json, '$.alarm_summary.n_active') AS INT) > 0 AS context_has_active_alarm,
                   l.fault_type, count(*) AS n, round(100 * avg(CAST(r.root_agreement AS INT)), 1) AS llm_pct,
                   round(100 * avg(CAST(r.ranker_top1_agreement AS INT)), 1) AS ranker_pct,
                   sum(CAST(r.llm_vs_ranker = 'changed_correct_to_wrong' AS INT)) AS changed_correct_to_wrong,
                   sum(CAST(r.llm_vs_ranker = 'uncertain_on_correct' AS INT)) AS uncertain_on_correct,
                   sum(CAST(r.llm_vs_ranker = 'changed_to_correct' AS INT)) AS changed_to_correct
            FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_results_dev r JOIN telco_netmon_febar_catalog.netmon_genai.genai_eval_contexts c USING (eval_id)
            JOIN telco_netmon_febar_catalog.netmon_eval.genai_eval_labels l USING (eval_id)
            GROUP BY GROUPING SETS ((1), (1, 2)) ORDER BY 1, 2 NULLS FIRST
```

| context_has_active_alarm | fault_type | n | llm_pct | ranker_pct | changed_correct_to_wrong | uncertain_on_correct | changed_to_correct |
|---|---|---|---|---|---|---|---|
| false | NULL | 6 | 100.0 | 100.0 | 0 | 0 | 0 |
| false | BACKHAUL_DEGRADATION | 5 | 100.0 | 100.0 | 0 | 0 | 0 |
| false | SITE_POWER_OUTAGE | 1 | 100.0 | 100.0 | 0 | 0 | 0 |
| true | NULL | 340 | 97.1 | 96.5 | 0 | 1 | 3 |
| true | AGG_ROUTER_FAILURE | 30 | 100.0 | 93.3 | 0 | 0 | 2 |
| true | AMF_OVERLOAD | 18 | 94.4 | 100.0 | 0 | 1 | 0 |
| true | BACKHAUL_DEGRADATION | 41 | 92.7 | 92.7 | 0 | 0 | 0 |
| true | CELL_OUTAGE | 205 | 97.6 | 97.1 | 0 | 0 | 1 |
| true | LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 100.0 | 0 | 0 | 0 |
| true | SITE_POWER_OUTAGE | 45 | 97.8 | 97.8 | 0 | 0 | 0 |

_10 row(s)_

## HOLDOUT: assistant vs ranker by whether the context has an active alarm

```sql
SELECT CAST(get_json_object(c.context_json, '$.alarm_summary.n_active') AS INT) > 0 AS context_has_active_alarm,
                   l.fault_type, count(*) AS n, round(100 * avg(CAST(r.root_agreement AS INT)), 1) AS llm_pct,
                   round(100 * avg(CAST(r.ranker_top1_agreement AS INT)), 1) AS ranker_pct,
                   sum(CAST(r.llm_vs_ranker = 'changed_correct_to_wrong' AS INT)) AS changed_correct_to_wrong,
                   sum(CAST(r.llm_vs_ranker = 'uncertain_on_correct' AS INT)) AS uncertain_on_correct,
                   sum(CAST(r.llm_vs_ranker = 'changed_to_correct' AS INT)) AS changed_to_correct
            FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_results_holdout r JOIN telco_netmon_febar_catalog.netmon_genai.genai_eval_contexts c USING (eval_id)
            JOIN telco_netmon_febar_catalog.netmon_eval.genai_eval_labels l USING (eval_id)
            GROUP BY GROUPING SETS ((1), (1, 2)) ORDER BY 1, 2 NULLS FIRST
```

| context_has_active_alarm | fault_type | n | llm_pct | ranker_pct | changed_correct_to_wrong | uncertain_on_correct | changed_to_correct |
|---|---|---|---|---|---|---|---|
| false | NULL | 164 | 80.5 | 98.8 | 5 | 25 | 0 |
| false | AGG_ROUTER_FAILURE | 6 | 83.3 | 83.3 | 0 | 0 | 0 |
| false | AMF_OVERLOAD | 6 | 50.0 | 100.0 | 0 | 3 | 0 |
| false | BACKHAUL_DEGRADATION | 24 | 100.0 | 100.0 | 0 | 0 | 0 |
| false | CELL_OUTAGE | 116 | 75.9 | 99.1 | 5 | 22 | 0 |
| false | LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 100.0 | 0 | 0 | 0 |
| false | SITE_POWER_OUTAGE | 11 | 100.0 | 100.0 | 0 | 0 | 0 |
| true | NULL | 159 | 83.6 | 95.6 | 13 | 8 | 2 |
| true | AGG_ROUTER_FAILURE | 33 | 81.8 | 90.9 | 2 | 2 | 1 |
| true | AMF_OVERLOAD | 11 | 81.8 | 100.0 | 0 | 2 | 0 |
| true | BACKHAUL_DEGRADATION | 22 | 100.0 | 100.0 | 0 | 0 | 0 |
| true | BUSHFIRE_GRID_OUTAGE | 1 | 100.0 | 0.0 | 0 | 0 | 1 |
| true | CELL_OUTAGE | 65 | 78.5 | 96.9 | 9 | 3 | 0 |
| true | SITE_POWER_OUTAGE | 27 | 85.2 | 96.3 | 2 | 1 | 0 |

_14 row(s)_

## Reading

- On dev, 340 of 346 contexts carry an active alarm and the assistant matches or beats the ranker.
- On the holdout, about half the contexts carry no active alarm (cell outages: about a third have one). Without the
  root's own alarm, the prompt's "alarms + impact pattern agree" reading fails: the assistant answers `uncertain` on
  correct ranker answers, or follows a surviving noise alarm on a neighbouring backhaul link.
- The lesson holds beyond this defect: OSS alarm feeds do drop and lag in real networks. The ranker, trained on KPIs
  and alarms, degrades gracefully; the LLM, told to look for corroborating alarms, does not. Keep the ranker as the
  system of record and treat the assistant as an explainer (see docs/genai_assistant.md, Results and Known limits).
