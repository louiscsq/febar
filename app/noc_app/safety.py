"""Last line of defence on every API response: no subscriber identifier and no ground-truth label leaves the app.

The app's sources hold neither (Lakebase serves the ranker's and the assistant's outputs; the UC views exclude
sessions and the ground-truth schema), so in normal operation nothing is removed. `scrub` still drops any forbidden column
by name, at any depth, and redacts raw IMSI / MSISDN-shaped values, so a future query or a Genie answer cannot leak
them through the app. Tests cover both.
"""

from __future__ import annotations

import re
from typing import Any

PII_COLUMNS = frozenset({"imsi", "msisdn", "subscriber_key", "imei", "subscriber_id"})
# Step 3's label columns (netmon_pipeline.rca.features.LABEL_COLUMNS) minus `incident_id`: the app's incident IDs
# are the ranker's operational RCA-<hash> references, not ground-truth INC-... IDs. A test keeps this in sync.
LABEL_COLUMNS = frozenset({
    "event_class", "fault_type", "root_element_id", "root_element_type", "root_element_ids",
    "affected_element_ids", "affected_cell_ids", "is_customer_impacting", "is_censored", "impact_start_ts",
    "impact_end_ts", "start_ts", "end_ts", "severity", "estimated_impacted_subscribers", "n_affected_cells",
    "label", "is_root", "case_label",
})
FORBIDDEN_COLUMNS = PII_COLUMNS | LABEL_COLUMNS

# Raw identifiers: a standalone 15-digit IMSI (not the fraction of a decimal number such as 6.000000476837158), or
# an E.164 MSISDN. Masked values (00101********33, +999******961) do not match.
_IMSI = re.compile(r"(?<!\d)(?<!\d\.)\d{15}(?!\d)(?!\.\d)")
_MSISDN = re.compile(r"\+\d{8,15}(?!\d)")
REDACTED = "[redacted]"


def redact_text(s: str) -> str:
    return _MSISDN.sub(REDACTED, _IMSI.sub(REDACTED, s))


def is_forbidden(column: str) -> bool:
    return column.strip().strip("`").lower() in FORBIDDEN_COLUMNS


def scrub(obj: Any) -> Any:
    """Recursively drop forbidden keys and redact raw identifiers in strings."""
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if not (isinstance(k, str) and is_forbidden(k))}
    if isinstance(obj, (list, tuple)):
        return [scrub(v) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj


def scrub_table(columns: list[str], rows: list[list]) -> tuple[list[str], list[list]]:
    """Drop forbidden columns from a tabular result (e.g. a Genie query result)."""
    keep = [i for i, c in enumerate(columns) if not is_forbidden(c)]
    return [columns[i] for i in keep], [[scrub(r[i]) for i in keep] for r in rows]


# A Genie answer may only draw on the NOC serving schema (`netmon_noc`, region-filtered views). The space's data
# sources hold nothing else, so in normal operation nothing matches; if an answer ever names another netmon schema,
# an evaluation / label table or ground truth (in its SQL, text, description or result values), the whole answer is
# withheld rather than partially redacted: a figure computed from ground truth is a leak even with its source removed.
_NON_SERVING_SOURCE = re.compile(
    r"\bnetmon_(?!noc\b)[a-z]+\b|\b(?:genai_)?eval_[a-z0-9_]+|\brca_training_[a-z_]+|\bbronze_g[t]_[a-z_]+|"
    r"\bground[ _]truth\b", re.I)
WITHHELD_TEXT = ("This answer referred to data outside the NOC serving views (evaluation or ground-truth tables or "
                 "labels) and was withheld.")


# Ground-truth label columns (the incidents' schema; step 3's LABEL_COLUMNS minus the generic words `severity`, `label`,
# `start_ts` / `end_ts`, which serving views also use). No `netmon_noc` view has any of these, so an answer naming one
# is withheld even when it names no evaluation table.
_LABEL_TOKEN = re.compile(
    r"\b(?:event_class|fault_type|root_element_ids?|root_element_type|root_cause\w*|affected_element_ids|"
    r"affected_cell_ids|is_customer_impacting|is_censored|impact_start_ts|impact_end_ts|estimated_impacted_subscribers|"
    r"n_affected_cells|is_root|case_label)\b", re.I)
# The generator's fault classes (netmon_datagen.faults.FAULT_SPECS; a test keeps this in sync). In the serving views
# they appear only as the step-4 assistant's operational guess, `incident_ai_summary.fault_hypothesis`, so a fault
# class in an answer is allowed only when its SQL reads that column; otherwise it can only be a ground-truth label.
FAULT_CLASSES = frozenset({
    "AGG_ROUTER_FAILURE", "ALARM_STORM", "AMF_OVERLOAD", "BACKHAUL_DEGRADATION", "BUSHFIRE_GRID_OUTAGE", "CELL_OUTAGE",
    "CORE_CONGESTION", "CYCLONE_BACKHAUL_CUT", "FLAPPING_ELEMENT", "LONG_HAUL_FIBRE_CUT", "PLANNED_MAINTENANCE",
    "SITE_POWER_OUTAGE", "TRAFFIC_SURGE"})
# Case-insensitive (`backhaul_degradation`, `Site_Power_Outage` are the same label); only the underscore-joined
# identifier form matches, so ordinary prose ("backhaul degradation on link X") is not a label. All three patterns
# here ignore case; identifiers in backticks or quotes still match because `\b` treats them as word boundaries.
_FAULT_CLASS = re.compile(r"\b(?:" + "|".join(sorted(FAULT_CLASSES)) + r")\b", re.I)
OPERATIONAL_FAULT_COLUMN = "fault_hypothesis"


def _strings(obj: Any):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)
    elif isinstance(obj, str):
        yield obj


def references_non_serving_data(obj: Any) -> bool:
    return any(_NON_SERVING_SOURCE.search(x) for x in _strings(obj))


def withhold_reason(ans: dict) -> str | None:
    """Why a Genie answer must not be shown (None: it may). Checks its SQL, text, description, columns and rows."""
    strings = list(_strings(ans))
    if any(_NON_SERVING_SOURCE.search(x) for x in strings):
        return "non_serving_source"
    if any(_LABEL_TOKEN.search(x) for x in strings):
        return "label_column"
    sql = ans.get("sql") or ""
    if any(_FAULT_CLASS.search(x) for x in strings) and not re.search(rf"\b{OPERATIONAL_FAULT_COLUMN}\b", sql, re.I):
        return "label_value"
    return None


def scrub_genie_answer(ans: dict) -> dict:
    """What the app returns for a Genie answer: forbidden columns dropped, raw identifiers redacted, and the whole
    answer withheld if any part of it refers to non-serving (evaluation / ground-truth) data, names a ground-truth
    label column, or carries a fault-class label that does not come from the assistant's `fault_hypothesis`."""
    ans = dict(ans or {})
    reason = withhold_reason(ans)
    if reason:
        return {"conversation_id": ans.get("conversation_id"), "message_id": ans.get("message_id"),
                "status": ans.get("status"), "text": [WITHHELD_TEXT], "sql": None, "description": None,
                "columns": [], "rows": [], "row_count": 0, "error": None, "withheld": True, "withheld_reason": reason}
    cols, rows = scrub_table(list(ans.get("columns") or []), list(ans.get("rows") or []))
    out = scrub({k: v for k, v in ans.items() if k not in ("columns", "rows")})
    return {**out, "columns": cols, "rows": rows}
