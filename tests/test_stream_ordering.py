"""Streaming emission-ordering guarantees on bounded runs.

A micro-batch file `batch-<t>-<seq>.json` lands at simulated time t + step; `-final` files land after
everything else. Ground truth must never land before the telemetry it describes, and DQ-log rows must
only describe records that were actually emitted.
"""

import contextlib
import glob
import json
import re
from pathlib import Path

import pandas as pd
import pytest

from conftest import count_bad_json_lines, read_table, tiny_cfg
from netmon_datagen.config import DQConfig, FaultConfig
from netmon_datagen.engine import FEEDS
from netmon_datagen.faults import opaque_id
from netmon_datagen.stream import run_stream

# 05:00 UTC = 16:00 in Sydney (AEDT) and 15:00 in Townsville: the run crosses the local busy hour.
START, STEP_S = "2026-10-08T05:00:00", 60
FINAL = pd.Timestamp.max.tz_localize("UTC")


def _stream(out: Path, dq: DQConfig, n: int = 180):
    return run_stream(tiny_cfg(dq=dq, faults=FaultConfig(rate_multiplier=1000)), out, step_seconds=STEP_S,
                      interval_seconds=0, max_batches=n, start=START, on_batch=lambda i, s: None, log=lambda *x: None)


@pytest.fixture(scope="module", params=["no_dq", "dq"])
def run(request, tmp_path_factory):
    out = tmp_path_factory.mktemp(f"stream_{request.param}")
    dq = DQConfig.none() if request.param == "no_dq" else DQConfig().scaled(4)
    return out, _stream(out, dq), request.param


def _landing(path: str) -> pd.Timestamp:
    m = re.search(r"batch-(\d{8}T\d{6})-(\d+|final)\.json$", path)
    if m.group(2) == "final":
        return FINAL
    return pd.Timestamp(m.group(1), tz="UTC") + pd.Timedelta(seconds=STEP_S)


def _truth_with_landing(out: Path) -> pd.DataFrame:
    frames = []
    for f in sorted(glob.glob(str(out / "ground_truth" / "incidents" / "**" / "batch-*.json"), recursive=True)):
        df = pd.read_json(f, lines=True)
        df["landed"] = _landing(f)
        frames.append(df)
    inc = pd.concat(frames, ignore_index=True)
    for c in ["start_ts", "end_ts", "impact_start_ts", "impact_end_ts"]:
        inc[c] = pd.to_datetime(inc[c], utc=True)
    return inc


def test_ground_truth_never_lands_before_its_telemetry(run):
    out, res, mode = run
    inc = _truth_with_landing(out)
    done = inc[~inc.is_censored]
    assert len(done) >= 3 and done.is_customer_impacting.any()
    if mode == "no_dq":  # without late arrivals, labels are published during the run, not only at stop
        assert (done.landed < FINAL).sum() >= 3

    kpis = read_table(out, "kpis")
    rid = kpis.record_id.str.extract(r"^K-(?P<cell>.+)-(?P<ts>\d{12})$")
    kpis["cell"] = rid["cell"]
    kpis["t"] = pd.to_datetime(rid["ts"], format="%Y%m%d%H%M", utc=True)  # event_ts may be a DQ defect
    kpis["emitted"] = pd.to_datetime(kpis.emitted_ts, utc=True)
    alarms = read_table(out, "alarms")
    alarms["emitted"] = pd.to_datetime(alarms.emitted_ts, utc=True)

    checked = 0
    for _, r in done.iterrows():
        ids = {opaque_id("ALM", r.incident_id, n) + s for n in range(r.n_alarms) for s in ("-R", "-C")}
        last = [alarms.loc[alarms.record_id.isin(ids), "emitted"].max()]
        if r.is_customer_impacting:
            k = kpis[kpis.cell.isin(r.affected_cell_ids) & (kpis.t < r.impact_end_ts)
                     & (kpis.t + pd.Timedelta(seconds=STEP_S) > r.impact_start_ts)]
            assert len(k), r.incident_id
            last.append(k.emitted.max())
        last = max(x for x in last if pd.notna(x))
        assert last < r.landed, (r.incident_id, r.fault_type, last, r.landed)
        checked += 1
    assert checked == len(done)
    # Only in-flight incidents are censored; their rows are written once, at the stop.
    assert (inc[inc.is_censored & (inc.fault_type != "FLAPPING_ELEMENT")].landed == FINAL).all()
    assert res["censored_incidents"] == (inc.is_censored & (inc.fault_type != "FLAPPING_ELEMENT")).sum()


def test_every_dq_log_row_describes_an_emitted_record(run):
    out, _, mode = run
    if mode == "no_dq":
        assert not list((out / "ground_truth" / "dq_injections").rglob("*.json"))
        return
    log = read_table(out, "ground_truth/dq_injections")
    assert len(log) and set(log.defect_type) >= {"late_arrival", "duplicate", "malformed", "null"}
    for feed in FEEDS:
        lf = log[log.feed == feed]
        emitted = set(read_table(out, feed).record_id.dropna())
        readable = lf[lf.defect_subtype != "truncated_json"]
        missing = set(readable.record_id) - emitted
        assert not missing, (feed, sorted(missing)[:5])
        # Truncated lines cannot be parsed back, but each logged one is in the feed exactly once.
        assert count_bad_json_lines(out, feed) == (lf.defect_subtype == "truncated_json").sum(), feed
    assert not log.duplicated(["feed", "record_id"]).any()  # at most one defect per record


def _records(path: str) -> list[dict]:
    rows = []
    with open(path) as fh:
        for line in fh:
            with contextlib.suppress(json.JSONDecodeError):
                rows.append(json.loads(line))
    return rows


def test_dq_log_lands_with_its_record(run):
    """A DQ-log row is published in the micro-batch where its record first lands, never earlier."""
    out, _, mode = run
    if mode == "no_dq":
        return
    rows = []
    for f in glob.glob(str(out / "ground_truth" / "dq_injections" / "**" / "*.json"), recursive=True):
        rows += [{**r, "landed": _landing(f)} for r in _records(f)]
    log = pd.DataFrame(rows)
    for feed in FEEDS:
        first: dict[str, pd.Timestamp] = {}
        for f in glob.glob(str(out / feed / "**" / "*.json"), recursive=True):
            landed = _landing(f)
            for r in _records(f):
                if r.get("record_id") is not None:
                    first[r["record_id"]] = min(first.get(r["record_id"], FINAL), landed)
        recs = log[(log.feed == feed) & (log.defect_subtype != "truncated_json")]
        assert len(recs), feed
        assert (recs.landed == recs.record_id.map(first)).all(), feed


def test_bounded_stop_drops_unobserved_records_with_their_dq_rows(tmp_path):
    """Alarms for future events (generated at the top of the hour) are dropped at a stop together with
    their DQ-log rows."""
    out = tmp_path / "s"
    _stream(out, DQConfig().scaled(10), n=20)
    t_end = pd.Timestamp(START, tz="UTC") + pd.Timedelta(minutes=20)
    alarms = read_table(out, "alarms")
    ok_ts = pd.to_datetime(alarms.event_ts, errors="coerce", utc=True, format="ISO8601")
    clean = ok_ts.notna() & ok_ts.dt.year.between(2000, 2098)
    assert (ok_ts[clean] < t_end).all()
    log = read_table(out, "ground_truth/dq_injections")
    al = log[(log.feed == "alarms") & (log.defect_subtype != "truncated_json")]
    assert len(al) and set(al.record_id) <= set(alarms.record_id.dropna())
