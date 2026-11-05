# Evaluation vs the step-2 localiser (held-out time split)

Captured 2026-11-05 16:33 UTC from workspace profile `febar` by `scripts/capture_evidence_step3.py`.

Test split = the last two days of `history_1m` (decision times from 2026-10-14 00:00 UTC), never used for any
choice. Validation (2026-10-13) chose the calibration and the alert threshold (0.31). Incidents are
scored faults only (customer-impacting, uncensored). `baseline_*` is step 2's `eval_rca_baseline` exactly as
published (region-wide ranking); `heuristic_same_cases_*` is the same heuristic applied to exactly the cases the
model ranks, so the framing and the model contributions can be told apart. n = incidents.

## Top-1 / top-3 accuracy, overall and by fault type (test)

```sql
SELECT fault_type, n, model_top1_pct, baseline_top1_pct, heuristic_same_cases_top1_pct,
               model_top3_pct, baseline_top3_pct, heuristic_same_cases_top3_pct
        FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_test_accuracy ORDER BY fault_type = 'ALL' DESC, n DESC
```

| fault_type | n | model_top1_pct | baseline_top1_pct | heuristic_same_cases_top1_pct | model_top3_pct | baseline_top3_pct | heuristic_same_cases_top3_pct |
|---|---|---|---|---|---|---|---|
| ALL | 355.0 | 81.4 | 23.4 | 76.1 | 93.5 | 36.3 | 85.1 |
| CELL_OUTAGE | 205.0 | 78.5 | 5.4 | 74.1 | 96.1 | 14.6 | 83.9 |
| BACKHAUL_DEGRADATION | 55.0 | 76.4 | 34.5 | 67.3 | 78.2 | 49.1 | 67.3 |
| SITE_POWER_OUTAGE | 46.0 | 84.8 | 21.7 | 73.9 | 93.5 | 50.0 | 95.7 |
| AGG_ROUTER_FAILURE | 30.0 | 93.3 | 83.3 | 93.3 | 100.0 | 100.0 | 100.0 |
| AMF_OVERLOAD | 18.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| LONG_HAUL_FIBRE_CUT | 1.0 | 100.0 | 0.0 | 100.0 | 100.0 | 100.0 | 100.0 |

_7 row(s)_

## Early catch: localised by the model's top-1 above the threshold, vs step-2 localisation (test)

Model time = first 1-minute decision time whose top-1 element is a valid root with calibrated score >= threshold, minus impact start (decision time = when all its inputs had arrived; pipeline latency, median 39 s live in step 2, comes on top). Step 2 = `eval_incident_detection.localisation_ttd_s` (a detection or the rollup on a root; a lower bound for the rollup path).

```sql
SELECT fault_type, n, model_localised_pct, model_within_5min_pct, model_median_s,
               step2_localised_pct, step2_within_5min_pct, step2_median_s
        FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_test_early_catch_summary ORDER BY fault_type = 'ALL' DESC, n DESC
```

| fault_type | n | model_localised_pct | model_within_5min_pct | model_median_s | step2_localised_pct | step2_within_5min_pct | step2_median_s |
|---|---|---|---|---|---|---|---|
| ALL | 355 | 99.4 | 83.7 | 92.0 | 100.0 | 79.2 | 46.0 |
| CELL_OUTAGE | 205 | 100.0 | 97.6 | 88.0 | 100.0 | 100.0 | 36.0 |
| BACKHAUL_DEGRADATION | 55 | 96.4 | 5.5 | 618.0 | 100.0 | 0.0 | 1020.0 |
| SITE_POWER_OUTAGE | 46 | 100.0 | 97.8 | 103.5 | 100.0 | 97.8 | 145.0 |
| AGG_ROUTER_FAILURE | 30 | 100.0 | 100.0 | 0.0 | 100.0 | 100.0 | 11.5 |
| AMF_OVERLOAD | 18 | 100.0 | 100.0 | 0.0 | 100.0 | 0.0 | 508.5 |
| LONG_HAUL_FIBRE_CUT | 1 | 100.0 | 100.0 | 168.0 | 100.0 | 100.0 | 228.0 |

_7 row(s)_

## Slow backhaul degradation, per incident (test)

```sql
SELECT incident_id, impact_start_ts, localisation_s AS model_localisation_s, within_5min AS model_within_5min,
               step2_localisation_s, step2_within_5min
        FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_test_early_catch WHERE fault_type = 'BACKHAUL_DEGRADATION' ORDER BY impact_start_ts
```

