"""Local prompt iteration on the DEV split only (the holdout is evaluated once, by the job, never from here).

Reads the evaluation set from Unity Catalog through a SQL warehouse, runs the same `genai.evaluation.run` as the
job (assistant through the governed endpoint, MLflow GenAI evaluation logged to the workspace experiment) and
prints the headline metrics.

    python scripts/genai_eval_local.py --profile febar --warehouse <id> --limit 40 [--no-judges]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import mlflow
from databricks.sdk import WorkspaceClient

from netmon_pipeline.genai import evaluation, gateway, service


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="febar")
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--catalog", default="telco_netmon_febar_catalog")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-judges", action="store_true")
    ap.add_argument("--experiment", default="/Shared/banksia_netmon/noc_assistant")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    ws = WorkspaceClient(profile=a.profile)
    sql = service.warehouse_sql(ws, a.warehouse)
    ctx = sql(f"SELECT * FROM {a.catalog}.netmon_genai.genai_eval_contexts WHERE split = 'dev'")
    lab = sql(f"SELECT * FROM {a.catalog}.netmon_eval.genai_eval_labels WHERE split = 'dev'")
    if a.limit:
        ctx = ctx.sample(n=min(a.limit, len(ctx)), random_state=a.seed).sort_values("eval_id")
    mlflow.set_tracking_uri(f"databricks://{a.profile}")
    mlflow.set_experiment(a.experiment)
    with mlflow.start_run(run_name="genai_eval_dev_local"):
        mlflow.set_tag("split", "dev")
        rows, metrics, _ = evaluation.run(evaluation.cases(ctx, lab), ws, "dev_local",
                                          judge_endpoint=None if a.no_judges else gateway.JUDGE_ENDPOINT)
        mlflow.log_metrics({k: float(v) for k, v in metrics.items() if isinstance(v, int | float)})
    print(json.dumps(metrics, indent=1))
    cols = ["eval_id", "fault_type", "ranker_top1", "llm_root", "llm_vs_ranker", "confidence", "fault_hypothesis",
            "hallucinated_element", "sms_llm_compliant", "latency_ms"]
    print(rows[cols].to_string(index=False))
    if a.out:
        rows.to_json(a.out, orient="records", lines=True)


if __name__ == "__main__":
    main()
