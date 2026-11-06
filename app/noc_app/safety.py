"""Last line of defence on every API response: no subscriber identifier and no ground-truth label leaves the app.

The app's sources hold neither (Lakebase serves the ranker's and the assistant's outputs; the UC views exclude
sessions and the eval schema), so in normal operation nothing is removed. `scrub` still drops any forbidden column
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
