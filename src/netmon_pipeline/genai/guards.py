"""Deterministic guardrails around the LLM calls. They run on every call whether or not the AI Gateway guardrails
are on, so the behaviour is the same on any workspace and is unit-tested.

Before a prompt is sent:
- `sanitize_free_text`: alarm free text is untrusted (it comes from network elements and OSS operators). It is
  truncated, PII is redacted, and text that looks like an instruction to the model (prompt injection) is withheld
  and flagged. The prompts also tell the model that context strings are data, never instructions.
- `assert_no_pii`: the serialised context / prompt is scanned for IMSI / MSISDN / phone / e-mail patterns; a hit
  raises and nothing is sent.

After a response:
- `validate_summary` (hallucination guard): the root cause must be one of the context's suspects or
  "uncertain"; every element ID in the text must exist in the context; evidence must cite context fields that
  exist; the customer-impact numbers are checked against the context. Violations are repaired and reported.
- `check_sms`: length <= 160, GSM-7 characters, no element IDs / internal jargon / vendor names / PII / real
  operator names / blame, and an ETA only when the context has one.
"""

from __future__ import annotations

import re
import unicodedata

# --- patterns ------------------------------------------------------------------------------------------------

ELEMENT_ID = re.compile(r"\b(?:AMF|UPF|AGG|BH|SITE|CELL)-[A-Z]{2,3}-[0-9]{2,5}(?:-[0-9A-Z]{2,4})?\b")
ELEMENT_ID_LOOSE = re.compile(r"\b(?:AMF|UPF|AGG|BH|SITE|CELL)[-_ ]?[A-Z]{2,3}[-_ ]?\d{2,5}\w*\b", re.IGNORECASE)
IMSI = re.compile(r"(?<!\d)\d{15}(?!\d)")  # any 15-digit run (IMSI length), incl. the 00101 test PLMN
MSISDN = re.compile(r"(?<![\w+])\+?\d{1,3}[ -]?\d{2,4}[ -]?\d{3}[ -]?\d{3,4}(?!\d)")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PII_PATTERNS = {"imsi": IMSI, "msisdn_or_phone": MSISDN, "email": EMAIL}

INJECTION = re.compile(
    r"(ignore|disregard|forget|override)\b.{0,40}\b(instruction|prompt|rule|above|previous|system)"
    r"|\b(system prompt|you are now|act as|pretend to be|new instructions?|developer mode)\b"
    r"|\b(assistant|system|user)\s*:"
    r"|\b(root[_ ]cause|likely_root_cause|confidence)\b.{0,20}\b(is|=|:|should be|must be)\b"
    r"|\b(reply|respond|answer|output|print|say)\b.{0,30}\b(only|exactly|with)\b"
    r"|\b(send|text|sms|notify|email)\b.{0,30}\b(all|every|customers?|subscribers?)\b"
    r"|<\|.*?\|>|```|\{\{|\}\}|\[INST\]",
    re.IGNORECASE | re.DOTALL)
FREE_TEXT_MAX = 120

# Real Australian (and large global) mobile operator / MVNO brands: never named in any draft.
REAL_OPERATORS = ["Telstra", "Optus", "Vodafone", "TPG", "iiNet", "Aussie Broadband", "Boost Mobile", "Amaysim",
                  "Belong", "Lebara", "Felix", "Southern Phone", "Dodo", "Spintel", "Moose Mobile", "Woolworths Mobile",
                  "ALDI Mobile", "Kogan Mobile", "Circles.Life", "Exetel", "Superloop", "Tangerine", "More Telecom",
                  "Spark", "One NZ", "2degrees", "Verizon", "AT&T", "T-Mobile", "Orange", "Singtel"]
# Internal vocabulary that must not reach customers (the network's vendors are fictional but still internal).
INTERNAL_TERMS = ["backhaul", "router", "AMF", "UPF", "MME", "SGW", "eNB", "gNB", "RCA", "root cause", "KPI",
                  "suspect", "ranker", "score", "alarm", "NOC", "incident ref", "Arcturus", "Borealis", "Eridani",
                  "Cygnus", "fibre cut", "node", "element", "OSS", "S1", "GTP", "PRB", "RRC"]
