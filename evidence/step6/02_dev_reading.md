# Step 6 collective backhaul detector: DEV reading (history_1m dev days, calibrated on: in-sample)

Generated 2026-11-07 02:14 UTC by `scripts/collective_backhaul_experiment.py`.

- reading `dev`: source_run `history_1m`, windows 2026-10-14T00:00:00Z .. 2026-10-16T00:00:00Z.
- frozen rule `detection.COLLECTIVE_BACKHAUL`, frozen at commit `e866511994f49fcf0084c994228221f6eb52af9a` (last change to the detector code), scored at
  HEAD `8ff94baded45122b2971bcc749c49a083690caea`: `{"name": "collective_backhaul_v1", "z": 2.5, "floors": {"latency_ms": 3.0, "packet_loss_pct": 0.1286, "session_drop_rate_pct": 0.0643}, "min_consistency": 0.6, "min_reporting_share": 0.8, "persist": 2, "consistency_z": 1.0, "watermark_s": 120}`
- detections computed in SQL on the warehouse from `gold_cell_health_1m`, topology and the change calendar only, written
  to `telco_netmon_febar_catalog.netmon_eval.eval_collective_backhaul_experiment` (reading = `dev`). Ground truth was read afterwards, for scoring only.
- timing: a link-minute is available at max(window_end + 120 s watermark, latest evidence_ts of the
  on-time cell windows used); a cell window arriving after window_end + watermark is not used. No record-level timing.
  "before" is the published step-2 metric (a) (`eval_incident_detection.impact_ttd_s`: first per-cell KPI or alarm
  detection on the incident footprint, evidence time + measured live pipeline latency). For the batch runs that latency
  is 0 on both sides; for `stream` the collective side has no measured pipeline latency (a lower bound).
- scored incidents: 55 customer-impacting, uncensored `BACKHAUL_DEGRADATION` (impact start in the reading).
  Healthy link-days: 198.2.

## Write (SQL)

```sql
MERGE INTO telco_netmon_febar_catalog.netmon_eval.eval_collective_backhaul_experiment t
USING (SELECT 'dev' AS reading, 'e866511994f49fcf0084c994228221f6eb52af9a' AS freeze_sha, '{"name": "collective_backhaul_v1", "z": 2.5, "floors": {"latency_ms": 3.0, "packet_loss_pct": 0.1286, "session_drop_rate_pct": 0.0643}, "min_consistency": 0.6, "min_reporting_share": 0.8, "persist": 2, "consistency_z": 1.0, "watermark_s": 120}' AS rule_json, current_timestamp() AS scored_at, *
FROM (
    WITH s AS (
    WITH topo AS (
      SELECT backhaul_id AS parent_id, count(DISTINCT element_id) AS n_desc_cells
      FROM telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes WHERE element_type = 'CELL' GROUP BY backhaul_id
    ),
    h AS (SELECT * FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m WHERE source_run = 'history_1m' AND window_start >= '2026-10-14T00:00:00Z' AND window_start < '2026-10-16T00:00:00Z'),
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
    FROM r WHERE qualifies AND n_qualified_in_frame >= 2)) s
ON t.reading = s.reading AND t.detection_id = s.detection_id
WHEN NOT MATCHED THEN INSERT *
```

## SQL vs Python mirror: detections

| check | value |
|---|---|
| SQL detections (table rows) | 5495 |
| distinct detection_id | 5495 |
| Python mirror detections | 5495 |
| in SQL only | 0 |
| in Python only | 0 |

_5 row(s)_


## SQL vs Python mirror: parent-minute statistic recomputed from the cell windows (one hour)

| check | value |
|---|---|
| hour | 2026-10-14T12:00:00Z .. 2026-10-14T13:00:00Z |
| link-minutes (SQL) | 7980 |
| link-minutes (Python) | 7980 |
| keys only in one side | 0 |
| n_reporting_cells mismatches | 0 |
| max abs diff reporting_share | 0 |
| max abs diff available_s | 0 |
| max abs diff wz_latency_ms | 3.55e-15 |
| max abs diff wdelta_latency_ms | 1.07e-14 |
| max abs diff frac_z1_latency_ms | 0 |
| max abs diff wz_packet_loss_pct | 7.11e-15 |
| max abs diff wdelta_packet_loss_pct | 6.66e-16 |
| max abs diff frac_z1_packet_loss_pct | 0 |
| max abs diff wz_session_drop_rate_pct | 1.78e-15 |
| max abs diff wdelta_session_drop_rate_pct | 2.22e-16 |
| max abs diff frac_z1_session_drop_rate_pct | 0 |

_16 row(s)_


## Time to detect, BACKHAUL_DEGRADATION (n = 55)

Ground truth used for scoring only. Undetected incidents count against 'within 5 min' but not in the percentiles.

