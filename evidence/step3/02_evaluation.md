# Evaluation vs the step-2 localiser: fresh holdout and dev

Captured 2026-11-05 23:47 UTC from workspace profile `febar` by `scripts/capture_evidence_step3.py`.

**How it is scored (GT-free first, ground truth after).** Every case of the run is scored by the frozen model
(`evaluate.case_outputs`: ID / feature columns and the score only). The ranked outputs are then attributed to
ground-truth incidents (same run and region, decision time in the incident window, case evidence overlapping
the footprint; per minute the output with the largest overlap). Matching never adds, removes or re-ranks
candidates. The step-2 heuristic is ranked on exactly the same case outputs ("heuristic, same cases"); step 2's
published region-wide `eval_rca_baseline` is shown as a secondary framing.

- **Top-1 / top-3**: the incident's primary output at the first decision time at least 5 minutes after impact
  start (up to 15 minutes).
- **Early catch**: every 1-minute decision time, the first one whose top-1 is a valid root with calibrated score
  >= the validation threshold (0.32). Times are signed `decision_ts - impact_start_ts`: pre-impact
  catches are negative, counted separately and kept in the median.

**Splits.**
- **Holdout** = `holdout_1m`: a fresh run generated after the design was frozen (new seed 4242 for faults,
  noise and defects, same network, 2026-10-17 … 10-18), through the unchanged step-2 pipeline, evaluated once
  with the frozen champion v4 (evaluation MLflow run `b678bdd4d2c84591bdc4e1bfec61d5c2`).
- **Dev** = the last two days of `history_1m` (2026-10-14 … 10-15). They were seen while the design was
  iterated, so they are **not** a holdout.
- **Validation** (2026-10-13) chose the calibration and the threshold.

Scored incidents only (customer-impacting, uncensored faults); n = incidents.

## HOLDOUT (holdout_1m, untouched): top-1 / top-3, model vs the step-2 heuristic on the same cases

`step2_region_wide_*` = step 2's published `eval_rca_baseline` (whole region, first 15 minutes), a different and weaker framing, shown for reference only.

```sql
SELECT fault_type, n, model_top1_pct, heuristic_same_cases_top1_pct, model_top3_pct,
                   heuristic_same_cases_top3_pct, baseline_top1_pct AS step2_region_wide_top1_pct,
                   baseline_top3_pct AS step2_region_wide_top3_pct
            FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_holdout_accuracy ORDER BY fault_type = 'ALL' DESC, n DESC
```

| fault_type | n | model_top1_pct | heuristic_same_cases_top1_pct | model_top3_pct | heuristic_same_cases_top3_pct | step2_region_wide_top1_pct | step2_region_wide_top3_pct |
|---|---|---|---|---|---|---|---|
| ALL | 337.0 | 93.2 | 78.3 | 95.3 | 80.7 | 27.9 | 43.9 |
| CELL_OUTAGE | 187.0 | 95.2 | 94.7 | 96.3 | 94.7 | 7.0 | 21.4 |
| BACKHAUL_DEGRADATION | 53.0 | 86.8 | 3.8 | 86.8 | 3.8 | 41.5 | 64.2 |
| AGG_ROUTER_FAILURE | 40.0 | 87.5 | 87.5 | 95.0 | 92.5 | 82.5 | 95.0 |
| SITE_POWER_OUTAGE | 38.0 | 97.4 | 84.2 | 100.0 | 100.0 | 23.7 | 50.0 |
| AMF_OVERLOAD | 17.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| BUSHFIRE_GRID_OUTAGE | 1.0 | 0.0 | 0.0 | 100.0 | 0.0 | 0.0 | 0.0 |
| LONG_HAUL_FIBRE_CUT | 1.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 0.0 |

_8 row(s)_

## HOLDOUT (holdout_1m, untouched): non-oracle companion, any live alert correct at the SLA decision time

No footprint matching: at the first decision time >= impact start + 5 min (up to 15 min), is any live alert of the incident's region (a case whose top-1 calibrated score >= the threshold) naming a valid root? Ground truth supplies only the region, the impact start and the root list. `oracle_matched_top1_pct` is the top-1 above (the case picked by footprint overlap, no threshold), on the same incidents. `median_region_alerts` = live alerts in the region at that minute. Job `banksia-rca-any-alert-metric` on the frozen v4 scores; nothing retrained.

```sql
SELECT fault_type, n, any_alert_correct_pct, matched_top1_pct AS oracle_matched_top1_pct,
                   median_region_alerts FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_holdout_any_alert_summary
            ORDER BY fault_type = 'ALL' DESC, n DESC
```

