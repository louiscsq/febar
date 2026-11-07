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
WITHHELD_TEXT = ("This answer referred to data outside the NOC serving views (evaluation or ground-truth tables) and "
                 "was withheld.")


def references_non_serving_data(obj: Any) -> bool:
    if isinstance(obj, dict):
        return any(references_non_serving_data(k) or references_non_serving_data(v) for k, v in obj.items())
    if isinstance(obj, (list, tuple)):
        return any(references_non_serving_data(v) for v in obj)
    return isinstance(obj, str) and bool(_NON_SERVING_SOURCE.search(obj))


def scrub_genie_answer(ans: dict) -> dict:
    """What the app returns for a Genie answer: forbidden columns dropped, raw identifiers redacted, and the whole
    answer withheld if any part of it refers to non-serving (evaluation / ground-truth) data."""
    ans = dict(ans or {})
    if references_non_serving_data(ans):
        return {"conversation_id": ans.get("conversation_id"), "message_id": ans.get("message_id"),
                "status": ans.get("status"), "text": [WITHHELD_TEXT], "sql": None, "description": None,
                "columns": [], "rows": [], "row_count": 0, "error": None, "withheld": True}
    cols, rows = scrub_table(list(ans.get("columns") or []), list(ans.get("rows") or []))
    out = scrub({k: v for k, v in ans.items() if k not in ("columns", "rows")})
    return {**out, "columns": cols, "rows": rows}