BLAME = re.compile(r"\b(fault of|blame|caused by|due to (?:a |an |the )?(?:contractor|vendor|council|third[- ]party|"
                   r"power company|supplier|staff|engineer|human error)|negligen\w*|our supplier)\b", re.IGNORECASE)
ETA_CLAIM = re.compile(r"\b(by|until|before|around|approx\.?|approximately|expected|estimate[ds]?|ETA|restored at|"
                       r"back (?:on|up) at|within)\b[^.]{0,25}?\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}:\d{2}|"
                       r"\d+\s*(?:min(?:ute)?s?|hours?|hrs?)|today|tonight|tomorrow|midnight|noon)\b", re.IGNORECASE)
UPDATE_PROMISE = re.compile(r"\b(we'?ll|we will) (update|keep you|let you know|be in touch|send (?:an )?update)",
                            re.IGNORECASE)
GSM7 = set("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿"
           "abcdefghijklmnopqrstuvwxyzäöñüà")
SMS_MAX = 160
UNCERTAIN = "uncertain"


# --- before the call ---------------------------------------------------------------------------------------------

def redact_pii(text: str) -> tuple[str, list[str]]:
    found = []
    for name, pat in PII_PATTERNS.items():
        if pat.search(text):
            found.append(name)
            text = pat.sub(f"[{name} redacted]", text)
    return text, found


def sanitize_free_text(text) -> tuple[str | None, bool]:
    """(safe text, flagged). Untrusted free text: control characters stripped, PII redacted, truncated; text that
    reads like an instruction to the model is withheld (flagged) rather than passed on."""
    if text is None:
        return None, False
    s = unicodedata.normalize("NFKC", str(text))
    s = "".join(ch if ch.isprintable() else " " for ch in s)
    s = re.sub(r"\s+", " ", s).strip()
    s, pii = redact_pii(s)
    if INJECTION.search(s):
        return "[free text withheld: looked like an instruction to the assistant]", True
    if len(s) > FREE_TEXT_MAX:
        s = s[: FREE_TEXT_MAX - 1] + "…"
    return s, bool(pii)


class PIIError(ValueError):
    pass


def pii_findings(text: str) -> list[str]:
    return [n for n, p in PII_PATTERNS.items() if p.search(text)]


def assert_no_pii(text: str) -> None:
    hits = pii_findings(text)
    if hits:
        raise PIIError(f"PII pattern(s) {hits} in a prompt / context; nothing was sent")


# --- after the call: NOC summary --------------------------------------------------------------------------------

def _element_ids(text: str) -> set[str]:
    return set(ELEMENT_ID.findall(text or ""))


def _scrub_ids(text: str, allowed: set[str]) -> tuple[str, list[str]]:
    bad = sorted(e for e in _element_ids(text) if e not in allowed)
    for e in bad:
        text = re.sub(rf"\b{re.escape(e)}\b", "[unknown element]", text)
    return text, bad