| fault_type | n | any_alert_correct_pct | oracle_matched_top1_pct | median_region_alerts |
|---|---|---|---|---|
| ALL | 337 | 81.0 | 93.2 | 5.0 |
| CELL_OUTAGE | 187 | 95.2 | 95.2 | 5.0 |
| BACKHAUL_DEGRADATION | 53 | 9.4 | 86.8 | 5.0 |
| AGG_ROUTER_FAILURE | 40 | 87.5 | 87.5 | 3.0 |
| SITE_POWER_OUTAGE | 38 | 97.4 | 97.4 | 5.0 |
| AMF_OVERLOAD | 17 | 100.0 | 100.0 | 1.0 |
| BUSHFIRE_GRID_OUTAGE | 1 | 0.0 | 0.0 | 5.0 |
| LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 100.0 | 5.0 |

_8 row(s)_

## HOLDOUT (holdout_1m, untouched): early catch (signed times), model vs heuristic on the same cases vs step-2 localisation

within 5 min = signed time <= 300 s (pre-impact catches included). The heuristic has no score threshold (its top-1 counts as soon as it is a root). Step 2 = `eval_incident_detection.localisation_ttd_s`, which step 2 clips at 0 (a lower bound for the rollup path); median 39 s of live pipeline latency comes on top of every system's time.

```sql
SELECT fault_type, n, model_localised_pct, model_within_5min_pct, model_pre_impact_n,
                   model_median_signed_s, heuristic_same_cases_within_5min_pct, heuristic_same_cases_median_signed_s,
                   step2_localised_pct, step2_within_5min_pct, step2_median_s
            FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_holdout_early_catch_summary ORDER BY fault_type = 'ALL' DESC, n DESC
```

| fault_type | n | model_localised_pct | model_within_5min_pct | model_pre_impact_n | model_median_signed_s | heuristic_same_cases_within_5min_pct | heuristic_same_cases_median_signed_s | step2_localised_pct | step2_within_5min_pct | step2_median_s |
|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 337 | 99.4 | 80.4 | 35 | 106.0 | 76.9 | 116.0 | 100.0 | 65.6 | 76.0 |
| CELL_OUTAGE | 187 | 99.5 | 94.7 | 0 | 98.5 | 93.6 | 97.0 | 100.0 | 100.0 | 51.0 |
| BACKHAUL_DEGRADATION | 53 | 98.1 | 0.0 | 0 | 615.0 | 0.0 | 727.5 | 100.0 | 0.0 | 1011.0 |
| AGG_ROUTER_FAILURE | 40 | 100.0 | 97.5 | 26 | -12.0 | 85.0 | 193.0 | 100.0 | 30.0 | 392.5 |
| SITE_POWER_OUTAGE | 38 | 100.0 | 97.4 | 0 | 156.0 | 84.2 | 152.5 | 100.0 | 57.9 | 195.0 |
| AMF_OVERLOAD | 17 | 100.0 | 100.0 | 9 | -113.0 | 100.0 | 204.0 | 100.0 | 0.0 | 514.0 |
| BUSHFIRE_GRID_OUTAGE | 1 | 100.0 | 0.0 | 0 | 759.0 | 0.0 | 8019.0 | 100.0 | 0.0 | 8010.0 |
| LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 100.0 | 0 | 236.0 | 100.0 | 176.0 | 100.0 | 0.0 | 416.0 |

_8 row(s)_

## HOLDOUT (holdout_1m, untouched): slow backhaul degradation, per incident

```sql
SELECT incident_id, impact_start_ts, localisation_s AS model_signed_s, within_5min AS model_within_5min,
                   heuristic_same_cases_localisation_s AS heuristic_signed_s, step2_localisation_s, step2_within_5min
            FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_holdout_early_catch WHERE fault_type = 'BACKHAUL_DEGRADATION' ORDER BY impact_start_ts
```

