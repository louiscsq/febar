# Databricks notebook source
# MAGIC %md
# MAGIC # NOC assistant on the open incidents: root-cause summary, next steps, customer SMS drafts
# MAGIC
# MAGIC Triggered when `netmon_rca.open_incidents` changes (job `banksia-genai-assistant`, table-update trigger), or
# MAGIC run by hand. For every open incident that is **new or whose suspects changed** (`store.suspects_signature`),
# MAGIC it builds the grounded context (`netmon_pipeline.genai.service.load_open_incident_context`), calls the
# MAGIC AI-Gateway-governed endpoint (`assistant.run`, MLflow traced) and writes:
# MAGIC
# MAGIC - `netmon_genai.incident_ai_summaries` (append) and `customer_notice_drafts` (append, `status = 'draft'`,
# MAGIC   human approval required, never sent by this job);
# MAGIC - `netmon_genai.incident_ai_latest` (MERGE, Change Data Feed): latest summary + SMS per open incident, closed
# MAGIC   incidents deleted; then triggers its Lakebase synced table `lb_incident_ai_latest` for the step-5 app;
# MAGIC - `netmon_genai.noc_assistant_request_log` (append): every LLM request / response.
# MAGIC
# MAGIC Unchanged incidents cost nothing: no context is built and no LLM is called for them.

# COMMAND ----------

dbutils.widgets.text("catalog", "telco_netmon_febar_catalog")
dbutils.widgets.text("rca_schema", "netmon_rca")
dbutils.widgets.text("genai_schema", "netmon_genai")
dbutils.widgets.text("model_name", "rca_ranker")
dbutils.widgets.text("max_incidents", "50")
dbutils.widgets.dropdown("force", "false", ["true", "false"])
dbutils.widgets.dropdown("sync_lakebase", "true", ["true", "false"])
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

from netmon_pipeline.genai import assistant, llm, service, store
from netmon_pipeline.rca.live import conform
from netmon_pipeline.rca.sources import utc_frame

spark.conf.set("spark.sql.session.timeZone", "UTC")
w = {k: dbutils.widgets.get(k) for k in ["catalog", "rca_schema", "genai_schema", "model_name", "max_incidents",
                                          "force", "sync_lakebase", "experiment"]}
CAT = w["catalog"]
R, G = f"`{CAT}`.`{w['rca_schema']}`", f"`{CAT}`.`{w['genai_schema']}`"
t_wall = time.time()

mlflow.set_registry_uri("databricks-uc")
mv = mlflow.MlflowClient(registry_uri="databricks-uc").get_model_version_by_alias(
    f"{CAT}.{w['rca_schema']}.{w['model_name']}", "champion")
threshold = float(mv.tags["alert_threshold"])
ws = WorkspaceClient()
ws.workspace.mkdirs(os.path.dirname(w["experiment"]))
mlflow.set_experiment(w["experiment"])  # traces of every assistant call land here


def sql(q: str) -> pd.DataFrame:
    return utc_frame(spark.sql(q).toPandas())


open_inc = sql(f"SELECT * FROM {R}.open_incidents")
latest_tbl = f"{G}.incident_ai_latest"
prev = sql(f"SELECT * FROM {latest_tbl}") if spark.catalog.tableExists(latest_tbl.replace("`", "")) else pd.DataFrame()
prev_sig = dict(zip(prev["incident_id"], prev["suspects_signature"], strict=True)) if len(prev) else {}
todo = [r for r in open_inc.to_dict("records")
        if w["force"] == "true" or prev_sig.get(r["incident_id"]) != store.suspects_signature(r)]
todo = todo[: int(w["max_incidents"])]
print(len(open_inc), "open incidents;", len(todo), "new or changed; threshold", threshold)

# COMMAND ----------

log = llm.RequestLog()
now = pd.Timestamp.now(tz="UTC")
summaries, drafts, latest_new, failures = [], [], [], []
for inc in todo:
    try:
        ctx = service.load_open_incident_context(inc["incident_id"], sql, CAT, threshold)
        res = assistant.run(ctx, ws, log=log)
    except Exception as e:  # noqa: BLE001 - one bad incident must not stop the others
        failures.append({"incident_id": inc["incident_id"], "error": str(e)[:500]})
        continue
    s, d, lt = store.rows_for(inc, ctx, res, now)
    summaries.append(s)
    drafts += d
    latest_new.append(lt)
    print(inc["incident_id"], s["likely_root_cause"], s["confidence"], s["generated_by"],
          [x["text"] for x in d], f"{s['latency_ms']:.0f} ms")