| incident_id | impact_start_ts | model_localisation_s | model_within_5min | step2_localisation_s | step2_within_5min |
|---|---|---|---|---|---|
| INC-00781 | 2026-10-14T00:09:24.000Z | 696.0 | false | 1056.000000 | false |
| INC-00787 | 2026-10-14T00:47:05.000Z | 355.0 | false | 595.000000 | false |
| INC-00790 | 2026-10-14T01:24:22.000Z | 878.0 | false | 1358.000000 | false |
| INC-00791 | 2026-10-14T01:25:53.000Z | 487.0 | false | 967.000000 | false |
| INC-00798 | 2026-10-14T01:59:46.000Z | 614.0 | false | 1034.000000 | false |
| INC-00800 | 2026-10-14T02:04:54.000Z | 606.0 | false | 1026.000000 | false |
| INC-00801 | 2026-10-14T02:06:24.000Z | 756.0 | false | 1236.000000 | false |
| INC-00805 | 2026-10-14T02:20:54.000Z | 426.0 | false | 966.000000 | false |
| INC-00806 | 2026-10-14T02:21:42.000Z | 858.0 | false | 1218.000000 | false |
| INC-00850 | 2026-10-14T12:47:16.000Z | 644.0 | false | 1184.000000 | false |
| INC-00851 | 2026-10-14T13:00:59.000Z | 781.0 | false | 1261.000000 | false |
| INC-00854 | 2026-10-14T13:32:48.000Z | 372.0 | false | 852.000000 | false |
| INC-00858 | 2026-10-14T13:49:25.000Z | 1595.0 | false | 1055.000000 | false |
| INC-00859 | 2026-10-14T13:51:22.000Z | 1478.0 | false | 1238.000000 | false |
| INC-00866 | 2026-10-14T14:35:14.000Z | 286.0 | true | 706.000000 | false |
| INC-00873 | 2026-10-14T14:52:45.000Z | 435.0 | false | 855.000000 | false |
| INC-00892 | 2026-10-14T16:01:45.000Z | 615.0 | false | 915.000000 | false |
| INC-00895 | 2026-10-14T16:18:55.000Z | 965.0 | false | 1385.000000 | false |
| INC-00898 | 2026-10-14T16:33:50.000Z | 910.0 | false | 1390.000000 | false |
| INC-00902 | 2026-10-14T16:52:42.000Z | 618.0 | false | 858.000000 | false |
| INC-00907 | 2026-10-14T17:14:27.000Z | 633.0 | false | 1053.000000 | false |
| INC-00912 | 2026-10-14T17:35:22.000Z | 758.0 | false | 1298.000000 | false |
| INC-00920 | 2026-10-14T18:03:33.000Z | 327.0 | false | 807.000000 | false |
| INC-00931 | 2026-10-14T18:43:12.000Z | 528.0 | false | 828.000000 | false |
| INC-00946 | 2026-10-14T20:01:44.000Z | 7216.0 | false | 7516.000000 | false |
| INC-00949 | 2026-10-14T20:20:00.000Z | 540.0 | false | 1020.000000 | false |
| INC-00962 | 2026-10-14T21:30:56.000Z | 544.0 | false | 1264.000000 | false |
| INC-00966 | 2026-10-14T21:55:28.000Z | 812.0 | false | 1292.000000 | false |
| INC-00978 | 2026-10-14T22:56:08.000Z | 472.0 | false | 952.000000 | false |
| INC-00986 | 2026-10-14T23:34:14.000Z | 1066.0 | false | 0.000000 | false |
| INC-01004 | 2026-10-15T01:19:07.000Z | 353.0 | false | 773.000000 | false |
| INC-01016 | 2026-10-15T02:16:10.000Z | 290.0 | true | 950.000000 | false |
| INC-01023 | 2026-10-15T02:51:09.000Z | NULL | false | 0.000000 | false |
| INC-01030 | 2026-10-15T03:07:45.000Z | 2775.0 | false | 0.000000 | false |
| INC-01032 | 2026-10-15T03:26:48.000Z | 852.0 | false | 6012.000000 | false |
| INC-01033 | 2026-10-15T03:30:50.000Z | 1090.0 | false | 1570.000000 | false |
| INC-01038 | 2026-10-15T03:51:50.000Z | 550.0 | false | 910.000000 | false |
| INC-01039 | 2026-10-15T03:53:19.000Z | 1001.0 | false | 1421.000000 | false |
| INC-01046 | 2026-10-15T05:00:37.000Z | 743.0 | false | 1283.000000 | false |
| INC-01052 | 2026-10-15T06:30:01.000Z | 299.0 | true | 719.000000 | false |
| INC-01053 | 2026-10-15T06:41:20.000Z | NULL | false | 940.000000 | false |
| INC-01070 | 2026-10-15T11:10:49.000Z | 671.0 | false | 971.000000 | false |
| INC-01072 | 2026-10-15T11:30:48.000Z | 552.0 | false | 972.000000 | false |
| INC-01082 | 2026-10-15T12:45:24.000Z | 636.0 | false | 996.000000 | false |
| INC-01103 | 2026-10-15T14:35:52.000Z | 728.0 | false | 1268.000000 | false |
| INC-01126 | 2026-10-15T16:22:59.000Z | 601.0 | false | 841.000000 | false |
| INC-01130 | 2026-10-15T16:48:39.000Z | 561.0 | false | 1101.000000 | false |
| INC-01131 | 2026-10-15T17:16:29.000Z | 871.0 | false | 1231.000000 | false |
| INC-01140 | 2026-10-15T17:43:45.000Z | 495.0 | false | 795.000000 | false |
| INC-01160 | 2026-10-15T19:07:42.000Z | 6858.0 | false | 7158.000000 | false |
| INC-01163 | 2026-10-15T19:19:29.000Z | 571.0 | false | 1051.000000 | false |
| INC-01165 | 2026-10-15T19:22:50.000Z | 670.0 | false | 1150.000000 | false |
| INC-01172 | 2026-10-15T20:15:33.000Z | 327.0 | false | 687.000000 | false |
| INC-01179 | 2026-10-15T21:06:53.000Z | 487.0 | false | 907.000000 | false |
| INC-01194 | 2026-10-15T22:21:10.000Z | 590.0 | false | 950.000000 | false |

