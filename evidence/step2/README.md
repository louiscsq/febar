# Step 2 evidence: pipeline and governance run on the workspace

All files are text, captured on 2026-10-08 (UTC) from workspace profile `febar` by
`scripts/capture_evidence.py` (SQL on the serverless starter warehouse, plus the Databricks CLI). This is
the fourth capture, after the third review. Every table was rebuilt with a full refresh, one fresh live
stream was run, and governance was re-applied. Samples are small, and IMSI / MSISDN only ever appear
masked.

## Headline: faults only (live 1-minute stream)

Scored incidents are customer-impacting and not censored. Two separate metrics; see
[`docs/pipeline.md`](../../docs/pipeline.md#detection-and-evaluation) for why. The real-time windows the
rollup and localisation are built from are qualified **and** timed from the same on-time records.

| live stream, `event_class = fault` (26 incidents) | rate | median | p90 | within 5 min |
|---|---|---|---|---|
| **(a) customer-impact detection**: first detection on the incident's footprint | 100 % | 141 s | 430 s | **88.5 %** |
| **(b) root-element localisation**: a same-run detection or rollup on an element of `root_element_ids` | **100 %** | 144 s | | 88.5 % |
| **alert-level fault precision**: per element per episode | **60.1 %** (104 TP / 69 FP alerts; 58 excluded as censored) | | | |
| **detection-row fault precision**: per degraded cell-minute or alarm | **98.2 %** (5,313 TP / 98 FP rows; 2,924 censored) | | | |
| maintenance suppression | n/a: no planned work occurred in this live run (history: 100 %) | | | |
| pipeline latency, file landed → detection row | | 39 s | | |

- Per fault type (live): all 20 `CELL_OUTAGE`, both `SITE_POWER_OUTAGE` and the one `AGG_ROUTER_FAILURE`
  fault were detected and localised within 5 min. The three `BACKHAUL_DEGRADATION` faults (they ramp in
  over 10–30 min by design) were detected after 10, 13 and 14 min and localised through the rollup after
  15, 19 and 20 min.
- Row and alert precision differ because a long outage over many cells produces thousands of TP rows but
  only a few alerts. The unmatched FP rows are mostly isolated single-minute deviations, and each one is
  its own alert. Alert-level is the number a NOC pager would see.
- Batch history (15-minute ROP, cannot meet a 5-minute SLA by construction), faults only (16 incidents):
  impact detected 93.8 %, 75.0 % within 5 min, root localised 87.5 % (68.8 % within 5 min). Row precision
  is 81.8 % and alert precision 69.1 % (the `TRAFFIC_SURGE` red herring counts as FP).
- **History `AMF_OVERLOAD` INC-00016 is localised at 1,499 s, from on-time inputs only**
  (`05_time_to_detect.md`). The qualifying rollup window is 10:15–10:20 UTC: 518 of 528 cells degraded,
  built from 518 on-time records and 0 late ones. It is stamped 10:34:00, the latest arrival of exactly
  those qualifying records (their 15-minute period ended at 10:30). The impact started at 10:09:01.
  The slowest history fault localisation is 1,909 s. The real-time 5-minute table holds 0 late records;
  the 24,359 late records live only in `gold_cell_health_5m_retrospective`, which nothing scores.
- RCA topology heuristic (the bar for the step-3 model): hit@1 53.8 % / hit@3 73.1 % live, 57.9 % / 68.4 %
  history.
- Every injected DQ defect type in both runs (77,929 history + 12,997 live defects) was handled by its
  intended mechanism (`handled_pct = 100`; session dedupe is not re-scored).

## Files

| file | content |
|---|---|
| [`01_pipeline_status.md`](01_pipeline_status.md) | pipeline spec, every update and its final state, flows of the last completed update, errors from earlier deploy-and-fix iterations |
| [`02_expectations.md`](02_expectations.md) | expectation pass/fail counts per dataset and rule (since the last full refresh), dropped rows, quarantine by rule, quarantine sample, injected-defect reconciliation |
| [`03_row_counts.md`](03_row_counts.md) | row counts for every table, bronze and silver per generator run |
| [`04_gold_samples.md`](04_gold_samples.md) | sample rows of every gold table, live pipeline latency |
| [`05_time_to_detect.md`](05_time_to_detect.md) | fault-only headline, every event class, per fault type, per live fault incident, ground-truth mix, alert-level and detection-row precision, the AMF INC-00016 localisation and its qualifying inputs, real-time vs retrospective late-record counts, RCA heuristic |
| [`06_governance.md`](06_governance.md) | masks, row filters, region-filtered views, policy functions, roles and members, each persona's privileges, base-table privileges of regional / pii-only principals (none), UC's view of a regional group, tags, comments, and the five-state membership demo |
| [`07_lineage.md`](07_lineage.md) | `system.access.table_lineage` edges, and the Volume → bronze hop via `_metadata.file_path` |

## What was run (fourth capture)

1. `databricks bundle deploy`. The previous live data was deleted, then `banksia-netmon-pipeline` ran
   with a full refresh over the 14-day `small` history (COMPLETED).
2. Live: pipeline redeployed **continuous**, then exactly one `banksia-netmon-stream-generator` run
   (`892527430873662`; the job does not queue): **31 minutes** (18:55–19:26 UTC), 360 one-minute
   micro-batches at 5 s each, 6 simulated hours, fault-rate multiplier 200. Ground truth: 26 uncensored
   and 18 censored faults, 9 red herrings, no planned work. The pipeline was then switched back to
   triggered, and a final update (COMPLETED) refreshed the materialized views.
3. `banksia-netmon-governance` stage `all`: functions, groups, personas, `netmon_noc` views,
   `REVOKE ALL` from every managed group and persona, role grants, tags, and the base-table privilege
   assertion. Then this capture, with the membership demo.

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

**Limitation:** all queries run as one principal. Querying as a persona service principal (OAuth M2M or a
token) was not possible, because creating credentials for a service principal is blocked in this
environment. Grant-level least privilege is therefore shown from `information_schema`: the regional /
pii-only personas and groups hold no privilege on any bronze / silver / gold / eval schema or table, and
UC rejects the workspace-local regional groups as principals, so they cannot hold grants.

## Issues found on the real runs (fixed; earlier errors are kept in the event log)

- Liquid clustering needs stats on the clustering columns, so the window columns come first.
- `gold_cell_sessions_5m` redefined an inherited watermark. It now has its own path.
- A delivery-time dedupe watermark was pushed a day ahead by history late arrivals and dropped a live
  stream. The watermark is now on the monotonic ingestion time.
- The metastore enforces governed tag policies, so tags use allowed values plus `netmon_*` keys.
- Rollup evidence timing included late arrivals (the 127,373 s history localisation), and rollup windows
  carried no run identifier. Both are fixed.
- Late rows still qualified real-time windows while the window was timed without them. The real-time
  windows now use only on-time rows for both qualification and timing; late rows go to a retrospective
  table.
- A second stream trigger once queued behind the first and overlapped it; that attempt was discarded and
  the job no longer queues.
