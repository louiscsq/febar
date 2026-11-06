"""Generated IDs are unique per run, so the pipeline's cross-run dedupe on `record_id` only removes real redeliveries.

Regression for the step-4 holdout finding (evidence/step4/09_holdout_alarm_gap.md): incident alarm IDs were
`opaque_id("ALM", incident_id, n)` with `incident_id` = INC-00001, ... in every batch run, so a later run's fault
alarms reused an earlier run's alarm IDs and silver dropped them as duplicates. Alarm and change IDs now also hash
the run key (`GeneratorConfig.run_key`: the run id, or the seeds and window).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from conftest import read_table, tiny_cfg
from netmon_datagen.batch import generate_history
from netmon_datagen.config import FaultConfig
from netmon_pipeline.dedupe import WatermarkDeduper

FAULTS = FaultConfig(rate_multiplier=50)  # plenty of incidents (and incident alarms) on the tiny network
ALARM_IDS = ["record_id", "alarm_id"]


def _gen(out: Path, **kw) -> Path:
    kw.setdefault("days", 2)
    kw.setdefault("fmt", "parquet")
    kw.setdefault("faults", FAULTS)
    generate_history(tiny_cfg(**kw), out, log=lambda *a: None)
    return out


@pytest.fixture(scope="module")
def runs(tmp_path_factory) -> dict[str, Path]:
    """Same seed and window, two run ids (`a`, `b`); `a` again; and a step-3-like history / holdout pair."""
    t = tmp_path_factory.mktemp("run_ids")
    return {
        "a": _gen(t / "a", run_id="a"),
        "a_again": _gen(t / "a_again", run_id="a"),
        "b": _gen(t / "b", run_id="b"),
        # like history_1m (seed 42) followed by holdout_1m (seed 4242, same network, the next days)
        "history": _gen(t / "history_1m", seed=42, run_id="history_1m"),
        "holdout": _gen(t / "holdout_1m", seed=4242, topology_seed=42, start="2026-09-06", run_id="holdout_1m"),
        # the pre-fix scheme: both runs hash the same key, so incident alarm IDs depend on INC-00001.. only
        "history_shared": _gen(t / "history_shared", seed=42, run_id="shared"),
        "holdout_shared": _gen(t / "holdout_shared", seed=4242, topology_seed=42, start="2026-09-06",
                               run_id="shared"),
    }


def _ids(root: Path, table: str, col: str) -> set[str]:
    return set(read_table(root, table)[col].dropna())


def _incident_alarm_ids(root: Path) -> set[str]:
    """Alarm IDs owned by incidents (fault / red-herring lifecycles), not background noise."""
    al = read_table(root, "alarms")
    inc = read_table(root, "ground_truth/incidents")
    assert inc["n_alarms"].sum() > 0
    noise_text = {"Threshold crossed", "Intermittent link state change", "Alarm cleared"}
    return set(al.loc[~al["additional_text"].isin(noise_text), "alarm_id"].dropna())


def test_different_run_ids_give_disjoint_alarm_and_change_ids(runs):
    a, b = runs["a"], runs["b"]
    for col in ALARM_IDS:
        ia, ib = _ids(a, "alarms", col), _ids(b, "alarms", col)
        assert ia and ib and not ia & ib, col
    ca, cb = _ids(a, "maintenance_windows", "change_id"), _ids(b, "maintenance_windows", "change_id")
    assert ca and cb and not ca & cb


def test_run_id_changes_only_the_ids(runs):
    """Same seed and window: KPIs, sessions and ground truth are identical; alarms differ only in their IDs."""
    a, b = runs["a"], runs["b"]
    for table in ("kpis", "sessions", "ground_truth/incidents", "topology_nodes"):
        pd.testing.assert_frame_equal(read_table(a, table), read_table(b, table), obj=table)
    strip = lambda df: df.drop(columns=ALARM_IDS).reset_index(drop=True)  # noqa: E731
    pd.testing.assert_frame_equal(strip(read_table(a, "alarms")), strip(read_table(b, "alarms")))
    log_a, log_b = read_table(a, "ground_truth/dq_injections"), read_table(b, "ground_truth/dq_injections")
    pd.testing.assert_frame_equal(log_a.drop(columns="record_id"), log_b.drop(columns="record_id"))
    keep = log_a["feed"] != "alarms"
    assert (log_a.loc[keep, "record_id"] == log_b.loc[keep, "record_id"]).all()


def test_same_run_is_deterministic(runs):
    for table in ("alarms", "maintenance_windows", "ground_truth/dq_injections"):
        pd.testing.assert_frame_equal(read_table(runs["a"], table), read_table(runs["a_again"], table), obj=table)


def test_default_run_key_depends_on_seed_and_window():
    base = tiny_cfg()
    keys = {base.run_key("batch", "w0"), base.with_(seed=7).run_key("batch", "w0"),
            base.run_key("batch", "w1"), base.with_(topology_seed=9).run_key("batch", "w0"),
            base.with_(days=1).run_key("batch", "w0")}
    assert len(keys) == 5
    assert base.with_(run_id="holdout_1m").run_key("batch", "w0") == "holdout_1m"


def test_step3_like_runs_have_disjoint_ids(runs):
    h, o = runs["history"], runs["holdout"]
    assert _incident_alarm_ids(h) and _incident_alarm_ids(o)
    assert not _ids(h, "alarms", "record_id") & _ids(o, "alarms", "record_id")
    # the pre-fix scheme reproduces the collision: the holdout's incident alarms reuse the history's IDs
    hs, os_ = runs["history_shared"], runs["holdout_shared"]
    assert _incident_alarm_ids(hs) & _incident_alarm_ids(os_)


def _silver(*roots: Path) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    """Each run's alarms ingested as one backfill micro-batch, one after the other with no gap (as on the
    workspace: the holdout landed while the history's keys were still in the 1-hour dedupe state).
    Returns rows admitted, duplicates dropped, and the run's injected alarm duplicates, per run."""
    d = WatermarkDeduper(delay_s=3600)
    kept, dropped, injected = {}, {}, {}
    for i, root in enumerate(roots):
        al = read_table(root, "alarms").dropna(subset=["record_id"])
        before = len(d.dropped_dup)
        out = d.batch([{"record_id": r, "ingested_s": 60.0 * i, "run": root.name} for r in al["record_id"]])
        kept[root.name], dropped[root.name] = len(out), len(d.dropped_dup) - before
        log = read_table(root, "ground_truth/dq_injections")
        injected[root.name] = int(((log["feed"] == "alarms") & (log["defect_type"] == "duplicate")).sum())
    return kept, dropped, injected