# COMMAND ----------


def append(rows: list[dict], name: str, ddl: str, comment: str) -> None:
    if not rows:
        return
    spark.createDataFrame(conform(pd.DataFrame(rows), ddl), schema=ddl).write.mode("append") \
        .option("mergeSchema", "true").saveAsTable(f"{G}.{name}")
    spark.sql(f"COMMENT ON TABLE {G}.{name} IS {json.dumps(comment)}")


append(summaries, "incident_ai_summaries", store.SUMMARY_DDL,
       "Every NOC assistant summary (status = draft, for NOC review): incident, endpoint / prompt / context / ranker "
       "versions, generated_at, likely root cause (a suspect or 'uncertain'), evidence, next steps, customer impact, "
       "guard report, latency, tokens, and the grounded context. Append-only history.")
append(drafts, "customer_notice_drafts", store.DRAFT_DDL,
       "Proactive customer outage SMS DRAFTS, one per incident x affected region. status = 'draft' and "
       "requires_human_approval = true always; approved_by / approved_at / sent_at stay NULL: this system never sends. "
       "A human approves and sends from the customer-communications tool.")

# latest per OPEN incident: new rows for processed incidents, previous rows for unchanged ones, closed ones dropped
keep = prev[prev["incident_id"].isin(set(open_inc["incident_id"]) - {r["incident_id"] for r in latest_new})] \
    if len(prev) else pd.DataFrame()
latest = pd.concat([keep, pd.DataFrame(latest_new)], ignore_index=True).assign(refreshed_at=now)
src = spark.createDataFrame(conform(latest, store.LATEST_DDL), schema=store.LATEST_DDL)
if not spark.catalog.tableExists(latest_tbl.replace("`", "")):
    src.limit(0).write.saveAsTable(latest_tbl)
    spark.sql(f"ALTER TABLE {latest_tbl} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
    spark.sql(f"ALTER TABLE {latest_tbl} ALTER COLUMN incident_id SET NOT NULL")
    spark.sql(f"ALTER TABLE {latest_tbl} ADD CONSTRAINT incident_ai_latest_pk PRIMARY KEY (incident_id)")
spark.sql(f"COMMENT ON TABLE {latest_tbl} IS 'Latest NOC assistant summary and SMS draft per open incident (status = "
          "draft). Source of the Lakebase synced table lb_incident_ai_latest read by the step-5 app.'")
src.createOrReplaceTempView("src_latest")
cols = [c.strip().split(" ")[0] for c in store.LATEST_DDL.split(",")]
spark.sql(f"""MERGE INTO {latest_tbl} t USING src_latest s ON t.incident_id = s.incident_id
              WHEN MATCHED THEN UPDATE SET {", ".join(f"t.{c} = s.{c}" for c in cols if c != "incident_id")}
              WHEN NOT MATCHED THEN INSERT *
              WHEN NOT MATCHED BY SOURCE THEN DELETE""")
n_log = store.write_request_log(spark, log, f"{G}.noc_assistant_request_log")

# COMMAND ----------

# MAGIC %md ## Trigger the Lakebase synced table (TRIGGERED mode reads the change feed)

# COMMAND ----------

synced = {}
if w["sync_lakebase"] == "true":
    name = f"{CAT}.{w['genai_schema']}.lb_incident_ai_latest"
    try:
        st_ = ws.database.get_synced_database_table(name)
        upd = ws.pipelines.start_update(st_.data_synchronization_status.pipeline_id)
        synced[name] = upd.update_id
    except Exception as e:  # noqa: BLE001 - first run: the synced table is created by the next bundle deploy
        print("no synced table yet", name, str(e)[:200])
out = {"open": len(open_inc), "processed": len(summaries), "skipped_unchanged": len(open_inc) - len(todo),
       "failures": failures, "sms_drafts": len(drafts), "llm_calls": n_log, "synced": synced,
       "prompt_tokens": int(sum(s["prompt_tokens"] or 0 for s in summaries)),
       "completion_tokens": int(sum(s["completion_tokens"] or 0 for s in summaries)),
       "minutes": round((time.time() - t_wall) / 60, 1)}
print(json.dumps(out, indent=1))
dbutils.notebook.exit(json.dumps(out))
