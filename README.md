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
column masks, a regional row filter, NOC groups, least-privilege grants, and comments and tags.
Everything is deployed as a Databricks Asset Bundle (`databricks.yml`, `resources/`).

```bash
databricks bundle deploy -p febar
databricks bundle run -p febar netmon_bootstrap      # history -> functions -> pipeline -> grants and tags
```

See [`docs/pipeline.md`](docs/pipeline.md) for the architecture, tables, expectations policy, latency
budget, governance model and run book, and [`evidence/step2/`](evidence/step2/) for the captured run.
