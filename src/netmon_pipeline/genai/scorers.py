"""Scorers for the MLflow GenAI evaluation of the assistant. Ground truth reaches them as `expectations` only;
`predict_fn` (the assistant) never sees it.

Code-based (`score_row`, deterministic):
- `root_agreement`: the assistant's root is in the incident's valid root list (any listed element counts);
  "uncertain" counts as not agreeing. `ranker_top1_agreement`: the ranker's suspect #1 on the same case.
  `llm_vs_ranker`: same / changed_to_correct / changed_to_wrong / changed_wrong_to_wrong / uncertain_on_correct /
  uncertain_on_wrong: whether the LLM adds or loses accuracy.
- `answered`: not "uncertain"; `selective_accuracy` = agreement on answered cases (aggregated later).
- `hallucinated_root` / `hallucinated_element`: the raw output (before the guard's repair) named a root that is not a
  suspect / any element ID absent from the context. `evidence_field_validity`: share of cited context paths that exist.
- `fault_hypothesis_match`: the hypothesis maps to the ground-truth fault type (`schema.HYPOTHESIS_TO_FAULT_TYPES`).
- `sms_compliant` (final drafts) and `sms_llm_compliant` (the LLM's own draft passed every rule at the first try).
- latency and tokens per incident.

LLM judges (`llm_judges`, model `gateway.JUDGE_ENDPOINT`, a different model family from the assistant):
- `groundedness`: every factual claim of the summary, evidence and next steps is supported by the context;
- `sms_guidelines`: the SMS drafts are plain, calm, apologetic, blame-free and jargon-free.
"""

from __future__ import annotations

from netmon_pipeline.genai.schema import HYPOTHESIS_TO_FAULT_TYPES

UNCERTAIN = "uncertain"


def compact_output(res_dict: dict) -> dict:
    """What `predict_fn` returns (and the judges read): the validated outputs plus the guard report and costs."""
    return {"summary": res_dict["summary"], "summary_report": res_dict["summary_report"],
            "sms": [{k: d[k] for k in ("region_code", "text", "chars", "generated_by", "llm_violations", "violations",
                                       "llm_attempts", "status", "requires_human_approval")} for d in res_dict["sms"]],
            "prompt_versions": res_dict["prompt_versions"], "latency_ms": res_dict["latency_ms"],
            "prompt_tokens": res_dict["prompt_tokens"], "completion_tokens": res_dict["completion_tokens"],
            "n_calls": len(res_dict["calls"]), "call_status": [c["status"] for c in res_dict["calls"]]}


def score_row(outputs: dict, expectations: dict, ranker_top1: str | None) -> dict:
    roots = set(expectations.get("root_element_ids") or [])
    s, rep = outputs["summary"], outputs["summary_report"]
    root = s.get("likely_root_cause")
    llm_ok = root in roots
    rk_ok = ranker_top1 in roots
    if root == UNCERTAIN:
        cmp_ = "uncertain_on_correct" if rk_ok else "uncertain_on_wrong"
    elif root == ranker_top1:
        cmp_ = "same"
    elif llm_ok:
        cmp_ = "changed_to_correct"
    else:
        cmp_ = "changed_correct_to_wrong" if rk_ok else "changed_wrong_to_wrong"
    n_valid = sum(len(e.get("context_fields") or []) for e in s.get("evidence") or [])
    n_invalid = len(rep.get("invalid_evidence_fields") or [])
    hyp = s.get("fault_hypothesis")
    sms = outputs.get("sms") or []
    return {
        "root_agreement": llm_ok, "ranker_top1_agreement": rk_ok, "llm_vs_ranker": cmp_,
        "answered": root != UNCERTAIN, "confidence": s.get("confidence"), "fault_hypothesis": hyp,
        "fault_hypothesis_match": expectations.get("fault_type") in HYPOTHESIS_TO_FAULT_TYPES.get(hyp, set()),
        "hallucinated_root": rep.get("root_not_in_context") is not None,
        "hallucinated_element": bool(rep.get("unknown_element_ids")) or rep.get("root_not_in_context") is not None,
        "n_unknown_element_ids": len(rep.get("unknown_element_ids") or []),
        "evidence_field_validity": None if n_valid + n_invalid == 0 else n_valid / (n_valid + n_invalid),
        "n_evidence": len(s.get("evidence") or []), "n_repairs": rep.get("n_repairs", 0),
        "impact_corrected": bool(rep.get("impact_corrected")), "fallback": rep.get("generated_by") == "fallback",
        "llm_status": rep.get("llm_status"),
        "sms_compliant": bool(sms) and all(not d["violations"] for d in sms),
        "sms_llm_compliant": bool(sms) and all(d["generated_by"] == "llm" and d["llm_attempts"] == 1 for d in sms),
        "sms_llm_compliant_after_repair": bool(sms) and all(d["generated_by"] == "llm" for d in sms),
        "sms_max_chars": max((d["chars"] for d in sms), default=None),
        "latency_ms": outputs.get("latency_ms"), "prompt_tokens": outputs.get("prompt_tokens"),
        "completion_tokens": outputs.get("completion_tokens"), "n_calls": outputs.get("n_calls"),
    }