| incident_id | impact_start_ts | model_signed_s | model_within_5min | heuristic_signed_s | step2_localisation_s | step2_within_5min |
|---|---|---|---|---|---|---|
| INC-00004 | 2026-10-17T00:18:31.000Z | 2609.0 | false | 2609.0 | 1109.000000 | false |
| INC-00006 | 2026-10-17T00:20:49.000Z | 2471.0 | false | 2471.0 | 971.000000 | false |
| INC-00013 | 2026-10-17T00:56:35.000Z | 325.0 | false | 445.0 | 625.000000 | false |
| INC-00029 | 2026-10-17T02:45:49.000Z | 371.0 | false | 431.0 | 671.000000 | false |
| INC-00030 | 2026-10-17T02:46:25.000Z | 935.0 | false | 935.0 | 1235.000000 | false |
| INC-00037 | 2026-10-17T03:45:29.000Z | 511.0 | false | 631.0 | 991.000000 | false |
| INC-00044 | 2026-10-17T04:37:59.000Z | 541.0 | false | 661.0 | 841.000000 | false |
| INC-00052 | 2026-10-17T05:03:02.000Z | 538.0 | false | 598.0 | 838.000000 | false |
| INC-00083 | 2026-10-17T12:11:11.000Z | 3049.0 | false | 3049.0 | 3349.000000 | false |
| INC-00093 | 2026-10-17T13:26:39.000Z | 681.0 | false | 741.0 | 921.000000 | false |
| INC-00105 | 2026-10-17T14:07:53.000Z | 607.0 | false | 667.0 | 847.000000 | false |
| INC-00111 | 2026-10-17T14:43:33.000Z | 687.0 | false | 747.0 | 1107.000000 | false |
| INC-00114 | 2026-10-17T14:54:06.000Z | 594.0 | false | 714.0 | 1074.000000 | false |
| INC-00115 | 2026-10-17T14:54:15.000Z | 405.0 | false | 405.0 | 765.000000 | false |
| INC-00119 | 2026-10-17T15:28:13.000Z | 707.0 | false | 887.0 | 1396.000000 | false |
| INC-00124 | 2026-10-17T15:49:31.000Z | 809.0 | false | 869.0 | 1049.000000 | false |
| INC-00141 | 2026-10-17T17:36:26.000Z | 514.0 | false | 634.0 | 934.000000 | false |
| INC-00163 | 2026-10-17T20:17:53.000Z | 727.0 | false | 1087.0 | 1447.000000 | false |
| INC-00164 | 2026-10-17T20:20:13.000Z | 647.0 | false | 707.0 | 1007.000000 | false |
| INC-00169 | 2026-10-17T20:40:09.000Z | 771.0 | false | 831.0 | 1011.000000 | false |
| INC-00171 | 2026-10-17T20:52:08.000Z | 952.0 | false | 1132.0 | 1492.000000 | false |
| INC-00179 | 2026-10-17T21:40:15.000Z | 825.0 | false | 885.0 | 1305.000000 | false |
| INC-00184 | 2026-10-17T22:11:55.000Z | 305.0 | false | 365.0 | 605.000000 | false |
| INC-00186 | 2026-10-17T22:24:36.000Z | 624.0 | false | 744.0 | 1044.000000 | false |
| INC-00196 | 2026-10-17T23:16:16.000Z | 584.0 | false | 764.0 | 944.000000 | false |
| INC-00199 | 2026-10-17T23:22:25.000Z | 635.0 | false | 755.0 | 1175.000000 | false |
| INC-00200 | 2026-10-17T23:24:41.000Z | 619.0 | false | 679.0 | 1039.000000 | false |
| INC-00204 | 2026-10-18T00:06:34.000Z | NULL | false | NULL | 0.000000 | false |
| INC-00209 | 2026-10-18T00:16:03.000Z | 477.0 | false | 537.0 | 957.000000 | false |
| INC-00214 | 2026-10-18T00:39:56.000Z | 484.0 | false | 604.0 | 1024.000000 | false |
| INC-00227 | 2026-10-18T01:37:59.000Z | 421.0 | false | 541.0 | 841.000000 | false |
| INC-00229 | 2026-10-18T01:42:23.000Z | 697.0 | false | 757.0 | 1177.000000 | false |
| INC-00244 | 2026-10-18T03:13:27.000Z | 633.0 | false | 753.0 | 1113.000000 | false |
| INC-00247 | 2026-10-18T03:31:13.000Z | 467.0 | false | 767.0 | 947.000000 | false |
| INC-00255 | 2026-10-18T04:08:54.000Z | 846.0 | false | 966.0 | 1386.000000 | false |
| INC-00282 | 2026-10-18T12:17:07.000Z | 2693.0 | false | 2693.0 | 2993.000000 | false |
| INC-00288 | 2026-10-18T13:07:42.000Z | 318.0 | false | 438.0 | 858.000000 | false |
| INC-00291 | 2026-10-18T13:30:55.000Z | 485.0 | false | 605.0 | 965.000000 | false |
| INC-00292 | 2026-10-18T13:39:39.000Z | 681.0 | false | 861.0 | 1041.000000 | false |
| INC-00324 | 2026-10-18T16:42:56.000Z | 604.0 | false | 664.0 | 1144.000000 | false |
| INC-00329 | 2026-10-18T17:01:00.000Z | 900.0 | false | 960.0 | 1260.000000 | false |
| INC-00330 | 2026-10-18T17:01:14.000Z | 526.0 | false | 646.0 | 946.000000 | false |
| INC-00333 | 2026-10-18T17:11:48.000Z | 432.0 | false | 552.0 | 912.000000 | false |
| INC-00344 | 2026-10-18T17:47:24.000Z | 336.0 | false | 456.0 | 876.000000 | false |
| INC-00348 | 2026-10-18T18:07:49.000Z | 611.0 | false | 611.0 | 851.000000 | false |
| INC-00351 | 2026-10-18T18:11:07.000Z | 833.0 | false | 953.0 | 1253.000000 | false |
| INC-00357 | 2026-10-18T18:33:18.000Z | 762.0 | false | 882.0 | 1122.000000 | false |
| INC-00373 | 2026-10-18T20:39:52.000Z | 488.0 | false | 608.0 | 1028.000000 | false |
| INC-00376 | 2026-10-18T20:56:10.000Z | 590.0 | false | 650.0 | 950.000000 | false |
| INC-00378 | 2026-10-18T21:00:06.000Z | 654.0 | false | 774.0 | 1014.000000 | false |
| INC-00381 | 2026-10-18T21:24:18.000Z | 462.0 | false | 522.0 | 762.000000 | false |
| INC-00382 | 2026-10-18T21:24:37.000Z | 503.0 | false | 563.0 | 743.000000 | false |
| INC-00384 | 2026-10-18T21:43:09.000Z | 651.0 | false | 771.0 | 1131.000000 | false |

