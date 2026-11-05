# Databricks notebook source
# MAGIC %md
# MAGIC # Score the live run with the champion ranker, publish element status and open incidents
# MAGIC
# MAGIC Batch scoring in the job, not through the serving endpoint: the job already holds every candidate's
# MAGIC features in memory, scores a few thousand rows per decision time in milliseconds with the same UC model
# MAGIC version (`@champion`), and needs no network hop or endpoint warm-up (the endpoint scales to zero). The
# MAGIC Model Serving endpoint serves the same version for on-demand scoring by the app and other clients.
# MAGIC
# MAGIC Writes (MERGE, Change Data Feed on) `netmon_rca.element_status` and `netmon_rca.open_incidents`, appends
# MAGIC every scored candidate to `netmon_rca.rca_live_scores`, then triggers the Lakebase synced tables.

# COMMAND ----------

dbutils.widgets.text("catalog", "telco_netmon_febar_catalog")
dbutils.widgets.text("rca_schema", "netmon_rca")
dbutils.widgets.text("live_run", "stream")
dbutils.widgets.text("model_name", "rca_ranker")
dbutils.widgets.text("lookback_minutes", "120")
dbutils.widgets.text("history_minutes", "60")
dbutils.widgets.dropdown("sync_lakebase", "true", ["true", "false"])

# COMMAND ----------

import json
import os
import sys
import time

try:
    import netmon_pipeline  # noqa: F401
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "src")))

import mlflow
import pandas as pd

from netmon_pipeline.rca import live, model
from netmon_pipeline.rca.features import FEATURE_COLUMNS, RunState, Topology
from netmon_pipeline.rca.sources import queries

w = {k: dbutils.widgets.get(k) for k in ["catalog", "rca_schema", "live_run", "model_name", "lookback_minutes",
                                          "history_minutes", "sync_lakebase"]}
CAT, SCH, RUN = w["catalog"], w["rca_schema"], w["live_run"]
FQ = f"`{CAT}`.`{SCH}`"
MODEL = f"{CAT}.{SCH}.{w['model_name']}"
t_wall = time.time()

mlflow.set_registry_uri("databricks-uc")
client = mlflow.MlflowClient(registry_uri="databricks-uc")
mv = client.get_model_version_by_alias(MODEL, "champion")
threshold = float(mv.tags["alert_threshold"])
clf = mlflow.sklearn.load_model(f"models:/{MODEL}@champion")
print("champion", MODEL, "v", mv.version, "threshold", threshold)

latest = spark.sql(f"SELECT max(window_start) FROM `{CAT}`.netmon_gold.gold_cell_health_1m "
                   f"WHERE source_run = '{RUN}'").collect()[0][0]
since = (pd.Timestamp(latest, tz="UTC") - pd.Timedelta(minutes=int(w["lookback_minutes"]))).isoformat()
print("latest window", latest, "reading since", since)

# COMMAND ----------

regions = [r[0] for r in spark.sql(f"SELECT DISTINCT region_code FROM `{CAT}`.netmon_silver.silver_topology_nodes "
                                   "ORDER BY 1").collect()]
topo_all = spark.sql(queries(CAT, RUN)["topology"]).toPandas()
parts = []
for r in regions:
    qr = queries(CAT, RUN, region=r, since=since)
    topo = Topology(topo_all[topo_all["region_code"] == r])
    st = RunState(topo, *(spark.sql(qr[k]).toPandas() for k in ("health", "alarms", "maintenance")))
    times = st.decision_times()
    times = times[times >= times.max() - int(w["history_minutes"])]
    f = st.features(times=times, regions=[r])
    if len(f):
        parts.append(f)
scored = pd.concat(parts, ignore_index=True)
scored["score"] = model.score(clf, scored)
print("scored", len(scored), "rows,", scored["case_id"].nunique(), "cases, latest", scored["decision_ts"].max())

