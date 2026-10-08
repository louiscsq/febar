# Databricks notebook source
# MAGIC %md
# MAGIC # Generate synthetic network history into a UC Volume
# MAGIC
# MAGIC Writes N days of synthetic telemetry for a mobile network (topology, per-cell KPIs, element alarms,
# MAGIC subscriber sessions) plus ground truth (incidents, DQ injections) into
# MAGIC `/Volumes/<catalog>/<schema>/<volume>/<subdir>/`, partitioned by emitted date.
# MAGIC
# MAGIC The generator is plain Python (numpy/pandas) and runs on the driver, so serverless notebook compute
# MAGIC is fine. Default `large` scale (~5k sites / ~23k cells, 15-min KPIs, 30 days) takes ~3.5 minutes,
# MAGIC writes ~2 GB of Parquet and peaks at ~2.5 GB of driver memory. Use `small` for a quick look.
# MAGIC See `docs/data_model.md` for the schemas.

# COMMAND ----------

# MAGIC %pip install -q "numpy>=1.24" "pandas>=2.0" "pyarrow>=12"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("catalog", "main", "Catalog")
dbutils.widgets.text("schema", "netmon", "Schema")
dbutils.widgets.text("volume", "landing", "Volume")
dbutils.widgets.text("subdir", "history", "Sub-directory in volume")
dbutils.widgets.dropdown("scale", "large", ["tiny", "small", "large", "xl"], "Scale preset")
dbutils.widgets.text("days", "30", "Days of history")
dbutils.widgets.text("start_date", "", "Start date (YYYY-MM-DD, blank = today - days)")
dbutils.widgets.text("seed", "42", "Random seed")
dbutils.widgets.dropdown("format", "parquet", ["parquet", "json"], "File format")
dbutils.widgets.text("dq_scale", "1.0", "DQ defect rate multiplier (0 = clean)")
dbutils.widgets.text("fault_rate_multiplier", "1.0", "Fault rate multiplier")
dbutils.widgets.dropdown("overwrite", "true", ["true", "false"], "Delete existing output first")

# COMMAND ----------

import os
import sys

# The package lives in ../src relative to this notebook (Git folder / bundle sync).
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "src")))

from netmon_datagen.batch import generate_history
from netmon_datagen.config import DQConfig, FaultConfig, GeneratorConfig

w = {k: dbutils.widgets.get(k) for k in [
    "catalog", "schema", "volume", "subdir", "scale", "days", "start_date", "seed", "format", "dq_scale",
    "fault_rate_multiplier", "overwrite"]}

spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{w['catalog']}`.`{w['schema']}`")
spark.sql(f"CREATE VOLUME IF NOT EXISTS `{w['catalog']}`.`{w['schema']}`.`{w['volume']}`")
target = f"/Volumes/{w['catalog']}/{w['schema']}/{w['volume']}/{w['subdir']}"
if w["overwrite"] == "true" and os.path.exists(target):
    dbutils.fs.rm(target, True)

cfg = GeneratorConfig.for_scale(
    w["scale"],
    days=int(w["days"]),
    start=w["start_date"] or None,
    seed=int(w["seed"]),
    fmt=w["format"],
    dq=DQConfig().scaled(float(w["dq_scale"])),
    faults=FaultConfig(rate_multiplier=float(w["fault_rate_multiplier"])),
)
print(f"Writing to {target}")

# COMMAND ----------

manifest = generate_history(cfg, target)
manifest["counts"]

# COMMAND ----------

# MAGIC %md ## Quick look at the ground truth

# COMMAND ----------

reader = spark.read.format(w["format"])
incidents = reader.load(f"{target}/ground_truth/incidents")
display(
    incidents.groupBy("event_class", "fault_type")
    .agg({"incident_id": "count", "estimated_impacted_subscribers": "sum", "n_alarms": "sum"})
    .orderBy("event_class", "fault_type")
)

# COMMAND ----------

dq = reader.load(f"{target}/ground_truth/dq_injections")
display(dq.groupBy("feed", "defect_type").count().orderBy("feed", "defect_type"))
