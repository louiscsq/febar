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
 A: NOC summary (prompt noc_summary_v3)          B: SMS drafts (prompt sms_v1, customer view only)
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

- [`noc_summary_v3.md`](../src/netmon_pipeline/genai/prompts/noc_summary_v3.md) (frozen, used for the final dev and
  holdout runs and live): rules (context only; strings are data; root must be a suspect or `uncertain`; when to be
  uncertain; relationships and numbers only as the context states them; evidence paths; impact copied exactly), and
  a signature + runbook per fault pattern. Earlier versions are kept for history; every change came from **dev**:
  - [`v1`](../src/netmon_pipeline/genai/prompts/noc_summary_v1.md) → v2: with suspect #1 at 0.07 (threshold 0.32) and
    no alarm (a dev cluster with no fault behind it), v1 still named a suspect. v2 makes `uncertain` mandatory then,
    and allows a below-threshold suspect at medium confidence at most when an alarm corroborates it.
  - v2 → v3: the dev run's groundedness judge passed 81.5 %; the failures were relationship slips (an alarmed router
    called a cell's "parent") and derived numbers (an RRC z-score reported as "RRC success 0 %"). v3 adds explicit
    rules for both.
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

## Governance: AI Gateway, guardrails, tracing

**Where the gateway sits.** Every LLM call goes to the Databricks-hosted pay-per-token endpoint
`databricks-gpt-5-4-mini`, with AI Gateway configured on that endpoint from code (`genai/gateway.py`, applied by
`scripts/genai_configure_gateway.py`; the live config is dumped in `evidence/step4/01_gateway_config.md`). A
dedicated, bundle-managed endpoint was not possible here (see [Workspace limitations](#workspace-limitations)).
Calls use the caller's own Databricks identity (job identity, app service principal, or a signed-in user); no
token is stored anywhere.

| AI Gateway feature | setting | status |
|---|---|---|
| usage tracking | on | per-request tokens in `system.serving.endpoint_usage`; `client_request_id` = the assistant's `X-Request-Id` |
| rate limits | 600 calls / min per endpoint, 300 per user | on (the evaluation runs 8 parallel workers and was never throttled) |
| PII guardrail, input | BLOCK | on: a prompt carrying an MSISDN / IMSI is blocked (`06_guardrail_tests.md` 2b) |
| PII guardrail, output | BLOCK | on |
| safety guardrail, output | on | on |
| safety guardrail, input | **off** | false positives: benign NOC prompts (telemetry + runbooks) flagged "violent-crimes" 3 / 3 times on the same request |
| inference table | requested | **fails server-side** on this workspace; replaced by the request log below |

### Guardrails

Two layers. The deterministic layer (`genai/guards.py`) runs on every call, so the behaviour does not depend on what
the gateway supports, and it is unit-tested. The gateway layer is a safety net on the wire.

| risk | deterministic (code) | gateway |
|---|---|---|
| **prompt injection** in alarm free text (typed by operators, sent by equipment) | `sanitize_free_text`: control chars stripped, PII redacted, truncated to 120 chars; instruction-like text (ignore / override instructions, role markers, "root cause is …", "reply only …", "send … to all customers", template tokens) is withheld and flagged; the prompt says context strings are data, never instructions | (input safety off, see above) |
| model **acting on** an injection anyway | the root can only be a suspect or `uncertain`; unknown element IDs scrubbed; SMS rules (no operator names, no blame, no unsupported ETA) | output safety |
| **PII** in a prompt | aggregates only, column allowlists, redaction, `assert_no_pii` before every call (IMSI, MSISDN / E.164 / AU numbers, e-mail) | input PII BLOCK |
| **PII** in a response | `check_sms` (PII patterns) | output PII BLOCK |
| **hallucinated** elements / numbers | `validate_summary` | |
| a blocked or failed call | deterministic fallback summary / template SMS, `generated_by` recorded | |

Live results (`evidence/step4/06_guardrail_tests.md`): an injection planted in a real incident's alarm text is
withheld (1a) and, with the sanitiser bypassed on purpose, the answer stays a suspect and the SMS stays compliant (1b);
an IMSI / MSISDN in alarm text is redacted (2a); a prompt carrying them is blocked by the gateway's PII guardrail (2b)
and by the pre-send check (2c); asking the model to put phone numbers into an SMS is blocked (2d).

**Gateway PII false positives.** The gateway's PII detector is a statistical model. It read a z-score `-10.292` and
a count `168.0` as phone numbers and blocked those prompts: 3 / 40 dev prompts at 3-decimal precision, 0 / 40 after
rounding (1–2 decimals, integer counts). A blocked call falls back to the ranker's view; the evaluation reports the
fallback rate.

### Request / response logging (in place of the inference table)

`llm.RequestLog` appends one row per call to `netmon_genai.noc_assistant_request_log`: request ID (also sent as
`X-Request-Id`, so it joins the gateway's usage rows), time, endpoint, purpose, prompt version, incident reference,
status (`ok` / `blocked` / `error` / `invalid_json`), error (the gateway's guardrail verdict when blocked), latency,
attempts, tokens, the request JSON's SHA-256, the full request and the raw response. Sample rows:
`evidence/step4/02_inference_log.md`.

### MLflow Tracing

`assistant.run` (span `AGENT` "noc_assistant") → `summarise` and `draft_sms` (`CHAIN`) → `llm.chat_json` (`LLM`,
with endpoint, status, tokens and prompt version as attributes). The jobs set the experiment
`/Shared/banksia_netmon/noc_assistant`, so every live summary and every evaluation case is a trace there; the
evaluation runs link their traces to the assessments.

## Evaluation

**Set** (`notebooks/08_genai_build_evalset.py`): one case per scored step-3 incident that had a case output at the SLA
moment, i.e. the same case and decision time step 3 judged its top-1 on (`rca_eval_{split}_ranking`), with the frozen
champion v4's GT-free scores. **Dev** = `history_1m` 2026-10-14 … 10-15: 346 of 355 scored incidents. **Holdout** =
step 3's fresh `holdout_1m` (2026-10-17 … 10-18): 323 of 337. The context table (`netmon_genai.genai_eval_contexts`)
holds no ground truth; the labels (`netmon_eval.genai_eval_labels`) are joined only by the scorers.

**Protocol.** Prompt iteration on dev only: a 40-case random sample, then the 12 dev cases where the ranker's top-1 is
wrong (to see whether the LLM fixes or breaks them), then two hand-built dev situations below the alert threshold
(`03b_early_and_ambiguous_examples.md`), which led to prompt v2, then a full dev run with the judges, whose
groundedness failures led to v3. The final dev run and then the holdout run used the
frozen prompts (`noc_summary_v3`, `sms_v1`). The holdout was run **once**; the job refuses to re-run it without
`force=true`.

**Scorers** (`genai/scorers.py`). Ground truth reaches them as `expectations`; `predict_fn` sees `inputs.context` only.

| measure | how | type |
|---|---|---|
| root-cause agreement | assistant's root ∈ valid root list (any listed element counts); `uncertain` = miss | code |
| vs the ranker's top-1 alone | ranker's suspect #1 ∈ valid roots on the same contexts; per case: same / changed to correct / changed correct to wrong / uncertain on correct / … | code |
| selective accuracy | agreement on the cases the assistant answered | code |
| hallucinated root / element | raw output (before repair) named a root that is not a suspect / any element ID not in the context | code |
| evidence validity | share of cited context paths that exist | code |
| fault-hypothesis match | hypothesis maps to the true fault type | code |
| SMS compliance | final drafts compliant; the LLM's own drafts compliant at the first try / after the repair round | code |
| groundedness | every claim in the summary, evidence and impact sentence supported by the context; next steps only refer to context elements | LLM judge (`make_judge`, Claude Sonnet 5.5) |
| SMS guidelines | plain, calm, apologetic, blame-free, jargon-free, no unsupported ETA | LLM judge (`Guidelines`, Claude Sonnet 5.5) |
| latency | per incident: summary + SMS call(s), p50 / p95 | code |
| tokens / cost | per incident, from the responses; DBUs from billing | code |

## Results

Every number below is from `evidence/step4/04_evaluation.md` (final runs: prompts `noc_summary_v3`, `sms_v1`).

| measure | **dev** (n = 346) | **holdout** (n = 323, run once) |
|---|---|---|
| **assistant root-cause agreement** (valid root list; `uncertain` = miss) | **97.1 %** | **82.0 %** |
| ranker's top-1 alone, same contexts | 96.5 % | 97.2 % |
| answered (not `uncertain`) | 99.7 % | 89.5 % |
| selective accuracy (answered cases) | 97.4 % | 91.7 % |
| ranker misses fixed by the assistant | 3 | 2 |
| correct ranker answers turned wrong / turned `uncertain` | 0 / 1 | **18 / 33** |
| fault-hypothesis match | 96.5 % | 69.0 % |
| hallucinated root (raw output, before the guard) | 0.0 % | 1.9 % |
| any unknown element ID in the raw output (scrubbed by the guard) | 2.6 % | 3.1 % |
| cited evidence paths that exist | 99.4 % | 99.5 % |
| fallback (gateway block / failure) | 0.3 % | 1.9 % |
| groundedness (LLM judge) | 81.8 % | 78.6 % |
| SMS: final drafts compliant | 100 % | 100 % |
| SMS: LLM drafts compliant at the first try / after one repair | 98.3 % / 99.7 % | 98.5 % / 99.4 % |
| SMS guidelines (LLM judge) | 99.7 % | 98.8 % |
| latency per incident p50 / p95 | 6.4 s / 8.0 s | 6.6 s / 7.9 s |
| tokens per incident (prompt / completion) | 4,896 / 772 | 4,705 / 791 |
| over **all** scored incidents (no case output = miss): assistant / ranker | 94.6 % / 94.1 % (n = 355) | 78.6 % / 93.2 % (n = 337) |

**Does the LLM add or lose accuracy? Honestly: on dev it adds a little, on the holdout it loses a lot.**

- *Dev*: it follows the ranker on 336 of 346 cases, fixes 3 of the 12 ranker misses (twice a router chosen over a
  sibling, once a sibling cell), never turns a right answer wrong, and goes `uncertain` once.
- *Holdout*: it turns 18 correct ranker answers wrong (mostly cell outages blamed on the backhaul link above them)
  and abstains on 33 more. **Cause, found after the run** (`evidence/step4/09_holdout_alarm_gap.md`; nothing re-run
  or tuned on the holdout): an upstream defect drops about 20 % of the holdout's alarms. The generator reuses
  incident-based alarm IDs across batch runs (`INC-00001` … in every run), so silver's cross-run dedupe treats the
  holdout's fault alarms as redeliveries of `history_1m`'s. Only 36 % of holdout cell-outage contexts still carry an
  active alarm (dev: 100 %), while seed-scoped noise alarms on neighbouring links survive. The ranker, which reads
  KPIs as well as alarms, still scores 97 %; the assistant, prompted to look for alarms that corroborate the impact
  pattern, either abstains or follows the surviving noise alarm. Even holdout contexts that do have an active alarm
  show the gap (83.6 % vs 95.6 %), because the alarms that remain are often not the root's own.
- *Lesson*: the LLM is not robust to gaps in the alarm feed, and real OSS alarm feeds do drop and lag. The ranker
  stays the system of record for "which element"; the assistant's value is the explanation, the runbook steps, the
  impact sentence and the customer draft, and its root-cause choice is shown **next to** the ranker's, never instead
  of it. A tempting fix (only let the assistant override the ranker below the alert threshold) was designed after
  seeing the holdout, so it is recorded as a next step to validate on a fresh run, not shipped here.
- *Grounding*: no hallucinated root on dev; on the holdout 1.9 % of raw answers named a non-suspect, and the guard
  turned those into `uncertain`. 2.6–3.1 % mentioned an element not in the context (e.g. a UPF named by convention);
  all were scrubbed. The groundedness judge failed about one answer in five, nearly always for one small slip in an
  otherwise supported answer: an RRC z-score reported as "RRC success 0 %", an alarm's severity misread, or an
  alarmed router called a cell's "parent". Prompt v3 targeted these; dev groundedness moved only 81.5 → 81.8 %.
- *SMS*: every final draft is compliant by construction; the model's own drafts pass the deterministic rules 98–99 %
  of the time at the first try, and the judge finds them plain, calm and blame-free in 99 % of cases.

Live: the 17 open incidents of step 3's live run all have a v3 summary and an SMS draft in UC and in Lakebase
(`05_outputs_and_lakebase.md`). The trigger was exercised: a `banksia-rca-score-live` MERGE fired
`banksia-genai-assistant`, which found all 17 unchanged and made **no** LLM call (0.3 min of notebook time, 1.0 min job run; `08_jobs_and_runs.md`).

## Latency and cost

| | p50 | p95 | tokens in / out |
|---|---|---|---|
| NOC summary call | 5.2 s | 6.5 s | 4,218 / 723 |
| SMS call | 1.2 s | 1.7 s | 581 / 49 |
| per incident (summary + SMS, repairs included; 2.02 calls on average) | 6.4–6.6 s | 7.9–8.0 s | ~4.8 k / ~0.8 k |
| Lakebase read of the latest summary (PK) | 2.8 ms | 6.0 ms | |
| Lakebase open incidents of a region + their summaries | 3.3 ms | 11.0 ms | |

(`07_latency_cost.md`, `05_outputs_and_lakebase.md`. Client-side times, job → endpoint; the app reads Lakebase, so the
LLM latency is off its path.)

**Cost.** About **4.8 k input + 0.8 k output tokens per incident** on GPT-5.4 mini (pay-per-token). At the
build's live rate (a few hundred incidents a day) that is roughly 1–2 M input and 0.2–0.3 M output tokens a day,
and the change detection keeps it at one summary per incident and suspect set, not per scoring run. The whole
step-4 build used 3,543 gateway-tracked requests, 8.4 M input and 1.25 M output tokens (`system.serving.endpoint_usage`,
this workspace and endpoint), most of it the evaluation runs and their judges. **The billing rows for these
tokens had not posted** when the evidence was captured (`system.billing.usage` lags); `07_latency_cost.md` holds
the query that turns them into DBUs and dollars (list price $0.07 / DBU for the `*_MODEL_SERVING` pay-per-token
SKUs). No per-token price is assumed here. The judges (Claude Sonnet 5.5) are evaluation-only cost.

## Outputs, serving to the app, trigger

| table (`telco_netmon_febar_catalog.netmon_genai`) | write | content |
|---|---|---|
| `incident_ai_summaries` | append | every NOC summary: incident, `generated_at`, `status = 'draft'`, endpoint, prompt / context / ranker versions, the structured output, guard report, latency, tokens, and the context it was grounded on |
| `customer_notice_drafts` | append | one SMS draft per incident × region: text, rule check, `status = 'draft'`, `requires_human_approval = true`, `approved_by` / `approved_at` / `sent_at` NULL (never sent) |
| `incident_ai_latest` | MERGE, Change Data Feed | latest summary + SMS draft per **open** incident (closed ones deleted) |
| `lb_incident_ai_latest` | synced table (TRIGGERED) | `incident_ai_latest` in Lakebase: database `netmon_serving`, schema `netmon_genai` |
| `noc_assistant_request_log` | append | every LLM request / response |
| `genai_eval_contexts`, `genai_eval_results_{dev,holdout}`, `genai_eval_summary_{dev,holdout}` | overwrite | evaluation |

**For the step-5 app.**
- *Fast path*: read Lakebase with psycopg and an OAuth database credential, next to step 3's tables:
  `SELECT … FROM netmon_rca.lb_open_incidents i LEFT JOIN netmon_genai.lb_incident_ai_latest a USING (incident_id)
  WHERE i.region_code = %s` (`notebooks/11_genai_lakebase_check.py` runs exactly this; p50 / p95 in `05_outputs_and_lakebase.md`).
- *On demand* ("refresh this summary"): `netmon_pipeline.genai.service.summarise_open_incident(incident_id, ws,
  warehouse_id)` builds the context through a SQL warehouse and calls the governed endpoint as the app's identity;
  it returns the summary, SMS drafts, guard report and context and writes nothing.

**Trigger: why a table-update trigger.** `banksia-genai-assistant` runs when `netmon_rca.open_incidents` changes (each
scoring run's MERGE; at most once a minute), and only calls the LLM for incidents that are new or whose suspects /
ranker version changed (`store.suspects_signature`); unchanged incidents are copied over at no cost.

| option | cost | latency to a summary | why not |
|---|---|---|---|
| **table-update trigger + change detection (chosen)** | a serverless job start per scoring run (seconds of compute when nothing changed) + ~2 LLM calls per new incident | one job start after detection (~1–4 min) | |
| a task inside `banksia-rca-score-live` | same LLM cost | lowest | couples the ranker's publish to the LLM: a gateway block or rate limit would fail the scoring run |
| fixed schedule (e.g. every 5 min) | idle job starts even when nothing changed | up to the schedule period | pays when idle |
| only on demand from the app | LLM cost only when a user asks | 6–8 s at click time | no summary waiting in Lakebase, no audit trail of what the NOC was shown |
| summarise every open incident every run | ~2 LLM calls × open incidents × runs | lowest | pays again for unchanged incidents (17 open incidents × 60 runs/h ≈ 2,000 calls/h) |

## Deploy and run

```bash
databricks bundle validate -t dev -p febar && databricks bundle deploy -t dev -p febar
python scripts/genai_configure_gateway.py --profile febar --no-inference-table   # AI Gateway on the endpoint
databricks bundle run -p febar genai_build_evalset                              # contexts + labels (dev, holdout)
python scripts/genai_eval_local.py --profile febar --warehouse <id> --limit 40  # dev iteration only
databricks bundle run -p febar genai_evaluate --params split=dev               # final dev run
databricks bundle run -p febar genai_evaluate --params split=holdout           # once
databricks bundle run -p febar genai_assistant                                 # also fires on open_incidents updates
databricks bundle run -p febar genai_lakebase_check                            # psycopg read-back + latency
python scripts/genai_guardrail_tests.py --profile febar --warehouse <id>       # live guardrail tests
python scripts/genai_early_example.py --profile febar --warehouse <id>         # below-threshold examples (dev)
python scripts/capture_evidence_step4.py --profile febar --warehouse <id>      # evidence/step4
```

The first `genai_assistant` run creates `incident_ai_latest`; the synced table (`resources/genai.synced_tables.yml`)
needs it to exist, so on a fresh workspace deploy once more after that run.

## Known limits

- **The assistant loses accuracy when alarms are missing** (holdout: 82.0 % vs the ranker's 97.2 %). The ranker
  stays the system of record; show the assistant's choice next to the ranker's suspects, never instead of them.
- **Upstream alarm-ID collision (step 1/2 follow-up).** Incident alarm IDs are not unique across batch runs
  (`opaque_id("ALM", incident_id, n)` with `INC-00001`…), so silver's dedupe drops 20 % of the holdout's alarms
  (`09_holdout_alarm_gap.md`). Fix: include the run / seed in the ID, then regenerate and re-ingest the holdout and
  re-run step 3's frozen-model holdout evaluation. Not done here because it changes step 3's published holdout result.
- **Same synthetic generator.** The runbooks and signatures in the prompt describe this generator's fault types. A real
  NOC would replace them with its own runbooks (ideally retrieved, not inlined) and evaluate on its own incidents.
- **Matched case.** Like step 3, the evaluation grades the case ground truth matched by footprint overlap at the SLA
  moment; incidents without a case output (dev 9, holdout 14) are not in the LLM evaluation and count as misses in the
  "all scored incidents" rows.
- **Subscriber counts are estimates**: peak connected users per impacted cell over the last hour, not unique
  subscribers; the sampled xDR failures are a 1 % sample.
- **Gateway PII detector**: statistical, so a residual rate of false-positive blocks on numeric telemetry remains;
  the fallback gives the ranker's view, but no LLM summary, for those incidents.
- **Judges are LLMs too**: groundedness and SMS-guideline verdicts come from Claude Sonnet 5.5 and were not
  hand-audited beyond the worked examples.
- **Live run.** The open incidents are step 3's static `stream` run (2026-10-08); no new live stream was started, so
  the table-update trigger was exercised by manual runs rather than by a continuous scorer.

## Workspace limitations

- **No dedicated governed endpoint.** The pay-per-token Claude / GPT / Gemini models are not eligible for provisioned
  throughput on this workspace (`get-model-optimization-info`: `optimizable: false`), and an external-model endpoint
  pointing back at them needs a stored API token. So AI Gateway is configured on the shared pay-per-token endpoint
  `databricks-gpt-5-4-mini` itself (this FEVM workspace serves only this project). Its config is code
  (`genai/gateway.py`), not a bundle resource, because bundles cannot manage system endpoints.
- **Inference tables fail to enable.** `PUT /api/2.0/serving-endpoints/databricks-gpt-5-4-mini/ai-gateway` with
  `inference_table_config` returns `500 INTERNAL_ERROR java.nio.channels.ClosedChannelException` (request
  `1e3b343b-f98f-4784-a001-b5a9e67826a0`), on `netmon_genai` and on `netmon_rca`, after creating an empty
  `<prefix>_payload` table (dropped again). Replaced by `noc_assistant_request_log` (same content) plus the gateway's
  usage tracking.
- **Input safety guardrail unusable** for this content (false positives above); prompt injection is handled in code.
- **No `CREATE CATALOG`** (as in step 3): the synced table is registered in the project catalog
  (`netmon_genai.lb_incident_ai_latest`).
- **System tables are account-wide** on this workspace: the evidence filters every system-table query to this
  workspace's ID and the assistant endpoint.
