# Telco Real-Time Network Monitoring & Root-Cause Localisation

Streaming monitoring and alerting for a mobile network operator's Network Operations team:
detect customer service impact within 5 minutes and pinpoint the network element most
likely causing the disruption.

Built on Databricks: Lakeflow (Spark Declarative Pipelines), Unity Catalog, Lakebase,
MLflow, a GenAI root-cause assistant, Genie, and a Databricks App with network topology
visualisation. All data is synthetic.

See `BUILD.md` for design decisions and trade-offs.

## Data generator

`src/netmon_datagen` generates the synthetic network of **Banksia Mobile**, a fictional tier-1
Australian operator, as seen by its national NOC: ten regions from Sydney to the Pilbara with real
coordinates and time zones, per-cell KPIs and sessions that follow local time (DST included; stored
timestamps are UTC), alarms, injected faults with ground truth, and data-quality defects. Faults include
Australian ones: bushfire grid outages, cyclone backhaul cuts in the tropical north and long-haul fibre
cuts that isolate remote areas. Identifiers stay on reserved test ranges. See
[`docs/data_model.md`](docs/data_model.md) for schemas, regions, the fault taxonomy, streaming ordering
guarantees and volume figures.

```bash
pip install -e ".[dev]"

# 30 days of history (default "large" preset: ~5k sites / ~23k cells, ~2.2 GB Parquet, ~4 min)
netmon-datagen batch --out ./data/local/history --days 30 --seed 42

# quick, small history as JSON lines
netmon-datagen batch --out ./data/local/small --scale small --days 3 --format json

# live JSON micro-batches every 10 s (1 simulated minute each), with extra faults for demos
netmon-datagen stream --out ./data/local/stream --scale small --interval-seconds 10 --fault-rate-multiplier 5

python -m pytest -q && ruff check .
```

On Databricks, run `notebooks/01_generate_history.py` (batch) or `notebooks/02_stream_generator.py`
(streaming). Both write to `/Volumes/<catalog>/<schema>/<volume>/...` and take their parameters from
widgets.

## Streaming pipeline and governance

A Lakeflow Spark Declarative Pipeline (`pipelines/netmon/`, serverless, Python `pyspark.pipelines`)
ingests the landing Volume with Auto Loader into bronze, validates and deduplicates it in silver (with
expectations and a quarantine), and builds gold tables for the NOC: per-cell 1- and 5-minute health windows
with baseline deviation, customer-impact detections with `detected_ts`, and a topology rollup that serves
as root-cause features. A separate `netmon_eval` schema scores detections against the generator's ground
truth (time-to-detect, % within 5 minutes). Unity Catalog governance in `governance/` adds IMSI / MSISDN
column masks and a regional row filter. Regional NOC roles read only region-filtered views. It also adds
NOC groups, least-privilege grants, and comments and tags.
Everything is deployed as a Databricks Asset Bundle (`databricks.yml`, `resources/`).

```bash
databricks bundle deploy -p febar
databricks bundle run -p febar netmon_bootstrap      # history -> functions -> pipeline -> grants and tags
```

Captured live run (1-minute stream, faults only, 26 incidents): customer impact detected for 100 % of
faults, **88.5 % within 5 minutes** (median 141 s, p90 430 s). The true root element was localised for
100 % of faults (88.5 % within 5 minutes). Fault precision is **60.1 % at alert level** (detections
grouped per element per episode) and 98.2 % at detection-row level, counting red herrings and unsuppressed
planned work as false positives.

See [`docs/pipeline.md`](docs/pipeline.md) for the architecture, tables, expectations policy, latency
budget, governance model and run book, and [`evidence/step2/`](evidence/step2/) for the captured run.

## Root-cause model, serving and Lakebase (step 3)