def test_regression_cross_run_dedupe_drops_only_injected_duplicates(runs):
    h, o = runs["history"], runs["holdout"]
    kept, dropped, injected = _silver(h, o)
    assert injected["holdout_1m"] > 0
    # only the run's own redeliveries are removed; every distinct holdout alarm event reaches silver
    assert dropped == injected
    assert kept["holdout_1m"] == read_table(o, "alarms")["record_id"].nunique()


def test_regression_pre_fix_scheme_drops_the_later_runs_incident_alarms(runs):
    """The original bug, reproduced with a shared run key: the later run loses alarms that are not duplicates."""
    hs, os_ = runs["history_shared"], runs["holdout_shared"]
    kept, dropped, injected = _silver(hs, os_)
    assert dropped["history_shared"] == injected["history_shared"]
    lost = dropped["holdout_shared"] - injected["holdout_shared"]
    assert lost > 0
    assert kept["holdout_shared"] < read_table(os_, "alarms")["record_id"].nunique()


def test_injected_duplicates_still_share_their_record_id(runs):
    """The DQ duplicate feature is unaffected: a redelivery is an exact copy, same record_id, same run."""
    root = runs["holdout"]
    al = read_table(root, "alarms")
    log = read_table(root, "ground_truth/dq_injections")
    dup_ids = log.loc[(log["feed"] == "alarms") & (log["defect_type"] == "duplicate"), "record_id"]
    assert len(dup_ids)
    counts = al["record_id"].value_counts()
    assert (counts.reindex(dup_ids).fillna(0) >= 2).all()
    # and nothing else repeats
    assert set(counts[counts > 1].index) <= set(dup_ids)