_53 row(s)_

## HOLDOUT (holdout_1m, untouched): secondary, alert-level fault precision (step 2's definitions)

Model alerts = case top-1 elements at or above the threshold, grouped per element with step 2's 10-minute gap and labelled with `netmon_pipeline.scoring`; the same code scores the step-2 detection rows of the same period. Reported, not optimised.

```sql
SELECT system, n_alerts, fault, censored, planned_suppressed, planned_fp, red_herring, unexplained,
                   fault_precision_pct FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_holdout_alert_precision
```

| system | n_alerts | fault | censored | planned_suppressed | planned_fp | red_herring | unexplained | fault_precision_pct |
|---|---|---|---|---|---|---|---|---|
| rca_model (top-1 >= threshold) | 395 | 353 | 0 | 13 | 0 | 0 | 29 | 92.4 |
| step2 detections | 14028 | 12600 | 0 | 1119 | 0 | 0 | 309 | 97.6 |

_2 row(s)_

## DEV (history_1m 10-14 … 10-15, seen during design): top-1 / top-3, model vs the step-2 heuristic on the same cases

`step2_region_wide_*` = step 2's published `eval_rca_baseline` (whole region, first 15 minutes), a different and weaker framing, shown for reference only.

```sql
SELECT fault_type, n, model_top1_pct, heuristic_same_cases_top1_pct, model_top3_pct,
                   heuristic_same_cases_top3_pct, baseline_top1_pct AS step2_region_wide_top1_pct,
                   baseline_top3_pct AS step2_region_wide_top3_pct
            FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_dev_accuracy ORDER BY fault_type = 'ALL' DESC, n DESC
```

| fault_type | n | model_top1_pct | heuristic_same_cases_top1_pct | model_top3_pct | heuristic_same_cases_top3_pct | step2_region_wide_top1_pct | step2_region_wide_top3_pct |
|---|---|---|---|---|---|---|---|
| ALL | 355.0 | 94.1 | 80.8 | 96.6 | 83.9 | 23.4 | 36.3 |
| CELL_OUTAGE | 205.0 | 97.1 | 96.6 | 100.0 | 97.6 | 5.4 | 14.6 |
| BACKHAUL_DEGRADATION | 55.0 | 78.2 | 5.5 | 78.2 | 5.5 | 34.5 | 49.1 |
| SITE_POWER_OUTAGE | 46.0 | 97.8 | 82.6 | 100.0 | 100.0 | 21.7 | 50.0 |
| AGG_ROUTER_FAILURE | 30.0 | 93.3 | 96.7 | 100.0 | 100.0 | 83.3 | 100.0 |
| AMF_OVERLOAD | 18.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| LONG_HAUL_FIBRE_CUT | 1.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 100.0 |

_7 row(s)_

## DEV (history_1m 10-14 … 10-15, seen during design): non-oracle companion, any live alert correct at the SLA decision time

No footprint matching: at the first decision time >= impact start + 5 min (up to 15 min), is any live alert of the incident's region (a case whose top-1 calibrated score >= the threshold) naming a valid root? Ground truth supplies only the region, the impact start and the root list. `oracle_matched_top1_pct` is the top-1 above (the case picked by footprint overlap, no threshold), on the same incidents. `median_region_alerts` = live alerts in the region at that minute. Job `banksia-rca-any-alert-metric` on the frozen v4 scores; nothing retrained.

```sql
SELECT fault_type, n, any_alert_correct_pct, matched_top1_pct AS oracle_matched_top1_pct,
                   median_region_alerts FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_dev_any_alert_summary
            ORDER BY fault_type = 'ALL' DESC, n DESC
```

