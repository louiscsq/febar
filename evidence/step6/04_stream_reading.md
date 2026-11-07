# Step 6 collective backhaul detector: Old live `stream` run (only 3 scored backhaul faults)

Generated 2026-11-07 01:48 UTC by `scripts/collective_backhaul_experiment.py`.

- reading `stream`: source_run `stream`, windows 2026-10-08T18:55:00Z .. 2026-10-09T00:55:00Z.
- frozen rule `detection.COLLECTIVE_BACKHAUL`, frozen at commit `e866511994f49fcf0084c994228221f6eb52af9a` (last change to the detector code), scored at
  HEAD `7e27c56dcdc76b17703a7aa5dc727c63390c5f23`: `{"name": "collective_backhaul_v1", "z": 2.5, "floors": {"latency_ms": 3.0, "packet_loss_pct": 0.1286, "session_drop_rate_pct": 0.0643}, "min_consistency": 0.6, "min_reporting_share": 0.8, "persist": 2, "consistency_z": 1.0, "watermark_s": 120}`
- detections computed in SQL on the warehouse from `gold_cell_health_1m`, topology and the change calendar only, written
  to `telco_netmon_febar_catalog.netmon_eval.eval_collective_backhaul_experiment` (reading = `stream`). Ground truth was read afterwards, for scoring only.
- timing: a link-minute is available at max(window_end + 120 s watermark, latest evidence_ts of the
  on-time cell windows used); a cell window arriving after window_end + watermark is not used. No record-level timing.
  "before" is the published step-2 metric (a) (`eval_incident_detection.impact_ttd_s`: first per-cell KPI or alarm
  detection on the incident footprint, evidence time + measured live pipeline latency). For the batch runs that latency
  is 0 on both sides; for `stream` the collective side has no measured pipeline latency (a lower bound).
- scored incidents: 3 customer-impacting, uncensored `BACKHAUL_DEGRADATION` (impact start in the reading).
  Healthy link-days: 30.0.

## Write (SQL)

