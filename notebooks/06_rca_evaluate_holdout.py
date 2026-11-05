# Databricks notebook source
# MAGIC %md
# MAGIC # Evaluate the frozen champion on the fresh holdout (once) and on the live run
# MAGIC
# MAGIC The design is frozen. This notebook loads `rca_ranker@champion` and its validation-chosen threshold, builds
# MAGIC GT-free candidate features for
# MAGIC
# MAGIC - **`holdout_1m`**: a fresh 1-minute run generated after the design was frozen (new seed 4242 for faults,
# MAGIC   noise and defects, same network, 2026-10-17 … 10-18, after the training run), through the unchanged step-2
# MAGIC   pipeline. Nothing about it was looked at before this evaluation.
# MAGIC - **`stream`**: the step-2 live run (out-of-run check; censored incidents are not scored),
# MAGIC
# MAGIC scores every case, and only then matches the ranked outputs to ground truth (`rca.train.evaluate_run`).
# MAGIC Writes `netmon_rca.rca_eval_holdout_*` / `rca_eval_live_*` and an MLflow run tagged with the model version.

# COMMAND ----------

dbutils.widgets.text("catalog", "telco_netmon_febar_catalog")
dbutils.widgets.text("rca_schema", "netmon_rca")
dbutils.widgets.text("holdout_run", "holdout_1m")
dbutils.widgets.text("live_run", "stream")
dbutils.widgets.text("model_name", "rca_ranker")
dbutils.widgets.text("experiment", "/Shared/banksia_netmon/rca_ranker")

# COMMAND ----------

import json
import os
import sys
import tempfile
import time

try:
    import netmon_pipeline  # noqa: F401
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "src")))

import mlflow
import numpy as np
import pandas as pd

from netmon_pipeline.rca import labels, model, train
from netmon_pipeline.rca.features import FEATURE_COLUMNS, ID_COLUMNS
from netmon_pipeline.rca.sources import queries, utc_frame

spark.conf.set("spark.sql.session.timeZone", "UTC")
w = {k: dbutils.widgets.get(k) for k in ["catalog", "rca_schema", "holdout_run", "live_run", "model_name",
                                          "experiment"]}
CAT, SCH = w["catalog"], w["rca_schema"]
FQ = f"`{CAT}`.`{SCH}`"
MODEL = f"{CAT}.{SCH}.{w['model_name']}"
SCRATCH = f"/Volumes/{CAT}/{SCH}/scratch/holdout"
t_start = time.time()

mlflow.set_registry_uri("databricks-uc")
client = mlflow.MlflowClient(registry_uri="databricks-uc")
mv = client.get_model_version_by_alias(MODEL, "champion")
threshold = float(mv.tags["alert_threshold"])
clf = mlflow.sklearn.load_model(f"models:/{MODEL}@champion")
print("frozen champion", MODEL, "v", mv.version, "threshold", threshold)


def loader(run):
    cache = {}

    def load(name, region=None):
        key = (name, region)
        if key not in cache:
            cache.clear() if name == "topology" else None
            cache[key] = utc_frame(spark.sql(queries(CAT, run, region)[name]).toPandas())
        return cache[key]

    return load


def flat(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in out.columns:
        if out[c].map(lambda v: isinstance(v, list | tuple | np.ndarray)).any():
            out[c] = out[c].map(lambda v: ",".join(map(str, v)) if isinstance(v, list | tuple | np.ndarray) else v)
    return out


def to_delta(df: pd.DataFrame, name: str, comment: str) -> None:
    os.makedirs(SCRATCH, exist_ok=True)
    path = f"{SCRATCH}/{name}.parquet"
    df = df.copy()
    df.attrs = {}
    df.to_parquet(path, index=False, coerce_timestamps="us", allow_truncated_timestamps=True)
    spark.read.parquet(path).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.{name}")
    spark.sql(f"COMMENT ON TABLE {FQ}.{name} IS {json.dumps(comment)}")


regions = [r[0] for r in spark.sql(f"SELECT DISTINCT region_code FROM `{CAT}`.netmon_silver.silver_topology_nodes "
                                   "ORDER BY 1").collect()]

# COMMAND ----------

results, all_tables, metrics = {}, {}, {}
for name, run in (("holdout", w["holdout_run"]), ("live", w["live_run"])):
    feats = train.build_features(loader(run), regions)
    # GT-free scoring of every case: features only, no label column exists at this point
    scored = feats[ID_COLUMNS + FEATURE_COLUMNS].assign(score=model.score(clf, feats))
    q = queries(CAT, run)
    inc = labels.prepare_incidents(utc_frame(spark.sql(q["incidents"]).toPandas()))
    cmp_ = {k: utc_frame(spark.sql(q[k]).toPandas()) for k in ("baseline", "step2_localisation", "step2_detections")}
    tables, m = train.evaluate_run(scored, inc, threshold, cmp_["baseline"], cmp_["step2_localisation"],
                                   cmp_["step2_detections"], name=name)
    all_tables.update(tables)
    metrics.update(m)
    if name == "holdout":
        to_delta(scored, "rca_holdout_scores", f"GT-free scored candidates of {run} (frozen champion v{mv.version}).")
    print(name, m)

# COMMAND ----------

from databricks.sdk import WorkspaceClient

WorkspaceClient().workspace.mkdirs(os.path.dirname(w["experiment"]))
mlflow.set_experiment(w["experiment"])
with mlflow.start_run(run_name=f"holdout_eval_v{mv.version}") as run:
    mlflow.set_tags({"model": MODEL, "model_version": mv.version, "holdout_run": w["holdout_run"],
                     "stage": "frozen-model holdout evaluation", "training_run_id": mv.run_id})
    mlflow.log_params({"alert_threshold": threshold, "holdout_run": w["holdout_run"], "live_run": w["live_run"]})
    mlflow.log_metrics(metrics)
    with tempfile.TemporaryDirectory() as tmp:
        for k, v in all_tables.items():
            flat(v).to_csv(os.path.join(tmp, f"{k}.csv"), index=False)
        mlflow.log_artifacts(tmp, artifact_path="evaluation")
    eval_run_id = run.info.run_id
client.set_model_version_tag(MODEL, mv.version, "holdout_top1_pct", str(metrics["holdout_top1_pct"]))
client.set_model_version_tag(MODEL, mv.version, "holdout_eval_run_id", eval_run_id)

meta = {"mlflow_run_id": eval_run_id, "model_version": str(mv.version), "threshold": threshold}
for k, v in all_tables.items():
    to_delta(flat(v).assign(**meta), f"rca_eval_{k}",
             f"Frozen champion v{mv.version} evaluated GT-free on {k.split('_')[0]} ({w['holdout_run'] if k.startswith('holdout') else w['live_run']}); "
             f"evaluation MLflow run {eval_run_id}.")
to_delta(pd.DataFrame([{**meta, "training_run_id": mv.run_id, **metrics,
                        "minutes": round((time.time() - t_start) / 60, 1)}]), "rca_holdout_runs",
         "One row per frozen-model holdout evaluation (latest overwrites).")
