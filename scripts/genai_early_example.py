"""Worked examples where the ranker is not sure (scores below the alert threshold). The step-5 app can call the
assistant at any time (`service.summarise_open_incident`), so both are real situations. Writes
evidence/step4/03b_early_and_ambiguous_examples.md:

1. a DEV slow-backhaul incident a few minutes before the SLA moment, when every suspect's score is still low;
2. a DEV impact cluster with no fault behind it (noise / red herring) and low scores: the assistant should answer
   "uncertain" rather than guess.

The case rows and their calibrated scores come from `rca_candidate_features` + `rca_training_labels.score` (the
frozen champion's scores of the dev days); ground truth only picks *which* dev incident to show and is printed for
the reader, never put in the prompt.

    python scripts/genai_early_example.py --profile febar --warehouse <id>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import pandas as pd
from databricks.sdk import WorkspaceClient

from netmon_pipeline.genai import assistant, service, sources
from netmon_pipeline.genai import context as C

OUT = Path(__file__).resolve().parents[1] / "evidence" / "step4" / "03b_early_and_ambiguous_examples.md"
CAT = "telco_netmon_febar_catalog"
THRESHOLD = 0.32


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="febar")
    ap.add_argument("--warehouse", required=True)
    a = ap.parse_args()
    ws = WorkspaceClient(profile=a.profile)
    import mlflow  # traces go to the workspace experiment, never to a local store

    mlflow.set_tracking_uri(f"databricks://{a.profile}")
    mlflow.set_experiment("/Shared/banksia_netmon/noc_assistant")
    sql = service.warehouse_sql(ws, a.warehouse)
    q = sources.Queries(CAT)
    # dev slow-backhaul incidents the ranker got right at the SLA moment (ground truth used for selection only)
    inc = sql(f"""SELECT l.eval_id, l.incident_id, l.root_element_ids, c.as_of, c.ranker_top1
                  FROM {CAT}.netmon_eval.genai_eval_labels l JOIN {CAT}.netmon_genai.genai_eval_contexts c USING (eval_id)
                  WHERE l.split = 'dev' AND l.fault_type = 'BACKHAUL_DEGRADATION' AND l.ranker_hit_at_1
                  ORDER BY l.incident_id""")
    pick = None
    for r in inc.itertuples(index=False):
        t = pd.Timestamp(r.as_of)
        early = sql(f"""SELECT f.case_id, f.decision_ts, max(t.score) AS case_top
                        FROM {CAT}.netmon_rca.rca_candidate_features f
                        JOIN {CAT}.netmon_rca.rca_training_labels t
                          ON t.source_run = f.source_run AND t.case_id = f.case_id AND t.element_id = f.element_id
                        WHERE f.source_run = 'history_1m' AND f.case_id IN (
                              SELECT case_id FROM {CAT}.netmon_rca.rca_candidate_features
                              WHERE source_run = 'history_1m' AND element_id = '{r.ranker_top1}'
                                AND decision_ts BETWEEN '{(t - pd.Timedelta(minutes=8)):%Y-%m-%d %H:%M:%S}'
                                                    AND '{(t - pd.Timedelta(minutes=2)):%Y-%m-%d %H:%M:%S}')
                        GROUP BY 1, 2 HAVING max(t.score) < {THRESHOLD} AND max(t.score) > 0.02
                        ORDER BY decision_ts DESC LIMIT 1""")
        if len(early):
            pick = (r, early.iloc[0])
            break
    if pick is None:
        raise SystemExit("no early below-threshold backhaul case found on dev")
    r, e = pick

    def render(case_id: str, ref_name: str, title: str, note: str) -> list[str]:
        rows = sources.utc(sql(f"""SELECT f.*, t.score FROM {CAT}.netmon_rca.rca_candidate_features f
                                  JOIN {CAT}.netmon_rca.rca_training_labels t
                                    ON t.source_run = f.source_run AND t.case_id = f.case_id AND t.element_id = f.element_id
                                  WHERE f.source_run = 'history_1m' AND f.case_id = '{case_id}'"""))
        rows = rows.drop(columns=[c for c in ("is_root", "case_label", "split") if c in rows]).drop_duplicates("element_id")
        ref = sources.ref_from_case(ref_name, rows, model_version="4", threshold=THRESHOLD)
        ctx = C.build_context(sources.load_inputs(sql, q, ref, "history_1m", rows))
        res = assistant.run(ctx, ws)
        d = res.as_dict()
        sus = ", ".join(f"`{s[0]}` {s[2]:.2f}" for s in ref.suspects)
        print(ref_name, res.summary["likely_root_cause"], res.summary["confidence"])
        return [f"## {title}\n", note + f" Context built at `{ref.as_of}`; ranker suspects (score): {sus}.\n",
                f"Assistant: **`{res.summary['likely_root_cause']}`**, confidence `{res.summary['confidence']}`, "
                f"hypothesis `{res.summary['fault_hypothesis']}`; generated by `{res.summary_report['generated_by']}`.\n",
                "### Context (input)\n", "```json\n" + json.dumps(ctx, indent=2) + "\n```\n",
                "### NOC summary (validated output)\n", "```json\n" + json.dumps(res.summary, indent=2) + "\n```\n",
                "### Guard report\n", "```json\n" + json.dumps(res.summary_report, indent=2) + "\n```\n",
                "### SMS drafts\n", "```json\n" + json.dumps(d["sms"], indent=2) + "\n```\n",
                "### Calls\n", "```json\n" + json.dumps(d["calls"], indent=2) + "\n```\n"]

    mins = (pd.Timestamp(r.as_of) - pd.Timestamp(e.decision_ts)).total_seconds() / 60
    parts = ["# Worked examples: the ranker is not yet sure (scores below the alert threshold)\n",
             f"Captured {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `scripts/genai_early_example.py` (dev data, "
             "after the dev evaluation; prompts unchanged). Ground truth lines are for the reader only.\n"]
    parts += render(e.case_id, "EARLY-dev-backhaul", f"1. Slow backhaul, {mins:.0f} min before the SLA moment",
                    f"Dev incident `{r.incident_id}` (ground truth: `BACKHAUL_DEGRADATION`, valid roots "
                    f"`{r.root_element_ids}`; at the SLA moment the ranker's top-1 is `{r.ranker_top1}`). The case's top "
                    f"score is **{float(e.case_top):.2f}**, below the alert threshold {THRESHOLD}.")
    noise = sql(f"""SELECT t.case_id, max(t.score) AS case_top, max(f.n_case_candidates) AS n_cand
                    FROM {CAT}.netmon_rca.rca_training_labels t JOIN {CAT}.netmon_rca.rca_candidate_features f
                      ON t.source_run = f.source_run AND t.case_id = f.case_id AND t.element_id = f.element_id
                    WHERE t.source_run = 'history_1m' AND t.split = 'dev' AND t.case_label IN ('none', 'red_herring')
                    GROUP BY 1 HAVING max(t.score) BETWEEN 0.05 AND 0.2 AND max(f.log_case_impacted_cells) >= 1.0
                    ORDER BY case_id LIMIT 1""")
    if len(noise):
        n0 = noise.iloc[0]
        parts += render(n0.case_id, "AMBIG-dev-noise", "2. An impact cluster with no fault behind it",
                        f"Dev case labelled `{'no fault'}` by ground truth (noise / red herring, shown for the reader "
                        f"only); top score **{float(n0.case_top):.2f}**.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
