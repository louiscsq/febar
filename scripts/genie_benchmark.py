"""Run the NOC Genie space's benchmark (Genie eval-run API) and write evidence/step5/02_genie_benchmark.md.

    python scripts/genie_benchmark.py --profile febar --warehouse <id> [--space-id <id>]

The benchmark questions and expected SQL are part of the space definition (netmon_pipeline.genie_space.BENCHMARKS,
deployed by the bundle). Genie answers every question itself and grades it against the expected SQL's result
(assessment GOOD / BAD / NEEDS_REVIEW). For a reviewer, this script also runs Genie's SQL and the expected SQL on
the warehouse and prints both results side by side, so every miss can be checked by hand. Misses are kept.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from capture_evidence import Runner, md_table  # noqa: E402

from netmon_pipeline import genie_space  # noqa: E402

EVIDENCE = Path(__file__).resolve().parents[1] / "evidence" / "step5"


def space_id_from_bundle(profile: str) -> str:
    out = subprocess.run(["databricks", "bundle", "summary", "-t", "dev", "-p", profile, "-o", "json"],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)["resources"]["genie_spaces"]["noc_genie"]["id"]


def response_sql(resp: list[dict] | None) -> str:
    for r in resp or []:
        if r.get("response_type") == "SQL":
            return r.get("response", "")
    return "\n".join(r.get("response", "") for r in resp or [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="febar")
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--space-id")
    ap.add_argument("--catalog", default="telco_netmon_febar_catalog")
    ap.add_argument("--out", default="02_genie_benchmark.md")
    a = ap.parse_args()
    out = EVIDENCE / a.out
    r = Runner(a.profile, a.warehouse)
    space = a.space_id or space_id_from_bundle(a.profile)

    run = r.cli("genie", "genie-create-eval-run", space, body={})
    run_id = run["eval_run_id"]
    print("eval run", run_id)
    while run.get("eval_run_status") not in ("DONE", "FAILED", "CANCELLED"):
        time.sleep(10)
        run = r.cli("genie", "genie-get-eval-run", space, run_id)
        print(run.get("eval_run_status"), run.get("num_done"), "/", run.get("num_questions"))
    results = r.cli("genie", "genie-list-eval-results", space, run_id).get("eval_results", [])

    rows, details = [], []
    for res in results:
        det = r.cli("genie", "genie-get-eval-result-details", space, run_id, res["result_id"])
        q = res["question"]
        got, exp = response_sql(det.get("actual_response")), res.get("benchmark_answer", "")
        verdict = det.get("assessment") or det.get("eval_run_status", "?")
        reasons = det.get("assessment_reasons") or []
        rows.append([q, verdict, ", ".join(map(str, reasons))])
        block = [f"### {q}\n", f"Genie assessment: **{verdict}**" + (f" ({', '.join(map(str, reasons))})" if reasons else "") + "\n",
                 "Expected SQL:\n", "```sql\n" + exp.strip() + "\n```\n", "Genie's SQL:\n",
                 "```sql\n" + (got.strip() or "(no SQL: text answer)") + "\n```\n"]
        for label, sql in (("Expected result", exp), ("Genie's result", got)):
            if not sql.strip().lower().startswith(("select", "with")):
                continue
            try:
                c, data = r.sql(sql)
                block.append(f"{label}:\n\n" + md_table(c, data[:10], max_cell=80))
            except RuntimeError as e:
                block.append(f"{label}: error `{str(e).splitlines()[0][:200]}`\n")
        details.append("\n".join(block))

    n = len(results)
    good = sum(1 for x in rows if x[1] == "GOOD")
    review = sum(1 for x in rows if x[1] == "NEEDS_REVIEW")
    order = {q: i for i, (q, _) in enumerate(genie_space.BENCHMARKS)}
    paired = sorted(zip(rows, details, strict=True), key=lambda p: order.get(p[0][0], 99))
    text = [
        "# Genie benchmark: NOC space\n",
        f"Captured {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC from workspace profile `{a.profile}` by "
        f"`scripts/genie_benchmark.py` (Genie eval-run API, run `{run_id}`, space `{space}`).\n",
        f"**Score: {good} / {n} GOOD ({100 * good / max(n, 1):.0f} %)**, {review} needs review, "
        f"{n - good - review} bad. Graded by Genie against the expected SQL's result (run by the API as the "
        "capturing user, who is in `noc_national`, so all regions are visible). The questions and expected SQL are "
        "in `src/netmon_pipeline/genie_space.py` (`BENCHMARKS`); 4 of 18 are close paraphrases of a trusted example "
        "SQL, the rest are not.\n",
        "## Summary\n", md_table(["question", "assessment", "reasons"], [p[0] for p in paired], max_cell=140),
        "## Per question (expected vs Genie, both executed)\n", *[p[1] for p in paired],
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(text))
    print("wrote", out, f"score {good}/{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
