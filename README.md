<!--
DRAFT for Louis to review and rewrite in his own words.
Replaces the top of README.md, everything above "## Data generator".
Numbers come from evidence/step2–step5. Re-check them against the final merged evidence before submitting.
-->

# Banksia Mobile NOC: detect customer impact in minutes, not hours

**Customer:** the Network Operations Centre (NOC) of a tier-1 Australian mobile operator. "Banksia Mobile" is fictional
and modelled on operators like Telstra and Optus. All data is synthetic.

**The problem.** In Australia's biggest recent outages, the NOC was not the first to know.

- In July 2026, a Telstra fault began at 02:50. It was detected at 04:29, about **99 minutes** later, when customer web
searches for "Telstra outage" crossed a threshold. The earliest alarms existed but weren't shown in 24x7 monitoring.
Finding the root cause took several hours.
- In September 2025, Optus's emergency 000 calls failed for about 13 hours. A customer and the police raised it.
The NOC had no alarms for those calls.
- The consequences were real: an A$12m+ ACMA penalty for Optus in 2023, and a 20-point cut to the Telstra CEO's and
network executive's bonuses in FY26.

**The outcome this build delivers** (measured on synthetic data, text evidence in `evidence/`):


| NOC KPI                                                                 | Result                                                                                                                                           |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Customer impact detected within 5 minutes                               | **88.5%** of real faults on the live stream (median 141 s). The end-to-end trace detects a site power outage in **124 s**.                       |
| Correct failing element is the top suspect (ML ranker, fresh test days) | **94.7%**, against 78.3% for a rules-based baseline on the same cases                                                                            |
| Root-cause summary and next steps per incident (Gen AI)                 | Agrees with the actual cause **97.5%** of the time. About 6 s and about US$0.01 per incident.                                                    |
| Customer outage SMS drafts                                              | 100% within the rules: ≤160 characters, no internal IDs, no personal data. A person must approve every draft, and nothing is sent automatically. |
| Subscriber privacy                                                      | IMSI and MSISDN masked for operators, and regional NOC teams see only their own region                                                           |


**What it's worth:** an estimated **A$4m per year** (range A$2–8m) for an operator of this scale, from faster repair, fewer
complaint calls and lower major-outage exposure. See [`docs/value_model.md`](docs/value_model.md). The assumptions are
stated and conservative.

**Known limit, stated plainly:** slowly degrading backhaul links (ramping over 10–30 minutes) are the one fault type
we don't catch within 5 minutes. The median is about 10 minutes. See `BUILD.md`.

**How it fits together:** synthetic network telemetry → **Lakeflow** streaming pipeline (bronze → silver → gold, with
data-quality expectations) → **Unity Catalog** governance (masks, row filters, lineage) → **ML** root-cause ranker
(MLflow, Model Serving) → **Gen AI** NOC assistant and SMS drafts (AI Gateway with guardrails and logging) →
**Lakebase** operational tables → **Databricks App** network topology view, with **Genie** for plain-English questions.
One fault traced through every layer: [`evidence/step5/03_trace_site_power_outage.md`](evidence/step5/03_trace_site_power_outage.md).
Architecture: [`docs/architecture.md`](docs/architecture.md). Decisions and trade-offs: [`BUILD.md`](BUILD.md).