_55 row(s)_

## Secondary: alert-level fault precision (test days), step 2's definitions

Model alerts = case top-1 elements at or above the threshold, grouped per element with step 2's 10-minute gap and labelled with `netmon_pipeline.scoring` (the same code scores the step-2 detection rows of the same days). Reported, not optimised.

```sql
SELECT system, n_alerts, fault, censored, planned_suppressed, planned_fp, red_herring, unexplained,
               fault_precision_pct, maintenance_suppression_pct
        FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_test_alert_precision
```

| system | n_alerts | fault | censored | planned_suppressed | planned_fp | red_herring | unexplained | fault_precision_pct | maintenance_suppression_pct |
|---|---|---|---|---|---|---|---|---|---|
| rca_model (top-1 >= threshold) | 442 | 393 | 0 | 21 | 0 | 0 | 28 | 93.3 | 100.0 |
| step2 detections | 12827 | 10558 | 0 | 1839 | 0 | 0 | 430 | 96.1 | 100.0 |

_2 row(s)_

## Validation day (for reference; used for calibration and the threshold)

```sql
SELECT fault_type, n, model_top1_pct, baseline_top1_pct, heuristic_same_cases_top1_pct, model_top3_pct,
               baseline_top3_pct FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_val_accuracy ORDER BY fault_type = 'ALL' DESC, n DESC
```

| fault_type | n | model_top1_pct | baseline_top1_pct | heuristic_same_cases_top1_pct | model_top3_pct | baseline_top3_pct |
|---|---|---|---|---|---|---|
| ALL | 158.0 | 82.3 | 23.4 | 72.2 | 93.7 | 35.4 |
| CELL_OUTAGE | 87.0 | 79.3 | 4.6 | 71.3 | 94.3 | 10.3 |
| BACKHAUL_DEGRADATION | 25.0 | 76.0 | 36.0 | 60.0 | 80.0 | 56.0 |
| SITE_POWER_OUTAGE | 23.0 | 82.6 | 21.7 | 69.6 | 100.0 | 47.8 |
| AGG_ROUTER_FAILURE | 14.0 | 100.0 | 78.6 | 92.9 | 100.0 | 100.0 |
| AMF_OVERLOAD | 8.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| CORE_CONGESTION | 1.0 | 100.0 | 0.0 | 0.0 | 100.0 | 0.0 |

