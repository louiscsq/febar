# Banksia Mobile NOC: detect customer impact in minutes, not hours

**Customer:** the Network Operations Centre (NOC) of a tier-1 Australian mobile operator. "Banksia Mobile" is fictional
and modelled on operators like Telstra and Optus. All data is synthetic.

**The problem.** In Australia's biggest recent outages, the NOC was not the first to know.

- In July 2026, a Telstra fault began at 02:50. It was detected at 04:29, about **99 minutes** later, when customer web
searches for "Telstra outage" crossed a threshold. The earliest alarms existed but weren't shown in 24x7 monitoring.
Finding the root cause took several hours. ([independent findings report for Telstra, Aug 2026](https://www.telstra.com.au/content/dam/tcom/dynamic-media-projects/luke-campbell/TAPFindingsforTelstraOutage.pdf))
- In September 2025, Optus's emergency 000 calls failed for about 13 hours. A customer and the police raised it.
The NOC had no alarms for those calls. ([summary with citations to Optus's updates](https://en.wikipedia.org/wiki/2025_Optus_emergency_calling_outage))
- The consequences were real: an A$12m+ ACMA penalty for Optus over its 2023 outage ([ACMA, Nov 2024](https://www.acma.gov.au/articles/2024-11/optus-pays-12-million-penalty-triple-zero-outage)), and a
20-point cut to the bonus multiplier of Telstra's CEO and network executive in FY26 ([Telstra FY26 Annual Report,
remuneration report](https://www.telstra.com.au/content/dam/tcom/about-us/investors/pdf-i/telstra-financial-results-and-annual-report-for-the-year-ended-30-jun-2026.pdf)).

**The outcome this build delivers** (measured on synthetic data, text evidence in `evidence/`):


| NOC KPI                                                                 | Result                                                                                                                                           |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Customer impact detected within 5 minutes                               | **88.5%** of real faults on the live stream (median 141 s). The end-to-end trace detects a site power outage in **124 s**.                       |
| Correct failing element is the top suspect (ML ranker, fresh test days) | **94.7%**, against 78.3% for a rules-based baseline on the same cases                                                                            |
| Root-cause summary and next steps per incident (Gen AI)                 | Agrees with the actual cause **97.5%** of the time. About 6 s and about US$0.01 per incident.                                                    |
| Customer outage SMS drafts                                              | 100% within the rules: ≤160 characters, no internal IDs, no personal data. A person must approve every draft, and nothing is sent automatically. |
| Subscriber privacy                                                      | IMSI and MSISDN masked for operators, and regional NOC teams see only their own region                                                           |


**Known limit, stated plainly:** slowly degrading backhaul links (ramping over 10–30 minutes) are the one fault type
we don't catch within 5 minutes. On the deployed per-cell path the median is about 9.4 minutes (562 s). An offline
link-level experiment cuts that to about 5.5 minutes (332 s), with 17.0% caught within 5 minutes and no extra false
alarms, but it isn't deployed yet. See `evidence/step6/README.md` and `BUILD.md`.

**How it fits together:** synthetic network telemetry → **Lakeflow** streaming pipeline (bronze → silver → gold, with
data-quality expectations) → **Unity Catalog** governance (masks, row filters, lineage) → **ML** root-cause ranker
(MLflow, Model Serving) → **Gen AI** NOC assistant and SMS drafts (AI Gateway with guardrails and logging) →
**Lakebase** operational tables → **Databricks App** network topology view, with **Genie** for plain-English questions.
One fault traced through every layer: [`evidence/step5/03_trace_site_power_outage.md`](evidence/step5/03_trace_site_power_outage.md).
Architecture: [`docs/architecture.md`](docs/architecture.md). Decisions and trade-offs: [`BUILD.md`](BUILD.md).
