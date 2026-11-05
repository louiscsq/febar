"""Step 4: Gen AI NOC assistant and proactive customer outage SMS drafts, governed through AI Gateway.

- `context`: grounded, structured incident context assembled from the build's own tables only (no PII, no
  ground truth; both are tested).
- `guards`: deterministic guardrails: alarm-text sanitising (prompt injection), PII / element-ID / operator
  name checks, SMS rules, the hallucination guard on the assistant's output.
- `schema`: the structured outputs (pydantic) and their JSON schemas.
- `prompts/`: the versioned prompt text.
- `llm`: the call to the AI-Gateway-governed Foundation Model endpoint (MLflow traced).
- `assistant`: NOC summary (A) and SMS drafts (B) end to end; the callable interface for the step-5 app.
- `gateway`: the AI Gateway configuration applied to the endpoint (inference table, guardrails, rate limits,
  usage tracking).
- `evalset`, `scorers`: evaluation set and code-based scorers for MLflow GenAI evaluation.

See docs/genai_assistant.md."""