_7 row(s)_

## Out-of-run check: live stream run (2026-10-08, different run, censored excluded)

```sql
SELECT fault_type, n, model_top1_pct, baseline_top1_pct, model_top3_pct, baseline_top3_pct
        FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_live_accuracy ORDER BY fault_type = 'ALL' DESC, n DESC
```

| fault_type | n | model_top1_pct | baseline_top1_pct | model_top3_pct | baseline_top3_pct |
|---|---|---|---|---|---|
| ALL | 26.0 | 80.8 | 53.8 | 84.6 | 73.1 |
| CELL_OUTAGE | 20.0 | 75.0 | 40.0 | 80.0 | 65.0 |
| BACKHAUL_DEGRADATION | 3.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| SITE_POWER_OUTAGE | 2.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| AGG_ROUTER_FAILURE | 1.0 | 100.0 | 100.0 | 100.0 | 100.0 |

_5 row(s)_

## Step 2's published RCA baseline per run (eval_rca_baseline)

The 58 % quoted in step 2 is `history` (15-minute ROP, 19 incidents). The 1-minute training run has ~60x more concurrent faults, where the region-wide heuristic is much weaker.

```sql
SELECT source_run, count(*) AS n, round(100 * avg(CAST(hit_at_1 AS INT)), 1) AS hit_at_1_pct,
               round(100 * avg(CAST(hit_at_3 AS INT)), 1) AS hit_at_3_pct
        FROM telco_netmon_febar_catalog.netmon_eval.eval_rca_baseline GROUP BY 1 ORDER BY 1
```

| source_run | n | hit_at_1_pct | hit_at_3_pct |
|---|---|---|---|
| history | 19 | 57.9 | 68.4 |
| history_1m | 1083 | 25.8 | 39.5 |
| stream | 26 | 53.8 | 73.1 |

_3 row(s)_

## Test incidents the model missed at top-1 (sample)

```sql
SELECT fault_type, incident_id, root_element_ids, top_candidates, baseline_top_candidates, n_cases,
               root_in_candidates
        FROM telco_netmon_febar_catalog.netmon_rca.rca_eval_test_ranking WHERE NOT hit_at_1 ORDER BY fault_type, incident_id LIMIT 25
```

