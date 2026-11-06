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

RESULTS_PLACEHOLDER
