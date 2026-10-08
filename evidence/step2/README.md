# Step 2 evidence: pipeline and governance run on the workspace

All files are text, captured on 2026-10-08 (UTC) from workspace profile `febar` by
`scripts/capture_evidence.py` (SQL on the serverless starter warehouse, plus the Databricks CLI).
Samples are small, and IMSI / MSISDN only ever appear masked.

| file | content |
|---|---|
| [`01_pipeline_status.md`](01_pipeline_status.md) | pipeline spec (serverless, continuous during the live run), every update and its final state, flows of the last completed update, errors from the deploy-and-fix iterations |
| [`02_expectations.md`](02_expectations.md) | expectation pass/fail counts per dataset and rule from the event log, dropped rows, quarantine by rule, quarantine sample, injected-defect reconciliation (`eval_dq_capture`) |
| [`03_row_counts.md`](03_row_counts.md) | row counts for every table, bronze and silver per generator run |
| [`04_gold_samples.md`](04_gold_samples.md) | sample rows of every gold table, live pipeline latency |
| [`05_time_to_detect.md`](05_time_to_detect.md) | time-to-detect against ground truth (median / p90 / % within 5 min), per incident, detection precision, RCA heuristic baseline |
| [`06_governance.md`](06_governance.md) | column masks, row filters, policy functions, grants, tags, comments, groups and personas, plus the mask and row-filter demo |
| [`07_lineage.md`](07_lineage.md) | `system.access.table_lineage` edges, and the Volume → bronze hop via `_metadata.file_path` |

## What was run

1. `databricks bundle deploy` created 6 schemas, the landing Volume, the pipeline and 4 jobs.
2. `banksia-netmon-generate-history`: `small` preset (4 regions, 300 sites, 1,431 cells), 14 days of
   15-minute KPIs as JSON lines with default DQ defects, about 4 minutes on serverless.
3. `banksia-netmon-governance` stage `functions`, then `banksia-netmon-pipeline` (triggered, full refresh):
   backfill COMPLETED in about 5 minutes.
4. Live: pipeline redeployed **continuous**, then `banksia-netmon-stream-generator` ran for **41 minutes**
   (12:38–13:19 UTC, 240 micro-batches). That is one simulated minute every 10 s, 4 simulated hours in
   total, with fault-rate multiplier 100. The pipeline processed it as it landed. It was then switched
   back to triggered and a final update (COMPLETED) refreshed the materialized views.
5. `banksia-netmon-governance` stage `policies`: groups, personas, grants, tags. Then evidence capture,
   with the mask and row-filter demo.

`banksia-netmon-bootstrap` chains steps 2–5 as one job. It was deployed and validated, but the steps
above were run individually.

## Headline results

| | history (15-min ROP backfill) | live stream (1-min) |
|---|---|---|
| scored incidents (customer-impacting, not censored) | 19 | 16 (13 more were censored at the bounded stop and excluded) |
| detected | 18 (94.7 %) | 16 (100 %) |
| median / p90 time-to-detect | 59 s / 1,201 s | **120 s / 365 s** |
| **detected within 5 minutes** | 73.7 % | **87.5 %** (faults only: 71.4 %, 5 of 7; planned: 9 of 9) |
| median pipeline latency (file landed → detection row) | n/a (backfill) | 36 s |
| detections explained by ground truth | KPI 87.7 %, alarm 100 % | KPI 100 %, alarm 100 % |

The two live misses are both `BACKHAUL_DEGRADATION`, which ramps in over 10–30 minutes by design and
was detected after 9 and 14 minutes. Every injected DQ defect of every type, in both runs, was handled by
its intended mechanism (`handled_pct = 100` in `eval_dq_capture`; session dedupe is not re-scored).
Governance demo: as a non-`pii_privileged` reader, 0 of 1.3 M IMSI / MSISDN values are visible in full;
with the same user added to `pii_privileged` all of them are (checked by pattern, values not printed).
Membership of `noc_region_nsw` only shows NSW rows in `silver_sessions` and `gold_impact_detections`, and
membership of no NOC group shows none.

## Issues found on the real run (fixed and kept in the event log)

- Liquid clustering needs stats on the clustering columns, so the health tables now put `window_start`
  in the leading 32 columns.
- `gold_cell_sessions_5m` tried to redefine the watermark inherited from the silver dedupe. It now has
  its own path.
- The first two live attempts dropped the whole live stream: history late arrivals are "delivered" up to
  36 h after the history window, in the future relative to the stream, which pushed the delivery-time
  dedupe watermark a day ahead. The watermark is now capped at the file's landing time. Both partial
  live runs were discarded and the run above was started clean.
- The metastore enforces governed tag policies, so the tags now use allowed values plus `netmon_*` keys.
