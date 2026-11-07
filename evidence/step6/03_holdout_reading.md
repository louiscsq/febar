# Step 6 collective backhaul detector: DETECTOR HOLDOUT READING (holdout_1m, read once, after the freeze)

> **Note (added after this run, in a later commit):** this is the as-run holdout reading, kept unchanged below. Its *before* rows count INC-00204, which no detector catches, as a per-cell detection at 0 s: `eval_incident_detection` gives undetected incidents `impact_ttd_s = 0`. The combined *after* arm takes the per-cell time, so **it is affected too**: the corrected after is median 332 s (not 331), p90 467.1 s (not 461.2) and 17.0 % within 5 min (not 18.9 %). The corrected before is 562 s / 810.3 s / 7.5 % (not 559 / 807.6 / 9.4). The re-scoring of the **same stored detections** (nothing recomputed, no holdout data re-read), with a full before/after delta table, is [`03b_holdout_rescore.md`](03b_holdout_rescore.md). Unaffected: the detections, the SQL-vs-mirror checks, the collective-alone rows, the link <= 6 cells rows and the false-alarm figures. The 60 s sensitivity's before / after rows below carry the same error.

Generated 2026-11-07 01:52 UTC by `scripts/collective_backhaul_experiment.py`.

- reading `holdout`: source_run `holdout_1m`, windows 2026-10-17T00:00:00Z .. 2026-10-19T00:00:00Z.
- frozen rule `detection.COLLECTIVE_BACKHAUL`, frozen at commit `e866511994f49fcf0084c994228221f6eb52af9a` (last change to the detector code), scored at
  HEAD `7e27c56dcdc76b17703a7aa5dc727c63390c5f23`: `{"name": "collective_backhaul_v1", "z": 2.5, "floors": {"latency_ms": 3.0, "packet_loss_pct": 0.1286, "session_drop_rate_pct": 0.0643}, "min_consistency": 0.6, "min_reporting_share": 0.8, "persist": 2, "consistency_z": 1.0, "watermark_s": 120}`
- detections computed in SQL on the warehouse from `gold_cell_health_1m`, topology and the change calendar only, written
  to `telco_netmon_febar_catalog.netmon_eval.eval_collective_backhaul_experiment` (reading = `holdout`). Ground truth was read afterwards, for scoring only.
- timing: a link-minute is available at max(window_end + 120 s watermark, latest evidence_ts of the
  on-time cell windows used); a cell window arriving after window_end + watermark is not used. No record-level timing.
  "before" is the published step-2 metric (a) (`eval_incident_detection.impact_ttd_s`: first per-cell KPI or alarm
  detection on the incident footprint, evidence time + measured live pipeline latency). For the batch runs that latency
  is 0 on both sides; for `stream` the collective side has no measured pipeline latency (a lower bound).
- scored incidents: 53 customer-impacting, uncensored `BACKHAUL_DEGRADATION` (impact start in the reading).
  Healthy link-days: 195.6.

**Declared detector holdout reading.** The collective detector's thresholds were calibrated on the history_1m dev days only and frozen at the commit above; this run was never read by the detector before. (`holdout_1m` was already used once by the RCA model; this is a separate reading for a separate detector.)

## Write (SQL)

