# Step 6 calibration: collective backhaul detector on history_1m DEV days

Generated 2026-11-07 01:36 UTC by `scripts/collective_backhaul_experiment.py`.

Calibration of `detection.CollectiveRule` on the **dev days of `history_1m`** (2026-10-14 .. 10-15 UTC: the RCA's dev split;
train 10-10 .. 10-12 and validation 10-13 are not read). No other run was read by this step; `holdout_1m` and `stream` are
scored only after the chosen thresholds were frozen in code and committed.

- input: `gold_cell_health_1m` (on-time 1-minute cell windows), `silver_topology_nodes`, `silver_maintenance_windows`;
  ground truth (`eval_gt_incidents`) and the published per-cell first detection (`eval_incident_detection`) are read only to
  score each candidate.
- parent: backhaul link (133 links, 1,431 cells). Watermark 120 s (the watermark of the table read).
- scored incidents: 55 customer-impacting, uncensored `BACKHAUL_DEGRADATION` faults whose impact starts in the dev days.
- healthy link-days (outside every ground-truth footprint touching the link, its cells or sites): 198.2.
- grid: z in [1.5, 2.0, 2.5, 3.0]; latency floor in [3.0, 4.0, 6.0, 8.0, 10.0] ms with loss floor = latency x 6/140 pp and drop floor =
  latency x 3/140 pp (the fault's own ratio); consistency in [0.25, 0.4, 0.6] (fraction of reporting cells with z > 1);
  persist in [1, 2, 3] minutes; reporting share >= 0.8. 180 configurations.
- selection rule (declared in the script before the sweep): Feasible: false collective alerts <= 1.0 per 100 healthy link-days AND >= 90 % of dev BACKHAUL_DEGRADATION incidents detected by the collective rule. Among feasible configurations, pick the lowest median collective TTD (undetected = +inf); ties: fewer false alarms, then larger persist, larger z, larger consistency (the more conservative).

## Parent-minute statistic (SQL, dev days)

```sql
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
    GROUP BY u.source_run, u.window_start, u.window_end, u.parent_id, t.n_desc_cells
```

## Feasible configurations, best first (top 15)

| z | lat_floor_ms | consistency | persist | detected_pct | median_ttd_s | p90_ttd_s | within_5min_pct | false_alarms | fa_per_100 | tp_alerts |
|---|---|---|---|---|---|---|---|---|---|---|
| 2.5 | 3.0 | 0.6 | 2.0 | 96.4 | 332.0 | 1348.200000000001 | 16.4 | 0.0 | 0.0 | 57.0 |
| 2.5 | 3.0 | 0.4 | 2.0 | 96.4 | 332.0 | 1348.200000000001 | 18.2 | 0.0 | 0.0 | 57.0 |
| 2.5 | 3.0 | 0.25 | 2.0 | 96.4 | 332.0 | 1348.200000000001 | 18.2 | 0.0 | 0.0 | 57.0 |
| 3.0 | 3.0 | 0.6 | 2.0 | 96.4 | 350.0 | 3377.4 | 7.3 | 0.0 | 0.0 | 56.0 |
| 3.0 | 3.0 | 0.4 | 2.0 | 96.4 | 350.0 | 3377.4 | 9.1 | 0.0 | 0.0 | 56.0 |
| 3.0 | 3.0 | 0.25 | 2.0 | 96.4 | 350.0 | 3377.4 | 9.1 | 0.0 | 0.0 | 56.0 |
| 3.0 | 4.0 | 0.6 | 2.0 | 96.4 | 361.0 | 3377.4 | 7.3 | 0.0 | 0.0 | 56.0 |
| 3.0 | 4.0 | 0.4 | 2.0 | 96.4 | 361.0 | 3377.4 | 9.1 | 0.0 | 0.0 | 56.0 |
| 3.0 | 4.0 | 0.25 | 2.0 | 96.4 | 361.0 | 3377.4 | 9.1 | 0.0 | 0.0 | 56.0 |
| 2.5 | 4.0 | 0.6 | 2.0 | 96.4 | 361.0 | 1348.200000000001 | 7.3 | 0.0 | 0.0 | 57.0 |
| 2.5 | 4.0 | 0.4 | 2.0 | 96.4 | 361.0 | 1348.200000000001 | 9.1 | 0.0 | 0.0 | 57.0 |
| 2.5 | 4.0 | 0.25 | 2.0 | 96.4 | 361.0 | 1348.200000000001 | 9.1 | 0.0 | 0.0 | 57.0 |
| 3.0 | 6.0 | 0.6 | 2.0 | 96.4 | 383.0 | 3377.4 | 5.5 | 0.0 | 0.0 | 56.0 |
| 3.0 | 6.0 | 0.4 | 2.0 | 96.4 | 383.0 | 3377.4 | 5.5 | 0.0 | 0.0 | 56.0 |
| 3.0 | 6.0 | 0.25 | 2.0 | 96.4 | 383.0 | 3377.4 | 5.5 | 0.0 | 0.0 | 56.0 |

_15 row(s)_


## Fastest configurations regardless of false alarms (top 15 by median TTD)

| z | lat_floor_ms | consistency | persist | detected_pct | median_ttd_s | p90_ttd_s | within_5min_pct | false_alarms | fa_per_100 | tp_alerts | feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.5 | 3.0 | 0.4 | 1 | 98.2 | 267.0 | 1098.9 | 65.5 | 402 | 202.82 | 81 | False |
| 1.5 | 3.0 | 0.25 | 1 | 98.2 | 267.0 | 1098.9 | 65.5 | 482 | 243.19 | 99 | False |
| 2.5 | 3.0 | 0.6 | 1 | 96.4 | 271.0 | 1288.200000000001 | 63.6 | 15 | 7.57 | 56 | False |
| 2.5 | 3.0 | 0.4 | 1 | 96.4 | 271.0 | 1288.200000000001 | 63.6 | 19 | 9.59 | 56 | False |
| 2.5 | 3.0 | 0.25 | 1 | 96.4 | 271.0 | 1288.200000000001 | 63.6 | 42 | 21.19 | 61 | False |
| 2.0 | 3.0 | 0.6 | 1 | 98.2 | 271.0 | 1217.8000000000002 | 65.5 | 77 | 38.85 | 60 | False |
| 2.0 | 3.0 | 0.4 | 1 | 98.2 | 271.0 | 1217.8000000000002 | 65.5 | 85 | 42.89 | 62 | False |
| 2.0 | 3.0 | 0.25 | 1 | 98.2 | 271.0 | 1217.8000000000002 | 65.5 | 112 | 56.51 | 70 | False |
| 1.5 | 3.0 | 0.6 | 1 | 98.2 | 271.0 | 1098.9 | 65.5 | 370 | 186.68 | 76 | False |
| 3.0 | 3.0 | 0.6 | 1 | 96.4 | 288.0 | 3317.4 | 56.4 | 6 | 3.03 | 56 | False |
| 3.0 | 3.0 | 0.4 | 1 | 96.4 | 288.0 | 3317.4 | 56.4 | 8 | 4.04 | 56 | False |
| 3.0 | 3.0 | 0.25 | 1 | 96.4 | 288.0 | 3317.4 | 56.4 | 23 | 11.6 | 59 | False |
| 1.5 | 4.0 | 0.6 | 1 | 98.2 | 290.0 | 1098.9 | 52.7 | 363 | 183.15 | 76 | False |
| 1.5 | 4.0 | 0.4 | 1 | 98.2 | 290.0 | 1098.9 | 52.7 | 394 | 198.79 | 81 | False |
| 1.5 | 4.0 | 0.25 | 1 | 98.2 | 290.0 | 1098.9 | 52.7 | 476 | 240.16 | 99 | False |

_15 row(s)_


## Full grid

| z | lat_floor_ms | consistency | persist | detected_pct | median_ttd_s | p90_ttd_s | within_5min_pct | false_alarms | fa_per_100 | tp_alerts | feasible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.5 | 3.0 | 0.25 | 1 | 98.2 | 267.0 | 1098.9 | 65.5 | 482 | 243.19 | 99 | False |
| 1.5 | 3.0 | 0.25 | 2 | 98.2 | 331.0 | 1158.9 | 23.6 | 15 | 7.57 | 59 | False |
| 1.5 | 3.0 | 0.25 | 3 | 98.2 | 391.0 | 1218.9 | 0.0 | 2 | 1.01 | 57 | False |
| 1.5 | 3.0 | 0.4 | 1 | 98.2 | 267.0 | 1098.9 | 65.5 | 402 | 202.82 | 81 | False |
| 1.5 | 3.0 | 0.4 | 2 | 98.2 | 331.0 | 1158.9 | 23.6 | 10 | 5.05 | 59 | False |
| 1.5 | 3.0 | 0.4 | 3 | 98.2 | 391.0 | 1218.9 | 0.0 | 2 | 1.01 | 57 | False |
| 1.5 | 3.0 | 0.6 | 1 | 98.2 | 271.0 | 1098.9 | 65.5 | 370 | 186.68 | 76 | False |
| 1.5 | 3.0 | 0.6 | 2 | 98.2 | 331.0 | 1158.9 | 18.2 | 8 | 4.04 | 58 | False |
| 1.5 | 3.0 | 0.6 | 3 | 98.2 | 391.0 | 1218.9 | 0.0 | 2 | 1.01 | 57 | False |
| 1.5 | 4.0 | 0.25 | 1 | 98.2 | 290.0 | 1098.9 | 52.7 | 476 | 240.16 | 99 | False |
| 1.5 | 4.0 | 0.25 | 2 | 98.2 | 360.0 | 1158.9 | 12.7 | 15 | 7.57 | 59 | False |
| 1.5 | 4.0 | 0.25 | 3 | 98.2 | 420.0 | 1218.9 | 0.0 | 2 | 1.01 | 57 | False |
| 1.5 | 4.0 | 0.4 | 1 | 98.2 | 290.0 | 1098.9 | 52.7 | 394 | 198.79 | 81 | False |
| 1.5 | 4.0 | 0.4 | 2 | 98.2 | 360.0 | 1158.9 | 12.7 | 10 | 5.05 | 59 | False |
| 1.5 | 4.0 | 0.4 | 3 | 98.2 | 420.0 | 1218.9 | 0.0 | 2 | 1.01 | 57 | False |
| 1.5 | 4.0 | 0.6 | 1 | 98.2 | 290.0 | 1098.9 | 52.7 | 363 | 183.15 | 76 | False |
| 1.5 | 4.0 | 0.6 | 2 | 98.2 | 360.0 | 1158.9 | 10.9 | 8 | 4.04 | 58 | False |
| 1.5 | 4.0 | 0.6 | 3 | 98.2 | 420.0 | 1218.9 | 0.0 | 2 | 1.01 | 57 | False |
| 1.5 | 6.0 | 0.25 | 1 | 98.2 | 318.0 | 1098.9 | 30.9 | 322 | 162.46 | 95 | False |
| 1.5 | 6.0 | 0.25 | 2 | 98.2 | 381.0 | 1158.9 | 5.5 | 11 | 5.55 | 59 | False |
| 1.5 | 6.0 | 0.25 | 3 | 98.2 | 441.0 | 1218.9 | 0.0 | 2 | 1.01 | 57 | False |
| 1.5 | 6.0 | 0.4 | 1 | 98.2 | 318.0 | 1098.9 | 30.9 | 257 | 129.67 | 79 | False |
| 1.5 | 6.0 | 0.4 | 2 | 98.2 | 381.0 | 1158.9 | 5.5 | 7 | 3.53 | 59 | False |
| 1.5 | 6.0 | 0.4 | 3 | 98.2 | 441.0 | 1218.9 | 0.0 | 2 | 1.01 | 57 | False |
| 1.5 | 6.0 | 0.6 | 1 | 98.2 | 318.0 | 1098.9 | 30.9 | 233 | 117.56 | 75 | False |
| 1.5 | 6.0 | 0.6 | 2 | 98.2 | 381.0 | 1158.9 | 5.5 | 5 | 2.52 | 58 | False |
| 1.5 | 6.0 | 0.6 | 3 | 98.2 | 441.0 | 1218.9 | 0.0 | 2 | 1.01 | 57 | False |
| 1.5 | 8.0 | 0.25 | 1 | 98.2 | 361.0 | 1098.9 | 21.8 | 194 | 97.88 | 87 | False |
| 1.5 | 8.0 | 0.25 | 2 | 98.2 | 421.0 | 1158.9 | 3.6 | 9 | 4.54 | 59 | False |
| 1.5 | 8.0 | 0.25 | 3 | 98.2 | 481.0 | 1218.9 | 0.0 | 2 | 1.01 | 57 | False |
| 1.5 | 8.0 | 0.4 | 1 | 98.2 | 361.0 | 1098.9 | 21.8 | 145 | 73.16 | 73 | False |
| 1.5 | 8.0 | 0.4 | 2 | 98.2 | 421.0 | 1158.9 | 3.6 | 6 | 3.03 | 59 | False |
| 1.5 | 8.0 | 0.4 | 3 | 98.2 | 481.0 | 1218.9 | 0.0 | 2 | 1.01 | 57 | False |
| 1.5 | 8.0 | 0.6 | 1 | 98.2 | 361.0 | 1098.9 | 21.8 | 126 | 63.57 | 69 | False |
| 1.5 | 8.0 | 0.6 | 2 | 98.2 | 421.0 | 1158.9 | 3.6 | 4 | 2.02 | 58 | False |
| 1.5 | 8.0 | 0.6 | 3 | 98.2 | 481.0 | 1218.9 | 0.0 | 2 | 1.01 | 57 | False |
| 1.5 | 10.0 | 0.25 | 1 | 98.2 | 374.0 | 1098.9 | 12.7 | 130 | 65.59 | 84 | False |
| 1.5 | 10.0 | 0.25 | 2 | 98.2 | 434.0 | 1158.9 | 0.0 | 6 | 3.03 | 59 | False |
| 1.5 | 10.0 | 0.25 | 3 | 98.2 | 494.0 | 1218.9 | 0.0 | 2 | 1.01 | 57 | False |
| 1.5 | 10.0 | 0.4 | 1 | 98.2 | 374.0 | 1098.9 | 12.7 | 92 | 46.42 | 72 | False |
| 1.5 | 10.0 | 0.4 | 2 | 98.2 | 434.0 | 1158.9 | 0.0 | 4 | 2.02 | 59 | False |
| 1.5 | 10.0 | 0.4 | 3 | 98.2 | 494.0 | 1218.9 | 0.0 | 2 | 1.01 | 57 | False |
| 1.5 | 10.0 | 0.6 | 1 | 98.2 | 374.0 | 1098.9 | 12.7 | 81 | 40.87 | 68 | False |
| 1.5 | 10.0 | 0.6 | 2 | 98.2 | 434.0 | 1158.9 | 0.0 | 3 | 1.51 | 58 | False |
| 1.5 | 10.0 | 0.6 | 3 | 98.2 | 494.0 | 1218.9 | 0.0 | 2 | 1.01 | 57 | False |
| 2.0 | 3.0 | 0.25 | 1 | 98.2 | 271.0 | 1217.8000000000002 | 65.5 | 112 | 56.51 | 70 | False |
| 2.0 | 3.0 | 0.25 | 2 | 98.2 | 331.0 | 1277.8000000000002 | 18.2 | 3 | 1.51 | 58 | False |
| 2.0 | 3.0 | 0.25 | 3 | 98.2 | 391.0 | 1337.8000000000002 | 0.0 | 0 | 0.0 | 57 | True |
| 2.0 | 3.0 | 0.4 | 1 | 98.2 | 271.0 | 1217.8000000000002 | 65.5 | 85 | 42.89 | 62 | False |
| 2.0 | 3.0 | 0.4 | 2 | 98.2 | 331.0 | 1277.8000000000002 | 18.2 | 2 | 1.01 | 58 | False |
| 2.0 | 3.0 | 0.4 | 3 | 98.2 | 391.0 | 1337.8000000000002 | 0.0 | 0 | 0.0 | 57 | True |
| 2.0 | 3.0 | 0.6 | 1 | 98.2 | 271.0 | 1217.8000000000002 | 65.5 | 77 | 38.85 | 60 | False |
| 2.0 | 3.0 | 0.6 | 2 | 98.2 | 331.0 | 1277.8000000000002 | 16.4 | 2 | 1.01 | 58 | False |
| 2.0 | 3.0 | 0.6 | 3 | 98.2 | 391.0 | 1337.8000000000002 | 0.0 | 0 | 0.0 | 57 | True |
| 2.0 | 4.0 | 0.25 | 1 | 98.2 | 301.0 | 1217.8000000000002 | 49.1 | 108 | 54.49 | 69 | False |
| 2.0 | 4.0 | 0.25 | 2 | 98.2 | 361.0 | 1277.8000000000002 | 9.1 | 3 | 1.51 | 58 | False |
| 2.0 | 4.0 | 0.25 | 3 | 98.2 | 421.0 | 1337.8000000000002 | 0.0 | 0 | 0.0 | 57 | True |
| 2.0 | 4.0 | 0.4 | 1 | 98.2 | 301.0 | 1217.8000000000002 | 49.1 | 84 | 42.38 | 62 | False |
| 2.0 | 4.0 | 0.4 | 2 | 98.2 | 361.0 | 1277.8000000000002 | 9.1 | 2 | 1.01 | 58 | False |
| 2.0 | 4.0 | 0.4 | 3 | 98.2 | 421.0 | 1337.8000000000002 | 0.0 | 0 | 0.0 | 57 | True |
| 2.0 | 4.0 | 0.6 | 1 | 98.2 | 301.0 | 1217.8000000000002 | 49.1 | 77 | 38.85 | 60 | False |
| 2.0 | 4.0 | 0.6 | 2 | 98.2 | 361.0 | 1277.8000000000002 | 7.3 | 2 | 1.01 | 58 | False |
| 2.0 | 4.0 | 0.6 | 3 | 98.2 | 421.0 | 1337.8000000000002 | 0.0 | 0 | 0.0 | 57 | True |
| 2.0 | 6.0 | 0.25 | 1 | 98.2 | 318.0 | 1217.8000000000002 | 30.9 | 103 | 51.97 | 68 | False |
| 2.0 | 6.0 | 0.25 | 2 | 98.2 | 381.0 | 1277.8000000000002 | 5.5 | 3 | 1.51 | 58 | False |
| 2.0 | 6.0 | 0.25 | 3 | 98.2 | 441.0 | 1337.8000000000002 | 0.0 | 0 | 0.0 | 57 | True |
| 2.0 | 6.0 | 0.4 | 1 | 98.2 | 318.0 | 1217.8000000000002 | 30.9 | 81 | 40.87 | 62 | False |
| 2.0 | 6.0 | 0.4 | 2 | 98.2 | 381.0 | 1277.8000000000002 | 5.5 | 2 | 1.01 | 58 | False |
| 2.0 | 6.0 | 0.4 | 3 | 98.2 | 441.0 | 1337.8000000000002 | 0.0 | 0 | 0.0 | 57 | True |
| 2.0 | 6.0 | 0.6 | 1 | 98.2 | 318.0 | 1217.8000000000002 | 30.9 | 75 | 37.84 | 60 | False |
| 2.0 | 6.0 | 0.6 | 2 | 98.2 | 381.0 | 1277.8000000000002 | 5.5 | 2 | 1.01 | 58 | False |
| 2.0 | 6.0 | 0.6 | 3 | 98.2 | 441.0 | 1337.8000000000002 | 0.0 | 0 | 0.0 | 57 | True |
| 2.0 | 8.0 | 0.25 | 1 | 98.2 | 361.0 | 1217.8000000000002 | 18.2 | 79 | 39.86 | 68 | False |
| 2.0 | 8.0 | 0.25 | 2 | 98.2 | 421.0 | 1277.8000000000002 | 3.6 | 1 | 0.5 | 58 | True |
| 2.0 | 8.0 | 0.25 | 3 | 98.2 | 481.0 | 1337.8000000000002 | 0.0 | 0 | 0.0 | 57 | True |
| 2.0 | 8.0 | 0.4 | 1 | 98.2 | 361.0 | 1217.8000000000002 | 18.2 | 58 | 29.26 | 62 | False |
| 2.0 | 8.0 | 0.4 | 2 | 98.2 | 421.0 | 1277.8000000000002 | 3.6 | 1 | 0.5 | 58 | True |
| 2.0 | 8.0 | 0.4 | 3 | 98.2 | 481.0 | 1337.8000000000002 | 0.0 | 0 | 0.0 | 57 | True |
| 2.0 | 8.0 | 0.6 | 1 | 98.2 | 361.0 | 1217.8000000000002 | 18.2 | 52 | 26.24 | 60 | False |
| 2.0 | 8.0 | 0.6 | 2 | 98.2 | 421.0 | 1277.8000000000002 | 3.6 | 1 | 0.5 | 58 | True |
| 2.0 | 8.0 | 0.6 | 3 | 98.2 | 481.0 | 1337.8000000000002 | 0.0 | 0 | 0.0 | 57 | True |
| 2.0 | 10.0 | 0.25 | 1 | 98.2 | 374.0 | 1217.8000000000002 | 12.7 | 54 | 27.25 | 67 | False |
| 2.0 | 10.0 | 0.25 | 2 | 98.2 | 434.0 | 1277.8000000000002 | 0.0 | 1 | 0.5 | 58 | True |
| 2.0 | 10.0 | 0.25 | 3 | 98.2 | 494.0 | 1337.8000000000002 | 0.0 | 0 | 0.0 | 57 | True |
| 2.0 | 10.0 | 0.4 | 1 | 98.2 | 374.0 | 1217.8000000000002 | 12.7 | 34 | 17.15 | 61 | False |
| 2.0 | 10.0 | 0.4 | 2 | 98.2 | 434.0 | 1277.8000000000002 | 0.0 | 1 | 0.5 | 58 | True |
| 2.0 | 10.0 | 0.4 | 3 | 98.2 | 494.0 | 1337.8000000000002 | 0.0 | 0 | 0.0 | 57 | True |
| 2.0 | 10.0 | 0.6 | 1 | 98.2 | 374.0 | 1217.8000000000002 | 12.7 | 30 | 15.14 | 59 | False |
| 2.0 | 10.0 | 0.6 | 2 | 98.2 | 434.0 | 1277.8000000000002 | 0.0 | 1 | 0.5 | 58 | True |
| 2.0 | 10.0 | 0.6 | 3 | 98.2 | 494.0 | 1337.8000000000002 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 3.0 | 0.25 | 1 | 96.4 | 271.0 | 1288.200000000001 | 63.6 | 42 | 21.19 | 61 | False |
| 2.5 | 3.0 | 0.25 | 2 | 96.4 | 332.0 | 1348.200000000001 | 18.2 | 0 | 0.0 | 57 | True |
| 2.5 | 3.0 | 0.25 | 3 | 96.4 | 392.0 | 1408.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 3.0 | 0.4 | 1 | 96.4 | 271.0 | 1288.200000000001 | 63.6 | 19 | 9.59 | 56 | False |
| 2.5 | 3.0 | 0.4 | 2 | 96.4 | 332.0 | 1348.200000000001 | 18.2 | 0 | 0.0 | 57 | True |
| 2.5 | 3.0 | 0.4 | 3 | 96.4 | 392.0 | 1408.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 3.0 | 0.6 | 1 | 96.4 | 271.0 | 1288.200000000001 | 63.6 | 15 | 7.57 | 56 | False |
| 2.5 | 3.0 | 0.6 | 2 | 96.4 | 332.0 | 1348.200000000001 | 16.4 | 0 | 0.0 | 57 | True |
| 2.5 | 3.0 | 0.6 | 3 | 96.4 | 392.0 | 1408.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 4.0 | 0.25 | 1 | 96.4 | 301.0 | 1288.200000000001 | 49.1 | 38 | 19.17 | 60 | False |
| 2.5 | 4.0 | 0.25 | 2 | 96.4 | 361.0 | 1348.200000000001 | 9.1 | 0 | 0.0 | 57 | True |
| 2.5 | 4.0 | 0.25 | 3 | 96.4 | 421.0 | 1408.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 4.0 | 0.4 | 1 | 96.4 | 301.0 | 1288.200000000001 | 49.1 | 18 | 9.08 | 56 | False |
| 2.5 | 4.0 | 0.4 | 2 | 96.4 | 361.0 | 1348.200000000001 | 9.1 | 0 | 0.0 | 57 | True |
| 2.5 | 4.0 | 0.4 | 3 | 96.4 | 421.0 | 1408.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 4.0 | 0.6 | 1 | 96.4 | 301.0 | 1288.200000000001 | 49.1 | 15 | 7.57 | 56 | False |
| 2.5 | 4.0 | 0.6 | 2 | 96.4 | 361.0 | 1348.200000000001 | 7.3 | 0 | 0.0 | 57 | True |
| 2.5 | 4.0 | 0.6 | 3 | 96.4 | 421.0 | 1408.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 6.0 | 0.25 | 1 | 96.4 | 321.0 | 1288.200000000001 | 30.9 | 34 | 17.15 | 60 | False |
| 2.5 | 6.0 | 0.25 | 2 | 96.4 | 383.0 | 1348.200000000001 | 5.5 | 0 | 0.0 | 57 | True |
| 2.5 | 6.0 | 0.25 | 3 | 96.4 | 443.0 | 1408.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 6.0 | 0.4 | 1 | 96.4 | 321.0 | 1288.200000000001 | 30.9 | 17 | 8.58 | 56 | False |
| 2.5 | 6.0 | 0.4 | 2 | 96.4 | 383.0 | 1348.200000000001 | 5.5 | 0 | 0.0 | 57 | True |
| 2.5 | 6.0 | 0.4 | 3 | 96.4 | 443.0 | 1408.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 6.0 | 0.6 | 1 | 96.4 | 321.0 | 1288.200000000001 | 30.9 | 15 | 7.57 | 56 | False |
| 2.5 | 6.0 | 0.6 | 2 | 96.4 | 383.0 | 1348.200000000001 | 5.5 | 0 | 0.0 | 57 | True |
| 2.5 | 6.0 | 0.6 | 3 | 96.4 | 443.0 | 1408.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 8.0 | 0.25 | 1 | 96.4 | 361.0 | 1288.200000000001 | 16.4 | 32 | 16.15 | 60 | False |
| 2.5 | 8.0 | 0.25 | 2 | 96.4 | 421.0 | 1348.200000000001 | 3.6 | 0 | 0.0 | 57 | True |
| 2.5 | 8.0 | 0.25 | 3 | 96.4 | 481.0 | 1408.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 8.0 | 0.4 | 1 | 96.4 | 361.0 | 1288.200000000001 | 16.4 | 16 | 8.07 | 56 | False |
| 2.5 | 8.0 | 0.4 | 2 | 96.4 | 421.0 | 1348.200000000001 | 3.6 | 0 | 0.0 | 57 | True |
| 2.5 | 8.0 | 0.4 | 3 | 96.4 | 481.0 | 1408.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 8.0 | 0.6 | 1 | 96.4 | 361.0 | 1288.200000000001 | 16.4 | 14 | 7.06 | 56 | False |
| 2.5 | 8.0 | 0.6 | 2 | 96.4 | 421.0 | 1348.200000000001 | 3.6 | 0 | 0.0 | 57 | True |
| 2.5 | 8.0 | 0.6 | 3 | 96.4 | 481.0 | 1408.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 10.0 | 0.25 | 1 | 96.4 | 378.0 | 1288.200000000001 | 12.7 | 31 | 15.64 | 60 | False |
| 2.5 | 10.0 | 0.25 | 2 | 96.4 | 438.0 | 1348.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 10.0 | 0.25 | 3 | 96.4 | 498.0 | 1408.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 10.0 | 0.4 | 1 | 96.4 | 378.0 | 1288.200000000001 | 12.7 | 15 | 7.57 | 56 | False |
| 2.5 | 10.0 | 0.4 | 2 | 96.4 | 438.0 | 1348.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 10.0 | 0.4 | 3 | 96.4 | 498.0 | 1408.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 10.0 | 0.6 | 1 | 96.4 | 378.0 | 1288.200000000001 | 12.7 | 13 | 6.56 | 56 | False |
| 2.5 | 10.0 | 0.6 | 2 | 96.4 | 438.0 | 1348.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 2.5 | 10.0 | 0.6 | 3 | 96.4 | 498.0 | 1408.200000000001 | 0.0 | 0 | 0.0 | 57 | True |
| 3.0 | 3.0 | 0.25 | 1 | 96.4 | 288.0 | 3317.4 | 56.4 | 23 | 11.6 | 59 | False |
| 3.0 | 3.0 | 0.25 | 2 | 96.4 | 350.0 | 3377.4 | 9.1 | 0 | 0.0 | 56 | True |
| 3.0 | 3.0 | 0.25 | 3 | 96.4 | 410.0 | 3437.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 3.0 | 0.4 | 1 | 96.4 | 288.0 | 3317.4 | 56.4 | 8 | 4.04 | 56 | False |
| 3.0 | 3.0 | 0.4 | 2 | 96.4 | 350.0 | 3377.4 | 9.1 | 0 | 0.0 | 56 | True |
| 3.0 | 3.0 | 0.4 | 3 | 96.4 | 410.0 | 3437.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 3.0 | 0.6 | 1 | 96.4 | 288.0 | 3317.4 | 56.4 | 6 | 3.03 | 56 | False |
| 3.0 | 3.0 | 0.6 | 2 | 96.4 | 350.0 | 3377.4 | 7.3 | 0 | 0.0 | 56 | True |
| 3.0 | 3.0 | 0.6 | 3 | 96.4 | 410.0 | 3437.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 4.0 | 0.25 | 1 | 96.4 | 301.0 | 3317.4 | 49.1 | 23 | 11.6 | 58 | False |
| 3.0 | 4.0 | 0.25 | 2 | 96.4 | 361.0 | 3377.4 | 9.1 | 0 | 0.0 | 56 | True |
| 3.0 | 4.0 | 0.25 | 3 | 96.4 | 421.0 | 3437.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 4.0 | 0.4 | 1 | 96.4 | 301.0 | 3317.4 | 49.1 | 8 | 4.04 | 56 | False |
| 3.0 | 4.0 | 0.4 | 2 | 96.4 | 361.0 | 3377.4 | 9.1 | 0 | 0.0 | 56 | True |
| 3.0 | 4.0 | 0.4 | 3 | 96.4 | 421.0 | 3437.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 4.0 | 0.6 | 1 | 96.4 | 301.0 | 3317.4 | 49.1 | 6 | 3.03 | 56 | False |
| 3.0 | 4.0 | 0.6 | 2 | 96.4 | 361.0 | 3377.4 | 7.3 | 0 | 0.0 | 56 | True |
| 3.0 | 4.0 | 0.6 | 3 | 96.4 | 421.0 | 3437.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 6.0 | 0.25 | 1 | 96.4 | 321.0 | 3317.4 | 30.9 | 16 | 8.07 | 57 | False |
| 3.0 | 6.0 | 0.25 | 2 | 96.4 | 383.0 | 3377.4 | 5.5 | 0 | 0.0 | 56 | True |
| 3.0 | 6.0 | 0.25 | 3 | 96.4 | 443.0 | 3437.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 6.0 | 0.4 | 1 | 96.4 | 321.0 | 3317.4 | 30.9 | 8 | 4.04 | 56 | False |
| 3.0 | 6.0 | 0.4 | 2 | 96.4 | 383.0 | 3377.4 | 5.5 | 0 | 0.0 | 56 | True |
| 3.0 | 6.0 | 0.4 | 3 | 96.4 | 443.0 | 3437.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 6.0 | 0.6 | 1 | 96.4 | 321.0 | 3317.4 | 30.9 | 6 | 3.03 | 56 | False |
| 3.0 | 6.0 | 0.6 | 2 | 96.4 | 383.0 | 3377.4 | 5.5 | 0 | 0.0 | 56 | True |
| 3.0 | 6.0 | 0.6 | 3 | 96.4 | 443.0 | 3437.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 8.0 | 0.25 | 1 | 96.4 | 361.0 | 3317.4 | 16.4 | 16 | 8.07 | 57 | False |
| 3.0 | 8.0 | 0.25 | 2 | 96.4 | 421.0 | 3377.4 | 1.8 | 0 | 0.0 | 56 | True |
| 3.0 | 8.0 | 0.25 | 3 | 96.4 | 481.0 | 3437.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 8.0 | 0.4 | 1 | 96.4 | 361.0 | 3317.4 | 16.4 | 8 | 4.04 | 56 | False |
| 3.0 | 8.0 | 0.4 | 2 | 96.4 | 421.0 | 3377.4 | 1.8 | 0 | 0.0 | 56 | True |
| 3.0 | 8.0 | 0.4 | 3 | 96.4 | 481.0 | 3437.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 8.0 | 0.6 | 1 | 96.4 | 361.0 | 3317.4 | 16.4 | 6 | 3.03 | 56 | False |
| 3.0 | 8.0 | 0.6 | 2 | 96.4 | 421.0 | 3377.4 | 1.8 | 0 | 0.0 | 56 | True |
| 3.0 | 8.0 | 0.6 | 3 | 96.4 | 481.0 | 3437.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 10.0 | 0.25 | 1 | 96.4 | 378.0 | 3317.4 | 12.7 | 16 | 8.07 | 57 | False |
| 3.0 | 10.0 | 0.25 | 2 | 96.4 | 438.0 | 3377.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 10.0 | 0.25 | 3 | 96.4 | 498.0 | 3437.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 10.0 | 0.4 | 1 | 96.4 | 378.0 | 3317.4 | 12.7 | 8 | 4.04 | 56 | False |
| 3.0 | 10.0 | 0.4 | 2 | 96.4 | 438.0 | 3377.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 10.0 | 0.4 | 3 | 96.4 | 498.0 | 3437.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 10.0 | 0.6 | 1 | 96.4 | 378.0 | 3317.4 | 12.7 | 6 | 3.03 | 56 | False |
| 3.0 | 10.0 | 0.6 | 2 | 96.4 | 438.0 | 3377.4 | 0.0 | 0 | 0.0 | 56 | True |
| 3.0 | 10.0 | 0.6 | 3 | 96.4 | 498.0 | 3437.4 | 0.0 | 0 | 0.0 | 56 | True |

_180 row(s)_


## Chosen (to be frozen as `detection.COLLECTIVE_BACKHAUL`)

```sql
z = 2.5, floors = (('latency_ms', 3.0), ('packet_loss_pct', 0.1286), ('session_drop_rate_pct', 0.0643)), min_consistency = 0.6, min_reporting_share = 0.8, persist = 2
```
