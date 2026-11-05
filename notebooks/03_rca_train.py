# Databricks notebook source
# MAGIC %md
# MAGIC # Train, evaluate and register the root-cause ranker
# MAGIC
# MAGIC 1. Builds detection-time candidate features for the labelled 1-minute run (`history_1m`) from the real-time
# MAGIC    gold / silver tables (`netmon_pipeline.rca.features`) and writes them to `netmon_rca.rca_candidate_features`.
# MAGIC 2. Labels the candidates from the ground truth (`netmon_rca.rca_training_labels`, kept in a separate table),
# MAGIC    excludes censored incidents, and splits **by time**: train on the first days, calibrate and pick the alert
# MAGIC    threshold on the next day, test on the last days (never tuned on).
# MAGIC 3. Trains a gradient-boosted classifier, logs it to MLflow (params, metrics, feature importance, signature,
# MAGIC    input example), registers it in Unity Catalog and moves the `champion` alias to the new version.
# MAGIC 4. Evaluates on the held-out days against the step-2 localiser on the same incidents, and on the live
# MAGIC    `stream` run as an extra out-of-run check; writes the tables `netmon_rca.rca_eval_*`.
# MAGIC
# MAGIC See docs/rca_model.md.

# COMMAND ----------

dbutils.widgets.text("catalog", "telco_netmon_febar_catalog")
dbutils.widgets.text("rca_schema", "netmon_rca")
dbutils.widgets.text("train_run", "history_1m")
dbutils.widgets.text("train_start", "2026-10-10")
dbutils.widgets.text("train_days", "3")
dbutils.widgets.text("val_days", "1")
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
    import netmon_pipeline  # noqa: F401  (installed from the bundle wheel in jobs)
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "src")))

import mlflow
import pandas as pd
from mlflow.models import infer_signature

from netmon_pipeline.rca import evaluate, labels, model, train
from netmon_pipeline.rca.features import FEATURE_COLUMNS, ID_COLUMNS
from netmon_pipeline.rca.sources import queries

w = {k: dbutils.widgets.get(k) for k in ["catalog", "rca_schema", "train_run", "train_start", "train_days",
                                          "val_days", "live_run", "model_name", "experiment"]}
CAT, SCH = w["catalog"], w["rca_schema"]
FQ = f"`{CAT}`.`{SCH}`"
MODEL = f"{CAT}.{SCH}.{w['model_name']}"
t_start = time.time()


def loader(run):
    cache = {}

    def load(name, region=None):
        key = (name, region)
        if key not in cache:
            cache.clear() if name == "topology" else None  # one region at a time: bounded driver memory
            cache[key] = spark.sql(queries(CAT, run, region)[name]).toPandas()
        return cache[key]

    return load


def regions():
    return [r[0] for r in spark.sql(f"SELECT DISTINCT region_code FROM `{CAT}`.netmon_silver.silver_topology_nodes "
                                    "ORDER BY 1").collect()]


def to_delta(df: pd.DataFrame, name: str, comment: str) -> None:
    sdf = spark.createDataFrame(df)
    sdf.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{FQ}.{name}")
    spark.sql(f"COMMENT ON TABLE {FQ}.{name} IS {json.dumps(comment)}")


def flat(df: pd.DataFrame) -> pd.DataFrame:
    """Lists to strings so the evaluation tables are easy to read in SQL and in the evidence."""
    out = df.copy()
    for c in out.columns:
        if out[c].map(lambda v: isinstance(v, list | tuple)).any():
            out[c] = out[c].map(lambda v: ",".join(map(str, v)) if isinstance(v, list | tuple) else v)
    return out

# COMMAND ----------

# MAGIC %md ## 1-2. Features, labels, time split

# COMMAND ----------

load = loader(w["train_run"])
feats = train.build_features(load, regions())
to_delta(feats[ID_COLUMNS + FEATURE_COLUMNS], "rca_candidate_features",
         "Detection-time candidate features per (case = run x region x 1-minute decision time, element). Built only "
         "from real-time tables (gold_cell_health_1m on-time windows, silver_alarms by arrival, topology, change "
         "calendar); feature_evidence_ts <= decision_ts. No ground truth.")
gt = spark.sql(queries(CAT, w["train_run"])["incidents"]).toPandas()
cmp_ = {k: spark.sql(queries(CAT, w["train_run"])[k]).toPandas()
        for k in ("baseline", "step2_localisation", "step2_detections")}
split = model.TimeSplit.by_days(pd.Timestamp(w["train_start"], tz="UTC"), int(w["train_days"]), int(w["val_days"]))
print(split)

# COMMAND ----------

# MAGIC %md ## 3. Train + calibrate (MLflow), 4. evaluate