```sql
INSERT INTO telco_netmon_febar_catalog.netmon_eval.eval_collective_backhaul_experiment
SELECT 'holdout' AS reading, 'e866511994f49fcf0084c994228221f6eb52af9a' AS freeze_sha, '{"name": "collective_backhaul_v1", "z": 2.5, "floors": {"latency_ms": 3.0, "packet_loss_pct": 0.1286, "session_drop_rate_pct": 0.0643}, "min_consistency": 0.6, "min_reporting_share": 0.8, "persist": 2, "consistency_z": 1.0, "watermark_s": 120}' AS rule_json, current_timestamp() AS scored_at, *
FROM (
    WITH s AS (
    WITH topo AS (
      SELECT backhaul_id AS parent_id, count(DISTINCT element_id) AS n_desc_cells
      FROM telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes WHERE element_type = 'CELL' GROUP BY backhaul_id
    ),
    h AS (SELECT * FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m WHERE source_run = 'holdout_1m' AND window_start >= '2026-10-17T00:00:00Z' AND window_start < '2026-10-19T00:00:00Z'),
    -- a cell is in a change window when its site, link or router is (deduplicated: one flag per cell window)
    hm AS (
      SELECT h.source_run, h.window_start, h.cell_id, true AS in_maint
      FROM h JOIN telco_netmon_febar_catalog.netmon_silver.silver_maintenance_windows mw ON mw.source_run = h.source_run
       AND mw.element_id IN (h.site_id, h.backhaul_id, h.router_id)
       AND mw.planned_start_ts < h.window_end AND mw.planned_end_ts > h.window_start
      GROUP BY h.source_run, h.window_start, h.cell_id
    ),
    c AS (
      SELECT h.source_run, h.window_start, h.window_end, h.cell_id, h.backhaul_id AS parent_id,
             greatest(coalesce(CAST(h.active_users AS DOUBLE), 0D), 1D) AS w, h.prb_util_pct, h.evidence_ts,
             arrays_overlap(coalesce(h.flags, array()), array('cell_unavailable', 'attach_failure', 'rrc_collapse')) AS hard,
             coalesce(hm.in_maint, false) AS in_maint, coalesce(h.n_late_reports, 0) AS n_late,
             (latency_ms - b_latency_ms_mean) / greatest(coalesce(b_latency_ms_std, 0), 2.0) AS z_latency_ms, (latency_ms - b_latency_ms_mean) AS d_latency_ms,
(packet_loss_pct - b_packet_loss_pct_mean) / greatest(coalesce(b_packet_loss_pct_std, 0), 0.05) AS z_packet_loss_pct, (packet_loss_pct - b_packet_loss_pct_mean) AS d_packet_loss_pct,
(session_drop_rate_pct - b_session_drop_rate_pct_mean) / greatest(coalesce(b_session_drop_rate_pct_std, 0), 0.1) AS z_session_drop_rate_pct, (session_drop_rate_pct - b_session_drop_rate_pct_mean) AS d_session_drop_rate_pct
      FROM h LEFT JOIN hm ON hm.source_run = h.source_run AND hm.window_start = h.window_start
                         AND hm.cell_id = h.cell_id
    ),
    u AS (
      SELECT *, (n_late = 0 AND evidence_ts <= window_end + INTERVAL 120 SECONDS AND NOT hard AND NOT in_maint AND z_latency_ms IS NOT NULL AND d_latency_ms IS NOT NULL AND z_packet_loss_pct IS NOT NULL AND d_packet_loss_pct IS NOT NULL AND z_session_drop_rate_pct IS NOT NULL AND d_session_drop_rate_pct IS NOT NULL) AS used
      FROM c
    )
    SELECT u.source_run, u.window_start, u.window_end, u.parent_id, 'BACKHAUL_LINK' AS parent_type,
           t.n_desc_cells, count(*) AS n_cell_windows, count_if(used) AS n_reporting_cells,
           count_if(used) / t.n_desc_cells AS reporting_share,
           count_if(hard) AS n_hard_rule_cells, count_if(in_maint) AS n_maintenance_cells,
           bool_or(in_maint) AS in_maintenance,
           sum(CASE WHEN used THEN w * z_latency_ms END) / sum(CASE WHEN used THEN w END) AS wz_latency_ms,
sum(CASE WHEN used THEN w * d_latency_ms END) / sum(CASE WHEN used THEN w END) AS wdelta_latency_ms,
count_if(used AND z_latency_ms > 1.0) / nullif(count_if(used), 0) AS frac_z1_latency_ms,
sum(CASE WHEN used THEN w * z_packet_loss_pct END) / sum(CASE WHEN used THEN w END) AS wz_packet_loss_pct,
sum(CASE WHEN used THEN w * d_packet_loss_pct END) / sum(CASE WHEN used THEN w END) AS wdelta_packet_loss_pct,
count_if(used AND z_packet_loss_pct > 1.0) / nullif(count_if(used), 0) AS frac_z1_packet_loss_pct,
sum(CASE WHEN used THEN w * z_session_drop_rate_pct END) / sum(CASE WHEN used THEN w END) AS wz_session_drop_rate_pct,
sum(CASE WHEN used THEN w * d_session_drop_rate_pct END) / sum(CASE WHEN used THEN w END) AS wdelta_session_drop_rate_pct,
count_if(used AND z_session_drop_rate_pct > 1.0) / nullif(count_if(used), 0) AS frac_z1_session_drop_rate_pct,
           sum(CASE WHEN used THEN w * prb_util_pct END) / sum(CASE WHEN used AND prb_util_pct IS NOT NULL THEN w END)
             AS w_prb_util_pct,
           max(CASE WHEN used THEN evidence_ts END) AS max_used_evidence_ts,
           greatest(u.window_end + INTERVAL 120 SECONDS, coalesce(max(CASE WHEN used THEN evidence_ts END), u.window_end + INTERVAL 120 SECONDS))
             AS available_ts
    FROM u JOIN topo t ON t.parent_id = u.parent_id
    GROUP BY u.source_run, u.window_start, u.window_end, u.parent_id, t.n_desc_cells),
    q AS (SELECT *, (coalesce(reporting_share >= 0.8, false) AND ((coalesce(wz_latency_ms > 2.5, false) AND coalesce(wdelta_latency_ms > 3.0, false) AND coalesce(frac_z1_latency_ms >= 0.6, false)) OR (coalesce(wz_packet_loss_pct > 2.5, false) AND coalesce(wdelta_packet_loss_pct > 0.1286, false) AND coalesce(frac_z1_packet_loss_pct >= 0.6, false)) OR (coalesce(wz_session_drop_rate_pct > 2.5, false) AND coalesce(wdelta_session_drop_rate_pct > 0.0643, false) AND coalesce(frac_z1_session_drop_rate_pct >= 0.6, false)))) AS qualifies, filter(array(CASE WHEN (coalesce(wz_latency_ms > 2.5, false) AND coalesce(wdelta_latency_ms > 3.0, false) AND coalesce(frac_z1_latency_ms >= 0.6, false)) THEN 'latency_ms' END, CASE WHEN (coalesce(wz_packet_loss_pct > 2.5, false) AND coalesce(wdelta_packet_loss_pct > 0.1286, false) AND coalesce(frac_z1_packet_loss_pct >= 0.6, false)) THEN 'packet_loss_pct' END, CASE WHEN (coalesce(wz_session_drop_rate_pct > 2.5, false) AND coalesce(wdelta_session_drop_rate_pct > 0.0643, false) AND coalesce(frac_z1_session_drop_rate_pct >= 0.6, false)) THEN 'session_drop_rate_pct' END), x -> x IS NOT NULL) AS qualifying_metrics,
                 CAST(unix_timestamp(window_start) / 60 AS BIGINT) AS minute_idx FROM s),
    r AS (SELECT *,
                 sum(CAST(qualifies AS INT)) OVER w AS n_qualified_in_frame,
                 max(available_ts) OVER w AS frame_available_ts
          FROM q
          WINDOW w AS (PARTITION BY source_run, parent_id ORDER BY minute_idx
                       RANGE BETWEEN 1 PRECEDING AND CURRENT ROW))
    SELECT sha2(concat('collective|', source_run, '|', parent_id, '|',
                       date_format(window_start, "yyyy-MM-dd'T'HH:mm:ss'Z'")), 256) AS detection_id,
           'collective' AS signal_source, 'collective_backhaul_v1' AS rule_name, source_run, parent_id AS element_id,
           parent_type AS element_type, window_start AS signal_start_ts, window_end AS signal_end_ts,
           qualifying_metrics, n_desc_cells, n_reporting_cells, reporting_share, n_hard_rule_cells,
           n_maintenance_cells, in_maintenance,
           wz_latency_ms, wdelta_latency_ms, frac_z1_latency_ms, wz_packet_loss_pct, wdelta_packet_loss_pct, frac_z1_packet_loss_pct, wz_session_drop_rate_pct, wdelta_session_drop_rate_pct, frac_z1_session_drop_rate_pct,
           w_prb_util_pct, max_used_evidence_ts, frame_available_ts AS available_ts
    FROM r WHERE qualifies AND n_qualified_in_frame >= 2)
```

