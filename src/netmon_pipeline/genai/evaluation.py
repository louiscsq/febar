"""MLflow GenAI evaluation of the assistant on one split of the evaluation set (`notebooks/09_genai_evaluate.py`,
and local dev iteration). The assistant (`predict_fn`) gets `inputs.context` only; ground truth is passed as
`expectations` to the scorers."""

from __future__ import annotations

import json
import os
import threading

import numpy as np
import pandas as pd

from netmon_pipeline.genai import assistant, gateway, llm, scorers

COST_FIELDS = ("latency_ms", "prompt_tokens", "completion_tokens")


def cases(ctx_df: pd.DataFrame, lab_df: pd.DataFrame) -> list[dict]:
    lab = lab_df.set_index("eval_id")
    out = []
    for r in ctx_df.itertuples(index=False):
        g = lab.loc[r.eval_id]
        roots = g["root_element_ids"]
        roots = json.loads(roots) if isinstance(roots, str) else list(roots)
        out.append({"eval_id": r.eval_id, "context": json.loads(r.context_json),
                    "expectations": {"root_element_ids": roots, "fault_type": g["fault_type"]},
                    "ranker_top1": r.ranker_top1, "fault_type": g["fault_type"], "incident_id": g["incident_id"]})
    return out


def run(case_list: list[dict], ws, run_name: str, endpoint: str = gateway.ASSISTANT_ENDPOINT,
        judge_endpoint: str | None = gateway.JUDGE_ENDPOINT, max_workers: int = 8,
        log: llm.RequestLog | None = None) -> tuple[pd.DataFrame, dict, object]:
    """Evaluate; returns (per-incident rows, summary metrics, MLflow EvaluationResult). Must run inside an active
    MLflow run (the caller sets the experiment and starts the run)."""
    import mlflow

    outputs: dict[str, dict] = {}
    lock = threading.Lock()

    def predict_fn(context: dict) -> dict:
        res = assistant.run(context, ws, endpoint, log=log)
        out = scorers.compact_output(res.as_dict())
        with lock:
            outputs[context["incident"]["ref"]] = out
        return out

    os.environ["MLFLOW_GENAI_EVAL_MAX_WORKERS"] = str(max_workers)
    data = [{"inputs": {"context": c["context"]}, "expectations": c["expectations"]} for c in case_list]
    sc = scorers.mlflow_scorers() + (scorers.llm_judges(judge_endpoint) if judge_endpoint else [])
    result = mlflow.genai.evaluate(data=data, predict_fn=predict_fn, scorers=sc)

    judged = _judge_values(result)
    rows = []
    for c in case_list:
        out = outputs.get(c["eval_id"])
        if out is None:
            continue
        row = {"eval_id": c["eval_id"], "incident_id": c["incident_id"], "fault_type": c["fault_type"],
               "ranker_top1": c["ranker_top1"], "llm_root": out["summary"]["likely_root_cause"],
               "root_element_ids": json.dumps(c["expectations"]["root_element_ids"]),
               **scorers.score_row(out, c["expectations"], c["ranker_top1"]),
               "sms_texts": json.dumps([d["text"] for d in out["sms"]]),
               "summary_json": json.dumps(out["summary"]), "summary_report_json": json.dumps(out["summary_report"]),
               "prompt_versions": json.dumps(out["prompt_versions"])}
        row.update(judged.get(c["eval_id"], {}))
        rows.append(row)
    df = pd.DataFrame(rows)
    return df, summarise(df), result


def _judge_values(result) -> dict[str, dict]:
    """eval_id -> {groundedness: bool, sms_guidelines: bool} from the evaluation result traces."""
    out: dict[str, dict] = {}
    try:
        df = result.result_df
    except Exception:  # noqa: BLE001
        return out
    if df is None or df.empty:
        return out
    for _, r in df.iterrows():
        req = r.get("request")
        try:
            ref = (req if isinstance(req, dict) else json.loads(req))["context"]["incident"]["ref"]
        except Exception:  # noqa: BLE001
            continue
        vals = {}
        for name in ("groundedness", "sms_guidelines"):
            v = r.get(f"{name}/value")
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                vals[name] = v if isinstance(v, bool) else str(v).strip().lower() in ("yes", "true", "pass")
        out[ref] = vals
    return out


def _pct(x: pd.Series) -> float | None:
    x = x.dropna()
    return None if x.empty else round(100.0 * x.astype(float).mean(), 1)


def summarise(df: pd.DataFrame, by: str | None = None) -> dict | pd.DataFrame:
    """Headline metrics (overall dict) or per-`by` table."""
    if by is not None:
        parts = [{"group": "ALL", **summarise(df)}] + [{"group": k, **summarise(g)} for k, g in df.groupby(by)]
        return pd.DataFrame(parts)
    if df.empty:
        return {"n": 0}
    ans = df[df["answered"]]
    lat = df["latency_ms"].astype(float)
    m = {"n": len(df),
         "llm_root_agreement_pct": _pct(df["root_agreement"]),
         "ranker_top1_agreement_pct": _pct(df["ranker_top1_agreement"]),
         "answered_pct": _pct(df["answered"]),
         "llm_selective_accuracy_pct": _pct(ans["root_agreement"]) if len(ans) else None,
         "ranker_top1_on_answered_pct": _pct(ans["ranker_top1_agreement"]) if len(ans) else None,
         "changed_to_correct": int((df["llm_vs_ranker"] == "changed_to_correct").sum()),
         "changed_correct_to_wrong": int((df["llm_vs_ranker"] == "changed_correct_to_wrong").sum()),
         "changed_wrong_to_wrong": int((df["llm_vs_ranker"] == "changed_wrong_to_wrong").sum()),
         "uncertain_on_correct": int((df["llm_vs_ranker"] == "uncertain_on_correct").sum()),
         "uncertain_on_wrong": int((df["llm_vs_ranker"] == "uncertain_on_wrong").sum()),
         "fault_hypothesis_match_pct": _pct(df["fault_hypothesis_match"]),
         "hallucinated_root_pct": _pct(df["hallucinated_root"]),
         "hallucinated_element_pct": _pct(df["hallucinated_element"]),
         "evidence_field_validity_pct": _pct(df["evidence_field_validity"]),
         "fallback_pct": _pct(df["fallback"]),
         "sms_compliant_pct": _pct(df["sms_compliant"]),
         "sms_llm_first_try_compliant_pct": _pct(df["sms_llm_compliant"]),
         "sms_llm_compliant_after_repair_pct": _pct(df["sms_llm_compliant_after_repair"]),
         "latency_p50_ms": round(float(lat.quantile(0.5)), 0), "latency_p95_ms": round(float(lat.quantile(0.95)), 0),
         "prompt_tokens_mean": round(float(df["prompt_tokens"].astype(float).mean()), 0),
         "completion_tokens_mean": round(float(df["completion_tokens"].astype(float).mean()), 0)}
    for j in ("groundedness", "sms_guidelines"):
        if j in df:
            m[f"judge_{j}_pct"] = _pct(df[j])
    return m