A trained root-cause ranker (scikit-learn gradient boosting, not an LLM; `src/netmon_pipeline/rca/`) scores every
candidate element of a customer-impact case using only what the NOC could see at that minute. It is trained on
a 6-day 1-minute labelled run with a time-based split (evaluated on a separate fresh holdout run) and tracked in MLflow. It is registered in Unity Catalog
as `telco_netmon_febar_catalog.netmon_rca.rca_ranker@champion` and served on a serverless, scale-to-zero
endpoint (`banksia-rca-ranker`). A scoring job publishes `element_status` and `open_incidents` (top-3
suspects), which Lakebase synced tables copy into Postgres for the topology app.

```bash
databricks bundle run -p febar rca_generate_training_history && databricks bundle run -p febar netmon_pipeline
databricks bundle run -p febar rca_train            # features, MLflow, UC model + champion, evaluation
databricks bundle run -p febar rca_score_live       # element_status / open_incidents -> Lakebase
databricks bundle run -p febar rca_lakebase_check   # psycopg + OAuth read-latency check
```

On a fresh holdout run generated after the design was frozen (337 faults), the model's top-1 is **93.2 %
against 78.3 %** for step 2's topology heuristic on the same GT-free cases (top-3 95.3 % vs 80.7 %). 80.4 % of
faults are localised within 5 minutes (step-2 localisation: 65.6 %). Slowly degrading backhaul links are still
not localised within 5 minutes by any system: median 615 s vs 1,011 s for step 2. Step 2's *published*,
region-wide baseline (27.9 % top-1 on the holdout; the "58 %" figure was the sparse 15-minute history) is a
different, weaker framing.

See [`docs/rca_model.md`](docs/rca_model.md) for features, labels, split, model choice, the evaluation protocol,
results against the step-2 localiser, serving and the Lakebase design, and [`evidence/step3/`](evidence/step3/)
for the captured run.

## Gen AI NOC assistant and customer SMS drafts (step 4)

For an open incident, an LLM (`databricks-gpt-5-4-mini`, Databricks Foundation Model API) drafts a root-cause
summary with evidence, runbook next steps and customer impact for the NOC, plus one proactive outage SMS per affected
region for human approval (never sent by the system). The context is assembled only from the build's own tables
(the ranker's top-3 and their signals, topology, alarms, KPI deviation, subscriber counts by region and segment), with
no per-subscriber data and no ground truth (both tested). Calls go through AI Gateway (PII guardrails, output safety,
rate limits, usage tracking), are MLflow traced and are checked by deterministic guards: the root cause must be a
suspect or "uncertain", unknown element IDs are scrubbed, and SMS rules are enforced. Results land in Unity Catalog
(`netmon_genai`) and in Lakebase for the topology app (`src/netmon_pipeline/genai/`).

```bash
python scripts/genai_configure_gateway.py --profile febar --no-inference-table
databricks bundle run -p febar genai_build_evalset && databricks bundle run -p febar genai_evaluate --params split=dev
databricks bundle run -p febar genai_assistant      # also triggered by every open_incidents update
```

On step 3's dev days the assistant's root cause agrees with ground truth on **97.1 %** of evaluated incidents (the
ranker's top-1 alone: 96.5 %; it fixed 3 ranker misses and broke none). On the fresh holdout it **loses** accuracy:
**82.0 % against 97.2 %**. Most of the gap traces to an upstream defect found after the run: incident alarm IDs repeat
across batch runs, so silver drops about 20 % of the holdout's alarms. The ranker copes from KPIs; the assistant,
looking for corroborating alarms, abstains or blames a neighbour. The ranker therefore stays the system of record.
No hallucinated root survives the guard. SMS drafts are 100 % rule-compliant (98 % at the model's first try). About
6.5 s and 5.6 k tokens per incident. 6 of 6 live guardrail tests (prompt injection, PII leaks) were blocked or
neutralised.

See [`docs/genai_assistant.md`](docs/genai_assistant.md) and [`evidence/step4/`](evidence/step4/).
