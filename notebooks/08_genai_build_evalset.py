# Databricks notebook source
# MAGIC %md
# MAGIC # Build the Gen AI assistant's evaluation set: grounded contexts (no ground truth) + labels (kept apart)
# MAGIC
# MAGIC One evaluation case per scored step-3 incident that had a case output at the SLA moment, on two splits:
# MAGIC - **dev**: `history_1m` 2026-10-14 … 10-15 (step 3's dev days). Prompt iteration happens here only.
# MAGIC - **holdout**: `holdout_1m` 2026-10-17 … 10-18 (step 3's fresh holdout). Scored once, never tuned on.
# MAGIC
# MAGIC The case and its decision time are the ones step 3 judged (`rca_eval_{split}_ranking`: the primary case at the
# MAGIC first decision time >= impact start + 5 min). Its candidate rows are the frozen champion's GT-free scores
# MAGIC (`rca_holdout_scores`; dev: `rca_candidate_features` scored with the same champion), so the suspects are exactly
# MAGIC what the ranker published. The context is then built with `netmon_pipeline.genai.context.build_context` from
# MAGIC operational tables only.
# MAGIC
# MAGIC Writes
# MAGIC - `netmon_genai.genai_eval_contexts`: eval_id, split, as_of, context_json (what the LLM sees; **no ground truth**);
# MAGIC - `netmon_eval.genai_eval_labels`: eval_id, ground-truth roots / fault type / subscriber estimate and the
# MAGIC   ranker's step-3 hits (**scoring only**, never joined into a prompt).

# COMMAND ----------

dbutils.widgets.text("catalog", "telco_netmon_febar_catalog")
dbutils.widgets.text("rca_schema", "netmon_rca")
dbutils.widgets.text("genai_schema", "netmon_genai")
dbutils.widgets.text("eval_schema", "netmon_eval")
dbutils.widgets.text("train_run", "history_1m")
dbutils.widgets.text("holdout_run", "holdout_1m")
dbutils.widgets.text("dev_start", "2026-10-14")
dbutils.widgets.text("model_name", "rca_ranker")

# COMMAND ----------

import hashlib
import json
import os
import sys

try:
    import netmon_pipeline  # noqa: F401
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "src")))

import mlflow
import pandas as pd

from netmon_pipeline.genai import context as C
from netmon_pipeline.genai import sources as GS
from netmon_pipeline.rca import labels, model
from netmon_pipeline.rca.features import FEATURE_COLUMNS, ID_COLUMNS
from netmon_pipeline.rca.sources import queries, utc_frame

spark.conf.set("spark.sql.session.timeZone", "UTC")
w = {k: dbutils.widgets.get(k) for k in ["catalog", "rca_schema", "genai_schema", "eval_schema", "train_run",
                                          "holdout_run", "dev_start", "model_name"]}
CAT = w["catalog"]
R, G, E = (f"`{CAT}`.`{w[k]}`" for k in ("rca_schema", "genai_schema", "eval_schema"))
MODEL = f"{CAT}.{w['rca_schema']}.{w['model_name']}"
SCRATCH = f"/Volumes/{CAT}/{w['rca_schema']}/scratch/genai_evalset"

mlflow.set_registry_uri("databricks-uc")
mv = mlflow.MlflowClient(registry_uri="databricks-uc").get_model_version_by_alias(MODEL, "champion")
threshold = float(mv.tags["alert_threshold"])
print("champion v", mv.version, "threshold", threshold)


def sql(q: str) -> pd.DataFrame:
    return utc_frame(spark.sql(q).toPandas())


def in_list(vals) -> str:
    return "(" + ", ".join("'" + str(v).replace("'", "''") + "'" for v in sorted(set(vals))) + ")"


def to_delta(df: pd.DataFrame, fq: str, comment: str) -> None:
    os.makedirs(SCRATCH, exist_ok=True)
    path = f"{SCRATCH}/{fq.split('.')[-1].strip('`')}.parquet"
    out = df.copy()
    out.attrs = {}
    out.to_parquet(path, index=False, coerce_timestamps="us", allow_truncated_timestamps=True)
    spark.read.parquet(path).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(fq)
    spark.sql(f"COMMENT ON TABLE {fq} IS {json.dumps(comment)}")


topo_all = sql(f"SELECT {', '.join(C.TOPOLOGY_COLUMNS)} FROM `{CAT}`.netmon_silver.silver_topology_nodes")

# COMMAND ----------

