# Holdout finding: incident alarms lost upstream, and what it does to the LLM

Captured 2026-11-06 08:14 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

**Status: resolved in PR #6** (resolution at the end; old vs new results in `10_holdout_rerun.md` and
`evidence/step3/08_alarm_id_fix.md`). The finding below is rebuilt from the snapshots taken before the fix
(`*_pr5` tables = the state of main 58004a7), so it reads exactly as it was found.

The holdout evaluation showed the assistant **losing** accuracy against the ranker. Root cause found afterwards
(analysis only; nothing was re-run or tuned on the holdout at the time): the generator derived incident alarm IDs from
the batch incident ID (`opaque_id("ALM", incident_id, n)`, with `incident_id` = `INC-00001`, `INC-00002`, … in every
batch run). The holdout's fault alarms therefore reused the alarm IDs of `history_1m`, and the silver layer's
cross-run deduplication (`dropDuplicatesWithinWatermark` on `record_id`) dropped them as redeliveries (dedupe state is
only evicted when a later batch advances the watermark, so the holdout batch was checked against `history_1m`'s keys).
`history_1m` lost 90 alarm IDs to the step-2 `history` run the same way. Background alarm IDs included the run seed
and survived. Result: the alarms that corroborate a fault were missing for much of the holdout, while noise alarms on
neighbouring elements remained.

## Alarms per run before the fix (snapshot)

`removed_by_dedupe` should equal `injected_duplicates`; `missing_ids_held_by_other_run` = distinct IDs absent from silver whose ID is in silver under another run.

```sql
SELECT * FROM telco_netmon_febar_catalog.netmon_eval.alarm_counts_pr5 ORDER BY run
```

| run | bronze_rows | bronze_distinct_ids | injected_duplicates | quarantined_rows | silver_rows | silver_distinct_ids | removed_by_dedupe | distinct_ids_missing_from_silver | missing_ids_held_by_other_run |
|---|---|---|---|---|---|---|---|---|---|
| history | 16730 | 16626 | 85 | 151 | 16494 | 16494 | 85 | 0 | 0 |
| history_1m | 96599 | 96024 | 480 | 864 | 95165 | 95165 | 570 | 90 | 89 |
| holdout_1m | 29109 | 28933 | 145 | 226 | 23321 | 23321 | 5562 | 5417 | 5380 |
| stream | 3154 | 3132 | 18 | 30 | 3106 | 3106 | 18 | 0 | 0 |

_4 row(s)_

## DEV (before the fix): assistant vs ranker by whether the context has an active alarm

```sql
SELECT CAST(get_json_object(c.context_json, '$.alarm_summary.n_active') AS INT) > 0 AS context_has_active_alarm,
               l.fault_type, count(*) AS n, round(100 * avg(CAST(r.root_agreement AS INT)), 1) AS llm_pct,
               round(100 * avg(CAST(r.ranker_top1_agreement AS INT)), 1) AS ranker_pct,
               sum(CAST(r.llm_vs_ranker = 'changed_correct_to_wrong' AS INT)) AS changed_correct_to_wrong,
               sum(CAST(r.llm_vs_ranker = 'uncertain_on_correct' AS INT)) AS uncertain_on_correct,
               sum(CAST(r.llm_vs_ranker = 'changed_to_correct' AS INT)) AS changed_to_correct
        FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_results_dev_pr5 r JOIN telco_netmon_febar_catalog.netmon_genai.genai_eval_contexts_pr5 c USING (eval_id)
        JOIN telco_netmon_febar_catalog.netmon_eval.genai_eval_labels_pr5 l USING (eval_id)
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

## HOLDOUT (before the fix): assistant vs ranker by whether the context has an active alarm

```sql
SELECT CAST(get_json_object(c.context_json, '$.alarm_summary.n_active') AS INT) > 0 AS context_has_active_alarm,
               l.fault_type, count(*) AS n, round(100 * avg(CAST(r.root_agreement AS INT)), 1) AS llm_pct,
               round(100 * avg(CAST(r.ranker_top1_agreement AS INT)), 1) AS ranker_pct,
               sum(CAST(r.llm_vs_ranker = 'changed_correct_to_wrong' AS INT)) AS changed_correct_to_wrong,
               sum(CAST(r.llm_vs_ranker = 'uncertain_on_correct' AS INT)) AS uncertain_on_correct,
               sum(CAST(r.llm_vs_ranker = 'changed_to_correct' AS INT)) AS changed_to_correct
        FROM telco_netmon_febar_catalog.netmon_genai.genai_eval_results_holdout_pr5 r JOIN telco_netmon_febar_catalog.netmon_genai.genai_eval_contexts_pr5 c USING (eval_id)
        JOIN telco_netmon_febar_catalog.netmon_eval.genai_eval_labels_pr5 l USING (eval_id)
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

## Reading (before the fix)

- On dev, 340 of 346 contexts carried an active alarm and the assistant matched or beat the ranker.
- On the holdout, about half the contexts carried no active alarm (cell outages: about a third had one). Without the
  root's own alarm, the prompt's "alarms + impact pattern agree" reading fails: the assistant answered `uncertain` on
  correct ranker answers, or followed a surviving noise alarm on a neighbouring backhaul link.
- The lesson holds beyond this defect: OSS alarm feeds do drop and lag in real networks. The ranker, trained on KPIs
  and alarms, degrades gracefully; the LLM, told to look for corroborating alarms, does not.

## Resolution (PR #6)

- **Fix**: alarm and change IDs hash a run key (`GeneratorConfig.run_id`, the landing sub-directory = `source_run`);
  event-time ties are broken by the run-independent key, so a new run id changes only IDs
  (`docs/data_model.md`, "IDs across runs"; tests in `tests/test_run_unique_ids.py`, including a regression that
  replays the original drop through the dedupe reference model).
- **Data**: `history_1m` and `holdout_1m` regenerated (same seeds and windows), verified to differ from the ingested
  files only in IDs, and their alarm / DQ-log / change-calendar feeds swapped in by `banksia-netmon-replace-run-feeds`
  (no full refresh). Every run now loses exactly its injected duplicates (table below).
- **Step 3**: training data was affected, so the ranker was retrained once with the frozen design (v5) and the holdout
  re-scored once (`evidence/step3/08_alarm_id_fix.md`).
- **Step 4**: evaluation set rebuilt; dev and the holdout re-run once with the frozen prompts (`force=true`, reason
  recorded on the MLflow run): `10_holdout_rerun.md`.

## Alarms per run after the fix (live)

```sql
SELECT n.run, o.silver_rows AS silver_before, n.silver_rows AS silver_after, n.injected_duplicates,
               o.removed_by_dedupe AS dedupe_removed_before, n.removed_by_dedupe AS dedupe_removed_after,
               n.distinct_ids_missing_from_silver AS missing_after
        FROM (
WITH b AS (SELECT _source_run run, count(*) bronze_rows, count(DISTINCT record_id) bronze_distinct_ids FROM telco_netmon_febar_catalog.netmon_bronze.bronze_alarms GROUP BY 1),
bid AS (SELECT DISTINCT _source_run run, record_id FROM telco_netmon_febar_catalog.netmon_bronze.bronze_alarms WHERE record_id IS NOT NULL),
s AS (SELECT source_run run, count(*) silver_rows, count(DISTINCT record_id) silver_distinct_ids FROM telco_netmon_febar_catalog.netmon_silver.silver_alarms GROUP BY 1),
sid AS (SELECT DISTINCT source_run run, record_id FROM telco_netmon_febar_catalog.netmon_silver.silver_alarms),
q AS (SELECT DISTINCT _source_run run, record_id FROM telco_netmon_febar_catalog.netmon_silver.silver_quarantine WHERE feed = 'alarms' AND record_id IS NOT NULL),
qn AS (SELECT _source_run run, count(*) quarantined_rows FROM telco_netmon_febar_catalog.netmon_silver.silver_quarantine WHERE feed = 'alarms' GROUP BY 1),
dup AS (SELECT _source_run run, count(*) injected_duplicates FROM telco_netmon_febar_catalog.netmon_eval.bronze_gt_dq_injections WHERE feed = 'alarms' AND defect_type = 'duplicate' GROUP BY 1),
miss AS (SELECT m.run, m.record_id, EXISTS (SELECT 1 FROM sid o WHERE o.record_id = m.record_id AND o.run <> m.run) AS in_other_run
         FROM (SELECT * FROM bid LEFT ANTI JOIN sid USING (run, record_id) LEFT ANTI JOIN q USING (run, record_id)) m),
mc AS (SELECT run, count(*) missing_ids, count_if(in_other_run) missing_ids_held_by_other_run FROM miss GROUP BY 1)
SELECT b.run, b.bronze_rows, b.bronze_distinct_ids, coalesce(dup.injected_duplicates, 0) injected_duplicates,
       coalesce(qn.quarantined_rows, 0) quarantined_rows, s.silver_rows, s.silver_distinct_ids,
       b.bronze_rows - s.silver_rows - coalesce(qn.quarantined_rows, 0) AS removed_by_dedupe,
       coalesce(mc.missing_ids, 0) distinct_ids_missing_from_silver, coalesce(mc.missing_ids_held_by_other_run, 0) missing_ids_held_by_other_run
FROM b LEFT JOIN s USING (run) LEFT JOIN qn USING (run) LEFT JOIN dup USING (run) LEFT JOIN mc USING (run)
) n JOIN telco_netmon_febar_catalog.netmon_eval.alarm_counts_pr5 o USING (run) ORDER BY n.run
```

| run | silver_before | silver_after | injected_duplicates | dedupe_removed_before | dedupe_removed_after | missing_after |
|---|---|---|---|---|---|---|
| history | 16494 | 16494 | 85 | 85 | 85 | 0 |
| history_1m | 95165 | 95254 | 480 | 570 | 480 | 0 |
| holdout_1m | 23321 | 28705 | 145 | 5562 | 145 | 0 |
| stream | 3106 | 3106 | 18 | 18 | 18 | 0 |

_4 row(s)_

## HOLDOUT (after the fix): assistant vs ranker by whether the context has an active alarm

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
| false | NULL | 8 | 87.5 | 100.0 | 0 | 1 | 0 |
| false | AMF_OVERLOAD | 1 | 0.0 | 100.0 | 0 | 1 | 0 |
| false | BACKHAUL_DEGRADATION | 5 | 100.0 | 100.0 | 0 | 0 | 0 |
| false | CELL_OUTAGE | 2 | 100.0 | 100.0 | 0 | 0 | 0 |
| true | NULL | 315 | 97.8 | 98.7 | 2 | 1 | 0 |
| true | AGG_ROUTER_FAILURE | 39 | 94.9 | 97.4 | 1 | 0 | 0 |
| true | AMF_OVERLOAD | 16 | 93.8 | 100.0 | 0 | 1 | 0 |
| true | BACKHAUL_DEGRADATION | 41 | 100.0 | 100.0 | 0 | 0 | 0 |
| true | BUSHFIRE_GRID_OUTAGE | 1 | 0.0 | 0.0 | 0 | 0 | 0 |
| true | CELL_OUTAGE | 179 | 98.3 | 98.9 | 1 | 0 | 0 |
| true | LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 100.0 | 0 | 0 | 0 |
| true | SITE_POWER_OUTAGE | 38 | 100.0 | 100.0 | 0 | 0 | 0 |

_12 row(s)_
