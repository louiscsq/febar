# Step 6: holdout reading re-scored from its stored detections

Generated 2026-11-07 02:09 UTC by `scripts/collective_backhaul_experiment.py`.

- reading `holdout` (`holdout_1m`, 2026-10-17T00:00:00Z .. 2026-10-19T00:00:00Z); 5421 detections read back from `telco_netmon_febar_catalog.netmon_eval.eval_collective_backhaul_experiment`, as written by the
  single scoring run with the rule frozen at `e866511994f49fcf0084c994228221f6eb52af9a`. **No detection was recomputed and no KPI / health row of `holdout_1m` was
  read again.** Only the scoring changed.
- Why: the as-run file (03_holdout_reading.md) took the per-cell first detection from eval_incident_detection.impact_ttd_s, which is 0 for an undetected incident (greatest(NULL, 0) = 0), so INC-00204, detected by neither detector, counted as a per-cell detection at 0 s. Fixed in fetch_before (commit after 03); the detections and the false-alarm figures are unaffected. The 60 s watermark sensitivity in 03 has the same issue in its before / combined rows (its collective-alone rows are unaffected) and is not recomputed here, since that would re-read the run's health data.
- scored incidents: 53; healthy link-days: 195.6.

## Time to detect, BACKHAUL_DEGRADATION (n = 53)

Undetected incidents count against 'within 5 min' but not in the percentiles.

| subset | n | detector | detected | median_ttd_s | p90_ttd_s | within_5min_pct |
|---|---|---|---|---|---|---|
| all | 53 | before: per-cell (published metric a) | 52 | 562.0 | 810.3 | 7.5 |
| all | 53 | collective alone | 52 | 333.5 | 1038.8 | 9.4 |
| all | 53 | after: per-cell + collective (first of) | 52 | 332.0 | 467.1 | 17.0 |
| link <= 6 cells | 22 | before: per-cell (published metric a) | 22 | 557.5 | 774.4 | 4.5 |
| link <= 6 cells | 22 | collective alone | 22 | 330.0 | 3114.8 | 13.6 |
| link <= 6 cells | 22 | after: per-cell + collective (first of) | 22 | 330.0 | 589.1 | 18.2 |
| link > 6 cells | 31 | before: per-cell (published metric a) | 30 | 562.0 | 819.8 | 9.7 |
| link > 6 cells | 31 | collective alone | 30 | 335.5 | 384.3 | 6.5 |
| link > 6 cells | 31 | after: per-cell + collective (first of) | 30 | 333.0 | 384.3 | 16.1 |
| all | 52 | median gain, before - after (s) | 52 | 190.0 | 380.5 | NULL |

_10 row(s)_


## Per incident

