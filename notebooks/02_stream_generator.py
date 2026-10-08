# Databricks notebook source
# MAGIC %md
# MAGIC # Stream synthetic network telemetry into a UC Volume
# MAGIC
# MAGIC Emits JSON-lines micro-batches (KPIs, alarms, sessions) to
# MAGIC `/Volumes/<catalog>/<schema>/<volume>/<subdir>/<feed>/date=YYYY-MM-DD/batch-*.json`, one batch every
# MAGIC `interval_seconds`, each advancing simulated time by `step_seconds`. Faults are injected live and
# MAGIC propagate down the topology. Ground truth for each incident appears under `ground_truth/incidents/`
# MAGIC once the incident has fully played out and all of its KPI/alarm records have landed (with DQ on, that
# MAGIC includes late arrivals, so set `dq_scale` to 0 for live labels). When a bounded run stops, in-flight
# MAGIC incidents are written with `is_censored = true`. Score time-to-detect against `impact_start_ts`. Files are written atomically
# MAGIC (temp + rename) so Auto Loader only ever sees complete files.
# MAGIC
# MAGIC Run as a notebook task in a job for a long-running feed, or interactively with `max_batches`.

# COMMAND ----------

# MAGIC %pip install -q "numpy>=1.24" "pandas>=2.0" "pyarrow>=12"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("catalog", "main", "Catalog")
dbutils.widgets.text("schema", "netmon", "Schema")
dbutils.widgets.text("volume", "landing", "Volume")
dbutils.widgets.text("subdir", "stream", "Sub-directory in volume")
dbutils.widgets.dropdown("scale", "small", ["tiny", "small", "large", "xl"], "Scale preset")
dbutils.widgets.text("seed", "42", "Random seed")
dbutils.widgets.text("start", "", "Simulated start (UTC ISO, blank = now)")
dbutils.widgets.text("step_seconds", "60", "Simulated seconds per micro-batch")
dbutils.widgets.text("interval_seconds", "60", "Wall-clock seconds between micro-batches (0 = max speed)")
dbutils.widgets.text("max_batches", "60", "Stop after N batches (blank = run forever)")
dbutils.widgets.text("fault_rate_multiplier", "5", "Fault rate multiplier (demo-friendly > 1)")
dbutils.widgets.text("dq_scale", "1.0", "DQ defect rate multiplier (0 = clean)")
# `days` is not used by streaming; kept so both notebooks share one widget set in jobs.
dbutils.widgets.text("days", "30", "Days (batch only)")

# COMMAND ----------

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "src")))

from netmon_datagen.config import DQConfig, FaultConfig, GeneratorConfig
from netmon_datagen.stream import run_stream

w = {k: dbutils.widgets.get(k) for k in [
    "catalog", "schema", "volume", "subdir", "scale", "seed", "start", "step_seconds", "interval_seconds",
    "max_batches", "fault_rate_multiplier", "dq_scale"]}

spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{w['catalog']}`.`{w['schema']}`")
spark.sql(f"CREATE VOLUME IF NOT EXISTS `{w['catalog']}`.`{w['schema']}`.`{w['volume']}`")
target = f"/Volumes/{w['catalog']}/{w['schema']}/{w['volume']}/{w['subdir']}"

cfg = GeneratorConfig.for_scale(
    w["scale"],
    seed=int(w["seed"]),
    dq=DQConfig().scaled(float(w["dq_scale"])),
    faults=FaultConfig(rate_multiplier=float(w["fault_rate_multiplier"])),
)
print(f"Streaming to {target}")

# COMMAND ----------

result = run_stream(
    cfg,
    target,
    step_seconds=int(w["step_seconds"]),
    interval_seconds=float(w["interval_seconds"]),
    max_batches=int(w["max_batches"]) if w["max_batches"].strip() else None,
    start=w["start"] or None,
)
result

# COMMAND ----------

# MAGIC %md ## Incidents injected so far

# COMMAND ----------

display(
    spark.read.json(f"{target}/ground_truth/incidents")
    .select("incident_id", "fault_type", "root_element_id", "start_ts", "impact_start_ts", "end_ts",
            "n_affected_cells", "estimated_impacted_subscribers")
    .orderBy("start_ts")
)