| fault_type | n | any_alert_correct_pct | oracle_matched_top1_pct | median_region_alerts |
|---|---|---|---|---|
| ALL | 355 | 83.9 | 94.1 | 6.0 |
| CELL_OUTAGE | 205 | 97.1 | 97.1 | 7.0 |
| BACKHAUL_DEGRADATION | 55 | 12.7 | 78.2 | 5.0 |
| SITE_POWER_OUTAGE | 46 | 97.8 | 97.8 | 6.0 |
| AGG_ROUTER_FAILURE | 30 | 93.3 | 93.3 | 2.0 |
| AMF_OVERLOAD | 18 | 100.0 | 100.0 | 1.0 |
| LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 100.0 | 2.0 |

_7 row(s)_

## DEV (history_1m 10-14 … 10-15, seen during design): early catch (signed times), model vs heuristic on the same cases vs step-2 localisation

within 5 min = signed time <= 300 s (pre-impact catches included). The heuristic has no score threshold (its top-1 counts as soon as it is a root). Step 2 = `eval_incident_detection.localisation_ttd_s`, which step 2 clips at 0 (a lower bound for the rollup path); median 39 s of live pipeline latency comes on top of every system's time.

```sql
SELECT fault_type, n, model_localised_pct, model_within_5min_pct, model_pre_impact_n,
                   model_median_signed_s, heuristic_same_cases_within_5min_pct, heuristic_same_cases_median_signed_s,
                   step2_localised_pct, step2_within_5min_pct, step2_median_s
            FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_dev_early_catch_summary ORDER BY fault_type = 'ALL' DESC, n DESC
```

| fault_type | n | model_localised_pct | model_within_5min_pct | model_pre_impact_n | model_median_signed_s | heuristic_same_cases_within_5min_pct | heuristic_same_cases_median_signed_s | step2_localised_pct | step2_within_5min_pct | step2_median_s |
|---|---|---|---|---|---|---|---|---|---|---|
| ALL | 355 | 99.4 | 83.7 | 35 | 93.0 | 80.6 | 95.0 | 100.0 | 79.2 | 46.0 |
| CELL_OUTAGE | 205 | 100.0 | 97.6 | 0 | 89.0 | 97.1 | 89.0 | 100.0 | 100.0 | 36.0 |
| BACKHAUL_DEGRADATION | 55 | 96.4 | 5.5 | 0 | 618.0 | 0.0 | 734.0 | 100.0 | 0.0 | 1020.0 |
| SITE_POWER_OUTAGE | 46 | 100.0 | 97.8 | 1 | 114.0 | 82.6 | 135.0 | 100.0 | 97.8 | 145.0 |
| AGG_ROUTER_FAILURE | 30 | 100.0 | 100.0 | 23 | -11.0 | 100.0 | 34.5 | 100.0 | 100.0 | 11.5 |
| AMF_OVERLOAD | 18 | 100.0 | 100.0 | 11 | -57.0 | 100.0 | 203.5 | 100.0 | 0.0 | 508.5 |
| LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 100.0 | 0 | 168.0 | 100.0 | 168.0 | 100.0 | 100.0 | 228.0 |

_7 row(s)_

## DEV (history_1m 10-14 … 10-15, seen during design): slow backhaul degradation, per incident

```sql
SELECT incident_id, impact_start_ts, localisation_s AS model_signed_s, within_5min AS model_within_5min,
                   heuristic_same_cases_localisation_s AS heuristic_signed_s, step2_localisation_s, step2_within_5min
            FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_dev_early_catch WHERE fault_type = 'BACKHAUL_DEGRADATION' ORDER BY impact_start_ts
```