inc = live.open_incidents(scored, threshold, mv.version)
status = live.element_status(topo_all, scored, inc)
refreshed = pd.Timestamp.now(tz="UTC")
inc["refreshed_at"] = refreshed
status["refreshed_at"] = refreshed
status["model_version"] = str(mv.version)
print(len(inc), "open incidents;", status["state"].value_counts().to_dict())

# COMMAND ----------


def upsert(df: pd.DataFrame, name: str, key: str, ddl: str, comment: str) -> None:
    """MERGE into a CDF-enabled Delta table (the synced tables read its change feed); rows that are no
    longer current (e.g. cleared incidents) are deleted."""
    tgt = f"{FQ}.{name}"
    cols_ddl = [c.strip().split(" ")[0] for c in ddl.split(",")]
    src = spark.createDataFrame(live.conform(df, ddl), schema=ddl)
    if not spark.catalog.tableExists(tgt):
        src.limit(0).write.saveAsTable(tgt)
        spark.sql(f"ALTER TABLE {tgt} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
        spark.sql(f"ALTER TABLE {tgt} ALTER COLUMN {key} SET NOT NULL")
        spark.sql(f"ALTER TABLE {tgt} ADD CONSTRAINT {name}_pk PRIMARY KEY ({key})")
    spark.sql(f"COMMENT ON TABLE {tgt} IS {json.dumps(comment)}")
    src.createOrReplaceTempView(f"src_{name}")
    cols = ", ".join(f"t.{c} = s.{c}" for c in cols_ddl if c != key)
    spark.sql(f"""MERGE INTO {tgt} t USING src_{name} s ON t.{key} = s.{key}
                  WHEN MATCHED THEN UPDATE SET {cols}
                  WHEN NOT MATCHED THEN INSERT *
                  WHEN NOT MATCHED BY SOURCE THEN DELETE""")


upsert(status, "element_status", "element_id", live.ELEMENT_STATUS_DDL,
       "Current health per network element at the latest scored decision time of the live run: state "
       "(down / degraded / impacted / alarm / ok), impact counts, alarms, highest root-cause score, open incident "
       "it is a suspect of. Source of the Lakebase synced table element_status.")
upsert(inc, "open_incidents", "incident_id", live.OPEN_INCIDENTS_DDL,
       "Detected incidents not yet cleared (model alert still active at the latest decision time) with the top-3 "
       "ranked suspect elements and their calibrated scores and the time detected. Source of the Lakebase synced "
       "table open_incidents.")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {FQ}.scratch COMMENT 'Staging Parquet for pandas -> Delta writes'")
os.makedirs(f"/Volumes/{CAT}/{SCH}/scratch/live", exist_ok=True)
_p = f"/Volumes/{CAT}/{SCH}/scratch/live/scores.parquet"
scored[["source_run", "decision_ts", "region_code", "case_id", "element_id", "element_type", "feature_evidence_ts",
        *FEATURE_COLUMNS, "score"]].assign(model_version=str(mv.version)).to_parquet(_p, index=False)
spark.read.parquet(_p).write.mode("append").option("mergeSchema", "true").saveAsTable(f"{FQ}.rca_live_scores")

# COMMAND ----------

# MAGIC %md ## Trigger the Lakebase synced tables (TRIGGERED mode reads the change feed)

# COMMAND ----------

from databricks.sdk import WorkspaceClient

ws = WorkspaceClient()
synced = {}
if w["sync_lakebase"] == "true":
    for t in ("element_status", "open_incidents"):
        name = f"{CAT}.{SCH}.lb_{t}"
        try:
            st_ = ws.database.get_synced_database_table(name)
        except Exception as e:  # not created yet (first run): resources/rca.synced_tables.yml
            print("no synced table", name, str(e)[:200])
            continue
        pid = st_.data_synchronization_status.pipeline_id
        upd = ws.pipelines.start_update(pid)
        synced[name] = {"pipeline_id": pid, "update_id": upd.update_id}
print(json.dumps(synced, indent=1))
print("minutes", round((time.time() - t_wall) / 60, 1))
dbutils.jobs.taskValues.set("n_open_incidents", len(inc))