```sql
INSERT INTO telco_netmon_febar_catalog.netmon_eval.eval_collective_backhaul_experiment
SELECT 'stream' AS reading, 'e866511994f49fcf0084c994228221f6eb52af9a' AS freeze_sha, '{"name": "collective_backhaul_v1", "z": 2.5, "floors": {"latency_ms": 3.0, "packet_loss_pct": 0.1286, "session_drop_rate_pct": 0.0643}, "min_consistency": 0.6, "min_reporting_share": 0.8, "persist": 2, "consistency_z": 1.0, "watermark_s": 120}' AS rule_json, current_timestamp() AS scored_at, *
FROM (
    WITH s AS (
    WITH topo AS (
      SELECT backhaul_id AS parent_id, count(DISTINCT element_id) AS n_desc_cells
      FROM telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes WHERE element_type = 'CELL' GROUP BY backhaul_id
    ),
    h AS (SELECT * FROM telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m WHERE source_run = 'stream' AND window_start >= '2026-10-08T18:55:00Z' AND window_start < '2026-10-09T00:55:00Z'),
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
| SQL detections (table rows) | 532 |
| distinct detection_id | 532 |
| Python mirror detections | 532 |
| in SQL only | 0 |
| in Python only | 0 |

_5 row(s)_


## SQL vs Python mirror: parent-minute statistic recomputed from the cell windows (one hour)

| check | value |
|---|---|
| hour | 2026-10-08T20:55:00Z .. 2026-10-08T21:55:00Z |
| link-minutes (SQL) | 7980 |
| link-minutes (Python) | 7980 |
| keys only in one side | 0 |
| n_reporting_cells mismatches | 0 |
| max abs diff reporting_share | 0 |
| max abs diff available_s | 0 |
| max abs diff wz_latency_ms | 4.44e-16 |
| max abs diff wdelta_latency_ms | 7.11e-15 |
| max abs diff frac_z1_latency_ms | 0 |
| max abs diff wz_packet_loss_pct | 8.88e-16 |
| max abs diff wdelta_packet_loss_pct | 5.55e-17 |
| max abs diff frac_z1_packet_loss_pct | 0 |
| max abs diff wz_session_drop_rate_pct | 4.44e-16 |
| max abs diff wdelta_session_drop_rate_pct | 5.55e-17 |
| max abs diff frac_z1_session_drop_rate_pct | 0 |

_16 row(s)_


## Time to detect, BACKHAUL_DEGRADATION (n = 3)

Ground truth used for scoring only. Undetected incidents count against 'within 5 min' but not in the percentiles.

| subset | n | detector | detected | median_ttd_s | p90_ttd_s | within_5min_pct |
|---|---|---|---|---|---|---|
| all | 3 | before: per-cell (published metric a) | 3 | 807.9 | 826.5 | 0.0 |
| all | 3 | collective alone | 3 | 326.0 | 354.0 | 33.3 |
| all | 3 | after: per-cell + collective (first of) | 3 | 326.0 | 354.0 | 33.3 |
| link <= 6 cells | 1 | before: per-cell (published metric a) | 1 | 587.2 | 587.2 | 0.0 |
| link <= 6 cells | 1 | collective alone | 1 | 267.0 | 267.0 | 100.0 |
| link <= 6 cells | 1 | after: per-cell + collective (first of) | 1 | 267.0 | 267.0 | 100.0 |
| link > 6 cells | 2 | before: per-cell (published metric a) | 2 | 819.5 | 828.9 | 0.0 |
| link > 6 cells | 2 | collective alone | 2 | 343.5 | 357.5 | 0.0 |
| link > 6 cells | 2 | after: per-cell + collective (first of) | 2 | 343.5 | 357.5 | 0.0 |
| all | 3 | median gain, before - after (s) | 3 | 470.2 | 479.5 | NULL |

_10 row(s)_


## Per incident

| incident_id | link | n_cells | before_ttd_s | collective_ttd_s | combined_ttd_s |
|---|---|---|---|---|---|
| INC-2026100820-00006 | BH-VIC-0044 | 21 | 831.2 | 361.0 | 361.0 |
| INC-2026100822-00004 | BH-NSW-0047 | 12 | 807.9 | 326.0 | 326.0 |
| INC-2026100822-00007 | BH-NQL-0012 | 6 | 587.2 | 267.0 | 267.0 |

_3 row(s)_


## False-alarm cost

Alerts: detections grouped per (run, link) with the step-2 rule (a new alert when a
detection starts > 10 min after the previous one ended), labelled by the ground truth whose footprint
holds the link (fault > censored > planned > red herring > unexplained). False alarm = unexplained, red herring, or planned
work not suppressed by the change window. Per 100 healthy link-days (30.0). The per-cell column applies the
same grouping to today's per-cell KPI detections on the link's cells (labelled by the cell's own footprint).

| measure | collective | per-cell KPI rules (today), grouped per link |
|---|---|---|
| n_alerts | 9 | 95 |
| n_fault_tp | 3 | 29 |
| n_censored | 5 | 16 |
| n_planned_suppressed | 0 | 0 |
| n_false_alarms | 1 | 50 |
| n_unexplained | 1 | 50 |
| n_red_herring | 0 | 0 |
| n_planned_unsuppressed | 0 | 0 |
| healthy_link_days | 29.95 | 29.95 |
| false_alarms_per_100_link_days | 3.34 | 166.93 |
| unexplained_per_100_link_days | 3.34 | 166.93 |
| unexplained_busy_hour | 1 | 0 |
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
| BACKHAUL_DEGRADATION | 3 |

_1 row(s)_


## Collective false alarms (all)

| link | start_utc | rows | label | suppressed | busy_hour (w. PRB >= 70 %) | nearby incidents |
|---|---|---|---|---|---|---|
| BH-NQL-0008 | 2026-10-08 21:50 | 3 | unexplained | False | True |  |

_1 row(s)_


## Sensitivity (secondary, not the headline): a dedicated 60 s watermark

The same frozen rule over the statistic rebuilt with a 60 s watermark, as a separate streaming flow with its own watermark would allow. The headline above uses the 120 s watermark of the table actually read.

| subset | n | detector | detected | median_ttd_s | p90_ttd_s | within_5min_pct |
|---|---|---|---|---|---|---|
| all | 3 | before: per-cell (published metric a) | 3 | 807.9 | 826.5 | 0.0 |
| all | 3 | collective alone | 3 | 266.0 | 294.0 | 66.7 |
| all | 3 | after: per-cell + collective (first of) | 3 | 266.0 | 294.0 | 66.7 |
| link <= 6 cells | 1 | before: per-cell (published metric a) | 1 | 587.2 | 587.2 | 0.0 |
| link <= 6 cells | 1 | collective alone | 1 | 207.0 | 207.0 | 100.0 |
| link <= 6 cells | 1 | after: per-cell + collective (first of) | 1 | 207.0 | 207.0 | 100.0 |
| link > 6 cells | 2 | before: per-cell (published metric a) | 2 | 819.5 | 828.9 | 0.0 |
| link > 6 cells | 2 | collective alone | 2 | 283.5 | 297.5 | 50.0 |
| link > 6 cells | 2 | after: per-cell + collective (first of) | 2 | 283.5 | 297.5 | 50.0 |
| all | 3 | median gain, before - after (s) | 3 | 530.2 | 539.5 | NULL |

_10 row(s)_


| measure | value |
|---|---|
| false alarms per 100 healthy link-days | 3.34 |

_1 row(s)_