def validate_summary(out: dict, ctx: dict) -> tuple[dict, dict]:
    """Hallucination guard on the structured NOC summary. Returns (repaired output, report). Report keys:
    `root_not_in_context`, `unknown_element_ids`, `invalid_evidence_fields`, `dropped_evidence`,
    `impact_corrected`, `n_repairs`."""
    from netmon_pipeline.genai.context import known_elements, resolve_path, suspect_ids

    o = {**out}
    rep: dict = {"root_not_in_context": None, "unknown_element_ids": [], "invalid_evidence_fields": [],
                 "dropped_evidence": 0, "impact_corrected": {}, "n_repairs": 0}
    sus = suspect_ids(ctx)
    allowed = known_elements(ctx)
    root = str(o.get("likely_root_cause") or "").strip()
    if root.lower() == UNCERTAIN:
        o["likely_root_cause"] = UNCERTAIN
    elif root not in sus:
        rep["root_not_in_context"] = root
        o["likely_root_cause"] = UNCERTAIN
        o["confidence"] = "low"
        rep["n_repairs"] += 1
    alts = []
    for a in o.get("alternative_suspects") or []:
        if a in sus and a != o["likely_root_cause"]:
            alts.append(a)
        elif a not in sus:
            rep["unknown_element_ids"].append(a)
            rep["n_repairs"] += 1
    o["alternative_suspects"] = alts
    for key in ("summary",):
        o[key], bad = _scrub_ids(str(o.get(key) or ""), allowed)
        rep["unknown_element_ids"] += bad
        rep["n_repairs"] += len(bad)
    steps = []
    for st in o.get("recommended_next_steps") or []:
        st, bad = _scrub_ids(str(st), allowed)
        rep["unknown_element_ids"] += bad
        rep["n_repairs"] += len(bad)
        steps.append(st)
    o["recommended_next_steps"] = steps
    ev_ok = []
    for ev in o.get("evidence") or []:
        fields = []
        for f in ev.get("context_fields") or []:
            try:
                resolve_path(ctx, f)
                fields.append(f)
            except (KeyError, IndexError, ValueError, TypeError):
                rep["invalid_evidence_fields"].append(f)
        stmt, bad = _scrub_ids(str(ev.get("statement") or ""), allowed)
        rep["unknown_element_ids"] += bad
        if fields:
            ev_ok.append({"statement": stmt, "context_fields": fields})
        else:
            rep["dropped_evidence"] += 1
    rep["n_repairs"] += len(rep["invalid_evidence_fields"]) + rep["dropped_evidence"]
    o["evidence"] = ev_ok
    imp = ctx.get("impact") or {}
    truth = {"estimated_affected_subscribers": imp.get("est_affected_subscribers_total"),
             "impacted_cells": imp.get("n_impacted_cells"), "impacted_sites": imp.get("n_impacted_sites")}
    ci = {**(o.get("customer_impact") or {})}
    for k, v in truth.items():
        if v is not None and ci.get(k) != v:
            rep["impact_corrected"][k] = {"model": ci.get(k), "context": v}
            ci[k] = v
    rep["n_repairs"] += len(rep["impact_corrected"])
    o["customer_impact"] = ci
    rep["unknown_element_ids"] = sorted(set(rep["unknown_element_ids"]))
    return o, rep


# --- after the call: SMS ----------------------------------------------------------------------------------------

def check_sms(text: str, eta: str | None) -> list[str]:
    """Violations of the customer SMS rules (empty list = compliant)."""
    v = []
    t = text or ""
    if not t.strip():
        return ["empty"]
    if len(t) > SMS_MAX:
        v.append(f"length {len(t)} > {SMS_MAX}")
    bad_chars = sorted({c for c in t if c not in GSM7})
    if bad_chars:
        v.append(f"non-GSM-7 characters {bad_chars}")
    if ELEMENT_ID.search(t) or ELEMENT_ID_LOOSE.search(t):
        v.append("internal element ID")
    hits = pii_findings(t)
    if hits:
        v.append(f"PII pattern {hits}")
    low = t.lower()
    ops = [o for o in REAL_OPERATORS if re.search(rf"(?<!\w){re.escape(o.lower())}(?!\w)", low)]
    if ops:
        v.append(f"real operator name {ops}")
    terms = [w for w in INTERNAL_TERMS if re.search(rf"(?<!\w){re.escape(w.lower())}(?!\w)", low)]
    if terms:
        v.append(f"internal term {terms}")
    if BLAME.search(t):
        v.append("blame wording")
    if eta is None and ETA_CLAIM.search(t):
        v.append("ETA not supported by the context")
    if eta is None and not UPDATE_PROMISE.search(t):
        v.append("no ETA in context: must say we'll update you")
    return v
