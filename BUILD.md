# BUILD.md: decisions, trade-offs and iterations

## 1. Who this is for and why

The customer is the Network Operations Centre of a tier-1 Australian mobile operator. "Banksia Mobile" is fictional,
modelled on Telstra and Optus. I picked this because I've worked on several use cases in the telco industry, and
real-time network operations in the NOC is one of the highest-value ones. It's usually at the top of a telco's
priority list. It also needs intelligence built on high-volume, high-velocity data as the foundation, which is a
sweet spot for the Databricks platform.

The two Australian incidents that shaped the requirements:

- **Telstra, July 2026:** customers' web searches detected the outage after about 99 minutes. The earliest alarms
existed but weren't shown in 24x7 tooling.
- **Optus, September 2025:** the NOC had no alarms for failed 000 calls.

Both are failures of *detection and triage*, not of repair. So the build targets two NOC KPIs:

- **time to detect customer impact**, with a 5-minute target
- **time to identify the failing element**

## 2. Key decisions and trade-offs


| Decision                                                                                                                                                                   | Alternatives considered                          | Why I chose it                                                                                                                                                                       | What it costs                                                                                                          |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| **Synthetic network with fault propagation** (core → router → backhaul → site → cell), with red herrings (traffic surges, alarm storms, flapping) and data-quality defects | Public telco datasets                            | No public dataset has topology plus ground truth for root cause. Without propagation, a model just learns "the cell that looks worst", which is a symptom, not the cause.            | It's synthetic. The model's accuracy will be lower on real data, so the next step is a pilot on the customer's alarms. |
| **Australian geography and local time** (DST, Brisbane has no DST, Adelaide +9:30), plus bushfire, cyclone and long-haul fibre faults                                      | Generic UK/US network (the first version was UK) | Busy hours follow local time. A grader or the customer would spot an evening peak at 10 am. Australian fault types make the story credible to an Australian NOC.                     | More generator complexity, and seasonal fault rates need a minimum per type so short runs still contain every story.   |
| **Streaming Lakeflow pipeline with 1-minute and 5-minute windows**, compared against each cell's own baseline for that local hour                                          | Static thresholds; batch every 15 min            | A static threshold either floods the NOC at busy hour or misses quiet-hour faults. 15-minute batches make a 5-minute target impossible.                                              | Baselines need history; new cells have none at first.                                                                  |
| **Late data excluded from real-time detection** and kept in a separate "after the fact" table                                                                              | Use all data whenever it arrives                 | Reviewers found that letting late records count made time to detect look *faster* than the NOC could ever have achieved. Now late data can only make detection later, never earlier. | If all of a cell's data for a window is late, the cell counts as silent, which is what the NOC really saw.             |
| **ML ranker (gradient boosting) over 55 features available at decision time**, not an LLM, for root cause                                                                  | LLM picks the cause; rules only                  | Ranking is a structured problem with labelled history. It's fast, cheap, explainable and measurable. The LLM is used where language helps: summary and SMS.                          | Needs labelled incidents. In real life those come from closed tickets.                                                 |
| **LLM restricted to the ranker's top 3 suspects, or "uncertain"**                                                                                                          | Free-form LLM diagnosis                          | An LLM inventing an element in a live NOC is dangerous. A guard turns any invented element into "uncertain", never into a guess.                                                     | The assistant can't outperform the ranker on cause. It scores 97.5% vs 98.8%; its value is speed of understanding.     |
| **SMS drafts need a person's approval, with no send path** (enforced by a database constraint)                                                                             | Auto-send                                        | Regulator-facing customer comms; a wrong message is worse than a slow one. It's better to have a person in the loop to review each message before it's sent.                         | A person stays in the loop.                                                                                            |
| **Governance:** IMSI/MSISDN masks, regional row filters, and a privileged group that can only unmask                                                                       | View-level security only                         | Regional NOC teams are a real org pattern. Subscriber identifiers are personal information under Australian privacy law.                                                             | The workspace couldn't apply groups the usual way, so service accounts stand in for groups. This is documented.        |
| **Lakebase for the app's operational reads**                                                                                                                               | Querying the SQL warehouse directly              | The app needs millisecond reads: about 12–36 ms p50 inside the app, against seconds from a warehouse. SMS approvals need transactional writes.                                       | A sync to maintain; data can lag Delta by a short interval.                                                            |
| **Genie on masked, region-filtered views only**                                                                                                                            | Genie on the raw gold tables                     | Genie runs as the user, so the same masks and filters apply. It never sees the evaluation (ground-truth) tables.                                                                     | Some questions need curated example SQL. Genie still varies run to run (16–18 of 18).                                  |


## 3. How I measured, and why the numbers are honest

- **Ground truth is used only for scoring, never for detection.** A test proves that shuffling the label columns
changes nothing.
- **The ML ranker was frozen, then scored once** on fresh test days that weren't used for any design choice. It's
compared with the rules baseline *on the same cases*: 94.7% vs 78.3% top-1. That's the fair comparison, not "vs 23%".
- **False alarms are reported per alert, not per record.** About 4 in 10 alerts are not real faults (60.1% precision
per alert). That's the next thing to improve.
- **Where the model doesn't win:** it only ties on router, AMF and cell outages. There was one bushfire case, so I
make no bushfire claim.

