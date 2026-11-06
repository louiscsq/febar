"""Structured outputs of the assistant (pydantic) and the strict JSON schemas sent as `response_format`."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# The assistant's fault hypothesis (a prediction from the evidence; the ground-truth fault type never enters a
# prompt). Mapped to the generator's fault types for scoring only (`HYPOTHESIS_TO_FAULT_TYPES`).
Hypothesis = Literal[
    "CELL_OUTAGE", "SITE_POWER_OUTAGE", "BACKHAUL_DEGRADATION", "BACKHAUL_CUT", "AGG_ROUTER_FAILURE",
    "LONG_HAUL_FIBRE_CUT", "CORE_CONGESTION", "AMF_OVERLOAD", "GRID_OUTAGE_CLUSTER", "PLANNED_WORK",
    "TRAFFIC_SURGE", "UNCERTAIN"]
HYPOTHESIS_TO_FAULT_TYPES = {
    "CELL_OUTAGE": {"CELL_OUTAGE"}, "SITE_POWER_OUTAGE": {"SITE_POWER_OUTAGE"},
    "BACKHAUL_DEGRADATION": {"BACKHAUL_DEGRADATION", "CYCLONE_BACKHAUL_CUT"},
    "BACKHAUL_CUT": {"CYCLONE_BACKHAUL_CUT"}, "AGG_ROUTER_FAILURE": {"AGG_ROUTER_FAILURE"},
    "LONG_HAUL_FIBRE_CUT": {"LONG_HAUL_FIBRE_CUT"}, "CORE_CONGESTION": {"CORE_CONGESTION"},
    "AMF_OVERLOAD": {"AMF_OVERLOAD"}, "GRID_OUTAGE_CLUSTER": {"BUSHFIRE_GRID_OUTAGE"},
    "PLANNED_WORK": {"PLANNED_MAINTENANCE"}, "TRAFFIC_SURGE": {"TRAFFIC_SURGE"}, "UNCERTAIN": set(),
}


class Evidence(BaseModel):
    statement: str = Field(description="One fact from the context supporting (or weakening) the conclusion")
    context_fields: list[str] = Field(description="Dotted paths of the context fields cited, e.g. "
                                                  "suspects[0].signals.latency_z_now")


class CustomerImpact(BaseModel):
    estimated_affected_subscribers: int
    impacted_cells: int
    impacted_sites: int
    description: str = Field(description="One sentence: who is affected, where, and how (from the context)")


class NocSummary(BaseModel):
    likely_root_cause: str = Field(description="Exactly one suspect element_id from the context, or 'uncertain'")
    fault_hypothesis: Hypothesis
    confidence: Literal["high", "medium", "low"]
    summary: str = Field(description="2-3 sentences for the NOC engineer")
    evidence: list[Evidence]
    recommended_next_steps: list[str] = Field(description="3-6 runbook-style actions, most urgent first")
    customer_impact: CustomerImpact
    alternative_suspects: list[str] = Field(description="Other suspect element_ids still plausible")


class SmsDraft(BaseModel):
    region_code: str
    text: str = Field(description="The SMS, at most 160 characters, plain English")


class SmsDrafts(BaseModel):
    drafts: list[SmsDraft]


def strict_json_schema(model: type[BaseModel]) -> dict:
    """pydantic's JSON schema made strict for `response_format: json_schema, strict: true`: every property
    required, no additional properties, no defaults / titles, `$defs` inlined."""
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def fix(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return fix(defs[node["$ref"].split("/")[-1]])
            node = {k: fix(v) for k, v in node.items() if k not in ("title", "default")}
            if node.get("type") == "object" and "properties" in node:
                node["required"] = list(node["properties"])
                node["additionalProperties"] = False
            return node
        if isinstance(node, list):
            return [fix(v) for v in node]
        return node

    return fix(raw)
