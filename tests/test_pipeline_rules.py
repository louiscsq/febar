"""Silver DQ rules (netmon_pipeline.rules) against the generator's own defect log.

Every injected defect must be caught by the mechanism docs/pipeline.md assigns to it, and clean records
must pass every DROP rule, so the quarantine holds defects only.
"""

from __future__ import annotations

import glob
import json
from collections import Counter, defaultdict

import pytest

from conftest import read_table
from netmon_pipeline import rules

FEEDS = ["kpis", "alarms", "sessions"]


@pytest.fixture(scope="module")
def landed(history_json):
    """What Auto Loader would see: every JSON line of every feed, parsed or flagged corrupt."""
    root, _ = history_json
    out = {}
    for feed in FEEDS:
        recs = []
        for f in sorted(glob.glob(str(root / feed / "**" / "*.json"), recursive=True)):
            with open(f) as fh:
                recs += [rules.parse_json_line(line) for line in fh if line.strip()]
        out[feed] = recs
    dq = read_table(root, "ground_truth/dq_injections")
    return out, dq


def by_id(recs):
    d = defaultdict(list)
    for r in recs:
        if not r.get("__corrupt__"):
            d[r.get("record_id")].append(r)
    return d


@pytest.mark.parametrize("feed", FEEDS)
def test_quarantine_defects_fail_a_drop_rule(landed, feed):
    recs, dq = landed
    ids = by_id(recs[feed])
    inj = dq[(dq.feed == feed) & dq.defect_type.isin(["malformed", "null", "out_of_range"])
             & (dq.defect_subtype != "truncated_json")]
    assert len(inj) > 0
    missed = [r.record_id for r in inj.itertuples() if not any(rules.failed_rules_py(feed, x) for x in ids[r.record_id])]
    assert missed == []


@pytest.mark.parametrize("feed", FEEDS)
def test_truncated_lines_are_corrupt_records(landed, feed):
    recs, dq = landed
    n_trunc = int(((dq.feed == feed) & (dq.defect_subtype == "truncated_json")).sum())
    corrupt = [r for r in recs[feed] if r.get("__corrupt__")]
    assert len(corrupt) == n_trunc
    assert all("parseable_record" in rules.failed_rules_py(feed, r) for r in corrupt)


@pytest.mark.parametrize("feed", FEEDS)
def test_clean_records_pass_every_drop_rule(landed, feed):
    recs, dq = landed
    defective = set(dq[(dq.feed == feed) & (dq.defect_type != "duplicate")].record_id)
    clean = [r for r in recs[feed] if not r.get("__corrupt__") and r["record_id"] not in defective]
    assert len(clean) > 1000
    failing = Counter(name for r in clean for name in rules.failed_rules_py(feed, r))
    assert failing == Counter()


@pytest.mark.parametrize("feed", FEEDS)
def test_late_arrivals_are_flagged_and_only_they_are(landed, feed):
    recs, dq = landed
    late_ids = set(dq[(dq.feed == feed) & (dq.defect_type == "late_arrival")].record_id)
    others = set(dq[dq.feed == feed].record_id) - late_ids
    flagged = {r["record_id"] for r in recs[feed] if not r.get("__corrupt__") and rules.is_late_py(feed, r)}
    assert late_ids and late_ids <= flagged
    # Records with no defect at all are never late (defective ones may be, e.g. a nulled timestamp).
    assert not {i for i in flagged - late_ids if i not in others}


@pytest.mark.parametrize("feed", FEEDS)
def test_duplicates_collapse_on_record_id(landed, feed):
    recs, dq = landed
    dup_ids = set(dq[(dq.feed == feed) & (dq.defect_type == "duplicate")].record_id)
    counts = Counter(r["record_id"] for r in recs[feed] if not r.get("__corrupt__"))
    assert dup_ids and all(counts[i] == 2 for i in dup_ids)
    assert {i for i, n in counts.items() if n > 1} == dup_ids
    # Redeliveries land within the dedupe watermark of the original's delivery time.
    for i in list(dup_ids)[:200]:
        a, b = (rules._parse_ts(r["emitted_ts"]) for r in by_id(recs[feed])[i])
        assert abs((a - b).total_seconds()) < 15 * 60


def test_expectation_sql_is_well_formed():
    for feed in FEEDS:
        drop = rules.drop_expectations(feed)
        assert "parseable_record" not in drop and "known_element" in drop
        assert len(drop) == len(set(drop))
        sql = rules.failed_rules_sql(drop)
        assert sql.startswith("filter(array(") and all(f"'{n}'" in sql for n in drop)
        assert rules.all_pass_sql(drop).count("coalesce(") == len(drop)
        assert set(rules.warn_expectations(feed)) == {"on_time"}
    assert set(rules.TOPOLOGY_FAIL) >= {"element_id_not_null", "valid_level"}


def test_range_rule_sql_and_python_agree():
    r = rules.Range("prb_util_pct", 0, 100)
    assert r.sql == "prb_util_pct IS NULL OR (prb_util_pct >= 0 AND prb_util_pct <= 100)"
    assert r.check({"prb_util_pct": 100.0}) and not r.check({"prb_util_pct": 101.0})
    assert r.check({"prb_util_pct": None}) and r.check({"prb_util_pct": "#VALUE!"})
    assert rules.Range("bytes_dl", 0).sql == "bytes_dl IS NULL OR (bytes_dl >= 0)"


def test_parse_json_line():
    assert rules.parse_json_line('{"a": 1}') == {"a": 1}
    assert rules.parse_json_line('{"record_id":"K-1","ev') == {"__corrupt__": True}
    assert rules.parse_json_line(json.dumps([1])) == {"__corrupt__": True}