| fault_type | incident_id | root_element_ids | top_candidates | baseline_top_candidates | n_cases | root_in_candidates |
|---|---|---|---|---|---|---|
| AGG_ROUTER_FAILURE | INC-00828 | AGG-NQL-04 | AGG-NQL-01,AGG-NQL-04,CELL-NQL-00012-4G2 | AGG-NQL-04,AGG-NQL-01,BH-NQL-0010 | 23 | true |
| AGG_ROUTER_FAILURE | INC-01106 | AGG-NQL-03 | AGG-NQL-01,AGG-NQL-03,CELL-NQL-00021-4G2 | AGG-NQL-03,AGG-NQL-01,BH-NQL-0002 | 19 | true |
| BACKHAUL_DEGRADATION | INC-00858 | BH-VIC-0010 | BH-VIC-0009,CELL-VIC-00013-4G1,CELL-VIC-00017-4G3 | AGG-VIC-04,BH-VIC-0038,BH-VIC-0040 | 5 | true |
| BACKHAUL_DEGRADATION | INC-00859 | BH-VIC-0017 | BH-VIC-0002,BH-VIC-0009,CELL-VIC-00013-4G1 | AGG-VIC-04,BH-VIC-0038,BH-VIC-0040 | 5 | true |
| BACKHAUL_DEGRADATION | INC-00895 | BH-VIC-0035 |  | BH-VIC-0009,SITE-VIC-00002,SITE-VIC-00020 | 0 | false |
| BACKHAUL_DEGRADATION | INC-00898 | BH-NSW-0018 |  | SITE-NSW-00066,SITE-NSW-00106,CELL-NSW-00041-5G2 | 0 | false |
| BACKHAUL_DEGRADATION | INC-00946 | BH-WA-0004 |  | CELL-WA-00009-5G2,CELL-WA-00010-4G2 | 0 | false |
| BACKHAUL_DEGRADATION | INC-00949 | BH-NQL-0005 | BH-NQL-0006,BH-NQL-0005,AGG-NQL-03 | BH-NQL-0005,BH-NQL-0006,SITE-NQL-00010 | 8 | true |
| BACKHAUL_DEGRADATION | INC-00986 | BH-NSW-0026 |  | AGG-NSW-01,BH-NSW-0014,BH-NSW-0004 | 0 | false |
| BACKHAUL_DEGRADATION | INC-01023 | BH-NSW-0055 |  | BH-NSW-0019,BH-NSW-0049,SITE-NSW-00044 | 0 | false |
| BACKHAUL_DEGRADATION | INC-01030 | BH-VIC-0019 |  | SITE-VIC-00095,CELL-VIC-00002-5G3,CELL-VIC-00005-4G1 | 0 | false |
| BACKHAUL_DEGRADATION | INC-01033 | BH-NSW-0042 |  | BH-NSW-0019,SITE-NSW-00044,SITE-NSW-00045 | 0 | false |
| BACKHAUL_DEGRADATION | INC-01039 | BH-NSW-0032 |  | BH-NSW-0042,SITE-NSW-00098,CELL-NSW-00052-5G1 | 0 | false |
| BACKHAUL_DEGRADATION | INC-01053 | BH-WA-0006 | BH-WA-0005,BH-WA-0004,BH-WA-0001 | BH-WA-0005,BH-WA-0004,BH-WA-0001 | 6 | true |
| BACKHAUL_DEGRADATION | INC-01160 | BH-NQL-0006 |  | AGG-NQL-01,BH-NQL-0002,BH-NQL-0001 | 0 | false |
| CELL_OUTAGE | INC-00785 | CELL-WA-00013-4G3 | CELL-WA-00001-4G1,CELL-WA-00013-4G3,SITE-WA-00010 | BH-WA-0017,SITE-WA-00034,BH-WA-0013 | 16 | true |
| CELL_OUTAGE | INC-00804 | CELL-NSW-00104-5G1 | BH-NSW-0055,CELL-NSW-00104-5G1,SITE-NSW-00116 | BH-NSW-0014,BH-NSW-0055,SITE-NSW-00006 | 15 | true |
| CELL_OUTAGE | INC-00810 | CELL-VIC-00068-4G3 | BH-VIC-0038,CELL-VIC-00068-4G3,CELL-VIC-00073-4G1 | BH-VIC-0019,BH-VIC-0038,BH-VIC-0017 | 17 | true |
| CELL_OUTAGE | INC-00811 | CELL-VIC-00071-4G3 | CELL-VIC-00068-4G3,CELL-VIC-00071-4G3,CELL-VIC-00073-4G1 | BH-VIC-0019,BH-VIC-0017,SITE-VIC-00010 | 16 | true |
| CELL_OUTAGE | INC-00822 | CELL-VIC-00082-5G3 | CELL-VIC-00078-5G2,CELL-VIC-00082-5G3,SITE-VIC-00082 | BH-VIC-0019,BH-VIC-0017,SITE-VIC-00010 | 14 | true |
| CELL_OUTAGE | INC-00857 | CELL-VIC-00042-4G2 | BH-VIC-0009,BH-VIC-0021,CELL-VIC-00013-4G1 | AGG-VIC-04,BH-VIC-0038,BH-VIC-0040 | 14 | true |
| CELL_OUTAGE | INC-00862 | CELL-VIC-00026-5G2 | BH-VIC-0002,BH-VIC-0009,CELL-VIC-00013-4G1 | AGG-VIC-04,BH-VIC-0038,BH-VIC-0040 | 15 | true |
| CELL_OUTAGE | INC-00872 | CELL-VIC-00028-4G3 | BH-VIC-0009,BH-VIC-0017,CELL-VIC-00026-5G2 | BH-VIC-0028,BH-VIC-0002,BH-VIC-0009 | 20 | true |
| CELL_OUTAGE | INC-00874 | CELL-WA-00006-4G3 | BH-WA-0006,CELL-WA-00006-4G3,CELL-WA-00013-4G3 | AGG-WA-02,BH-WA-0010,BH-WA-0015 | 17 | true |
| CELL_OUTAGE | INC-00886 | CELL-VIC-00102-4G2 | CELL-VIC-00092-4G1,CELL-VIC-00102-4G2,CELL-VIC-00107-5G1 | BH-VIC-0009,SITE-VIC-00002,SITE-VIC-00020 | 15 | true |

_25 row(s)_
