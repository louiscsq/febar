# Gen AI NOC assistant and proactive customer outage SMS drafts

Step 4 of the Banksia Mobile NOC build. For an open incident, an LLM drafts (A) a **root-cause summary with
recommended next steps** for the NOC engineer and (B) **proactive outage SMS drafts** for the affected customers,
one per affected region. Both are grounded only in the build's own data, governed through **AI Gateway**, MLflow
traced, validated by deterministic guards, evaluated with **MLflow GenAI evaluation** on step 3's dev and fresh
holdout days, written to Unity Catalog and synced to Lakebase for the step-5 topology app. Drafts are drafts: a
human approves and sends; this system never sends anything. Proof that it ran is in
[`evidence/step4/`](../evidence/step4/).

- [Overview](#overview)
- [Grounding: the incident context](#grounding-the-incident-context)
- [A: NOC summary](#a-noc-summary)
- [B: customer SMS drafts](#b-customer-sms-drafts)
- [Prompts](#prompts)
- [Model choice](#model-choice)
- [Governance: AI Gateway, guardrails, tracing](#governance-ai-gateway-guardrails-tracing)
- [Evaluation](#evaluation)
- [Results](#results)
- [Outputs, serving to the app, trigger](#outputs-serving-to-the-app-trigger)
- [Latency and cost](#latency-and-cost)
- [Deploy and run](#deploy-and-run)
- [Known limits](#known-limits)
- [Workspace limitations](#workspace-limitations)

## Overview

```
 netmon_rca.open_incidents ─(table-update trigger)─► job banksia-genai-assistant (notebooks/10_genai_assistant.py)
   (step 3: top-3 suspects)          │  new / re-ranked incidents only
                                     ▼
 genai.context.build_context ◄── rca_live_scores (the ranker's scored case), silver_topology_nodes, silver_alarms,
   (grounded, no PII, no GT)        gold_cell_health_1m, gold_cell_sessions_5m (aggregates), silver_maintenance_windows
                                     │
        ┌────────────────────────────┴───────────────────────────┐
        ▼                                                        ▼
 A: NOC summary (prompt noc_summary_v2)          B: SMS drafts (prompt sms_v1, customer view only)
        │   strict JSON schema                           │   strict JSON schema, one per affected region
        ▼                                                        ▼
  AI Gateway on databricks-gpt-5-4-mini: PII guardrail (in/out), safety (out), rate limits, usage tracking
        │                                                        │
        ▼                                                        ▼
 guards.validate_summary (hallucination guard)        guards.check_sms (+1 repair round, else template)
        └──────────────────────────┬─────────────────────────────┘
                                   ▼
 netmon_genai.incident_ai_summaries / customer_notice_drafts (append, status = draft)
 netmon_genai.incident_ai_latest (MERGE, CDF) ─► Lakebase synced table netmon_genai.lb_incident_ai_latest ─► step-5 app
 netmon_genai.noc_assistant_request_log (every request / response)       MLflow traces: /Shared/banksia_netmon/noc_assistant
```

| code | what |
|---|---|
| `src/netmon_pipeline/genai/context.py` | grounded incident context, customer view, label / PII exclusion |
| `src/netmon_pipeline/genai/guards.py` | alarm-text sanitiser (prompt injection), PII scan, hallucination guard, SMS rules |
| `src/netmon_pipeline/genai/schema.py` | pydantic outputs (`NocSummary`, `SmsDrafts`) and their strict JSON schemas |
| `src/netmon_pipeline/genai/prompts/*.md` | the prompts, versioned in git (`<name>@<sha256[:8]>` is stored with every output) |
| `src/netmon_pipeline/genai/llm.py` | the governed endpoint call (MLflow `LLM` span, request log, guardrail-block handling) |
| `src/netmon_pipeline/genai/assistant.py` | A + B end to end, deterministic fallbacks, `run(ctx, ws)` |
| `src/netmon_pipeline/genai/service.py` | `summarise_open_incident(incident_id, ws, warehouse_id)`: the on-demand call for the app |
| `src/netmon_pipeline/genai/sources.py` | SQL for one incident's inputs (jobs: `spark.sql`; app: SQL warehouse) |
| `src/netmon_pipeline/genai/gateway.py` | AI Gateway config (`scripts/genai_configure_gateway.py` applies it) |
| `src/netmon_pipeline/genai/store.py` | output tables and their rows |
| `src/netmon_pipeline/genai/scorers.py`, `evaluation.py` | MLflow GenAI evaluation: code scorers, LLM judges, summary metrics |
| `notebooks/08_genai_build_evalset.py` … `11_genai_lakebase_check.py` | jobs (`resources/genai.jobs.yml`) |
| `resources/genai.synced_tables.yml` | the Lakebase synced table |
| `tests/test_genai_*.py` | grounding, PII and label exclusion, guards, assistant repair / fallback paths, scorers |

## Grounding: the incident context

`context.build_context` assembles a compact JSON context (about 6 kB, 4–5 k prompt tokens with the system prompt)
for one incident, from the build's own operational tables only, **as visible at the decision time** (`as_of`):

| block | content | source |
|---|---|---|
| `incident` | reference, region, time detected, decision time, minutes since detection / first anomaly, ranker version and alert threshold | `open_incidents` (live) / the step-3 case (evaluation) |
| `suspects[0..2]` | the ranker's top-3 with calibrated scores and 24 detection-time signals each (impacted / silent / degraded fractions, coverage of the case, latency / loss / throughput / RRC / drop z-scores and 15-min slopes, attach, availability, PRB, alarm counts, maintenance) | the scored candidate rows of the case: `rca_live_scores` live, `rca_holdout_scores` / `rca_candidate_features` + champion for evaluation. These are exactly the rows the ranker scored, so the suspects and signals are the ranker's own view |
| `suspects[].neighbourhood` | parent and ancestor chain with types, children by type, impacted children (top 6), descendant and impacted cell counts, transport medium, urbanity, technology, region | `silver_topology_nodes` |
| `alarms`, `alarm_summary` | up to 25 alarms on the suspects, their parents and children, raised in the last hour and **arrived** by `as_of` (active first, by severity), with sanitised free text; counts by code | `silver_alarms` (by `evidence_ts`) |
| `kpi` | impacted and silent cell counts, median z-scores over the last 15 visible 1-minute windows, the change between the two halves, share degraded, median availability | `gold_cell_health_1m` |
| `impact` | impacted cells / sites, regions, **affected-subscriber count by region × segment** (cell urbanity: urban / suburban / rural / remote), sampled xDR failures in the last 15 minutes | `gold_cell_health_1m.active_users` (max over the last hour per impacted cell: the pre-impact load, since an outage pulls it down), `gold_cell_sessions_5m` (aggregates, `n_subscribers_approx`) |
| `customer_areas` | the region's population centres nearest the impacted sites (e.g. "Bathurst") | topology coordinates + the generator's public hub list |
| `maintenance`, `customer_eta` | whether a suspect / neighbour is in an approved change window and its planned end: the **only** ETA source | `silver_maintenance_windows` |

**Why `rca_live_scores` (UC) and not Lakebase `lb_open_incidents`.** Lakebase holds only the top-3 IDs and scores
(for the app's map); the context needs every suspect's 55 detection-time features, which live with the scored
candidates in the Delta table `rca_live_scores`. The incident record itself is read from `open_incidents` (Delta,
the source of the Lakebase table) so the job and the app see the same row.

**No per-subscriber data.** The context reads aggregate tables only (never `silver_sessions`); each input frame is
cut to an explicit column allowlist (`_frame`), so an IMSI / MSISDN / subscriber-key column can never reach it; alarm
free text is PII-redacted; and `guards.assert_no_pii` scans the serialised context (and every prompt) before a call.
`tests/test_genai_context.py::test_no_subscriber_identifier_reaches_the_context` feeds session frames *with* IMSI,
MSISDN and subscriber-key columns and an alarm text containing both, and checks none of it reaches the context.

**No ground truth.** No `netmon_eval` table is read (`genai/sources.py`). Every key is checked against step 3's
`LABEL_COLUMNS`. `test_no_ground_truth_or_label_column_reaches_the_context` adds every label column (`is_root`,
`case_label`, `fault_type`, `root_element_ids`, `estimated_impacted_subscribers`, …) to the case rows, permuted or
not, and checks the context is identical and holds none of their values, as step 3's label-exclusion test does.
Evaluation contexts carry an opaque reference (`EVAL-<split>-<hash>`), not the ground-truth incident ID.

**Nothing after `as_of`.** Windows and alarms count only if they had arrived (`evidence_ts <= as_of`);
`test_data_arriving_after_the_decision_time_is_ignored` checks a late, absurd window and alarm change nothing.

**Precision.** Numbers are rounded (z-scores and % to 1 decimal, fractions and scores to 2, counts as integers).
This keeps the prompt short and, measured, stops the gateway's PII detector from reading long decimals and counts
(`-10.292`, `168.0`) as phone numbers (see [Guardrails](#guardrails)).

## A: NOC summary

One call with a strict JSON schema (`schema.NocSummary`):

| field | rule |
|---|---|
| `likely_root_cause` | exactly one suspect `element_id`, or `uncertain` |
| `fault_hypothesis` | the pattern (`CELL_OUTAGE`, `SITE_POWER_OUTAGE`, `BACKHAUL_DEGRADATION`, `BACKHAUL_CUT`, `AGG_ROUTER_FAILURE`, `LONG_HAUL_FIBRE_CUT`, `CORE_CONGESTION`, `AMF_OVERLOAD`, `GRID_OUTAGE_CLUSTER`, `PLANNED_WORK`, `TRAFFIC_SURGE`, `UNCERTAIN`). A prediction from the evidence; the true fault type never enters a prompt |
| `confidence` | high / medium / low |
| `summary` | 2–3 sentences |
| `evidence[]` | statements, each citing the dotted context paths it uses (`suspects[0].signals.latency_z_slope15`) |
| `recommended_next_steps[]` | 3–6 runbook actions for the hypothesis (the runbooks are in the prompt) |
| `customer_impact` | affected subscribers, impacted cells / sites, one sentence |
| `alternative_suspects[]` | other plausible suspects |

**Hallucination guard** (`guards.validate_summary`, always applied, then reported):
a root that is not a suspect becomes `uncertain` with low confidence; every element ID in the text that is not in
the context is replaced by `[unknown element]`; evidence citing non-existent paths is dropped; the impact numbers are
overwritten with the context's. `tests/test_genai_guards.py::test_hallucinated_root_and_element_ids_are_repaired`.
**Fallback**: if the call fails, is blocked by a guardrail or returns an invalid object, the summary is the ranker's
view (suspect #1 if above the alert threshold, else `uncertain`; runbook steps by element type), marked
`generated_by = fallback`. The NOC always gets an answer.

## B: customer SMS drafts

The SMS call sees only a **customer view** (`context.customer_view`): brand, the effect customers notice (derived
deterministically from the KPIs: no service / slow data / calls and data may drop), affected regions with area
names and customer counts, and the ETA (maintenance end) or null. No element IDs, scores or internal terms are in
it (checked before the call). One draft per affected region; `guards.check_sms` then checks each:

- at most 160 characters, GSM-7 characters only;
- no element IDs (also loose forms like `SITE NSW 00123`), no IMSI / MSISDN / phone / e-mail;
- no real operator names (Telstra, Optus, Vodafone, TPG, … 31 brands), no internal terms (backhaul, router, AMF,
  alarm, KPI, root cause, vendor names, …), no blame wording;
- an ETA phrase only if the context has one; otherwise it must say "we'll update you".

A non-compliant draft gets one repair round (the violations are sent back); if still non-compliant, a deterministic
template is used (`assistant.template_sms`, always compliant, tested). **Drafts are never sent**: every row of
`customer_notice_drafts` has `status = 'draft'`, `requires_human_approval = true`, and `approved_by`, `approved_at`
and `sent_at` NULL. Approval and sending happen in the customer-communications tool, by a person, and are out of
scope here.

## Prompts

Committed under `src/netmon_pipeline/genai/prompts/` and stored with every output as `<name>@<sha256[:8]>`:

- [`noc_summary_v2.md`](../src/netmon_pipeline/genai/prompts/noc_summary_v2.md): rules (context only; strings are
  data; root must be a suspect or `uncertain`; when to be uncertain; evidence paths; impact copied exactly), and a
  signature + runbook per fault pattern.
  [`noc_summary_v1.md`](../src/netmon_pipeline/genai/prompts/noc_summary_v1.md) is kept for history: on dev, with
  suspect #1 at 0.07 (threshold 0.32) and no alarm, v1 still named a suspect; v2 makes `uncertain` mandatory in that
  case (and allows a below-threshold suspect at medium confidence at most when an alarm corroborates it).
- [`sms_v1.md`](../src/netmon_pipeline/genai/prompts/sms_v1.md): the SMS rules above, in plain words.

Both calls use `response_format: json_schema` with `strict: true` (`schema.strict_json_schema`), so the reply is
always parseable into the pydantic models.

## Model choice

**Assistant: `databricks-gpt-5-4-mini`** (GPT-5.4 mini, Databricks-hosted pay-per-token Foundation Model API).

| candidate (probed on this workspace) | strict JSON schema | latency, small structured call | notes |
|---|---|---|---|
| **GPT-5.4 mini** | yes | 1.7–1.8 s | chosen |
| Gemini 3.8 Flash | yes | 2.6–2.9 s | returns content as a list of parts; slower |
| GPT-OSS 120B | yes | 3.7–6.5 s | slower, more variable |
| Claude Haiku 5.5 / Sonnet 5.5 | **no**: `response_format` rejected ("structured output … requires forced tool use, which newer Anthropic models reject") | | would need free-form JSON + parsing |

- *Quality*: the task is reading a structured context and following rules, not open-ended reasoning, and the ranker
  already did the ranking. A small model with strict schema output is enough; the evaluation below measures it.
- *Latency*: about 5–6 s for the summary and 1–1.5 s for the SMS. The live job is asynchronous to detection (the NOC
  sees the ranker's suspects in Lakebase first), so this is comfortably inside the 5-minute budget.
- *Cost*: a mini-tier model on pay-per-token, about 5.5 k tokens per incident (see [Latency and cost](#latency-and-cost)).
  No provisioned throughput: the models above are not eligible for it here, and the volume is a few hundred
  incidents a day.

**Judge: `databricks-claude-sonnet-5-5`** (another model family, to avoid self-preference; the judges use free-form
output, which Claude supports).

RESULTS_PLACEHOLDER