## SQL vs Python mirror: detections

| check | value |
|---|---|
| SQL detections (table rows) | 5421 |
| distinct detection_id | 5421 |
| Python mirror detections | 5421 |
| in SQL only | 0 |
| in Python only | 0 |

_5 row(s)_


## SQL vs Python mirror: parent-minute statistic recomputed from the cell windows (one hour)

| check | value |
|---|---|
| hour | 2026-10-17T12:00:00Z .. 2026-10-17T13:00:00Z |
| link-minutes (SQL) | 7980 |
| link-minutes (Python) | 7980 |
| keys only in one side | 0 |
| n_reporting_cells mismatches | 0 |
| max abs diff reporting_share | 0 |
| max abs diff available_s | 0 |
| max abs diff wz_latency_ms | 3.33e-16 |
| max abs diff wdelta_latency_ms | 1.42e-14 |
| max abs diff frac_z1_latency_ms | 0 |
| max abs diff wz_packet_loss_pct | 3.33e-16 |
| max abs diff wdelta_packet_loss_pct | 8.88e-16 |
| max abs diff frac_z1_packet_loss_pct | 0 |
| max abs diff wz_session_drop_rate_pct | 4.44e-16 |
| max abs diff wdelta_session_drop_rate_pct | 4.44e-16 |
| max abs diff frac_z1_session_drop_rate_pct | 0 |

