"""The call to the AI-Gateway-governed Foundation Model endpoint.

`chat_json` POSTs an OpenAI-style chat request with a strict JSON schema to
`/serving-endpoints/<endpoint>/invocations` with the caller's Databricks identity (job identity, app service
principal or the user's CLI login; no token is stored anywhere). The endpoint's AI Gateway applies the safety /
PII guardrails, rate limits and usage tracking. A request the gateway blocks comes back as an error and is
returned as `status="blocked"`, never retried.

Every call is an MLflow trace span (`span_type=LLM`) and appends one row to `RequestLog` (request, response,
status, tokens, latency), keyed by the `client_request_id` sent in the body, written by the jobs to `netmon_genai.noc_assistant_request_log`: the request /
response record that the gateway inference table would hold (it cannot be enabled on this workspace; see
`gateway.apply`).
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

try:
    import mlflow

    trace = mlflow.trace
except ImportError:  # mlflow is optional for unit tests of the pure parts
    mlflow = None

    def trace(func=None, **_kw):
        return func if func is not None else (lambda f: f)


GUARDRAIL_MARKERS = ("guardrail", "pii", "safety", "unsafe", "blocked", "content filter", "policy")
RETRYABLE = ("429", "rate limit", "REQUEST_LIMIT_EXCEEDED", "temporarily", "timed out", "503", "502", "504")


@dataclass
class LlmResult:
    request_id: str
    endpoint: str
    purpose: str
    status: str  # ok | blocked | error | invalid_json
    content: dict | None
    raw_text: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: float
    error: str | None = None
    attempts: int = 1
    response_id: str | None = None  # the model's own id (chatcmpl-...); request_id is our client_request_id


@dataclass
class RequestLog:
    """Request / response records of every LLM call (in place of the gateway inference table)."""

    rows: list[dict] = field(default_factory=list)

    def add(self, res: LlmResult, request: dict, prompt_version: str, incident_ref: str | None) -> None:
        self.rows.append({
            "request_id": res.request_id, "response_id": res.response_id, "request_time": datetime.now(timezone.utc).isoformat(),
            "endpoint": res.endpoint, "purpose": res.purpose, "prompt_version": prompt_version,
            "incident_ref": incident_ref, "status": res.status, "error": res.error,
            "latency_ms": round(res.latency_ms, 1), "attempts": res.attempts,
            "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
            "request_sha256": hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest(),
            "request": json.dumps(request), "response": res.raw_text})


def _is_guardrail_error(msg: str) -> bool:
    m = msg.lower()
    return any(k in m for k in GUARDRAIL_MARKERS) and ("400" in m or "invalid" in m or "block" in m or "guard" in m)


def _text(content) -> str:
    """Message content as text: a string, or a list of content parts (some models return parts)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return "" if content is None else str(content)


@trace(span_type="LLM")
def chat_json(ws, endpoint: str, messages: list[dict], schema: dict, schema_name: str, purpose: str,
              max_tokens: int = 1500, retries: int = 3, log: RequestLog | None = None, prompt_version: str = "",
              incident_ref: str | None = None) -> LlmResult:
    rid = str(uuid.uuid4())
    # `client_request_id` in the body is what the gateway's usage tracking records (system.serving.endpoint_usage), so
    # a usage row joins its request-log row on it; a header alone is not recorded.
    body = {"messages": messages, "max_tokens": max_tokens, "client_request_id": rid,
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": schema_name, "schema": schema, "strict": True}}}
    t0 = time.perf_counter()
    err, attempt = None, 0
    out = None
    while attempt < retries:
        attempt += 1
        try:
            out = ws.api_client.do("POST", f"/serving-endpoints/{endpoint}/invocations", body=body,
                                   headers={"Content-Type": "application/json", "X-Request-Id": rid})
            err = None
            break
        except Exception as e:  # noqa: BLE001 - classified below
            err = str(e)
            if _is_guardrail_error(err):
                res = LlmResult(rid, endpoint, purpose, "blocked", None, None, None, None,
                                (time.perf_counter() - t0) * 1000, err[:2000], attempt)
                if log is not None:
                    log.add(res, body, prompt_version, incident_ref)
                return res
            if not any(k.lower() in err.lower() for k in RETRYABLE):
                break
            time.sleep(min(20.0, 2.0 ** attempt))
    latency = (time.perf_counter() - t0) * 1000
    if err is not None or out is None:
        res = LlmResult(rid, endpoint, purpose, "error", None, None, None, None, latency, (err or "")[:2000], attempt)
    else:
        usage = out.get("usage") or {}
        text = _text(((out.get("choices") or [{}])[0].get("message") or {}).get("content"))
        try:
            content, status, perr = json.loads(text), "ok", None
        except (json.JSONDecodeError, TypeError) as e:
            content, status, perr = None, "invalid_json", str(e)
        res = LlmResult(rid, endpoint, purpose, status, content, text, usage.get("prompt_tokens"),
                        usage.get("completion_tokens"), latency, perr, attempt, response_id=out.get("id"))
    if mlflow is not None:
        span = mlflow.get_current_active_span()
        if span is not None:
            span.set_attributes({"endpoint": endpoint, "purpose": purpose, "status": res.status,
                                 "prompt_tokens": res.prompt_tokens or 0,
                                 "completion_tokens": res.completion_tokens or 0, "prompt_version": prompt_version})
    if log is not None:
        log.add(res, body, prompt_version, incident_ref)
    return res


def as_dict(res: LlmResult) -> dict:
    return asdict(res)
