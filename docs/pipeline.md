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
 netmon_gov      mask_imsi · mask_msisdn · region_filter · is_pii_privileged
```

- **One pipeline, one schema per layer.** The pipeline's default schema is `netmon_bronze` and every other
  table is published with a fully qualified name, so grants follow the layers: NOC personas get gold
  and selected silver tables, never bronze, the quarantine or the eval schema.
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
| `silver_kpis` | streaming | `record_id` | typed, UTC + local time (`event_ts_local`, `local_hour`, `day_type`) from the cell's IANA zone, ancestors (`site_id` … `amf_id`), `lag_s`, `is_late`, `landed_ts`, `evidence_ts` |
| `silver_alarms` | streaming | `record_id` | plus element region and ancestors, `is_service_down` |
| `silver_sessions` | streaming | `record_id` | IMSI / MSISDN column masks, `region_filter` row filter, pseudonymous `subscriber_key` |
| `silver_quarantine` | streaming | one row per rejected line | `feed`, `record_id`, `failed_rules`, raw timestamp, payload (no PII), redacted rescued / corrupt text |
| `gold_cell_baseline` | MV | `valid_date, cell_id, local_hour, day_type` | mean / std of latency, loss, DL throughput, RRC success, drop rate over the 14 days **before** `valid_date` |
| `gold_cell_health_1m`, `_5m` | streaming | `window_start, cell_id` | window means, baseline means and std, z-scores, fired rules (`flags`), `is_degraded` |
| `gold_impact_detections` | streaming | `detection_id` | one row per degraded KPI record or element-down alarm: `detected_ts`, `evidence_ts`, `pipeline_latency_s`, `flags`, `severity_score`, `in_maintenance`; **row-filtered** |
| `gold_element_impact_5m` | MV | `window_start, element_id` | topology rollup (see below) |
| `gold_cell_sessions_5m` | streaming | `window_start, cell_id` | session outcomes, `n_subscribers_approx`, `failure_rate`; no PII |
| `eval_*` | MV / streaming | | see [evaluation](#detection-and-evaluation) |

Every pipeline table has a table comment in code, and `silver_sessions` has column comments in its
declared schema. Tags are applied by `governance/sql/03_comments_tags.sql`.

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
| silver dedupe (`dropDuplicatesWithinWatermark`) | `emitted_ts` (delivery time) | 15 min | redeliveries arrive 1–600 s after the original. Using delivery time rather than event time means a 36-hour-late record is still deduplicated, not discarded as late |
| `gold_cell_health_1m` / `_5m` | `event_ts` | 2 min | 1-minute KPIs arrive 6–30 s after their period ends; 2 minutes absorbs that plus pipeline jitter |
| `gold_cell_sessions_5m` | `end_ts` | 5 min | xDRs are emitted 5–90 s after the session closes |

Late arrivals (30 min – 36 h) are kept in silver, flagged `is_late`, and included in the batch MVs
(baseline, rollup, eval), but they arrive behind the event-time watermark, so the streaming health windows
drop them. A late record is no use for real-time detection anyway.

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

**Baseline without leakage.** `gold_cell_baseline` is keyed by `valid_date`. The row used on date *D*
aggregates only days *D−14 … D−1* (daily count / sum / sum-of-squares combined over the window). Each
record is scored against its own cell, local hour and day type (weekday / weekend, from the cell's IANA
zone, DST included). That is true even when the whole history is backfilled in one update, so no record
is ever scored against its own day or later days. Outage periods are excluded from the baseline. The
first day of history has no baseline, so only the hard rules apply there.

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

**Scoring** (`netmon_eval`, definitions in `src/netmon_pipeline/scoring.py`):

- Scored incidents: `is_customer_impacting AND NOT is_censored`. Censored rows were not fully observed.
- A detection matches an incident if its element is the root, any of `root_element_ids` (every site or
  link of a bushfire or cyclone cluster), `affected_element_ids` or `affected_cell_ids`, from the same run,
  and its signal overlaps the impact window (+10 min slack for alarm lag). `root_detected` says whether a
  detection hit a true root, so a cluster fault counts as long as any of its roots was flagged.
- `ttd_s = available_ts − impact_start_ts`, where `available_ts = evidence_ts + pipeline_latency_s`.
  `evidence_ts` is when the evidence reached the NOC on the generator's clock. For live files that is the
  micro-batch landing time (from the file name); for batch history it is `emitted_ts`.
  `pipeline_latency_s` is wall-clock time from the file landing in the Volume to the detection row being
  written, counted for live files only (a backfill's processing delay is not detection latency). In a
  real-time stream (`interval_seconds = step_seconds`) this equals `detected_ts − impact_start_ts`. The
  decomposition also makes accelerated streams (several simulated minutes per wall minute) score
  correctly.
- `eval_ttd_summary`: per run (history = 15-min ROP backfill, stream = 1-min live), overall and per fault
  type: detected %, median and p90 TTD, % within 5 minutes (undetected counts as missed).
- `eval_detection_precision`: share of detections explained by any ground-truth event, including red
  herrings and planned work.
- `eval_rca_baseline`: a topology heuristic that ranks the rollup's elements and scores hit@1 / hit@3
  against `root_element_ids`. It is the bar the ML model has to beat.

The 15-minute history cannot meet a 5-minute SLA by construction: evidence only exists once the 15-minute
period closes and is delivered 30–240 s later. Its TTD is reported for completeness; the SLA is measured
on the 1-minute stream.

## Governance

Applied by `governance/apply_governance.py` (job `banksia-netmon-governance`, or as tasks of
`banksia-netmon-bootstrap`). It runs the SQL in `governance/sql/` with `${...}` substitution:

| file | content |
|---|---|
| `01_functions.sql` | `is_pii_privileged()`, `mask_imsi`, `mask_msisdn` (full value for `pii_privileged`, otherwise PLMN / country code plus the last 2–3 digits), `region_filter(region_code)` (`noc_national` sees everything, `noc_region_<code>` only its region) |
| `02_grants.sql` | per persona: `USE CATALOG`; `USE SCHEMA` + `SELECT` on gold; `SELECT` on `silver_sessions`, `silver_kpis`, `silver_alarms`, topology and maintenance; `USE SCHEMA` on gov. No bronze, quarantine or eval, and no `MODIFY` |
| `03_comments_tags.sql` | schema comments and tags (`domain`, `layer`, `contains_pii`), PII tags on IMSI / MSISDN in bronze and silver, domain / grain / consumer tags on the gold tables, `ground_truth` tags on eval |

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
  (`noc_national`), `netmon-noc-nsw-analyst` (`noc_region_nsw`), `netmon-noc-wa-analyst` (`noc_region_wa`)
  and `netmon-pii-officer` (`noc_national` + `pii_privileged`).
- The pipeline owner is added to `noc_national` (sees all regions) but not to `pii_privileged`, so the
  owner reads masked identifiers too.

**Lineage** (Volume → bronze → silver → gold) is captured by Unity Catalog automatically. The evidence
includes a query against `system.access.table_lineage`.

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
# 4. groups, personas, grants, comments, tags
databricks bundle run -p febar netmon_governance --params stage=policies
#    (steps 1-4 in one go: databricks bundle run -p febar netmon_bootstrap)

# 5. live: switch the pipeline to continuous and stream for ~40 min (240 simulated minutes, 6x speed)
databricks bundle deploy -p febar --var pipeline_continuous=true
databricks bundle run -p febar netmon_pipeline --no-wait
databricks bundle run -p febar netmon_stream_generator \
    --params max_batches=240,interval_seconds=10,fault_rate_multiplier=100
# stop the continuous pipeline afterwards
databricks pipelines stop <pipeline-id> -p febar
databricks bundle deploy -p febar          # back to triggered

# evidence (local, uses the SQL warehouse)
python scripts/capture_evidence.py --profile febar --warehouse <id>
```

Live stream parameters. At the `small` preset, a real-time stream would see too few incidents finish
within a reasonable demo window: most fault types last 20 minutes to several hours, and scoring needs
uncensored incidents. So the demo runs the generator 6× faster (one simulated minute every 10 s) with a
fault-rate multiplier of 100. TTD stays honest because it adds the measured wall-clock pipeline latency
to the simulated evidence time ([above](#detection-and-evaluation)).

## Known limitations

- **Workspace-local groups and SP personas** instead of account groups (see [Governance](#governance)).
  Masks and filters are demonstrated by changing the owner's group membership and calling the policy
  functions. Querying as a persona service principal was not possible because creating OAuth secrets
  for service principals is not available to this session.
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
- **Sessions are sparse** at `small` (1 % sample), so they feed features rather than detection.
