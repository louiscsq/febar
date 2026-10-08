# Step 2 evidence: pipeline and governance run on the workspace

All files are text, captured on 2026-10-08 (UTC) from workspace profile `febar` by
`scripts/capture_evidence.py` (SQL on the serverless starter warehouse, plus the Databricks CLI). This is
the second capture, after the review fixes: every table was rebuilt with a full refresh and a fresh live
stream. Samples are small, and IMSI / MSISDN only ever appear masked.

## Headline: faults only (live 1-minute stream)

Scored incidents are customer-impacting and not censored. Two separate metrics; see
[`docs/pipeline.md`](../../docs/pipeline.md#detection-and-evaluation) for why.

| live stream, `event_class = fault` (31 incidents) | rate | median | p90 | within 5 min |
|---|---|---|---|---|
| **(a) customer-impact detection**: first detection on the incident's footprint | 100 % | 112 s | 265 s | **90.3 %** |
| **(b) root-element localisation**: a detection or the rollup on an element of `root_element_ids` | **96.8 %** | 114 s | | 87.1 % |
| **fault-detection precision** (TP / (TP + FP); red herrings and unsuppressed planned work are FP, censored excluded) | **99.8 %** | | | |
| maintenance suppression (planned-work detections flagged `in_maintenance`) | 97.4 % | | | |
| pipeline latency, file landed → detection row | | 40 s | | |

- Per fault type (live): `CELL_OUTAGE` 19/19 and `AGG_ROUTER_FAILURE` 4/4 were detected and localised
  within 5 min. `SITE_POWER_OUTAGE` had 5/5 detected within 5 min and 4/5 localised.
  `BACKHAUL_DEGRADATION` had 0/3 within 5 min (detected after 6, 7 and 10 min): it ramps in over 10–30 min
  by design. All three backhaul faults were localised, through the rollup, after the SLA.
- Batch history (15-minute ROP, cannot meet a 5-minute SLA by construction), faults only (16 incidents):
  impact detected 93.8 %, 75.0 % within 5 min, root localised 87.5 % (68.8 % within 5 min), fault
  precision 81.8 %. The 171 detections on the `TRAFFIC_SURGE` red herring now count as false positives.
- RCA topology heuristic (the bar for the step-3 model): hit@1 34.3 % / hit@3 51.4 % live, 63.2 % / 73.7 %
  history.
- Every injected DQ defect type in both runs (77,929 history + 12,539 live defects) was handled by its
  intended mechanism (`handled_pct = 100`; session dedupe is not re-scored).

## Files

| file | content |
|---|---|
| [`01_pipeline_status.md`](01_pipeline_status.md) | pipeline spec, every update and its final state, flows of the last completed update, errors from the deploy-and-fix iterations |
| [`02_expectations.md`](02_expectations.md) | expectation pass/fail counts per dataset and rule from the event log (since the last full refresh), dropped rows, quarantine by rule, quarantine sample, injected-defect reconciliation (`eval_dq_capture`) |
| [`03_row_counts.md`](03_row_counts.md) | row counts for every table, bronze and silver per generator run |
| [`04_gold_samples.md`](04_gold_samples.md) | sample rows of every gold table, live pipeline latency |
| [`05_time_to_detect.md`](05_time_to_detect.md) | fault-only headline, every event class, per fault type, per live fault incident, ground-truth mix, fault precision and maintenance suppression, RCA heuristic |
| [`06_governance.md`](06_governance.md) | masks, row filters, region-filtered views, policy functions, roles and members, every persona's privileges, tags, comments, and the five-state membership demo |
| [`07_lineage.md`](07_lineage.md) | `system.access.table_lineage` edges, and the Volume → bronze hop via `_metadata.file_path` |

## What was run (second capture)

1. `databricks bundle deploy`, which also created the `netmon_noc` schema. The previous live data was
   deleted, then `banksia-netmon-pipeline` ran with a full refresh over the 14-day `small` history
   (COMPLETED).
2. Live: pipeline redeployed **continuous**, then `banksia-netmon-stream-generator` ran for **30 minutes**
   (14:52–15:22 UTC wall clock, 360 one-minute micro-batches at 5 s each, 6 simulated hours, fault-rate
   multiplier 200). The pipeline processed it as it landed. Ground truth: 31 uncensored and 14 censored
   faults, 4 planned, 7 red herrings. The pipeline was then switched back to triggered, and a final
   update (COMPLETED) refreshed the materialized views.
3. `banksia-netmon-governance` stage `all`: functions, groups, personas, `netmon_noc` views, persona grant
   reset and role grants, tags. Then this capture, with the membership demo.

## Governance demo (06_governance.md)

The capturing user's group membership is changed, and every object a regional role can read (the 12
`netmon_noc` views) is queried in each state:

| state | rows visible | IMSI / MSISDN |
|---|---|---|
| `noc_national` | all regions | masked (0 full values) |
| `noc_region_nsw` only | **NSW only, in every view** | masked |
| no NOC group | **no rows in any view** | — |
| `pii_privileged` only (no NOC role) | **no rows in any view**; the `netmon-pii-only` persona holds no privileges | — |
| `noc_national` + `pii_privileged` | all regions | **unmasked** (checked by pattern, never printed) |

The capturing user owns the catalog and can always read the base tables, so it cannot itself show a
grant denial. Grant-level least privilege is shown from `information_schema` for every persona: the
regional analysts hold only `netmon_noc`, and `pii_privileged` holds nothing.

## Issues found on the real runs (fixed; earlier errors are kept in the event log)

- Liquid clustering needs stats on the clustering columns, so the window columns come first.
- `gold_cell_sessions_5m` redefined an inherited watermark. It now has its own path.
- First run: a delivery-time dedupe watermark was pushed a day ahead by history late arrivals and dropped
  the live stream. Review fix: the watermark is now on the monotonic ingestion time.
- The metastore enforces governed tag policies, so tags use allowed values plus `netmon_*` keys.
