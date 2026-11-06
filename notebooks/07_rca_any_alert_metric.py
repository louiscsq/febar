# Databricks notebook source
# MAGIC %md
# MAGIC # Non-oracle companion metric for the step-3 evaluation: any live alert correct at the SLA decision time
# MAGIC
# MAGIC The step-3 top-1 / top-3 judge, per incident, the case output that ground truth picked (largest overlap with
# MAGIC the incident footprint). This companion uses no footprint: at the first decision time at least 5 minutes after
# MAGIC impact start, is **any** live alert of the region (a case whose top-1 calibrated score >= the champion's
# MAGIC threshold) naming a valid root? (`netmon_pipeline.rca.evaluate.any_alert_at_sla`.)
# MAGIC
# MAGIC Nothing is retrained or re-tuned. The frozen champion's stored GT-free scores are reused:
# MAGIC - **holdout** (`holdout_1m`): `netmon_rca.rca_holdout_scores`, written by the one-shot holdout evaluation;
# MAGIC - **dev** (`history_1m`, 2026-10-14 … 10-15): `netmon_rca.rca_candidate_features` of the dev days, scored with
# MAGIC   the same champion (identical to the training job's evaluation scores).
# MAGIC
# MAGIC Writes `netmon_rca.rca_eval_{holdout,dev}_any_alert` and `..._any_alert_summary`.

# COMMAND ----------

dbutils.widgets.text("catalog", "telco_netmon_febar_catalog")
dbutils.widgets.text("rca_schema", "netmon_rca")
dbutils.widgets.text("train_run", "history_1m")
dbutils.widgets.text("holdout_run", "holdout_1m")
dbutils.widgets.text("dev_start", "2026-10-14")
dbutils.widgets.text("model_name", "rca_ranker")

# COMMAND ----------

import json
import os
import sys

try:
    import netmon_pipeline  # noqa: F401
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "src")))

import mlflow
import numpy as np
import pandas as pd

from netmon_pipeline.rca import evaluate, labels, model
from netmon_pipeline.rca.features import FEATURE_COLUMNS, ID_COLUMNS
from netmon_pipeline.rca.sources import queries, utc_frame

spark.conf.set("spark.sql.session.timeZone", "UTC")
w = {k: dbutils.widgets.get(k) for k in ["catalog", "rca_schema", "train_run", "holdout_run", "dev_start",
                                          "model_name"]}
CAT, SCH = w["catalog"], w["rca_schema"]
FQ = f"`{CAT}`.`{SCH}`"
MODEL = f"{CAT}.{SCH}.{w['model_name']}"
SCRATCH = f"/Volumes/{CAT}/{SCH}/scratch/any_alert"

mlflow.set_registry_uri("databricks-uc")
mv = mlflow.MlflowClient(registry_uri="databricks-uc").get_model_version_by_alias(MODEL, "champion")
threshold = float(mv.tags["alert_threshold"])
print("frozen champion v", mv.version, "threshold", threshold)


def to_delta(df: pd.DataFrame, name: str, comment: str) -> None:
    os.makedirs(SCRATCH, exist_ok=True)
    out = df.copy()
    out.attrs = {}
    for c in out.columns:
        if out[c].map(lambda v: isinstance(v, list | tuple | np.ndarray)).any():
            out[c] = out[c].map(lambda v: ",".join(map(str, v)) if isinstance(v, list | tuple | np.ndarray) else v)
    path = f"{SCRATCH}/{name}.parquet"
    out.to_parquet(path, index=False, coerce_timestamps="us", allow_truncated_timestamps=True)
    spark.read.parquet(path).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.{name}")
    spark.sql(f"COMMENT ON TABLE {FQ}.{name} IS {json.dumps(comment)}")


dev_lo = pd.Timestamp(w["dev_start"], tz="UTC")
dev_feats = utc_frame(spark.sql(
    f"SELECT * FROM {FQ}.rca_candidate_features WHERE source_run = '{w['train_run']}' "
    f"AND decision_ts >= '{(dev_lo - pd.Timedelta(minutes=30)).isoformat()}'").toPandas())
clf = mlflow.sklearn.load_model(f"models:/{MODEL}/{mv.version}")
dev_scored = dev_feats[ID_COLUMNS + FEATURE_COLUMNS].assign(score=model.score(clf, dev_feats))
hold_scored = utc_frame(spark.sql(f"SELECT * FROM {FQ}.rca_holdout_scores").toPandas())

results = {}
for name, run, scored, lo in (("holdout", w["holdout_run"], hold_scored, None),
                              ("dev", w["train_run"], dev_scored, dev_lo)):
    inc = labels.prepare_incidents(utc_frame(spark.sql(queries(CAT, run)["incidents"]).toPandas()))
    inc = inc[inc["is_scored"] & ((inc["impact_start_ts"] >= lo) if lo is not None else True)]
    out = evaluate.case_outputs(scored, "score")  # GT-free outputs; same function as the evaluation
    per = evaluate.any_alert_at_sla(out, inc, threshold)
    ranks = evaluate.rank_incidents(out, inc)  # the oracle-matched metric on the same incidents, for reference
    summ = evaluate.any_alert_summary(per, ranks)
    meta = {"model_version": str(mv.version), "threshold": threshold}
    to_delta(per.assign(**meta), f"rca_eval_{name}_any_alert",
             f"Non-oracle companion ({name}, {run}): per scored incident, the region's live alerts at the first decision "
             f"time >= impact start + 5 min and whether any names a valid root. No footprint matching. Frozen v{mv.version}.")
    to_delta(summ.assign(**meta), f"rca_eval_{name}_any_alert_summary",
             f"Per fault type: any-alert-correct % next to the oracle-matched top-1 % ({name}, frozen v{mv.version}).")
    results[name] = summ.set_index("fault_type").loc["ALL"].to_dict()
    print(name, results[name])
dbutils.notebook.exit(json.dumps(results, default=str))
