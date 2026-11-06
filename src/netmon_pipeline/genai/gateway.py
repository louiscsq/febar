"""AI Gateway configuration of the Foundation Model endpoint the assistant calls.

The assistant calls a Databricks-hosted pay-per-token Foundation Model endpoint (`ASSISTANT_ENDPOINT`). On this
workspace a dedicated, bundle-managed endpoint cannot serve those models (they are not eligible for provisioned
throughput, and an external-model endpoint pointing back at them needs a stored API token), so AI Gateway is
configured on the pay-per-token endpoint itself, from code (`apply`, run by `scripts/genai_configure_gateway.py`).
See docs/genai_assistant.md, "Governance".

Configured features:

- **inference table**: every request / response is logged to `<catalog>.<genai schema>.<prefix>_payload`;
- **guardrails**: PII detection with BLOCK on input and output; the safety filter on the output. The input safety
  filter is off by default (`input_safety=False`): on this workspace it flagged benign NOC prompts (telemetry +
  runbook text) as "violent-crimes" on every try (3 / 3 identical requests blocked, the verdict flipping with harmless
  wording changes), which would block most summaries. Prompt injection in the input is handled by the
  deterministic `guards.sanitize_free_text`; PII by the gateway and `guards.assert_no_pii`;
- **rate limits**: per endpoint and per user (calls / minute), so a runaway job cannot exhaust the quota;
- **usage tracking**: token counts per request in `system.serving.endpoint_usage`.
"""

from __future__ import annotations

from dataclasses import dataclass

ASSISTANT_ENDPOINT = "databricks-gpt-5-4-mini"
JUDGE_ENDPOINT = "databricks-claude-sonnet-5-5"
TABLE_PREFIX = "noc_assistant"
ENDPOINT_CALLS_PER_MIN = 600
USER_CALLS_PER_MIN = 300


@dataclass(frozen=True)
class GatewaySpec:
    catalog: str
    schema: str
    table_prefix: str = TABLE_PREFIX
    guardrails: bool = True
    input_safety: bool = False  # see the module docstring: false positives on NOC telemetry prompts
    endpoint_calls_per_min: int = ENDPOINT_CALLS_PER_MIN
    user_calls_per_min: int = USER_CALLS_PER_MIN

    @property
    def payload_table(self) -> str:
        return f"{self.catalog}.{self.schema}.{self.table_prefix}_payload"


def desired_config(spec: GatewaySpec) -> dict:
    """The AI Gateway config as the REST API body (`PUT /api/2.0/serving-endpoints/{name}/ai-gateway`)."""
    cfg: dict = {
        "inference_table_config": {"enabled": True, "catalog_name": spec.catalog, "schema_name": spec.schema,
                                   "table_name_prefix": spec.table_prefix},
        "rate_limits": [
            {"calls": spec.endpoint_calls_per_min, "key": "endpoint", "renewal_period": "minute"},
            {"calls": spec.user_calls_per_min, "key": "user", "renewal_period": "minute"},
        ],
        "usage_tracking_config": {"enabled": True},
    }
    if spec.guardrails:
        cfg["guardrails"] = {
            "input": {"safety": spec.input_safety, "pii": {"behavior": "BLOCK"}},
            "output": {"safety": True, "pii": {"behavior": "BLOCK"}},
        }
    return cfg


def apply(ws, endpoint: str, spec: GatewaySpec, inference_table: bool = True) -> dict:
    """PUT the config. Features the workspace rejects are dropped one at a time (inference table first, then
    guardrails) and the error is reported, so the rest is still applied. Returns {config, errors}.

    On this workspace enabling the inference table on the pay-per-token endpoint fails server-side
    (`INTERNAL_ERROR: java.nio.channels.ClosedChannelException`, on every schema tried; the PUT creates an
    empty `<prefix>_payload` table before failing). The assistant then logs every request / response itself
    (`llm.RequestLog` -> `netmon_genai.noc_assistant_request_log`), with the gateway's usage tracking alongside."""
    path = f"/api/2.0/serving-endpoints/{endpoint}/ai-gateway"
    errors: dict[str, str] = {}
    attempts = [(inference_table, spec.guardrails), (False, spec.guardrails), (False, False)]
    for inf, guard in dict.fromkeys(attempts):
        body = desired_config(GatewaySpec(**{**spec.__dict__, "guardrails": guard}))
        if not inf:
            body.pop("inference_table_config")
        try:
            return {"config": ws.api_client.do("PUT", path, body=body), "errors": errors}
        except Exception as e:  # noqa: BLE001 - surfaced in the result and the evidence
            errors["inference_table" if inf else "guardrails"] = str(e)
    raise RuntimeError(f"AI Gateway config rejected: {errors}")


def current_config(ws, endpoint: str) -> dict:
    """The endpoint's AI Gateway section and identity (no secrets are part of it)."""
    ep = ws.api_client.do("GET", f"/api/2.0/serving-endpoints/{endpoint}")
    ents = (ep.get("config") or {}).get("served_entities") or [{}]
    fm = ents[0].get("foundation_model") or {}
    return {"name": ep.get("name"), "task": ep.get("task"), "state": ep.get("state"),
            "foundation_model": fm.get("name"), "ai_gateway": ep.get("ai_gateway")}