| incident_id | link | n_cells | before_ttd_s | collective_ttd_s | combined_ttd_s |
|---|---|---|---|---|---|
| INC-00004 | BH-NSW-0016 | 12 | 533.0 | 329.0 | 329.0 |
| INC-00006 | BH-NSW-0036 | 9 | 513.0 | 311.0 | 311.0 |
| INC-00013 | BH-NSW-0037 | 21 | 282.0 | 325.0 | 282.0 |
| INC-00029 | BH-NSW-0005 | 3 | 322.0 | 311.0 | 311.0 |
| INC-00030 | BH-VIC-0038 | 24 | 881.0 | 1055.0 | 881.0 |
| INC-00037 | BH-NQL-0010 | 18 | 471.0 | 331.0 | 331.0 |
| INC-00044 | BH-NSW-0056 | 12 | 508.0 | 361.0 | 361.0 |
| INC-00052 | BH-NSW-0055 | 18 | 487.0 | 298.0 | 298.0 |
| INC-00083 | BH-VIC-0020 | 6 | 3008.0 | 3169.0 | 3008.0 |
| INC-00093 | BH-NSW-0032 | 3 | 641.0 | 321.0 | 321.0 |
| INC-00105 | BH-VIC-0023 | 24 | 559.0 | 307.0 | 307.0 |
| INC-00111 | BH-NSW-0005 | 3 | 641.0 | 327.0 | 327.0 |
| INC-00114 | BH-NSW-0010 | 3 | 542.0 | 294.0 | 294.0 |
| INC-00115 | BH-VIC-0015 | 3 | 360.0 | 285.0 | 285.0 |
| INC-00119 | BH-NSW-0014 | 24 | 671.0 | 347.0 | 347.0 |
| INC-00124 | BH-NSW-0033 | 12 | 759.0 | 329.0 | 329.0 |
| INC-00141 | BH-NSW-0032 | 3 | 462.0 | 334.0 | 334.0 |
| INC-00163 | BH-NSW-0016 | 12 | 683.0 | 367.0 | 367.0 |
| INC-00164 | BH-WA-0006 | 6 | 602.0 | 2627.0 | 602.0 |
| INC-00169 | BH-VIC-0013 | 12 | 718.0 | 351.0 | 351.0 |
| INC-00171 | BH-VIC-0021 | 9 | 915.0 | 352.0 | 352.0 |
| INC-00179 | BH-VIC-0030 | 6 | 780.0 | 345.0 | 345.0 |
| INC-00184 | BH-NQL-0011 | 6 | 260.0 | 305.0 | 260.0 |
| INC-00186 | BH-VIC-0008 | 6 | 592.0 | 324.0 | 324.0 |
| INC-00196 | BH-VIC-0003 | 6 | 532.0 | 344.0 | 344.0 |
| INC-00199 | BH-NSW-0018 | 12 | 591.0 | 335.0 | 335.0 |
| INC-00200 | BH-VIC-0001 | 12 | 569.0 | 319.0 | 319.0 |
| INC-00204 | BH-NSW-0036 | 9 | NULL | NULL | NULL |
| INC-00209 | BH-NSW-0026 | 12 | 438.0 | 297.0 | 297.0 |
| INC-00214 | BH-NQL-0013 | 6 | 449.0 | 304.0 | 304.0 |
| INC-00227 | BH-WA-0019 | 18 | 385.0 | 301.0 | 301.0 |
| INC-00229 | BH-NQL-0006 | 6 | 645.0 | 337.0 | 337.0 |
| INC-00244 | BH-NQL-0003 | 3 | 592.0 | 333.0 | 333.0 |
| INC-00247 | BH-NSW-0037 | 21 | 421.0 | 347.0 | 347.0 |
| INC-00255 | BH-WA-0011 | 9 | 813.0 | 366.0 | 366.0 |
| INC-00282 | BH-NSW-0020 | 12 | 982.0 | 893.0 | 893.0 |
| INC-00288 | BH-VIC-0007 | 15 | 279.0 | 318.0 | 279.0 |
| INC-00291 | BH-NSW-0042 | 3 | 449.0 | 305.0 | 305.0 |
| INC-00292 | BH-VIC-0036 | 9 | 643.0 | 381.0 | 381.0 |
| INC-00324 | BH-NSW-0044 | 9 | 565.0 | 304.0 | 304.0 |
| INC-00329 | BH-NSW-0017 | 3 | 863.0 | 1980.0 | 863.0 |
| INC-00330 | BH-NQL-0008 | 6 | 473.0 | 7366.0 | 473.0 |
| INC-00333 | BH-NQL-0012 | 6 | 383.0 | 4932.0 | 383.0 |
| INC-00344 | BH-VIC-0024 | 12 | 286.0 | 336.0 | 286.0 |
| INC-00348 | BH-NSW-0032 | 3 | 573.0 | 311.0 | 311.0 |
| INC-00351 | BH-VIC-0023 | 24 | 786.0 | 353.0 | 353.0 |
| INC-00357 | BH-NSW-0048 | 6 | 724.0 | 342.0 | 342.0 |
| INC-00373 | BH-WA-0015 | 12 | 435.0 | 308.0 | 308.0 |
| INC-00376 | BH-NSW-0036 | 9 | 541.0 | 350.0 | 350.0 |
| INC-00378 | BH-VIC-0024 | 12 | 609.0 | 414.0 | 414.0 |
| INC-00381 | BH-NQL-0012 | 6 | 411.0 | 282.0 | 282.0 |
| INC-00382 | BH-NSW-0008 | 12 | 451.0 | 323.0 | 323.0 |
| INC-00384 | BH-NSW-0050 | 15 | 597.0 | 351.0 | 351.0 |

_53 row(s)_


## False-alarm cost (does not use the per-cell first detection, so unchanged by the fix)

| measure | collective | per-cell KPI rules (today), grouped per link |
|---|---|---|
| n_alerts | 53 | 1609 |
| n_fault_tp | 53 | 1231 |
| n_censored | 0 | 0 |
| n_planned_suppressed | 0 | 113 |
| n_false_alarms | 0 | 265 |
| n_unexplained | 0 | 265 |
| n_red_herring | 0 | 0 |
| n_planned_unsuppressed | 0 | 0 |
| healthy_link_days | 195.65 | 195.65 |
| false_alarms_per_100_link_days | 0.0 | 135.45 |
| unexplained_per_100_link_days | 0.0 | 135.45 |
| unexplained_busy_hour | 0 | 0 |
| unexplained_near_traffic_surge | 0 | 0 |
| unexplained_near_other_incident | 0 | 0 |

_14 row(s)_


| measure | value |
|---|---|
| collective false alarms on a link with no per-cell alert within 10 min (new pages) | 0 |

_1 row(s)_


## Collective alerts that are true positives, by fault type

| fault_type | collective TP alerts |
|---|---|
| BACKHAUL_DEGRADATION | 53 |

_1 row(s)_