| subset | n | detector | detected | median_ttd_s | p90_ttd_s | within_5min_pct |
|---|---|---|---|---|---|---|
| all | 55 | before: per-cell (published metric a) | 53 | 569.0 | 957.4 | 9.1 |
| all | 55 | collective alone | 53 | 331.0 | 1348.2 | 16.4 |
| all | 55 | after: per-cell + collective (first of) | 53 | 323.0 | 821.4 | 21.8 |
| link <= 6 cells | 25 | before: per-cell (published metric a) | 25 | 563.0 | 1013.8 | 4.0 |
| link <= 6 cells | 25 | collective alone | 25 | 321.0 | 1143.0 | 24.0 |
| link <= 6 cells | 25 | after: per-cell + collective (first of) | 25 | 315.0 | 592.4 | 28.0 |
| link > 6 cells | 30 | before: per-cell (published metric a) | 28 | 591.5 | 884.7 | 13.3 |
| link > 6 cells | 30 | collective alone | 28 | 337.0 | 3714.0 | 10.0 |
| link > 6 cells | 30 | after: per-cell + collective (first of) | 28 | 336.0 | 884.7 | 16.7 |
| all | 53 | median gain, before - after (s) | 53 | 191.0 | 439.0 | NULL |

_10 row(s)_


## Per incident

| incident_id | link | n_cells | before_ttd_s | collective_ttd_s | combined_ttd_s |
|---|---|---|---|---|---|
| INC-00781 | BH-WA-0013 | 3 | 644.0 | 336.0 | 336.0 |
| INC-00787 | BH-VIC-0015 | 3 | 310.0 | 415.0 | 310.0 |
| INC-00790 | BH-VIC-0038 | 24 | 840.0 | 398.0 | 398.0 |
| INC-00791 | BH-VIC-0016 | 3 | 437.0 | 367.0 | 367.0 |
| INC-00798 | BH-NSW-0014 | 24 | 563.0 | 314.0 | 314.0 |
| INC-00800 | BH-NSW-0055 | 18 | 552.0 | 306.0 | 306.0 |
| INC-00801 | BH-VIC-0017 | 15 | 705.0 | 336.0 | 336.0 |
| INC-00805 | BH-VIC-0019 | 24 | 381.0 | 306.0 | 306.0 |
| INC-00806 | BH-NSW-0031 | 6 | 814.0 | 318.0 | 318.0 |
| INC-00850 | BH-VIC-0002 | 18 | 596.0 | 344.0 | 344.0 |
| INC-00851 | BH-VIC-0021 | 9 | 746.0 | 361.0 | 361.0 |
| INC-00854 | BH-VIC-0009 | 18 | 323.0 | 312.0 | 312.0 |
| INC-00858 | BH-VIC-0010 | 3 | 588.0 | 275.0 | 275.0 |
| INC-00859 | BH-VIC-0017 | 15 | 587.0 | 758.0 | 587.0 |
| INC-00866 | BH-VIC-0028 | 21 | 233.0 | 286.0 | 233.0 |
| INC-00873 | BH-WA-0006 | 6 | 403.0 | 315.0 | 315.0 |
| INC-00892 | BH-WA-0002 | 3 | 569.0 | 315.0 | 315.0 |
| INC-00895 | BH-VIC-0035 | 18 | 919.0 | 4505.0 | 919.0 |
| INC-00898 | BH-NSW-0018 | 12 | 870.0 | 5410.0 | 870.0 |
| INC-00902 | BH-NQL-0006 | 6 | 572.0 | 4278.0 | 572.0 |
| INC-00907 | BH-NSW-0053 | 6 | 600.0 | 1173.0 | 600.0 |
| INC-00912 | BH-NSW-0039 | 12 | 714.0 | 338.0 | 338.0 |
| INC-00920 | BH-NSW-0035 | 6 | 290.0 | 327.0 | 290.0 |
| INC-00931 | BH-NSW-0049 | 6 | 479.0 | 288.0 | 288.0 |
| INC-00946 | BH-WA-0004 | 12 | 7162.0 | 7336.0 | 7162.0 |
| INC-00949 | BH-NQL-0005 | 9 | 494.0 | 300.0 | 300.0 |
| INC-00962 | BH-NSW-0023 | 9 | 503.0 | 364.0 | 364.0 |
| INC-00966 | BH-NSW-0022 | 24 | 759.0 | 332.0 | 332.0 |
| INC-00978 | BH-WA-0001 | 6 | 433.0 | 292.0 | 292.0 |
| INC-00986 | BH-NSW-0026 | 12 | NULL | NULL | NULL |
| INC-01004 | BH-NSW-0042 | 3 | 312.0 | 293.0 | 293.0 |
| INC-01016 | BH-NSW-0019 | 27 | 138.0 | 350.0 | 138.0 |
| INC-01023 | BH-NSW-0055 | 18 | NULL | NULL | NULL |
| INC-01030 | BH-VIC-0019 | 24 | 2728.0 | 3375.0 | 2728.0 |
| INC-01032 | BH-NSW-0051 | 6 | 5661.0 | 1392.0 | 1392.0 |
| INC-01033 | BH-NSW-0042 | 3 | 1045.0 | 370.0 | 370.0 |
| INC-01038 | BH-VIC-0034 | 18 | 496.0 | 370.0 | 370.0 |
| INC-01039 | BH-NSW-0032 | 3 | 967.0 | 581.0 | 581.0 |
| INC-01046 | BH-WA-0001 | 6 | 696.0 | 323.0 | 323.0 |
| INC-01052 | BH-WA-0005 | 21 | 261.0 | 299.0 | 261.0 |
| INC-01053 | BH-WA-0006 | 6 | 542.0 | 280.0 | 280.0 |
| INC-01070 | BH-NSW-0020 | 12 | 627.0 | 671.0 | 627.0 |
| INC-01072 | BH-VIC-0010 | 3 | 500.0 | 312.0 | 312.0 |
| INC-01082 | BH-VIC-0004 | 9 | 601.0 | 336.0 | 336.0 |
| INC-01103 | BH-VIC-0006 | 12 | 675.0 | 368.0 | 368.0 |
| INC-01126 | BH-VIC-0027 | 6 | 563.0 | 301.0 | 301.0 |
| INC-01130 | BH-NQL-0013 | 6 | 531.0 | 321.0 | 321.0 |
| INC-01131 | BH-VIC-0020 | 6 | 825.0 | 331.0 | 331.0 |
| INC-01140 | BH-VIC-0011 | 6 | 446.0 | 315.0 | 315.0 |
| INC-01160 | BH-NQL-0006 | 6 | 6809.0 | 1098.0 | 1098.0 |
| INC-01163 | BH-VIC-0018 | 12 | 517.0 | 331.0 | 331.0 |
| INC-01165 | BH-VIC-0001 | 12 | 616.0 | 310.0 | 310.0 |
| INC-01172 | BH-NSW-0057 | 9 | 281.0 | 327.0 | 281.0 |
| INC-01179 | BH-NSW-0007 | 18 | 443.0 | 307.0 | 307.0 |
| INC-01194 | BH-VIC-0010 | 3 | 555.0 | 290.0 | 290.0 |