## 4. Iterations: what went wrong and what I changed

The review process sent each pull request to a second AI from a *different vendor*. It sent 6 of the 7 PRs back at least once.
These are the ones that mattered:

1. **Scoring flattered the results (step 2).** Red-herring traffic surges and maintenance counted as "detected", and
 a detection on any affected cell counted as success. I split it into two measures, impact spotted and correct
 element, and counted red herrings as false alarms.
2. **Late data made detection look faster (step 2, round 4).** Fixed by the late-data rule above.
3. **Label leak in the ML evaluation (step 3).** The evaluation used the incident labels to pick which cases to rank,
 and the "held-out" days had shaped the design. I re-ran on fresh days, label-free, scored once. Surprisingly,
 accuracy went *up* (81% to 93%), because the old method took the best score over a 20-minute window. A reviewer
 confirmed it was real.
4. **Duplicate alarm IDs across runs (found in step 4).** About 20% of alarms on the test days were silently dropped
 as duplicates. The LLM looked weak (82%) when it was really starved of alarms. After the fix it scored 97.5%.
5. **Answer key visible in the app (step 5).** A ground-truth scorecard was exposed to Genie and an app tile. I
 removed it and added a test that fails if it comes back.

## 5. How I used AI

- **Orchestration:** I used a multi-agent setup. A lead agent (Claude) planned and wrote each task brief. Claude Code
implemented each step in its own git worktree and opened a PR. Codex, from a different vendor, reviewed each diff
against the brief. I reviewed and merged every PR myself.
- **What AI was good at:** generator realism, pipeline boilerplate, test coverage, and catching evaluation bugs I'd
have missed.
- **Where I made the calls:**
  - **Use case and core design:** I chose the real-time NOC monitoring use case and set the 5-minute
  detection goal. I also set the core flow: a staged Lakeflow pipeline, a Genie space for operators, and an app
  that pinpoints the failing node on the network topology.
  - **ML and Gen AI together:** I asked for both, rather than one or the other.
  - **The customer:** I defined it as the network operations team at a large mobile *operator*, like Telstra, rather
  than an equipment vendor. I then had the network moved to Australian geography with local time zones.
  - **No real operator name:** I chose a fictional tier-1 operator rather than naming Telstra, so a real customer's
  network is never presented as its data.
  - **How the root-cause model is judged:** I chose top-1 and top-3 accuracy against the rules baseline, plus how many
  slow backhaul faults are caught within 5 minutes. Alert precision is reported but not optimised.
  - **Gen AI scope:** I chose two parts, the NOC root-cause summary for the network team and customer outage SMS
  drafts for the customer side, so the build serves both the network executive's and the customer executive's KPIs.
  - **The duplicate-alarm fix:**
    - I decided it should be a separate PR, so the earlier steps' published numbers would be corrected before
    the deck.
    - For reloading the data, I chose the targeted replace over a full pipeline refresh. A full refresh was
    simpler, but it would have invalidated the step-2 live-stream evidence.
  - **AI Gateway:** I approved putting AI Gateway on the shared pay-per-token LLM endpoint.
  - **Grading against the real rubric:** I steered the build against the official FE Bar page and the Telecom
  Outcome Map.
  - **Every merge:** I reviewed and merged every PR myself.
- **AI inside the solution:** the ML ranker for root cause, the LLM for the NOC summary and customer SMS, and Genie
for questions in plain English. All of it is governed: AI Gateway handles PII guardrails, rate limits and usage
tracking; MLflow tracing is on; and every request and response is logged.

## 6. Known limits and what I'd do next

- **Slow backhaul degradation isn't caught within 5 minutes** (median about 10 min, ramp of 10–30 min).
  - **Why:** detection works cell by cell, and early in the ramp each cell degrades only a little, so none crosses
  its threshold on its own.
  - **What I added:** detect impact from the *customers attached to the cells behind each link*. Roll cell
  health up the topology to the backhaul link, weighted by each cell's connected users. A small, consistent
  degradation across every cell and subscriber behind one link is a strong signal well before any single cell looks
  bad. Session records were the obvious source, but they're a 1% sample and only arrive when a session ends. The
  per-minute connected-user count in the cell KPIs gives the same subscriber view without the delay.
  - **Measured result** (offline experiment, thresholds frozen on dev days, fresh test days scored once, 53 slow
  backhaul faults, `evidence/step6/`): median time to detect fell from 562 s to 332 s (about 3 minutes faster), p90
  from 810 s to 467 s, and the share within 5 minutes rose from 7.5% to 17.0%, with no extra false alarms in about
  196 healthy link-days. Most slow backhaul faults still miss 5 minutes: about 120 s of every detection is fixed
  pipeline wait, and synthetic cell noise is more independent than a real network's, so this is a best case. The
  real fix for the 5-minute target is monitoring the link itself (interface errors, signal levels).
  - **Why it helps twice:** it also points directly at the link as the likely cause.
- **Alert precision of about 60%** means the next model target is false-alarm reduction.
- **Workspace limits** (documented): inference tables wouldn't enable; AI Gateway's input safety filter flagged
normal NOC prompts and is off, with code checks instead; there's no second user for a two-user masking test.
- **Next:** a pilot on one region's real alarm and KPI feeds; train on closed incident tickets; measure MTTR before
and after.

