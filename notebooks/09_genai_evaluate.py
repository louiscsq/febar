# Databricks notebook source
# MAGIC %md
# MAGIC # MLflow GenAI evaluation of the NOC assistant and the SMS drafts (one split)
# MAGIC
# MAGIC Reads the evaluation set (`netmon_genai.genai_eval_contexts`, no ground truth) and its labels
# MAGIC (`netmon_eval.genai_eval_labels`, passed to the scorers as `expectations` only), runs the assistant through the
# MAGIC AI-Gateway-governed endpoint for every case (`mlflow.genai.evaluate`, traced), and scores it with code-based
# MAGIC scorers and two LLM judges (`netmon_pipeline.genai.scorers`).
# MAGIC
# MAGIC - `split=dev`: prompt iteration happens on dev only.
# MAGIC - `split=holdout`: the final, one-shot run. The notebook refuses to overwrite an existing holdout result unless
# MAGIC   `force=true`.
# MAGIC
# MAGIC Writes `netmon_genai.genai_eval_results_<split>` (per incident), `genai_eval_summary_<split>` (overall and per
# MAGIC fault type) and appends the LLM request log to `netmon_genai.noc_assistant_request_log`.

# COMMAND ----------

dbutils.widgets.text("catalog", "telco_netmon_febar_catalog")
dbutils.widgets.text("genai_schema", "netmon_genai")
dbutils.widgets.text("eval_schema", "netmon_eval")
dbutils.widgets.dropdown("split", "dev", ["dev", "holdout"])
dbutils.widgets.text("limit", "0")
dbutils.widgets.dropdown("judges", "true", ["true", "false"])
dbutils.widgets.text("max_workers", "8")
dbutils.widgets.dropdown("force", "false", ["true", "false"])
dbutils.widgets.text("experiment", "/Shared/banksia_netmon/noc_assistant")

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
from databricks.sdk import WorkspaceClient

from netmon_pipeline.genai import assistant, evaluation, gateway, llm
from netmon_pipeline.genai.store import write_request_log

spark.conf.set("spark.sql.session.timeZone", "UTC")
w = {k: dbutils.widgets.get(k) for k in ["catalog", "genai_schema", "eval_schema", "split", "limit", "judges",
                                          "max_workers", "force", "experiment"]}
CAT, SPLIT = w["catalog"], w["split"]
G, E = f"`{CAT}`.`{w['genai_schema']}`", f"`{CAT}`.`{w['eval_schema']}`"
res_table = f"{G}.genai_eval_results_{SPLIT}"
if SPLIT == "holdout" and w["force"] != "true" and spark.catalog.tableExists(res_table.replace("`", "")):
    raise RuntimeError("holdout already evaluated once; set force=true only to reproduce, never to tune")

ctx_df = spark.sql(f"SELECT * FROM {G}.genai_eval_contexts WHERE split = '{SPLIT}' ORDER BY eval_id").toPandas()
lab_df = spark.sql(f"SELECT * FROM {E}.genai_eval_labels WHERE split = '{SPLIT}'").toPandas()
if int(w["limit"]) > 0:
    ctx_df = ctx_df.sample(n=min(int(w["limit"]), len(ctx_df)), random_state=7).sort_values("eval_id")
cases = evaluation.cases(ctx_df, lab_df)
n_scored = int(len(lab_df))
print(SPLIT, "cases", len(cases), "of", n_scored, "scored incidents")

# COMMAND ----------

ws = WorkspaceClient()
log = llm.RequestLog()
WorkspaceClient().workspace.mkdirs(os.path.dirname(w["experiment"]))
mlflow.set_experiment(w["experiment"])
t0 = time.time()
with mlflow.start_run(run_name=f"genai_eval_{SPLIT}") as run:
    versions = {"noc_summary": assistant.prompt(assistant.NOC_PROMPT)[1], "sms": assistant.prompt(assistant.SMS_PROMPT)[1]}
    mlflow.set_tags({"split": SPLIT, "assistant_endpoint": gateway.ASSISTANT_ENDPOINT,
                     "judge_endpoint": gateway.JUDGE_ENDPOINT if w["judges"] == "true" else "none", **versions})
    rows, metrics, result = evaluation.run(cases, ws, f"genai_eval_{SPLIT}",
                                           judge_endpoint=gateway.JUDGE_ENDPOINT if w["judges"] == "true" else None,
                                           max_workers=int(w["max_workers"]), log=log)
    # over every scored incident: incidents without a case output count as misses for both systems
    lab_all = lab_df.copy()
    metrics["n_scored_incidents"] = n_scored
    metrics["ranker_top1_all_scored_pct"] = round(100 * lab_all["ranker_hit_at_1"].astype(bool).mean(), 1)
    hit = set(rows.loc[rows["root_agreement"], "eval_id"])
    metrics["llm_root_agreement_all_scored_pct"] = round(100 * lab_all["eval_id"].isin(hit).mean(), 1) \
        if int(w["limit"]) == 0 else None
    metrics["wall_minutes"] = round((time.time() - t0) / 60, 1)
    mlflow.log_metrics({k: float(v) for k, v in metrics.items() if isinstance(v, int | float)})
    by_ft = evaluation.summarise(rows, by="fault_type")
    with open("/tmp/genai_eval_summary.json", "w") as f:
        json.dump(metrics, f, indent=1, default=str)
    mlflow.log_artifact("/tmp/genai_eval_summary.json")
    run_id = run.info.run_id
print(json.dumps(metrics, indent=1, default=str))

# COMMAND ----------

meta = {"mlflow_run_id": run_id, "split": SPLIT, "assistant_endpoint": gateway.ASSISTANT_ENDPOINT,
        "noc_prompt_version": versions["noc_summary"], "sms_prompt_version": versions["sms"]}


def save(df: pd.DataFrame, fq: str, comment: str) -> None:
    sdf = spark.createDataFrame(df.assign(**meta).astype({c: "object" for c in df.columns if df[c].dtype == object}))
    sdf.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(fq)
    spark.sql(f"COMMENT ON TABLE {fq} IS {json.dumps(comment)}")


save(rows.where(pd.notna(rows), None), res_table,
     f"Gen AI assistant evaluation ({SPLIT}): per incident, the assistant's root vs the ranker's top-1 vs ground truth, "
     f"guard repairs, SMS compliance, judges, latency and tokens. MLflow run {run_id}.")
summ = pd.concat([pd.DataFrame([{"group": "ALL_WITH_CASE", **metrics}]), by_ft[by_ft["group"] != "ALL"]],
                 ignore_index=True)
summ = summ.astype({c: "object" for c in summ.columns}).where(pd.notna(summ), None).astype(str)
save(summ, f"{G}.genai_eval_summary_{SPLIT}", f"Gen AI evaluation summary ({SPLIT}), overall and per fault type.")
write_request_log(spark, log, f"{G}.noc_assistant_request_log")
dbutils.notebook.exit(json.dumps(metrics, default=str))
