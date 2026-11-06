"""Step 4 evaluation: code-based scorers and the summary metrics (ground truth only through `expectations`)."""

from __future__ import annotations

import pandas as pd

from netmon_pipeline.genai import evaluation, scorers


def _out(root, hyp="BACKHAUL_DEGRADATION", report=None, sms_by="llm", attempts=1, violations=()):
    rep = {"root_not_in_context": None, "unknown_element_ids": [], "invalid_evidence_fields": [], "n_repairs": 0,
           "impact_corrected": {}, "generated_by": "llm", "llm_status": "ok", **(report or {})}
    return {"summary": {"likely_root_cause": root, "fault_hypothesis": hyp, "confidence": "high",
                        "evidence": [{"statement": "s", "context_fields": ["kpi.n_cells"]}]},
            "summary_report": rep,
            "sms": [{"region_code": "NSW", "text": "t", "chars": 1, "generated_by": sms_by, "llm_violations": [],
                     "violations": list(violations), "llm_attempts": attempts, "status": "draft",
                     "requires_human_approval": True}],
            "latency_ms": 1000.0, "prompt_tokens": 100, "completion_tokens": 10, "n_calls": 2}


EXP = {"root_element_ids": ["BH-1"], "fault_type": "BACKHAUL_DEGRADATION"}


def test_llm_vs_ranker_categories():
    assert scorers.score_row(_out("BH-1"), EXP, "BH-1")["llm_vs_ranker"] == "same"
    assert scorers.score_row(_out("BH-1"), EXP, "SITE-1")["llm_vs_ranker"] == "changed_to_correct"
    assert scorers.score_row(_out("SITE-1"), EXP, "BH-1")["llm_vs_ranker"] == "changed_correct_to_wrong"
    assert scorers.score_row(_out("SITE-1"), EXP, "AGG-1")["llm_vs_ranker"] == "changed_wrong_to_wrong"
    r = scorers.score_row(_out("uncertain", "UNCERTAIN"), EXP, "BH-1")
    assert r["llm_vs_ranker"] == "uncertain_on_correct" and not r["answered"] and not r["root_agreement"]


def test_hallucination_evidence_and_sms_scores():
    r = scorers.score_row(_out("uncertain", report={"root_not_in_context": "BH-9", "unknown_element_ids": ["BH-9"],
                                                    "invalid_evidence_fields": ["x.y"]}), EXP, "BH-1")
    assert r["hallucinated_root"] and r["hallucinated_element"] and r["evidence_field_validity"] == 0.5
    ok = scorers.score_row(_out("BH-1"), EXP, "BH-1")
    assert ok["fault_hypothesis_match"] and ok["sms_compliant"] and ok["sms_llm_compliant"]
    t = scorers.score_row(_out("BH-1", sms_by="template", attempts=2), EXP, "BH-1")
    assert t["sms_compliant"] and not t["sms_llm_compliant"] and not t["sms_llm_compliant_after_repair"]


def test_summary_metrics():
    rows = [scorers.score_row(o, EXP, top) | {"fault_type": "BACKHAUL_DEGRADATION"}
            for o, top in ((_out("BH-1"), "BH-1"), (_out("uncertain", "UNCERTAIN"), "BH-1"),
                           (_out("SITE-1"), "BH-1"), (_out("BH-1"), "SITE-1"))]
    m = evaluation.summarise(pd.DataFrame(rows))
    assert m["n"] == 4 and m["llm_root_agreement_pct"] == 50.0 and m["ranker_top1_agreement_pct"] == 75.0
    assert m["answered_pct"] == 75.0 and m["llm_selective_accuracy_pct"] == 66.7
    assert m["changed_to_correct"] == 1 and m["changed_correct_to_wrong"] == 1 and m["uncertain_on_correct"] == 1
    assert m["latency_p50_ms"] == 1000.0
    by = evaluation.summarise(pd.DataFrame(rows), by="fault_type")
    assert list(by["group"]) == ["ALL", "BACKHAUL_DEGRADATION"]