_16 row(s)_


## Time to detect, BACKHAUL_DEGRADATION (n = 53)

Ground truth used for scoring only. Undetected incidents count against 'within 5 min' but not in the percentiles.

| subset | n | detector | detected | median_ttd_s | p90_ttd_s | within_5min_pct |
|---|---|---|---|---|---|---|
| all | 53 | before: per-cell (published metric a) | 53 | 559.0 | 807.6 | 9.4 |
| all | 53 | collective alone | 52 | 333.5 | 1038.8 | 9.4 |
| all | 53 | after: per-cell + collective (first of) | 53 | 331.0 | 461.2 | 18.9 |
| link <= 6 cells | 22 | before: per-cell (published metric a) | 22 | 557.5 | 774.4 | 4.5 |
| link <= 6 cells | 22 | collective alone | 22 | 330.0 | 3114.8 | 13.6 |
| link <= 6 cells | 22 | after: per-cell + collective (first of) | 22 | 330.0 | 589.1 | 18.2 |
| link > 6 cells | 31 | before: per-cell (published metric a) | 31 | 559.0 | 813.0 | 12.9 |
| link > 6 cells | 31 | collective alone | 30 | 335.5 | 384.3 | 6.5 |
| link > 6 cells | 31 | after: per-cell + collective (first of) | 31 | 331.0 | 381.0 | 19.4 |
| all | 53 | median gain, before - after (s) | 53 | 189.0 | 379.0 | NULL |

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
| INC-00204 | BH-NSW-0036 | 9 | 0.0 | NULL | 0.0 |
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


## False-alarm cost

Alerts: detections grouped per (run, link) with the step-2 rule (a new alert when a
detection starts > 10 min after the previous one ended), labelled by the ground truth whose footprint
holds the link (fault > censored > planned > red herring > unexplained). False alarm = unexplained, red herring, or planned
work not suppressed by the change window. Per 100 healthy link-days (195.6). The per-cell column applies the
same grouping to today's per-cell KPI detections on the link's cells (labelled by the cell's own footprint).

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
| TRAFFIC_SURGE incidents in this run (ground truth) | 0 |

_2 row(s)_


## Collective alerts that are true positives, by fault type

| fault_type | collective TP alerts |
|---|---|
| BACKHAUL_DEGRADATION | 53 |

_1 row(s)_


## Collective false alarms (all)

| link | start_utc | rows | label | suppressed | busy_hour (w. PRB >= 70 %) | nearby incidents |
|---|---|---|---|---|---|---|
| (none) |  |  |  |  |  |  |

_1 row(s)_


## Sensitivity (secondary, not the headline): a dedicated 60 s watermark

The same frozen rule over the statistic rebuilt with a 60 s watermark, as a separate streaming flow with its own watermark would allow. The headline above uses the 120 s watermark of the table actually read.

| subset | n | detector | detected | median_ttd_s | p90_ttd_s | within_5min_pct |
|---|---|---|---|---|---|---|
| all | 53 | before: per-cell (published metric a) | 53 | 559.0 | 807.6 | 9.4 |
| all | 53 | collective alone | 52 | 273.5 | 978.8 | 75.5 |
| all | 53 | after: per-cell + collective (first of) | 53 | 273.0 | 455.0 | 77.4 |
| link <= 6 cells | 22 | before: per-cell (published metric a) | 22 | 557.5 | 774.4 | 4.5 |
| link <= 6 cells | 22 | collective alone | 22 | 270.0 | 3054.8 | 77.3 |
| link <= 6 cells | 22 | after: per-cell + collective (first of) | 22 | 270.0 | 589.1 | 77.3 |
| link > 6 cells | 31 | before: per-cell (published metric a) | 31 | 559.0 | 813.0 | 12.9 |
| link > 6 cells | 31 | collective alone | 30 | 275.5 | 324.3 | 74.2 |
| link > 6 cells | 31 | after: per-cell + collective (first of) | 31 | 275.0 | 321.0 | 77.4 |
| all | 53 | median gain, before - after (s) | 53 | 249.0 | 439.0 | NULL |

_10 row(s)_


| measure | value |
|---|---|
| false alarms per 100 healthy link-days | 0.0 |

_1 row(s)_

