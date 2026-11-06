"""Apply the AI Gateway configuration (netmon_pipeline.genai.gateway) to the assistant's Foundation Model endpoint
and print the resulting config (no secrets are part of it).

    python scripts/genai_configure_gateway.py --profile febar [--catalog ...] [--schema netmon_genai]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from databricks.sdk import WorkspaceClient

from netmon_pipeline.genai import gateway


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="febar")
    ap.add_argument("--catalog", default="telco_netmon_febar_catalog")
    ap.add_argument("--schema", default="netmon_genai")
    ap.add_argument("--endpoint", default=gateway.ASSISTANT_ENDPOINT)
    ap.add_argument("--no-guardrails", action="store_true")
    ap.add_argument("--no-inference-table", action="store_true",
                    help="skip the inference table (it fails server-side on this workspace; see gateway.apply)")
    a = ap.parse_args()
    ws = WorkspaceClient(profile=a.profile)
    spec = gateway.GatewaySpec(a.catalog, a.schema, guardrails=not a.no_guardrails)
    res = gateway.apply(ws, a.endpoint, spec, inference_table=not a.no_inference_table)
    print(json.dumps({"errors": res["errors"], "config": gateway.current_config(ws, a.endpoint)},
                     indent=1, default=str))


if __name__ == "__main__":
    main()