_55 row(s)_


## False-alarm cost

Alerts: detections grouped per (run, link) with the step-2 rule (a new alert when a
detection starts > 10 min after the previous one ended), labelled by the ground truth whose footprint
holds the link (fault > censored > planned > red herring > unexplained). False alarm = unexplained, red herring, or planned
work not suppressed by the change window. Per 100 healthy link-days (198.2). The per-cell column applies the
same grouping to today's per-cell KPI detections on the link's cells (labelled by the cell's own footprint).

| measure | collective | per-cell KPI rules (today), grouped per link |
|---|---|---|
| n_alerts | 57 | 1645 |
| n_fault_tp | 57 | 1135 |
| n_censored | 0 | 0 |
| n_planned_suppressed | 0 | 164 |
| n_false_alarms | 0 | 346 |
| n_unexplained | 0 | 346 |
| n_red_herring | 0 | 0 |
| n_planned_unsuppressed | 0 | 0 |
| healthy_link_days | 198.2 | 198.2 |
| false_alarms_per_100_link_days | 0.0 | 174.57 |
| unexplained_per_100_link_days | 0.0 | 174.57 |
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
| BACKHAUL_DEGRADATION | 57 |

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
| all | 55 | before: per-cell (published metric a) | 53 | 569.0 | 957.4 | 9.1 |
| all | 55 | collective alone | 53 | 271.0 | 1288.2 | 61.8 |
| all | 55 | after: per-cell + collective (first of) | 53 | 271.0 | 818.2 | 61.8 |
| link <= 6 cells | 25 | before: per-cell (published metric a) | 25 | 563.0 | 1013.8 | 4.0 |
| link <= 6 cells | 25 | collective alone | 25 | 261.0 | 1083.0 | 68.0 |
| link <= 6 cells | 25 | after: per-cell + collective (first of) | 25 | 261.0 | 588.8 | 68.0 |
| link > 6 cells | 30 | before: per-cell (published metric a) | 28 | 591.5 | 884.7 | 13.3 |
| link > 6 cells | 30 | collective alone | 28 | 277.0 | 3654.0 | 56.7 |
| link > 6 cells | 30 | after: per-cell + collective (first of) | 28 | 276.0 | 884.7 | 56.7 |
| all | 53 | median gain, before - after (s) | 53 | 251.0 | 499.0 | NULL |

_10 row(s)_


| measure | value |
|---|---|
| false alarms per 100 healthy link-days | 0.0 |

_1 row(s)_

