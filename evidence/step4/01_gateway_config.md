# AI Gateway configuration of the assistant endpoint

Captured 2026-11-06 02:26 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

The assistant calls the Databricks-hosted pay-per-token Foundation Model endpoint `databricks-gpt-5-4-mini` (GPT-5.4 mini). AI Gateway is
configured on it from code (`netmon_pipeline.genai.gateway`, applied by `scripts/genai_configure_gateway.py`). Below:
the live endpoint config as returned by the serving API (it holds no secrets), what the code asks for, and the
feature that the workspace rejects.

## Live endpoint AI Gateway config (GET /api/2.0/serving-endpoints/{name})

```json
{
  "name": "databricks-gpt-5-4-mini",
  "task": "llm/v1/chat",
  "state": {
    "ready": "READY",
    "config_update": "NOT_UPDATING"
  },
  "foundation_model": "system.ai.databricks-gpt-5-4-mini",
  "ai_gateway": {
    "usage_tracking_config": {
      "enabled": true
    },
    "rate_limits": [
      {
        "calls": 600,
        "key": "endpoint",
        "renewal_period": "minute"
      },
      {
        "calls": 300,
        "key": "user",
        "renewal_period": "minute"
      }
    ],
    "guardrails": {
      "input": {
        "safety": false,
        "pii_detection": true,
        "pii": {
          "behavior": "BLOCK"
        }
      },
      "output": {
        "safety": true,
        "pii_detection": true,
        "pii": {
          "behavior": "BLOCK"
        }
      }
    }
  }
}
```

## What the code asks for (`gateway.desired_config`)

```json
{
  "inference_table_config": {
    "enabled": true,
    "catalog_name": "telco_netmon_febar_catalog",
    "schema_name": "netmon_genai",
    "table_name_prefix": "noc_assistant"
  },
  "rate_limits": [
    {
      "calls": 600,
      "key": "endpoint",
      "renewal_period": "minute"
    },
    {
      "calls": 300,
      "key": "user",
      "renewal_period": "minute"
    }
  ],
  "usage_tracking_config": {
    "enabled": true
  },
  "guardrails": {
    "input": {
      "safety": false,
      "pii": {
        "behavior": "BLOCK"
      }
    },
    "output": {
      "safety": true,
      "pii": {
        "behavior": "BLOCK"
      }
    }
  }
}
```

## Feature status

| feature | status on this workspace |
|---|---|
| usage tracking | **on**: per-request tokens in `system.serving.endpoint_usage` (see `02_inference_log.md`) |
| rate limits | **on**: 600 calls / min per endpoint, 300 calls / min per user |
| PII guardrail, input | **on, BLOCK** (demonstrated in `06_guardrail_tests.md`) |
| PII guardrail, output | **on, BLOCK** |
| safety guardrail, output | **on** |
| safety guardrail, input | **off by choice**: flagged benign NOC prompts as "violent-crimes" on 3 / 3 identical requests (request `2f3ef1b0-83b2-4510-aef5-e7ce8ba81141`). Prompt injection is handled by `guards.sanitize_free_text` (tested live in `06_guardrail_tests.md`) |
| inference table | **fails to enable**: `PUT .../ai-gateway` with `inference_table_config` returns `500 INTERNAL_ERROR: java.nio.channels.ClosedChannelException` (request `1e3b343b-f98f-4784-a001-b5a9e67826a0`; same in schema `netmon_rca`), after creating an empty `<prefix>_payload` table (dropped). **Equivalent in code:** every request / response is logged by `llm.RequestLog` to `netmon_genai.noc_assistant_request_log` |