| incident_id | impact_start_ts | model_signed_s | model_within_5min | heuristic_signed_s | step2_localisation_s | step2_within_5min |
|---|---|---|---|---|---|---|
| INC-00781 | 2026-10-14T00:09:24.000Z | 696.0 | false | 756.0 | 1056.000000 | false |
| INC-00787 | 2026-10-14T00:47:05.000Z | 355.0 | false | 415.0 | 595.000000 | false |
| INC-00790 | 2026-10-14T01:24:22.000Z | 878.0 | false | 998.0 | 1358.000000 | false |
| INC-00791 | 2026-10-14T01:25:53.000Z | 487.0 | false | 607.0 | 967.000000 | false |
| INC-00798 | 2026-10-14T01:59:46.000Z | 614.0 | false | 734.0 | 1034.000000 | false |
| INC-00800 | 2026-10-14T02:04:54.000Z | 606.0 | false | 726.0 | 1026.000000 | false |
| INC-00801 | 2026-10-14T02:06:24.000Z | 756.0 | false | 816.0 | 1236.000000 | false |
| INC-00805 | 2026-10-14T02:20:54.000Z | 426.0 | false | 606.0 | 966.000000 | false |
| INC-00806 | 2026-10-14T02:21:42.000Z | 858.0 | false | 858.0 | 1218.000000 | false |
| INC-00850 | 2026-10-14T12:47:16.000Z | 644.0 | false | 764.0 | 1184.000000 | false |
| INC-00851 | 2026-10-14T13:00:59.000Z | 781.0 | false | 901.0 | 1261.000000 | false |
| INC-00854 | 2026-10-14T13:32:48.000Z | 372.0 | false | 432.0 | 852.000000 | false |
| INC-00858 | 2026-10-14T13:49:25.000Z | 1595.0 | false | 1595.0 | 1055.000000 | false |
| INC-00859 | 2026-10-14T13:51:22.000Z | 1478.0 | false | 1478.0 | 1238.000000 | false |
| INC-00866 | 2026-10-14T14:35:14.000Z | 286.0 | true | 406.0 | 706.000000 | false |
| INC-00873 | 2026-10-14T14:52:45.000Z | 435.0 | false | 495.0 | 855.000000 | false |
| INC-00892 | 2026-10-14T16:01:45.000Z | 615.0 | false | 615.0 | 915.000000 | false |
| INC-00895 | 2026-10-14T16:18:55.000Z | 965.0 | false | 1085.0 | 1385.000000 | false |
| INC-00898 | 2026-10-14T16:33:50.000Z | 910.0 | false | 1090.0 | 1390.000000 | false |
| INC-00902 | 2026-10-14T16:52:42.000Z | 618.0 | false | 678.0 | 858.000000 | false |
| INC-00907 | 2026-10-14T17:14:27.000Z | 633.0 | false | 753.0 | 1053.000000 | false |
| INC-00912 | 2026-10-14T17:35:22.000Z | 758.0 | false | 878.0 | 1298.000000 | false |
| INC-00920 | 2026-10-14T18:03:33.000Z | 327.0 | false | 447.0 | 807.000000 | false |
| INC-00931 | 2026-10-14T18:43:12.000Z | 528.0 | false | 648.0 | 828.000000 | false |
| INC-00946 | 2026-10-14T20:01:44.000Z | 7216.0 | false | 7216.0 | 7516.000000 | false |
| INC-00949 | 2026-10-14T20:20:00.000Z | 540.0 | false | 780.0 | 1020.000000 | false |
| INC-00962 | 2026-10-14T21:30:56.000Z | 544.0 | false | 724.0 | 1264.000000 | false |
| INC-00966 | 2026-10-14T21:55:28.000Z | 812.0 | false | 932.0 | 1292.000000 | false |
| INC-00978 | 2026-10-14T22:56:08.000Z | 472.0 | false | 532.0 | 952.000000 | false |
| INC-00986 | 2026-10-14T23:34:14.000Z | 1066.0 | false | NULL | 0.000000 | false |
| INC-01004 | 2026-10-15T01:19:07.000Z | 353.0 | false | 413.0 | 773.000000 | false |
| INC-01016 | 2026-10-15T02:16:10.000Z | 290.0 | true | 710.0 | 950.000000 | false |
| INC-01023 | 2026-10-15T02:51:09.000Z | NULL | false | NULL | 0.000000 | false |
| INC-01030 | 2026-10-15T03:07:45.000Z | 2775.0 | false | NULL | 0.000000 | false |
| INC-01032 | 2026-10-15T03:26:48.000Z | 852.0 | false | 5712.0 | 6012.000000 | false |
| INC-01033 | 2026-10-15T03:30:50.000Z | 1090.0 | false | 1150.0 | 1570.000000 | false |
| INC-01038 | 2026-10-15T03:51:50.000Z | 550.0 | false | 610.0 | 910.000000 | false |
| INC-01039 | 2026-10-15T03:53:19.000Z | 1001.0 | false | 1121.0 | 1421.000000 | false |
| INC-01046 | 2026-10-15T05:00:37.000Z | 743.0 | false | 863.0 | 1283.000000 | false |
| INC-01052 | 2026-10-15T06:30:01.000Z | 299.0 | true | 359.0 | 719.000000 | false |
| INC-01053 | 2026-10-15T06:41:20.000Z | NULL | false | NULL | 940.000000 | false |
| INC-01070 | 2026-10-15T11:10:49.000Z | 671.0 | false | 791.0 | 971.000000 | false |
| INC-01072 | 2026-10-15T11:30:48.000Z | 552.0 | false | 612.0 | 972.000000 | false |
| INC-01082 | 2026-10-15T12:45:24.000Z | 636.0 | false | 756.0 | 996.000000 | false |
| INC-01103 | 2026-10-15T14:35:52.000Z | 728.0 | false | 908.0 | 1268.000000 | false |
| INC-01126 | 2026-10-15T16:22:59.000Z | 601.0 | false | 661.0 | 841.000000 | false |
| INC-01130 | 2026-10-15T16:48:39.000Z | 561.0 | false | 681.0 | 1101.000000 | false |
| INC-01131 | 2026-10-15T17:16:29.000Z | 871.0 | false | 991.0 | 1231.000000 | false |
| INC-01140 | 2026-10-15T17:43:45.000Z | 495.0 | false | 555.0 | 795.000000 | false |
| INC-01160 | 2026-10-15T19:07:42.000Z | 6858.0 | false | 6858.0 | 7158.000000 | false |
| INC-01163 | 2026-10-15T19:19:29.000Z | 571.0 | false | 631.0 | 1051.000000 | false |
| INC-01165 | 2026-10-15T19:22:50.000Z | 670.0 | false | 790.0 | 1150.000000 | false |
| INC-01172 | 2026-10-15T20:15:33.000Z | 327.0 | false | 447.0 | 687.000000 | false |
| INC-01179 | 2026-10-15T21:06:53.000Z | 487.0 | false | 607.0 | 907.000000 | false |
| INC-01194 | 2026-10-15T22:21:10.000Z | 590.0 | false | 650.0 | 950.000000 | false |

