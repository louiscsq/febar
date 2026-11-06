# Genie space for the NOC

Step 5 of the Banksia Mobile NOC build. A Genie space lets the NOC team, its Head of Network Operations and the
customer-experience side ask about live incidents, element health, customer impact and detection KPIs in plain
English. It is defined in code, deployed by the bundle, governed by Unity Catalog per asking user, benchmarked, and
called from the topology app. Evidence: [`evidence/step5/`](../evidence/step5/) (`01_genie_space.md`,
`02_genie_benchmark.md`).

## Definition as code

| file | role |
|---|---|
| `src/netmon_pipeline/genie_space.py` | the space: tables, column descriptions, entity-matching columns, general instructions, join hints, SQL snippets (measures, filters, expressions), 8 trusted example SQLs, 10 sample questions, 18 benchmark questions |
| `scripts/genie_build_space.py` | writes it to `resources/genie/noc_space.geniespace.json` (`--check` fails if stale) |
| `resources/genie.yml` | bundle `genie_spaces.noc_genie` resource: title, description, warehouse, `file_path`, permissions (CAN_RUN for the NOC groups) |
| `scripts/genie_benchmark.py` | runs the space's benchmark through the Genie eval-run API and writes `evidence/step5/02_genie_benchmark.md` |
| `tests/test_genie_space.py` | the committed file matches the module; contracted content (8+ samples, 10+ benchmarks, NOC vocabulary); deterministic sorted ids; only governed tables; every SQL references only space tables |

IDs in the serialized space are an MD5 of their content, so the generated file only changes when the content does
and a redeploy is a no-op otherwise.

## Tables, and why these

| table | why |
|---|---|
| `netmon_noc.open_incidents` | "what is broken and where": the ranker's alert per case with the top-3 suspects and scores |
| `netmon_noc.element_status` | health of every element along core > router > backhaul > site > cell; "which sites are down" |
| `netmon_noc.incident_ai_summary` | the assistant's root cause, next steps and estimated affected subscribers (aggregate) |
| `netmon_noc.customer_sms_drafts` | draft history (status always `draft`; decisions are recorded by the app in Lakebase) |
| `netmon_noc.incident_detection_times` | operational time to detect per incident (MTTD, share within 5 minutes) without ground truth |
| `netmon_noc.gold_impact_detections` | the per-record detections behind the KPIs |
| `netmon_noc.silver_topology_nodes` | names, hierarchy, coordinates, technology, urbanity |
| `netmon_noc.gold_cell_health_5m` | cell KPI health (availability, latency, loss, throughput, z-scores) |
| `netmon_noc.silver_alarms` | alarm codes and severities on an element |
| `netmon_eval.eval_ttd_summary` | **evaluation scorecard** (ground-truth scored detection SLA per run / fault type), labelled as such in its description and the instructions; national role only |

Left out on purpose: `silver_sessions` and every bronze table (subscriber identifiers), the eval schema's per-incident
ground truth (`eval_gt_incidents`, `eval_incident_detection`, labels), and the RCA feature / training tables (too wide
for NOC questions, and the labels live next to them).

**Governance.** Every operational table is a `netmon_noc` view that applies `netmon_gov.region_filter(region_code)`
(`governance/sql/02_noc_views.sql`, `05_serving_views.sql`). Genie runs the SQL it generates as the asking user, so a
`noc_region_nsw` member only ever gets NSW rows and anyone without a NOC role gets none; the regional role has no grant
on `netmon_eval`, so the scorecard only answers for the national role. No table in the space carries IMSI / MSISDN,
and the instructions tell Genie to refuse identifier requests (`07_auth_governance.md` shows the refusal).

## Instructions (summary)

The full text is in `genie_space.INSTRUCTIONS` and in `01_genie_space.md`. It defines the hierarchy and NOC
vocabulary (AMF / MME, UPF, aggregation router, backhaul, cell site, cell), the region codes, "suspect 1 = failing
element", that "now" means the latest scoring time of the replayed feed (not `current_timestamp()`), local-time
conversion, the KPI definitions (time to detect, MTTD, within-5-minutes, the scored scorecard), that **MTTR cannot be
computed** (only open incidents exist), that subscriber impact is an aggregate estimate, that drafts are never sent,
and that "waiting for approval" means the current draft per open incident.

## Benchmark

18 questions with expected SQL (`genie_space.BENCHMARKS`), graded by Genie's own eval-run against the expected
result. Two runs are committed:

| run | GOOD | needs review | bad | notes |
|---|---|---|---|---|
| 1 (`02a_genie_benchmark_run1.md`) | 17 / 18 | 0 | 1 | "How many SMS drafts are waiting for approval?" counted all 68 historical drafts (`customer_sms_drafts`) instead of the 17 current ones: a real ambiguity, fixed by an instruction line |
| 2, final (`02_genie_benchmark.md`) | 16 / 18 | 1 | 1 | the SMS question now passes; two answers the grader marks down are right on inspection: an unrounded average (165.83 vs 165.8, `NEEDS_REVIEW`) and the element types under a router without the count column (`BAD`) |

So 16 / 18 (89 %) by Genie's strict grader on the final run, 18 / 18 answer-correct on manual review of that run. Genie
is not deterministic: the two marked-down questions passed in run 1. Four benchmark questions are close paraphrases of
a trusted example SQL; the other 14 are not.

## Known limits

- **MTTR is not available**: the data holds only currently open incidents. Genie says so.
- **Operational TTD is a lower bound for slow faults.** It starts at the first anomaly visible in the telemetry; a
  backhaul link that ramps up slowly hurts customers before any KPI rule fires (BH-VIC-0005: 204 s operational, 511 s
  against ground truth; `03b_trace_slow_backhaul.md`). The scorecard (`eval_ttd_summary`) is the official SLA figure.
- **SMS decisions live in Lakebase only.** No Lakebase database catalog can be registered here (no `CREATE CATALOG`),
  so Genie cannot see the app's approve / reject decisions; it reports the draft status from Unity Catalog.
- **Replayed data**: the live feed ended on 2026-10-09 00:56 UTC; "now" is that time.