# COMMAND ----------

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(w["experiment"])
with mlflow.start_run(run_name=f"rca_ranker_{w['train_run']}") as run:
    res = train.train_and_evaluate(feats, gt, split, cmp_["baseline"], cmp_["step2_localisation"],
                                   cmp_["step2_detections"])
    d = res.data
    to_delta(d[["source_run", "case_id", "decision_ts", "region_code", "element_id", "case_label", "is_root",
                "split", "score"]],
             "rca_training_labels",
             "LABELS (ground truth) and split per candidate row of rca_candidate_features: is_root = candidate is in a "
             "matched uncensored fault's root_element_ids; case_label in step-2 priority; split by decision time with "
             "an incident embargo; score = calibrated model score. Censored cases excluded.")
    counts = d.groupby("split").agg(rows=("is_root", "size"), positives=("is_root", "sum"),
                                    cases=("case_id", "nunique")).reset_index()
    mlflow.log_params({**{f"hgb_{k}": v for k, v in model.PARAMS.items()},
                       "model_type": "sklearn HistGradientBoostingClassifier + isotonic calibration (validation days)",
                       "train_run": w["train_run"], "val_start": str(split.val_start),
                       "test_start": str(split.test_start), "n_features": len(FEATURE_COLUMNS),
                       "alert_threshold": res.threshold, "decision_step_minutes": 1,
                       **{f"rows_{r.split}": int(r.rows) for r in counts.itertuples()},
                       **{f"positives_{r.split}": int(r.positives) for r in counts.itertuples()}})

    # Extra out-of-run check on the live stream (different run and day; not used for any choice).
    live_load = loader(w["live_run"])
    live_feats = train.build_features(live_load, regions())
    live_gt = spark.sql(queries(CAT, w["live_run"])["incidents"]).toPandas()
    live_inc = labels.prepare_incidents(live_gt)
    live = labels.label(live_feats, live_inc)
    live = live[live["case_label"] != "censored"].assign(score=lambda x: model.score(res.model, x))
    live_base = spark.sql(queries(CAT, w["live_run"])["baseline"]).toPandas()
    live_rank = evaluate.rank_incidents(live, live_inc).merge(
        live_base.rename(columns={"top_candidates": "baseline_top_candidates", "hit_at_1": "baseline_hit_at_1",
                                  "hit_at_3": "baseline_hit_at_3"}), on="incident_id", how="left")
    live_acc = evaluate.summarise(live_rank, {"model_top1_pct": "hit_at_1", "baseline_top1_pct": "baseline_hit_at_1",
                                              "model_top3_pct": "hit_at_3", "baseline_top3_pct": "baseline_hit_at_3"})
    la = live_acc.set_index("fault_type").loc["ALL"]
    res.metrics.update({"live_n_incidents": int(la["n"]), "live_top1_pct": float(la["model_top1_pct"]),
                        "live_top3_pct": float(la["model_top3_pct"]),
                        "live_baseline_top1_pct": float(la["baseline_top1_pct"])})
    mlflow.log_metrics(res.metrics)

    # feature importance: permutation (average precision) on a sample of the validation rows
    val = d[d["split"] == "val"]
    imp = model.permutation_importance(res.model, val.sample(min(len(val), 60_000), random_state=0))
    with tempfile.TemporaryDirectory() as tmp:
        for name, df in {"feature_importance.csv": imp, "threshold_curve.csv": res.threshold_curve,
                         "split_counts.csv": counts, "live_accuracy.csv": live_acc,
                         **{f"{k}.csv": flat(v) for k, v in res.tables.items()}}.items():
            df.to_csv(os.path.join(tmp, name), index=False)
        mlflow.log_artifacts(tmp, artifact_path="evaluation")
    mlflow.log_text(json.dumps(FEATURE_COLUMNS, indent=1), "feature_columns.json")

    X = d.loc[d["split"] == "train", FEATURE_COLUMNS].head(5).astype("float64")
    sig = infer_signature(X, res.model.predict_proba(X))
    info = mlflow.sklearn.log_model(res.model, name="model", signature=sig, input_example=X,
                                    registered_model_name=MODEL, pyfunc_predict_fn="predict_proba",
                                    pip_requirements=["scikit-learn==" + __import__("sklearn").__version__,
                                                      "numpy", "pandas"])
    run_id = run.info.run_id

client = mlflow.MlflowClient(registry_uri="databricks-uc")
version = info.registered_model_version
client.set_registered_model_alias(MODEL, "champion", version)
client.set_model_version_tag(MODEL, version, "alert_threshold", str(res.threshold))
client.set_model_version_tag(MODEL, version, "train_run", w["train_run"])
client.set_model_version_tag(MODEL, version, "test_top1_pct", str(res.metrics["test_top1_pct"]))
client.update_registered_model(MODEL, description=(
    "Banksia NOC root-cause ranker: scores every candidate element of a customer-impact case (region x 1-minute "
    "decision time) as the likely root cause. Input: the detection-time features in feature_columns.json; output: "
    "predict_proba [p(not root), p(root)], calibrated. Rank candidates of a case by p(root). See docs/rca_model.md."))
print("run", run_id, "model", MODEL, "version", version, "metrics", res.metrics)

# COMMAND ----------

# MAGIC %md ## Evaluation tables

# COMMAND ----------

meta = {"mlflow_run_id": run_id, "model_version": str(version), "threshold": res.threshold}
for k, v in res.tables.items():
    to_delta(flat(v).assign(**meta), f"rca_eval_{k}", f"RCA model evaluation ({k}) on {w['train_run']}, MLflow run "
             f"{run_id}, model version {version}. Step-2 columns: eval_rca_baseline / eval_incident_detection.")
to_delta(flat(live_acc).assign(**meta, source_run=w["live_run"]), "rca_eval_live_accuracy",
         "Top-1 / top-3 on the live stream run (out-of-run check), model vs step-2 baseline.")
to_delta(flat(live_rank).assign(**meta), "rca_eval_live_ranking", "Per live incident ranking, model vs step 2.")
to_delta(imp.assign(**meta), "rca_feature_importance", "Permutation importance (average precision) on validation.")
to_delta(pd.DataFrame([{**meta, "model": MODEL, "alias": "champion", **res.metrics,
                        "minutes": round((time.time() - t_start) / 60, 1)}]), "rca_training_runs",
         "One row per training run of the RCA ranker (latest overwrites).")
dbutils.jobs.taskValues.set("model_version", str(version))