_55 row(s)_

## DEV (history_1m 10-14 … 10-15, seen during design): secondary, alert-level fault precision (step 2's definitions)

Model alerts = case top-1 elements at or above the threshold, grouped per element with step 2's 10-minute gap and labelled with `netmon_pipeline.scoring`; the same code scores the step-2 detection rows of the same period. Reported, not optimised.

```sql
SELECT system, n_alerts, fault, censored, planned_suppressed, planned_fp, red_herring, unexplained,
                   fault_precision_pct FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_dev_alert_precision
```

| system | n_alerts | fault | censored | planned_suppressed | planned_fp | red_herring | unexplained | fault_precision_pct |
|---|---|---|---|---|---|---|---|---|
| rca_model (top-1 >= threshold) | 442 | 393 | 0 | 21 | 0 | 0 | 28 | 93.3 |
| step2 detections | 12827 | 10558 | 0 | 1839 | 0 | 0 | 430 | 96.1 |

_2 row(s)_

## Validation day (calibration and threshold were chosen here)

```sql
SELECT fault_type, n, model_top1_pct, heuristic_same_cases_top1_pct, model_top3_pct,
               heuristic_same_cases_top3_pct FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_val_accuracy ORDER BY fault_type = 'ALL' DESC, n DESC
```

| fault_type | n | model_top1_pct | heuristic_same_cases_top1_pct | model_top3_pct | heuristic_same_cases_top3_pct |
|---|---|---|---|---|---|
| ALL | 158.0 | 92.4 | 75.9 | 94.9 | 82.3 |
| CELL_OUTAGE | 87.0 | 96.6 | 95.4 | 97.7 | 96.6 |
| BACKHAUL_DEGRADATION | 25.0 | 76.0 | 0.0 | 80.0 | 0.0 |
| SITE_POWER_OUTAGE | 23.0 | 91.3 | 69.6 | 100.0 | 100.0 |
| AGG_ROUTER_FAILURE | 14.0 | 100.0 | 92.9 | 100.0 | 100.0 |
| AMF_OVERLOAD | 8.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| CORE_CONGESTION | 1.0 | 0.0 | 0.0 | 0.0 | 100.0 |

_7 row(s)_

## Live stream run (2026-10-08, out-of-run check; censored incidents not scored)

```sql
SELECT fault_type, n, model_top1_pct, heuristic_same_cases_top1_pct, model_top3_pct,
               heuristic_same_cases_top3_pct, baseline_top1_pct AS step2_region_wide_top1_pct
        FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_live_accuracy ORDER BY fault_type = 'ALL' DESC, n DESC
```

| fault_type | n | model_top1_pct | heuristic_same_cases_top1_pct | model_top3_pct | heuristic_same_cases_top3_pct | step2_region_wide_top1_pct |
|---|---|---|---|---|---|---|
| ALL | 26.0 | 84.6 | 73.1 | 84.6 | 73.1 | 53.8 |
| CELL_OUTAGE | 20.0 | 80.0 | 80.0 | 80.0 | 80.0 | 40.0 |
| BACKHAUL_DEGRADATION | 3.0 | 100.0 | 0.0 | 100.0 | 0.0 | 100.0 |
| SITE_POWER_OUTAGE | 2.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| AGG_ROUTER_FAILURE | 1.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |

_5 row(s)_

## Step 2's published RCA baseline per run (eval_rca_baseline, region-wide framing)

Step 2's "58 % top-1" is the `history` row: 19 incidents of a sparse 15-minute run. It is not comparable with the dense 1-minute runs, where several faults are usually open per region.

```sql
SELECT source_run, count(*) AS n, round(100 * avg(CAST(hit_at_1 AS INT)), 1) AS hit_at_1_pct,
               round(100 * avg(CAST(hit_at_3 AS INT)), 1) AS hit_at_3_pct
        FROM telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline GROUP BY 1 ORDER BY 1
```

| source_run | n | hit_at_1_pct | hit_at_3_pct |
|---|---|---|---|
| history | 19 | 57.9 | 68.4 |
| history_1m | 1083 | 25.8 | 39.5 |
| holdout_1m | 366 | 28.7 | 45.9 |
| stream | 26 | 53.8 | 73.1 |

