"""Data-quality defect rates, determinism by seed, and streaming mode."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from conftest import count_bad_json_lines, read_table, tiny_cfg
from netmon_datagen.batch import generate_history
from netmon_datagen.config import DQConfig, FaultConfig
from netmon_datagen.engine import FEEDS
from netmon_datagen.stream import run_stream

DEFECT_RATE = {"duplicate": "duplicate_rate", "late_arrival": "late_rate", "malformed": "malformed_rate",
               "null": "null_rate", "out_of_range": "out_of_range_rate"}


@pytest.fixture(scope="module")
def dq(history_json):
    out, manifest = history_json
    return out, manifest, read_table(out, "ground_truth/dq_injections")


@pytest.mark.parametrize("feed", FEEDS)
def test_defect_rates_within_tolerance(dq, feed):
    _, manifest, log = dq
    n = manifest["counts"][f"{feed}_generated"]
    cfg = DQConfig()
    for defect, attr in DEFECT_RATE.items():
        got = (log[(log.feed == feed) & (log.defect_type == defect)]).shape[0] / n
        want = getattr(cfg, attr)
        assert got == pytest.approx(want, rel=0.25, abs=3 / n), (feed, defect, got, want)


def test_written_rows_equal_generated_plus_duplicates(dq):
    _, manifest, log = dq
    for feed in FEEDS:
        dups = ((log.feed == feed) & (log.defect_type == "duplicate")).sum()
        assert manifest["counts"][f"{feed}_written"] == manifest["counts"][f"{feed}_generated"] + dups


def test_duplicates_share_record_id(dq):
    out, _, log = dq
    k = read_table(out, "kpis")
    dup_ids = set(log[(log.feed == "kpis") & (log.defect_type == "duplicate")].record_id)
    counts = k.record_id.value_counts()
    assert set(counts[counts > 1].index) == dup_ids


def test_truncated_lines_are_unparseable(dq):
    out, _, log = dq
    for feed in FEEDS:
        n_trunc = ((log.feed == feed) & (log.defect_subtype == "truncated_json")).sum()
        assert count_bad_json_lines(out, feed) == n_trunc


def test_late_arrivals_detectable_from_timestamps(dq):
    out, _, log = dq
    k = read_table(out, "kpis")
    late_ids = set(log[(log.feed == "kpis") & (log.defect_type == "late_arrival")].record_id)
    bad_ts = set(log[(log.feed == "kpis") & log.column.isin(["event_ts"])].record_id)
    k = k[~k.record_id.isin(bad_ts)].drop_duplicates("record_id")
    lag = pd.to_datetime(k.emitted_ts) - pd.to_datetime(k.event_ts)
    is_late = k.record_id.isin(late_ids)
    assert (lag[is_late] > pd.Timedelta(minutes=30)).all()
    assert (lag[~is_late] < pd.Timedelta(minutes=20)).all()
    # Late records land in a later emitted-date partition at least sometimes.
    assert (pd.to_datetime(k.emitted_ts[is_late]).dt.date > pd.to_datetime(k.event_ts[is_late]).dt.date).any()


def test_out_of_range_and_nulls_visible(dq):
    out, _, log = dq
    k = read_table(out, "kpis").drop_duplicates("record_id").set_index("record_id")
    oor = log[(log.feed == "kpis") & (log.defect_type == "out_of_range")]
    for _, r in oor.iterrows():
        assert str(k.at[r.record_id, r.column]) in (r.injected_value, str(float(r.injected_value)))
    nul = log[(log.feed == "kpis") & (log.defect_type == "null")]
    for _, r in nul.iterrows():
        assert pd.isna(k.at[r.record_id, r.column])


def test_pii_identifiers_are_synthetic(history_json):
    out, _ = history_json
    s = read_table(out, "sessions").dropna(subset=["imsi"])
    assert s.imsi.str.fullmatch(r"00101\d{10}").all()
    assert s.msisdn.dropna().str.fullmatch(r"\+999\d{9}").all()
    assert s.outcome.dropna().isin(["COMPLETED", "DROPPED", "SETUP_FAILED"]).all()


def _digest(root: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in root.rglob("*") if p.is_file() and p.name != "_manifest.json"):
        h.update(str(f.relative_to(root)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def test_batch_deterministic_by_seed(tmp_path):
    a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    for out, seed in ((a, 1), (b, 1), (c, 2)):
        generate_history(tiny_cfg(days=1, seed=seed, fmt="json"), out, log=lambda *x: None)
    assert _digest(a) == _digest(b)
    assert _digest(a) != _digest(c)


def test_streaming_writes_micro_batches_deterministically(tmp_path):
    runs = []
    for name in ("s1", "s2"):
        out = tmp_path / name
        res = run_stream(tiny_cfg(), out, step_seconds=60, interval_seconds=0, max_batches=6,
                         start="2026-10-08T18:00:00", on_batch=lambda i, s: None, log=lambda *x: None)
        assert res["batches"] == 6
        runs.append(out)
    out = runs[0]
    # (tiny raises only ~3 background alarms/hour; alarms are checked in the live-fault test below)
    for feed in ["kpis", "sessions", "topology_nodes", "topology_edges", "ground_truth/incidents"]:
        assert list((out / feed).rglob("*.json")), feed
    kpi_files = sorted((out / "kpis").rglob("batch-*.json"))
    assert len(kpi_files) >= 5  # KPIs for a period are emitted after it closes
    first = [json.loads(x) for x in kpi_files[0].read_text().splitlines()[:5] if x.startswith("{") and x.endswith("}")]
    assert first and {"record_id", "cell_id", "event_ts", "emitted_ts"} <= set(first[0])
    assert not list(out.rglob(".*.tmp"))  # atomic writes leave no temp files
    assert _digest(runs[0]) == _digest(runs[1])


def test_streaming_injects_faults_live(tmp_path):
    """Live faults change streamed KPIs only on the cells named in the ground truth (vs a no-fault run)."""
    common = dict(interval_seconds=0, max_batches=60, start="2026-10-08T18:00:00",
                  on_batch=lambda i, s: None, log=lambda *x: None)
    run_stream(tiny_cfg(dq=DQConfig.none(), faults=FaultConfig(rate_multiplier=200)), tmp_path / "f", **common)
    run_stream(tiny_cfg(dq=DQConfig.none(), faults=FaultConfig(enabled=False)), tmp_path / "b", **common)
    inc = read_table(tmp_path / "f", "ground_truth/incidents")
    assert (inc.event_class == "fault").any()
    assert len(read_table(tmp_path / "f", "alarms"))
    kf, kb = read_table(tmp_path / "f", "kpis"), read_table(tmp_path / "b", "kpis")
    m = kb.merge(kf, on=["record_id", "cell_id"], how="left", suffixes=("_b", "_f"))
    cols = ["availability_pct", "active_users", "latency_ms", "attach_success_pct", "dl_throughput_mbps"]
    changed = m.availability_pct_f.isna() | np.logical_or.reduce(
        [~np.isclose(m[f"{c}_b"].astype(float), m[f"{c}_f"].astype(float)) for c in cols])
    affected = set().union(*inc.loc[inc.is_customer_impacting, "affected_cell_ids"].map(set))
    assert changed.any()
    assert set(m.loc[changed, "cell_id"]) <= affected


@pytest.mark.parametrize("kwargs", [
    dict(duplicate_rate=0.5, late_rate=0.4, malformed_rate=0.2),  # sums to 1.1
    dict(null_rate=1.5),
    dict(late_rate=-0.1),
])
def test_dq_config_rejects_invalid_rates(kwargs):
    with pytest.raises(ValueError, match="DQ rates"):
        DQConfig(**kwargs)


def test_dq_scale_beyond_population_is_rejected():
    DQConfig().scaled(40)  # total 0.96: allowed
    with pytest.raises(ValueError, match="sum to <= 1"):
        DQConfig().scaled(50)  # total 1.2


def test_dq_rates_summing_to_one_are_delivered_in_full():
    from netmon_datagen.dq import inject_defects

    n = 1000
    df = pd.DataFrame({"record_id": [f"r{i}" for i in range(n)], "event_ts": "2026-09-01T00:00:00Z",
                       "cell_id": "C", "availability_pct": 100.0, "active_users": 5, "granularity_s": 900,
                       "rrc_setup_success_pct": 99.0, "dl_throughput_mbps": 50.0, "latency_ms": 20.0,
                       "prb_util_pct": 40.0,
                       "_emitted": np.datetime64("2026-09-01T00:20:00", "s")})
    cfg = DQConfig(duplicate_rate=0.2, late_rate=0.2, malformed_rate=0.2, null_rate=0.2, out_of_range_rate=0.2)
    out, log = inject_defects(df, "kpis", cfg, np.random.default_rng(0), "json")
    per_type = log.groupby("defect_type").size()
    assert per_type.sum() == n and (per_type == 200).all()
    assert log.drop_duplicates("record_id").shape[0] == n  # one defect per record
    assert len(out) == n + 200