clf = None
ctx_rows, label_rows = [], []
for split, run in (("dev", w["train_run"]), ("holdout", w["holdout_run"])):
    rk = sql(f"SELECT * FROM {R}.rca_eval_{split}_ranking")
    gt = labels.prepare_incidents(sql(queries(CAT, run)["incidents"])).set_index("incident_id")
    with_case = rk[rk["case_id"].notna() & (rk["case_id"] != "")]
    case_ids = sorted(with_case["case_id"].unique())
    if split == "holdout":
        rows = sql(f"SELECT * FROM {R}.rca_holdout_scores WHERE case_id IN {in_list(case_ids)}")
    else:
        rows = sql(f"SELECT * FROM {R}.rca_candidate_features WHERE source_run = '{run}' AND case_id IN {in_list(case_ids)}")
        if clf is None:
            clf = mlflow.sklearn.load_model(f"models:/{MODEL}/{mv.version}")
        rows = rows[ID_COLUMNS + FEATURE_COLUMNS].assign(score=model.score(clf, rows))
    rows = rows.drop_duplicates(["case_id", "element_id"])
    by_case = dict(tuple(rows.groupby("case_id")))
    cells = sorted(set(rows.loc[(rows["level"] == 5) & (rows["n_impacted_cells"] > 0), "element_id"]))
    t_lo = (rows["decision_ts"].min() - pd.Timedelta(minutes=90)).strftime("%Y-%m-%d %H:%M:%S")
    t_hi = rows["decision_ts"].max().strftime("%Y-%m-%d %H:%M:%S")
    health = sql(f"SELECT {', '.join(C.HEALTH_COLUMNS)} FROM `{CAT}`.netmon_gold.gold_cell_health_1m "
                 f"WHERE source_run = '{run}' AND cell_id IN {in_list(cells)} "
                 f"AND window_start BETWEEN '{t_lo}' AND '{t_hi}'")
    sess = sql(f"SELECT {', '.join(C.SESSION_COLUMNS)} FROM `{CAT}`.netmon_gold.gold_cell_sessions_5m "
               f"WHERE cell_id IN {in_list(cells)} AND window_start BETWEEN '{t_lo}' AND '{t_hi}'")
    alarms = sql(f"SELECT {', '.join(C.ALARM_COLUMNS)} FROM `{CAT}`.netmon_silver.silver_alarms "
                 f"WHERE source_run = '{run}' AND event_ts BETWEEN '{t_lo}' AND '{t_hi}'")
    alarms = alarms.merge(topo_all[["element_id", "region_code"]], on="element_id", how="left")
    maint = sql(f"SELECT element_id, planned_start_ts, planned_end_ts FROM `{CAT}`.netmon_silver.silver_maintenance_windows "
                f"WHERE source_run = '{run}'")
    health_by_cell = dict(tuple(health.groupby("cell_id")))
    sess_by_cell = dict(tuple(sess.groupby("cell_id"))) if len(sess) else {}
    print(split, run, "cases", len(case_ids), "rows", len(rows), "cells", len(cells), "health", len(health),
          "sessions", len(sess), "alarms", len(alarms))
    for r in rk.itertuples(index=False):
        g = gt.loc[r.incident_id]
        eval_id = None
        if r.case_id in by_case:
            case = by_case[r.case_id]
            eval_id = f"EVAL-{split}-" + hashlib.sha1(f"{run}|{r.case_id}".encode()).hexdigest()[:12]
            ref = GS.ref_from_case(eval_id, case, model_version=str(mv.version), threshold=threshold)
            ccells, _ = C.impacted_cells(case)
            h = pd.concat([health_by_cell[c] for c in ccells if c in health_by_cell] or [pd.DataFrame()])
            s = pd.concat([sess_by_cell[c] for c in ccells if c in sess_by_cell] or [pd.DataFrame()])
            a = alarms[alarms["region_code"] == ref.region_code]
            ctx = C.build_context(C.ContextInputs(ref, case, topo_all[topo_all["region_code"] == ref.region_code],
                                                  a, h, s, maint, GS.XDR_SAMPLE_RATE["small"]))
            ctx_rows.append({"eval_id": eval_id, "split": split, "source_run": run, "as_of": ref.as_of,
                             "region_code": ref.region_code, "ranker_top1": ref.suspects[0][0],
                             "ranker_top1_score": ref.suspects[0][2], "n_suspects": len(ref.suspects),
                             "context_version": C.CONTEXT_VERSION, "context_json": C.to_json(ctx)})
        roots = list(g["roots"])
        label_rows.append({"eval_id": eval_id, "split": split, "source_run": run, "incident_id": r.incident_id,
                           "fault_type": r.fault_type, "root_element_ids": json.dumps(sorted(roots)),
                           "gt_estimated_impacted_subscribers": None if pd.isna(g.get("estimated_impacted_subscribers"))
                           else int(g["estimated_impacted_subscribers"]),
                           "ranker_hit_at_1": bool(r.hit_at_1), "ranker_hit_at_3": bool(r.hit_at_3),
                           "has_case_output": eval_id is not None, "model_version": str(mv.version)})

ctx_df, lab_df = pd.DataFrame(ctx_rows), pd.DataFrame(label_rows)
to_delta(ctx_df, f"{G}.genai_eval_contexts",
         "Gen AI evaluation set: one grounded incident context per scored step-3 incident with a case output at the SLA "
         "moment (dev = history_1m 10-14..10-15, holdout = holdout_1m). context_json is exactly what the assistant sees. "
         "No ground truth: labels are in netmon_eval.genai_eval_labels.")
to_delta(lab_df, f"{E}.genai_eval_labels",
         "Ground truth for the Gen AI evaluation (scoring only, never in a prompt): valid root list, fault type, GT "
         "subscriber estimate and the ranker's step-3 hits per scored incident; eval_id null = no case output.")
print(ctx_df.groupby("split").size().to_dict(), lab_df.groupby(["split", "has_case_output"]).size().to_dict())
dbutils.notebook.exit(json.dumps({"contexts": ctx_df.groupby("split").size().to_dict()}))