_4 row(s)_

## Holdout incidents the model missed at top-1 (sample)

```sql
SELECT fault_type, incident_id, root_element_ids, top_candidates, heuristic_same_cases_top, has_output,
               evaluated_at_s FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_holdout_ranking WHERE NOT hit_at_1 ORDER BY fault_type, incident_id
        LIMIT 25
```

| fault_type | incident_id | root_element_ids | top_candidates | heuristic_same_cases_top | has_output | evaluated_at_s |
|---|---|---|---|---|---|---|
| AGG_ROUTER_FAILURE | INC-00007 | AGG-NQL-04 |  |  | false | NULL |
| AGG_ROUTER_FAILURE | INC-00139 | AGG-VIC-01 | AGG-VIC-04,BH-VIC-0015,CELL-VIC-00017-5G3 | AGG-VIC-04,AGG-VIC-01,BH-VIC-0038 | true | 316.0 |
| AGG_ROUTER_FAILURE | INC-00147 | AGG-NQL-04 | CELL-NQL-00004-5G3,AGG-NQL-04,CELL-NQL-00002-4G2 | AGG-NQL-04,BH-NQL-0010,BH-NQL-0009 | true | 315.0 |
| AGG_ROUTER_FAILURE | INC-00370 | AGG-VIC-04 | AGG-VIC-02,AGG-VIC-04,AGG-VIC-01 | AGG-VIC-04,AGG-VIC-02,AGG-VIC-01 | true | 338.0 |
| AGG_ROUTER_FAILURE | INC-00391 | AGG-WA-03 | AGG-WA-01,AGG-WA-03,AMF-WA-01 | AGG-WA-01,BH-WA-0005,BH-WA-0009 | true | 350.0 |
| BACKHAUL_DEGRADATION | INC-00004 | BH-NSW-0016 |  |  | false | NULL |
| BACKHAUL_DEGRADATION | INC-00006 | BH-NSW-0036 |  |  | false | NULL |
| BACKHAUL_DEGRADATION | INC-00030 | BH-VIC-0038 |  |  | false | NULL |
| BACKHAUL_DEGRADATION | INC-00083 | BH-VIC-0020 |  |  | false | NULL |
| BACKHAUL_DEGRADATION | INC-00171 | BH-VIC-0021 |  |  | false | NULL |
| BACKHAUL_DEGRADATION | INC-00204 | BH-NSW-0036 |  |  | false | NULL |
| BACKHAUL_DEGRADATION | INC-00282 | BH-NSW-0020 |  |  | false | NULL |
| BUSHFIRE_GRID_OUTAGE | INC-00073 | SITE-NSW-00087,SITE-NSW-00089 | BH-NSW-0037,CELL-NSW-00089-5G2,SITE-NSW-00089 | CELL-NSW-00089-5G2,AMF-NSW-01,UPF-NSW-01 | true | 339.0 |
| CELL_OUTAGE | INC-00001 | CELL-NSW-00058-5G1 |  |  | false | NULL |
| CELL_OUTAGE | INC-00002 | CELL-VIC-00103-4G3 |  |  | false | NULL |
| CELL_OUTAGE | INC-00003 | CELL-WA-00001-5G3 |  |  | false | NULL |
| CELL_OUTAGE | INC-00005 | CELL-VIC-00006-5G2 |  |  | false | NULL |
| CELL_OUTAGE | INC-00008 | CELL-WA-00010-4G2 |  |  | false | NULL |
| CELL_OUTAGE | INC-00010 | CELL-VIC-00044-5G1 |  |  | false | NULL |
| CELL_OUTAGE | INC-00140 | CELL-NSW-00022-4G3 | SITE-NSW-00021,CELL-NSW-00022-4G3,BH-NSW-0008 | SITE-NSW-00021,CELL-NSW-00021-4G1,CELL-NSW-00021-4G2 | true | 342.0 |
| CELL_OUTAGE | INC-00246 | CELL-WA-00035-5G3 | AGG-WA-01,CELL-WA-00035-5G3,BH-WA-0019 | AGG-WA-01,BH-WA-0005,BH-WA-0009 | true | 334.0 |
| CELL_OUTAGE | INC-00309 | CELL-VIC-00093-4G2 | AGG-VIC-03,BH-VIC-0036,CELL-VIC-00077-5G1 | AGG-VIC-02,AGG-VIC-03,AGG-VIC-01 | true | 359.0 |
| SITE_POWER_OUTAGE | INC-00097 | SITE-NSW-00086 | SITE-NSW-00087,SITE-NSW-00089,SITE-NSW-00086 | SITE-NSW-00086,SITE-NSW-00089,SITE-NSW-00087 | true | 316.0 |

_23 row(s)_