def mlflow_scorers(ranker_top1_key: str = "ranker_top1") -> list:
    """The code-based scorers as MLflow `@scorer`s (they read `expectations` only for ground truth)."""
    from mlflow.genai.scorers import scorer

    def _row(inputs, outputs, expectations):
        ctx = inputs["context"]
        top1 = ctx["suspects"][0]["element_id"] if ctx.get("suspects") else None
        return score_row(outputs, expectations, top1)

    @scorer(name="root_agreement")
    def root_agreement(inputs, outputs, expectations) -> bool:
        return _row(inputs, outputs, expectations)["root_agreement"]

    @scorer(name="ranker_top1_agreement")
    def ranker_top1_agreement(inputs, outputs, expectations) -> bool:
        return _row(inputs, outputs, expectations)["ranker_top1_agreement"]

    @scorer(name="answered")
    def answered(inputs, outputs, expectations) -> bool:
        return _row(inputs, outputs, expectations)["answered"]

    @scorer(name="no_hallucinated_element")
    def no_hallucinated_element(inputs, outputs, expectations) -> bool:
        return not _row(inputs, outputs, expectations)["hallucinated_element"]

    @scorer(name="fault_hypothesis_match")
    def fault_hypothesis_match(inputs, outputs, expectations) -> bool:
        return _row(inputs, outputs, expectations)["fault_hypothesis_match"]

    @scorer(name="sms_compliant")
    def sms_compliant(inputs, outputs, expectations) -> bool:
        return _row(inputs, outputs, expectations)["sms_compliant"]

    @scorer(name="sms_llm_compliant")
    def sms_llm_compliant(inputs, outputs, expectations) -> bool:
        return _row(inputs, outputs, expectations)["sms_llm_compliant"]

    return [root_agreement, ranker_top1_agreement, answered, no_hallucinated_element, fault_hypothesis_match,
            sms_compliant, sms_llm_compliant]


GROUNDEDNESS_INSTRUCTIONS = """You are auditing a network-operations assistant. {{ inputs }} holds the incident CONTEXT
(JSON) the assistant was given. {{ outputs }} holds its answer: `summary` (likely root cause, summary, evidence
statements, recommended next steps, customer impact) and `sms` drafts.

Is the answer GROUNDED in the context? Answer true only if every factual claim in summary.summary,
summary.evidence[].statement and summary.customer_impact.description is supported by the context (element IDs,
element types, numbers, alarm codes, times and trends must match the context), and the recommended next steps
only refer to elements and conditions present in the context. Generic runbook actions (e.g. "open a transport
ticket", "dispatch a technician") are allowed. A root cause of "uncertain" is acceptable. Do not judge whether
the root cause is correct, only whether the claims are supported. Answer false if any claim is unsupported or
contradicted."""

SMS_GUIDELINES = [
    "Each SMS draft in outputs.sms is plain English that a non-technical customer understands, with no network "
    "jargon, equipment names or internal identifiers.",
    "Each SMS draft is calm and apologetic, and blames no one (no supplier, contractor, weather, equipment or "
    "power company).",
    "No SMS draft promises a restoration time unless the context gives a maintenance end time (customer_eta).",
]


def llm_judges(model_endpoint: str) -> list:
    from mlflow.genai.judges import make_judge
    from mlflow.genai.scorers import Guidelines

    model = f"databricks:/{model_endpoint}"
    return [make_judge(name="groundedness", instructions=GROUNDEDNESS_INSTRUCTIONS, model=model,
                       feedback_value_type=bool),
            Guidelines(name="sms_guidelines", guidelines=SMS_GUIDELINES, model=model)]
