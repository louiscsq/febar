# Streaming pipeline and Unity Catalog governance

Step 2 of the Banksia Mobile NOC build. A Lakeflow Spark Declarative Pipeline (Python, serverless) turns
the generator's landing Volume into gold tables that detect customer impact within 5 minutes and give
the later root-cause model topology-aware features. Unity Catalog governance (masks, row filters, groups,
grants, tags) is applied by code in `governance/`. Proof that all of this ran on the workspace is in
[`evidence/step2/`](../evidence/step2/).

- [Architecture](#architecture)
- [Tables](#tables)
- [Expectations policy](#expectations-policy)
- [Windowing, watermarks and the 5-minute latency budget](#windowing-watermarks-and-the-5-minute-latency-budget)
- [Detection and evaluation](#detection-and-evaluation)
- [Collective backhaul detector (offline experiment)](#collective-backhaul-detector-offline-experiment)
- [Governance](#governance)
- [Deploy and run](#deploy-and-run)
- [Known limitations](#known-limitations)

## Architecture

```
 notebooks/01_generate_history.py ──┐                   (jobs, serverless, generator wheel)
 notebooks/02_stream_generator.py ──┤
                                    ▼
 /Volumes/<cat>/netmon_raw/landing/{history,stream}/<feed>/date=YYYY-MM-DD/*.json
                                    │  Auto Loader (cloudFiles), explicit schemas,
                                    ▼  _rescued_data + _corrupt_record, _metadata.file_path
 netmon_bronze   bronze_kpis · bronze_alarms · bronze_sessions · bronze_topology_* · bronze_maintenance_windows
                                    │  parse UTC timestamps, dedupe on record_id (watermark),
                                    ▼  join topology, expectations ──► silver_quarantine
 netmon_silver   silver_kpis · silver_alarms · silver_sessions (masked, row-filtered) · silver_topology_* (MV)
                                    │
                                    ▼
 netmon_gold     gold_cell_baseline (MV) ─► gold_cell_health_1m / _5m · gold_impact_detections (row-filtered)
                 gold_element_impact_5m (MV, topology rollup) · gold_cell_sessions_5m
                                    │
 netmon_eval     bronze_gt_* (ground truth) · eval_detection_log ─► eval_incident_detection · eval_ttd_summary
                 eval_detection_precision · eval_dq_capture · eval_rca_baseline · netmon_pipeline_event_log
 netmon_noc      region-filtered views over the silver / gold tables (the only data regional NOC roles read)
 netmon_gov      mask_imsi · mask_msisdn · region_filter · is_pii_privileged
```

- **One pipeline, one schema per layer.** The pipeline's default schema is `netmon_bronze` and every other
  table is published with a fully qualified name, so grants follow the layers. The national NOC role gets
  gold and selected silver tables, and regional roles get only the region-filtered `netmon_noc` views.
  No role gets bronze, the quarantine or the eval schema.
- **One Auto Loader stream per feed over every generator run.** Each run writes its own sub-directory
  (`history/`, `stream/`), and bronze globs `landing/*/<feed>/`, so a backfill and a live stream share the
  same tables. `_source_run` (from the path) keeps them apart where it matters, such as scoring.
- **Ground truth is ingested into `netmon_eval`, never bronze.** No feature table reads that schema.
- **Code layout.** Pipeline sources live in `pipelines/netmon/transformations/` (`bronze.py`,
  `silver.py`, `gold.py`, `evaluation.py`, using `from pyspark import pipelines as dp`). Rules, schemas,
  detection thresholds, hierarchy and scoring are plain Python in `src/netmon_pipeline/`, rendered to
  Spark SQL and unit-tested locally. The pipeline imports them from the bundle's synced `src/`
  (`netmon.src_path`); the jobs install the same package as a wheel.
- **Execution mode.** The pipeline is **triggered** by default (`pipeline_continuous: false`): the history
  backfill runs to completion and nothing runs (or costs) while idle. For the live demo it is deployed
  with `--var pipeline_continuous=true` and runs **continuously**, processing each micro-batch file as it
  lands. Continuous mode is what the 5-minute SLA needs: a triggered serverless update spends 1–2 minutes
  starting up, which on its own would use a third of the budget.

## Tables

| table | type | grain / key | notes |
|---|---|---|---|
| `bronze_kpis`, `bronze_alarms`, `bronze_sessions` | streaming | one row per delivered line | explicit schema, timestamps as strings, `_rescued_data`, `_corrupt_record`, `_source_file`, `_file_modification_time`, `_ingested_at`, `_source_run` |
| `bronze_topology_nodes`, `_edges`, `bronze_maintenance_windows` | streaming | one row per snapshot line | |
| `silver_topology_nodes`, `_edges` | MV | `element_id` (latest snapshot) | `expect_all_or_fail` on ids, element type, level, region / time zone |
| `silver_maintenance_windows` | MV | `change_id` | UTC timestamps |
| `silver_kpis` | streaming | `record_id` | typed, UTC + local time (`event_ts_local`, `local_date`, `local_hour`, `day_type`) from the cell's IANA zone, ancestors (`site_id` … `amf_id`), `lag_s`, `is_late`, `landed_ts`, `evidence_ts` |
| `silver_alarms` | streaming | `record_id` | plus element region and ancestors, `is_service_down` |
| `silver_sessions` | streaming | `record_id` | IMSI / MSISDN column masks, `region_filter` row filter, pseudonymous `subscriber_key` |
| `silver_quarantine` | streaming | one row per rejected line | `feed`, `record_id`, `failed_rules`, raw timestamp, payload (no PII), redacted rescued / corrupt text |
| `gold_cell_baseline` | MV | `valid_date (local), cell_id, local_hour, day_type` | mean / std of latency, loss, DL throughput, RRC success, drop rate over the 14 local days **before** `valid_date` |
| `gold_cell_health_1m`, `_5m` | streaming | `window_start, source_run, cell_id` | real-time windows from on-time records only: window means, baseline means and std, z-scores, fired rules (`flags`), `is_degraded`, `evidence_ts` |
| `gold_cell_health_5m_retrospective` | MV | `window_start, source_run, cell_id` | the same over all records incl. late arrivals (`n_late_reports`); analysis only, never scored |
| `gold_impact_detections` | streaming | `detection_id` | one row per degraded KPI record or element-down alarm: `detected_ts`, `evidence_ts`, `pipeline_latency_s`, `flags`, `severity_score`, `in_maintenance`; **row-filtered** |
| `gold_element_impact_5m` | MV | `window_start, element_id` | topology rollup (see below), with `evidence_ts` |
| `gold_cell_sessions_5m` | streaming | `window_start, cell_id` | session outcomes, `n_subscribers_approx`, `failure_rate`; no PII |
| `eval_*` | MV / streaming | | see [evaluation](#detection-and-evaluation) |
| `netmon_noc.*` | views | | region-filtered views over the tables above, for regional NOC roles (see [governance](#governance)) |

Every pipeline table has a table comment in code, and `silver_sessions` has column comments in its
declared schema. Tags are applied by `governance/sql/04_comments_tags.sql`.

**Topology rollup (`gold_element_impact_5m`).** For every 5-minute window in which cells reported, every
cell is classed as degraded (from `gold_cell_health_5m`), silent (no KPI row while others reported, so
dark), or fine. The class is then stacked onto the cell's ancestors (`site_id`, `backhaul_id`,
`router_id`, `upf_id`, `amf_id`: one `stack()`, no recursive join). Per element it gives
`n_desc_cells`, `n_silent_cells`, `n_degraded_cells`, `impacted_fraction`, `n_impacted_children` /
`n_children`, `parent_impacted_fraction`, mean latency and throughput z-scores, alarms raised on the
element (`n_alarms`, `n_critical_alarms`, `n_service_down_alarms`, `alarm_codes`) and in its subtree, and
`in_maintenance_window`. These are the candidate root-cause features for the ML step. A high
`impacted_fraction` with a low `parent_impacted_fraction` and alarms on the element is the classic
root signature. No ground-truth column is read.

## Expectations policy

Rules are data in `src/netmon_pipeline/rules.py` and are tested against the generator's own defect log
(`tests/test_pipeline_rules.py`): every injected defect is caught by its mechanism, and every clean
record passes.

| generator defect | mechanism | action |
|---|---|---|
| `malformed / truncated_json` | Auto Loader `_corrupt_record` | the line never reaches the typed view; a dedicated flow writes it to `silver_quarantine` with `failed_rules = [parseable_record]`, the `record_id` recovered from the text where possible, and IMSI/MSISDN redacted |
| `malformed / type_mismatch` | value lands in `_rescued_data` | **drop** (`no_rescued_data`) → quarantine |
| `malformed / bad_timestamp` | `try_to_timestamp` returns NULL | **drop** (`event_ts_valid` / `start_ts_valid`) → quarantine |
| `null / missing_value` | `<col>_not_null` | **drop** → quarantine |
| `out_of_range / impossible_value` | `<col>_in_range` (percentages 0–100, non-negative users / throughput / bytes / duration, latency 0–60 s) | **drop** → quarantine |
| `out_of_range / clock_skew` (alarms 1970 / 2099) | `event_ts_plausible` (event no more than 3 days before or 15 min after delivery) | **drop** → quarantine |
| unknown element (not in topology) | `known_element` | **drop** → quarantine |
| `late_arrival` | `on_time` (delivered > 20 min after the interval ended) | **warn**: kept and flagged `is_late`; it is valid data |
| `duplicate / redelivery` | `dropDuplicatesWithinWatermark(record_id)` | removed in silver; measured in `eval_dq_capture` |
| broken topology (null id, bad level or type, missing zone) | `expect_all_or_fail` | **fail** the update: every join depends on it |

Drop rules use `@dp.expect_all_or_drop`, and the same predicates feed an append flow per feed into
`silver_quarantine`, which records `failed_rules`. So the event log has pass/fail counts per rule, and
every dropped row can still be inspected. `eval_dq_capture` reconciles the quarantine and the silver flags
against `ground_truth/dq_injections`.

## Windowing, watermarks and the 5-minute latency budget

| operator | watermark column | delay | why |
|---|---|---|---|
| silver dedupe (`dropDuplicatesWithinWatermark` on `record_id`) | `_ingested_at` (set by bronze when Auto Loader picks the file up) | 1 h | Ingestion time only moves forward, so no row is ever late for the deduper: not a 36-hour-late record, and not a file that is discovered after newer files. Event and delivery times are used only for the lateness flag. Redeliveries arrive 1–600 s after the original, so the 1-hour horizon gives 6× headroom. Earlier versions watermarked delivery time, then `least(delivery, file mtime)`; both could drop valid rows (the first dropped a whole live run). The semantics are pinned by a reference model in `src/netmon_pipeline/dedupe.py` and its tests |
| `gold_cell_health_1m` / `_5m` | `event_ts` | 2 min | 1-minute KPIs arrive 6–30 s after their period ends; 2 minutes absorbs that plus pipeline jitter |
| `gold_cell_sessions_5m` | `end_ts` | 10 min | xDRs are emitted 5–90 s after the session closes. A stream can only define one watermark, so this table reads an un-watermarked sessions view and deduplicates on `record_id` itself (copies share `end_ts`) |

**One record set for qualification and timing.** The real-time health windows (`gold_cell_health_1m` /
`_5m`) are built **only from on-time records** (`NOT is_late`, `src/netmon_pipeline/windows.py`). Each
window's `evidence_ts` is the latest arrival among exactly those records. Everything downstream inherits
this: the topology rollup, rollup localisation, and the RCA baseline. A window can therefore only qualify
(degraded, or a cell silent) on evidence that had arrived by the time it is stamped with, and it is never
timed by records other than the ones that made it qualify.

- *Choice: option (a), exclude late rows, rather than (b), keep them and time the window by their arrival.*
  With (b) a single late record would re-open a window up to 36 h after it closed. The window's
  qualification would then change after the fact, and so would every rollup and localisation built on it,
  which is a moving target for the step-3 model. With (a) the real-time tables mean exactly what the NOC
  could see at the time. The cost: a cell whose only rows in a window arrived late counts as silent in
  that window (which is what the NOC saw), and late data never improves the real-time picture.
- **Late records are not lost.** They stay in silver (flagged `is_late`), count in the batch baseline and
  eval, and appear in **`gold_cell_health_5m_retrospective`**: the same 5-minute aggregate over all records,
  with `n_late_reports`. That table is for after-the-fact analysis only; no time-to-detect, localisation or
  rollup reads it.
- **Per-record detections** (`gold_impact_detections`) are still emitted for late records, because a late
  degraded record is still a real impact signal. Each one is timed at that record's own arrival (its
  landing or delivery time), so it can make a time-to-detect later but never earlier.
- In a live stream the 2-minute event-time watermark already drops most late rows from the streaming
  windows. The explicit filter makes the rule hold in a one-shot backfill too, where the first micro-batch
  carries no watermark yet. In the first review capture, history late arrivals sat in those windows and
  produced the 127,373 s `AMF_OVERLOAD` localisation.

Tests (`tests/test_pipeline_windows.py`) cover the case where a late row is the one that would make a
window qualify (it is excluded, so nothing is localised from it). They also check that a qualifying window
is never stamped earlier than the arrival of its qualifying row, and that a late record's own detection is
timed at its arrival.

**One implementation, tested in Spark.** The late rule (`windows.is_late_sql`, used by silver for kpis, alarms
and sessions), the real-time record filter (`windows.realtime_records`), the window aggregate
(`windows.window_health`) and the per-record baseline comparison (`windows.score_against_baseline`) live in
`src/netmon_pipeline/windows.py` and are what `silver.py` / `gold.py` call. The real-time stream and the
after-the-fact `gold_cell_health_5m_retrospective` share the same baseline-comparison and window code.
`tests/test_pipeline_windows_spark.py` runs these functions on a local SparkSession and checks them, record by
record and window by window, against the Python mirror (`rules.is_late_py`, `windows.realtime_window`),
including the 20-minute threshold edge; it also asserts that the pipeline sources contain no private copy of
the rule. It needs `pyspark` and a Java 17/21 runtime (`pip install -e ".[dev,spark-tests]"`).

**Latency budget** (impact start → detection row available to the NOC), live 1-minute feed:

| stage | budget | |
|---|---|---|
| KPI period containing the impact closes | ≤ 60 s | a cell that fails 30 s into a minute reports `availability ≈ 50 %` for that minute, which already fires `cell_unavailable` |
| collector delivery (`emitted_ts`) | 6–30 s | |
| landing as a micro-batch file | ≤ 60 s | the generator publishes one file per feed per simulated minute |
| pipeline: Auto Loader → silver → detection | measured as `pipeline_latency_s` | continuous mode; stateless detection, so no window or watermark wait |
| **total target** | **< 300 s** | |

Detection is **stateless per record** (KPI rules against the baseline, and element-down alarms), so it
never waits for a window to close or for the watermark. The 1- and 5-minute windows feed trends,
the rollup and ML features; they are append-only, so a window is emitted once the watermark passes its
end (window + 2 min).

**Baseline without leakage, on the local calendar.** Each KPI record gets `event_ts_local`, `local_date`,
`local_hour` and `day_type` from its cell's IANA zone (`from_utc_timestamp`, so DST is included).
`gold_cell_baseline` is keyed by `valid_date`, a **local** date. The row used on local date *D* aggregates
only local days *D−14 … D−1* (daily count / sum / sum-of-squares combined over the window), and records
join on `local_date = valid_date`. The daily aggregation, the lookback and the join therefore use the same
local day as the hour and day-type keys. A Sydney record at 00:30 local (13:30 UTC the previous day)
belongs to the new local day. Tests cover local midnight, the Sydney DST transitions in October and April,
Brisbane (no DST), Adelaide (+9:30 / +10:30) and Perth. No record is ever scored against its own local
day or later days, even in a one-shot backfill. Outage periods are excluded from the baseline. The first
local day of history has no baseline, so only the hard rules apply there.

## Detection and evaluation

**Rules** (`src/netmon_pipeline/detection.py`):

- hard: `cell_unavailable` (availability < 95 %), `attach_failure` (attach < 95 %), `rrc_collapse`
  (RRC < 80 %). Healthy cells always report 100 % availability and > 98 % attach success, so these have no
  organic false positives (tested on generator output).
- deviation, z > 4 **and** an absolute floor: `latency_degradation` (+40 ms), `packet_loss` (+1.5 pp),
  `throughput_collapse` (and below 50 % of the baseline mean: organic load swings move throughput a lot,
  and the faults that matter cut it by 60–65 %), `rrc_degradation` (−3 pp), `drop_rate_spike` (+2 pp).
- element-down alarms for dark elements, which send no KPIs: `CELL_OUT_OF_SERVICE`, site
  `NE_UNREACHABLE` and CRITICAL `S1_NG_LINK_FAILURE`, CRITICAL backhaul `LINK_DOWN`, router `NODE_DOWN` /
  `NE_UNREACHABLE`. Codes that the generator uses for background noise or flapping (`LOS`, MAJOR
  `LINK_DOWN`, `SYNC_LOSS`) are excluded.

Detections in a change window are kept but flagged `in_maintenance` for suppression downstream.

**Scoring** (`netmon_eval`, definitions in `src/netmon_pipeline/scoring.py`). Scored incidents are
`is_customer_impacting AND NOT is_censored`; censored rows were not fully observed. Each incident gets
**two separate metrics**:

| metric | succeeds when | columns |
|---|---|---|
| **(a) customer-impact detection**, the 5-minute SLA | any detection lands on the incident's **impact footprint** (`root_element_ids`, `affected_element_ids`, `affected_cell_ids`), from the same run, with its signal overlapping the impact window (+10 min slack for alarm lag) | `impact_detected`, `impact_ttd_s`, `impact_within_sla` |
| **(b) root-element localisation** | a detection, **or** the topology rollup (`gold_element_impact_5m`: ≥ 80 % of the element's descendant cells degraded or silent, or a service-down alarm on it), lands on an element of **`root_element_ids`** (falling back to `root_element_id`). For bushfire / cyclone clusters **any** root counts | `root_localised`, `localisation_source`, `localisation_ttd_s`, `localised_within_sla` |

*Why two metrics rather than requiring a root match for "detected".* Step-2 detection is per cell by design,
because customer impact is visible on cells. A dark site or a failed router is the root, while every
symptom is a cell. Requiring the detection itself to land on the root would make the step-2 SLA metric
mostly measure which faults happen to raise an element-level alarm (`NODE_DOWN`, `NE_UNREACHABLE`,
`CELL_OUT_OF_SERVICE`). Quiet faults, such as a backhaul link that only degrades, would never count
however fast customers were flagged. So (a) answers *"did we see the customer impact within 5 minutes?"*
(the NOC's SLA), and (b) answers *"did anything in step 2 point at the true root?"*, which is the contract's
"cluster faults count if any element of `root_element_ids` matches". Ranking the right root above its
ancestors and neighbours is step 3's job (`eval_rca_baseline` is the heuristic bar it has to beat). The
headline tables lead with fault-only rows; planned work is reported separately because the NOC suppresses
it via the change calendar.

- **Evidence before impact.** `evidence_lag_s` and the TTDs are clipped at 0 (a detection is never credited
  before the impact exists). The unclipped value is kept as `signed_evidence_lag_s`, with
  `evidence_before_impact`; it is negative when the first matching evidence, typically an alarm such as a
  router's `NODE_DOWN` raised before its cells lose service, predates `impact_start_ts`.
  `eval_ttd_summary` reports `median_signed_evidence_lag_s`, `min_signed_evidence_lag_s` and
  `n_evidence_before_impact`.
- **Timing.** `ttd = available_ts − impact_start_ts`, where `available_ts = evidence_ts + pipeline_latency_s`.
  `evidence_ts` is when the evidence reached the NOC on the generator's clock: the micro-batch landing
  time (from the file name) for live files, `emitted_ts` for batch history. `pipeline_latency_s` is
  wall-clock time from the file landing in the Volume to the detection row being written, counted for live
  files only (a backfill's processing delay is not detection latency). In a real-time stream this equals
  `detected_ts − impact_start_ts`. The decomposition also scores accelerated streams correctly.
  Localisation through the rollup has no measured emission time, so its time is a lower bound:
  `max(window_end + 2-min watermark, evidence_ts)`, with the MV refresh not included. Windows are
  qualified **and** timed from the same on-time records ([windowing](#windowing-watermarks-and-the-5-minute-latency-budget)). Time and
  element come from one `min(struct(ts, element))`, so the reported element is the earliest localisation.
- **Runs never mix.** `source_run` (the generator run directory) is carried through `silver_*`,
  `gold_cell_health_1m` / `_5m` (grouped by it), `gold_element_impact_5m` (every CTE keyed by it),
  maintenance windows and the detections. Every evaluation join (footprint, rollup localisation, RCA
  baseline, precision) is on `source_run` plus the element, so evidence from one run can never credit an
  incident of another, even if their times overlapped (tested).
- **`eval_ttd_summary`**: per run (history = 15-min ROP backfill, stream = 1-min live), per event class and
  fault type: impact-detected %, median / p90 TTD, % within 5 min (undetected counts as missed), root
  localised %, median localisation time and % localised within 5 min.
- **Precision, at two levels.** Each detection row is labelled by the ground truth it overlaps, in
  priority order. Uncensored fault = **TP**. Overlapping a censored incident = **excluded** (incomplete
  label). Planned work = **suppressed** when `in_maintenance`, else a **FP** (a page for announced work).
  Red herring (e.g. `TRAFFIC_SURGE`) = **FP**. Nothing = **FP**.
  - `eval_detection_precision` gives **detection-row precision** (`row_fault_precision_pct`), one row per
    degraded cell-minute or alarm. A long outage over many cells contributes thousands of TP rows, so this
    figure is flattering on its own.
  - `eval_alert_precision` gives **alert-level precision** (`alert_fault_precision_pct`). Detections of one
    element in one run form one alert until a detection starts more than 10 minutes after the previous
    signal ended (one page to the NOC; back-to-back 15-minute history periods stay one alert). An alert takes the highest-priority label of its rows and is suppressed when its first row
    is in a change window.
  - Both report `maintenance_suppression_pct`, and both join and group on `(source_run, detection_id)`.
- **`eval_rca_baseline`**: a topology heuristic that ranks the rollup's elements and scores hit@1 / hit@3
  against `root_element_ids`. It is the bar the ML model has to beat.

The 15-minute history cannot meet a 5-minute SLA by construction: evidence only exists once the 15-minute
period closes and is delivered 30–240 s later. Its TTD is reported for completeness; the SLA is measured
on the 1-minute stream.

## Collective backhaul detector (offline experiment)

Step 6 question: does rolling cell health up to the backhaul link, weighted by the customers attached to it, detect
slow `BACKHAUL_DEGRADATION` faults earlier than the per-cell rules, and at what false-alarm cost? Evidence:
[`evidence/step6/`](../evidence/step6/). **Offline only:** nothing here is read by the pipeline, the eval MVs, the
`impact_signals` union, the RCA ranker, Lakebase, the app or Genie. No published table was altered (`05_no_change.md`:
`last_altered` of the 89 published result tables). As a **partial retrospective check** against the committed step 2–4
evidence (multiset row comparison; step 5 not replayed, no pre-step snapshot existed): 54 tables identical, 10 unchanged
plus rows of later runs, and 5 that differ for reasons that predate step 6 (evidence README).

**Why slow backhaul is late today.** A backhaul ramp reaches the per-cell floors (+40 ms latency, +1.5 pp loss) only
when about 30 % of its full intensity has built up on one cell, about 8–9 minutes after impact start. The per-minute
noise is about 3 ms / 0.013 pp, so the floors sit far beyond it. Averaging N cells that share a link shrinks
independent noise by about √N. A shift of a few ms that all of the link's cells share is then already significant.

**Design** (`windows.parent_health(_sql)`, `detection.CollectiveRule`, `collective_eval`, all with tests):

- Input: `gold_cell_health_1m` (on-time 1-minute cell windows), topology, change calendar. A cell window is
  **used** in its link-minute only if it holds no late record, its evidence arrived by window_end + watermark (a
  streaming aggregate would have dropped it), no hard rule fired (outages are not soft degradation and are already
  detected per cell), it is not in a change window (site, link or router), and it has a baseline. Silent cells are
  simply not reporting.
- Statistic per `source_run × minute × link`: the `active_users`-weighted mean (weight ≥ 1, so a night-time cell
  still counts) of per-cell z and Δ vs baseline for latency, loss and drop; `n_reporting_cells` / descendant cells
  (`reporting_share`); for each metric the share of reporting cells with z > 1 (the **consistency guard**, so one
  cell cannot carry the mean).
- Rule: for any metric, weighted z > T **and** weighted Δ > floor **and** consistency ≥ c, with
  `reporting_share ≥ 0.8`, on `persist` consecutive minutes. SQL (`collective_detections_sql`, a RANGE frame over
  minute indices) and a Python mirror (scalar and vectorised). `detection_id = sha2('collective|run|link|minute')`.
- **Timing under the late-data rule:** a link-minute is available at **max(window_end + 120 s, latest evidence_ts of
  the cell windows used)**. 120 s is the watermark of `gold_cell_health_1m`, the table actually read. A detection is
  available when its own (latest) minute is. There is no record-level timing in any headline figure.

**Protocol** (as for the RCA model, [`docs/rca_model.md`](rca_model.md)):

1. Calibrate on the `history_1m` **dev days only** (2026-10-14 .. 10-15, the RCA dev split). The script declared a
   180-configuration grid and a selection rule before the sweep: ≤ 1 false alarm per 100 healthy link-days, ≥ 90 %
   detected, then the lowest median TTD (`01_calibration.md`).
2. **Freeze** in `detection.COLLECTIVE_BACKHAUL` (z 2.5; floors 3 ms / 0.1286 pp / 0.0643 pp; consistency 0.6;
   share 0.8; persist 2), commit `e866511`, pushed before any other run was read.
3. Score `holdout_1m` **once** as a separately declared detector-holdout reading. The detector had never touched
   that run; it is a separate reading from the RCA model's use of the same run. Score the old live `stream` run
   too (only 3 scored backhaul faults).
4. A scoring bug in the *before* lookup (below) was fixed after the holdout run. The holdout was re-scored once
   **from its stored detections** (nothing recomputed, no holdout data re-read): `03b_holdout_rescore.md`.
   The detections are identical. The *before* arm and, through it, the combined *after* arm changed:
   after median 331 -> 332 s, p90 461.2 -> 467.1 s, within 5 min 18.9 % -> 17.0 %; before 559 -> 562 s,
   807.6 -> 810.3 s, 9.4 -> 7.5 %. Collective-alone and false-alarm figures are unchanged.

**Results**, `BACKHAUL_DEGRADATION`, TTD = availability − impact start, ground truth used for scoring only. *Before*
= the published step-2 metric (a), the first per-cell KPI or alarm detection on the footprint. *After* = whichever of
per-cell and collective is first:

| reading | n | before median / p90 / ≤ 5 min | after median / p90 / ≤ 5 min | median gain | false collective alerts |
|---|---|---|---|---|---|
| **holdout_1m (detector holdout)** | 53 | 562 s / 810 s / 7.5 % | **332 s / 467 s / 17.0 %** | **190 s** | **0 in 195.7 healthy link-days** |
| holdout, link ≤ 6 cells | 22 | 558 s / 774 s / 4.5 % | 330 s / 589 s / 18.2 % | | |
| holdout, link > 6 cells | 31 | 562 s / 820 s / 9.7 % | 333 s / 384 s / 16.1 % | | |
| history_1m dev (calibrated on) | 55 | 569 s / 957 s / 9.1 % | 323 s / 821 s / 21.8 % | 191 s | 0 in 198.2 |
| stream (old live run) | 3 | 808 s / 827 s / 0 % | 326 s / 354 s / 33.3 % | 470 s | 1 in 30.0 (busy hour) |

- **About 3.2 minutes earlier**, on a run the thresholds were not tuned on, and small links gain as much as large
  ones. That just meets the feasibility report's bar of about 3 minutes for going further.
- **The 5-minute SLA is still mostly missed:** 17 % within 5 min. About 120 s of every collective TTD is the
  watermark. As a secondary sensitivity only, the same frozen rule over a dedicated 60 s-watermark flow gives a
  collective-alone median of about 270 s and 75 % within 5 min on the holdout (`03_holdout_reading.md`).
- **False-alarm cost:** 0 collective false alerts in 195.7 healthy holdout link-days; the 95 % upper bound
  (rule of three) is about 1.5 per 100 link-days, i.e. up to about 2 a day across 133 links. On the
  same link-days, today's per-cell KPI rules raise 135 false alerts per 100 link-days. Every collective alert that
  was not a true positive sat on a link that already had a per-cell alert within 10 minutes: no new pages. The
  only false alarm in any reading (stream) is at busy hour (weighted PRB ≥ 70 %).
- **Not measurable on these runs:** there are no `TRAFFIC_SURGE` incidents in any 1-minute run, and no
  `CORE_CONGESTION` in the dev days, holdout or stream. So these readings cannot show surge false alarms or
  collective true positives on other fault types. All collective true positives were backhaul faults.
- 2 dev incidents and 1 holdout incident are detected by neither detector.
- **Published-metric quirk (found here, not changed):** `eval_incident_detection.impact_ttd_s` is 0, not NULL, for
  an undetected incident (`greatest(NULL, 0)`), so `eval_ttd_summary` medians include those as 0 s. This affects
  1 holdout and 4 history_1m incidents. The step-6 *before* treats them as undetected.

**Caveats.**

- **Generator noise is nearly independent across cells.** `netmon_datagen.kpis` draws every cell's per-minute noise
  separately; the feasibility simulation measured a within-link correlation of latency z of 0.017. Real networks
  have common-mode variation (shared demand, weather, transport jitter), so the √N gain and the zero false-alarm
  count here are an **upper bound**. Thresholds must be re-checked on real or correlated data.
- The *before* side for the batch runs has no pipeline latency (evidence = emission time), and neither does the
  collective side. On `stream`, the *before* includes measured live pipeline latency and the collective side does
  not, so the stream gain is a lower bound on collective TTD, with n = 3.

**Why it stays offline and is not wired into the ranker.** Adding a source to the `impact_signals` union forces a
full refresh, which would recompute the live run's `pipeline_latency_s` as backfill time. Every published step-2
figure would also move. The ranker opens cases only from per-cell degradation, so a collective signal would need
case seeding, a retrain (v6) and a new fresh holdout (`holdout_1m` is now used). The honest SLA claim needs
measured live latency from a new live stream. That is the full version (b) of the feasibility study.

## Governance

Applied by `governance/apply_governance.py` (job `banksia-netmon-governance`, or as tasks of
`banksia-netmon-bootstrap`). It runs the SQL in `governance/sql/` with `${...}` substitution:

| file | content |
|---|---|
| `01_functions.sql` | `is_pii_privileged()`, `mask_imsi`, `mask_msisdn` (full value for `pii_privileged`, otherwise PLMN / country code plus the last 2–3 digits), `region_filter(region_code)` (`noc_national` sees everything, `noc_region_<code>` only its region) |
| `02_noc_views.sql` | `netmon_noc`: one view per silver / gold table a regional NOC user needs (KPIs, alarms, sessions, topology nodes / edges, maintenance, baseline, 1- and 5-min health, detections, rollup, session outcomes), each `WHERE region_filter(region_code)`. Tables without `region_code` take it from the topology |
| `03_grants_national.sql` | `noc_national`: `USE CATALOG`; `USE SCHEMA` + `SELECT` on gold; `SELECT` on `silver_sessions`, `silver_kpis`, `silver_alarms`, topology and maintenance; `SELECT` on `netmon_noc` |
| `03_grants_regional.sql` | `noc_region_<code>`: `USE CATALOG`, `USE SCHEMA` + `SELECT` on `netmon_noc` only, plus `EXECUTE` on `region_filter`. No silver or gold table directly |
| (none) | `pii_privileged`: **no grants**. It is only tested inside the mask functions, so it unmasks IMSI / MSISDN for someone who already holds a NOC role and gives access to nothing on its own |
| `04_comments_tags.sql` | schema comments and tags (`domain`, `layer`, `contains_pii`), PII tags on IMSI / MSISDN in bronze and silver, domain / grain / consumer tags on the gold tables, `ground_truth` tags on eval |

**Where masks and filters attach.** The pipeline declares them on its own tables, since Lakeflow-managed
tables take policies in their definition: `silver_sessions` has
`imsi STRING MASK <gov>.mask_imsi` and `msisdn STRING MASK <gov>.mask_msisdn` in its schema plus
`ROW FILTER <gov>.region_filter ON (region_code)`, and `gold_impact_detections` has the same row
filter. Two design points follow:

- Filtered or masked tables are **leaves** in the pipeline. Gold reads the unfiltered `sessions_typed`
  view, and the evaluation reads `eval_detection_log` (an unfiltered copy of the detections), never a
  policy-protected table. A filter evaluates against the identity of whoever reads, which inside a
  pipeline is the owner, so a non-leaf filtered table would silently drop rows depending on the
  owner's group memberships.
- **Regional access goes through views.** Regional roles must not see other regions in any table they
  can read. Putting a row filter on every region-bearing pipeline table would break the leaf rule above,
  since the pipeline streams from silver KPIs, alarms, topology and the health tables. So regional roles
  are granted only `netmon_noc`, whose views apply `region_filter`. The filter and the masks are evaluated
  for the querying user, including through a view. `noc_national` reads the tables directly.
- **Grant convergence.** Before the role grants are applied, `REVOKE ALL PRIVILEGES` is issued on every
  netmon securable (catalog, every `netmon_*` schema, table, view and function, enumerated from
  `information_schema`) from **every managed principal**: all `noc_*` / `pii_privileged` groups and every
  persona. A rerun therefore converges to the declared roles, and nothing left from an older grant model
  (such as direct silver / gold access for a regional group) survives. Groups that UC rejects as
  principals (workspace-local) are recorded; they cannot hold grants at all. The job then asserts that no
  regional or pii-only principal holds any privilege on bronze, silver, gold or eval.
- Bronze holds raw IMSI / MSISDN and is not granted to anyone. The quarantine payload leaves them out, and
  its rescued / corrupt text is regex-redacted.

**Groups (platform constraint).** This FEVM workspace lets a workspace admin create **workspace-local**
groups but not account groups, and Unity Catalog rejects workspace-local groups as grantees
(`PRINCIPAL_DOES_NOT_EXIST`). So:

- `noc_national`, `pii_privileged` and `noc_region_<code>` for all ten regions are created as
  workspace-local groups. The policy functions check `is_account_group_member(g) OR is_member(g)`, so they
  work unchanged with account groups in production.
- Grants are attempted on the group first. When UC rejects the group, the grants go to the group's
  **persona service principals**, which are account-level identities: `netmon-noc-national`
  (`noc_national`), `netmon-noc-nsw-analyst` (`noc_region_nsw`), `netmon-noc-wa-analyst` (`noc_region_wa`),
  `netmon-pii-officer` (`noc_national` + `pii_privileged`: unmasked) and `netmon-pii-only`
  (`pii_privileged` only: holds no privileges at all).
- The pipeline owner is added to `noc_national` (sees all regions) but not to `pii_privileged`, so the
  owner reads masked identifiers too.

**Lineage** is captured by Unity Catalog automatically. `system.access.table_lineage` has every
bronze → silver → gold → eval edge (`evidence/step2/07_lineage.md`). On this workspace the Auto Loader hop
from the Volume is recorded as a pipeline edge into each bronze table with a NULL source (no Volume path),
both in the system table and in the lineage REST API. That hop is shown instead by `_source_file`
(`_metadata.file_path`) on every bronze row.

## Deploy and run

```bash
databricks bundle validate -p febar
databricks bundle deploy -p febar

# 1. history backfill (small preset, 14 days of 15-minute KPIs as JSON, ~4 min)
databricks bundle run -p febar netmon_generate_history
# 2. mask / filter functions (the pipeline's tables reference them)
databricks bundle run -p febar netmon_governance --params stage=functions
# 3. pipeline, triggered: processes the history to completion
databricks bundle run -p febar netmon_pipeline
# 4. groups, personas, region-filtered views, role grants, comments, tags
databricks bundle run -p febar netmon_governance --params stage=policies
#    (steps 1-4 in one go: databricks bundle run -p febar netmon_bootstrap)

# 5. live: switch the pipeline to continuous and stream for ~30 min (360 simulated minutes, 12x speed)
databricks bundle deploy -p febar --var pipeline_continuous=true
databricks bundle run -p febar netmon_pipeline --no-wait
databricks bundle run -p febar netmon_stream_generator \
    --params max_batches=360,interval_seconds=5,fault_rate_multiplier=200
# stop the continuous pipeline afterwards
databricks pipelines stop <pipeline-id> -p febar
databricks bundle deploy -p febar          # back to triggered

# evidence (local, uses the SQL warehouse)
python scripts/capture_evidence.py --profile febar --warehouse <id> --pipeline-id <id> --governance-demo
```

Live stream parameters. At the `small` preset, a real-time stream would see too few incidents finish
within a reasonable demo window: most fault types last 20 minutes to several hours, and scoring needs
uncensored incidents. So the demo runs the generator 12× faster (one simulated minute every 5 s, 6 simulated
hours) with a fault-rate multiplier of 200, which gives a few dozen uncensored fault incidents. TTD stays
honest because it adds the measured wall-clock pipeline latency to the simulated evidence time
([above](#detection-and-evaluation)).

## Known limitations

- **Workspace-local groups and SP personas** instead of account groups (see [Governance](#governance)).
  Masks and filters are demonstrated by changing the capturing user's group membership and querying every
  object a regional role is granted. Querying as a persona service principal was not possible because
  creating OAuth secrets for service principals is not available to this session. Grant-level denial
  (for example the pii-only persona) is shown from `information_schema` privileges. The capturing user
  is the catalog owner and can always read the base tables, so it cannot itself show a grant denial.
- **Dedupe horizon.** Streaming dedupe holds state for 1 hour of ingestion time. A redelivery ingested
  later than that is admitted to silver (bounded state) and counted by `eval_dq_capture`
  (`n_single_copy_in_silver`). Exactly-once over unbounded time would need unbounded state or a MERGE-based
  silver.
- **Dedupe is global across runs.** One silver table and one dedupe state serve every generator run, so
  `record_id` must be unique across runs, not just within one (`docs/data_model.md`, "IDs across runs"). State is
  evicted only when a later micro-batch advances the watermark: after an idle gap, the first batch is still
  checked against the previous batch's keys, however old. That is how `holdout_1m` lost 5,417 alarm IDs to
  `history_1m` and `history_1m` lost 90 to `history` (four weeks apart) while incident alarm IDs repeated between
  runs (fixed in PR #6; `evidence/step3/08_alarm_id_fix.md`).
- **Replacing a run's feed.** Bronze feeds and `silver_alarms` are read with `skipChangeCommits`: appends are read
  as before, and a commit that only deletes rows does not break the streams. That is what made the PR #6
  correction possible without a full refresh (which would have reset the append-only health windows and
  recomputed the live run's wall-clock latency): `banksia-netmon-replace-run-feeds` swaps the regenerated
  alarm / DQ-log / change-calendar files in (new names), deletes the superseded rows in bronze, silver, quarantine
  and the alarm detections, then runs an incremental update. Deletes are not propagated by the pipeline itself;
  the job deletes in every affected streaming table. The change calendar's derived tables are materialized views
  recomputed from bronze, so they need no delete. A final `check` task (`netmon_pipeline.replace_check`) fails the
  job unless no superseded row, pre-fix change ID or duplicate maintenance window remains
  (`evidence/step3/09_replace_check.md`).
- **In-maintenance join fan-out.** `impact_signals` flags a detection as in maintenance by joining the change
  calendar on its site or router. A detection inside two overlapping windows (site and router, or two router
  changes) is written once per window, with identical content. 0.03–0.6 % of the 1-minute runs' detection
  rows repeat this way (`09_replace_check.md`). Downstream counts that use `count(*)` over detections can be
  slightly inflated; a distinct-window aggregation before the join would fix it. It predates PR #6 and was not
  changed there (step-2 tables and the frozen step-3/4 inputs would move).
- **Backfill ordering.** The event-time watermarks assume the history arrives roughly in emission order.
  Bronze allows 20,000 files per micro-batch, so a `small` history is ingested in one batch; a much
  larger backfill split over several batches could see some 15-minute history rows fall behind the
  2-minute health watermark. Silver and the batch MVs are unaffected.
- **Baseline size.** One baseline row per cell × local hour × day type × date is fine at `small` (≈1 M
  rows). At `large` / `xl`, switch to weekly `valid_from` snapshots.
- **Detection granularity.** Detections are per cell-minute (or per alarm), not deduplicated into
  incidents. Grouping into incidents and ranking the root is the ML step's job, using
  `gold_element_impact_5m`.
- **Silent-cell inference** in the rollup only covers windows in which some cell reported. A whole-network
  outage would look like no data at all.
- **Ramped faults.** Backhaul degradation and core congestion ramp in over 10–30 minutes. At low intensity
  they are inside normal variation, so their TTD is naturally longer than for outages.
  The offline collective link detector (step 6, [above](#collective-backhaul-detector-offline-experiment))
  brings backhaul TTD from about 9.4 to 5.5 minutes on the holdout, still mostly outside 5 minutes; link-level
  telemetry (interface errors, RSL, utilisation) remains the real fix.
- **Sessions are sparse** at `small` (1 % sample), so they feed features rather than detection.
- **Volume lineage.** `system.access.table_lineage` does not record the Volume path as the source of the
  Auto Loader tables on this workspace (see [Governance](#governance)); `_source_file` carries it.
