"""Silver dedupe watermark (ingestion time) and the local-calendar keys used by the baseline."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from netmon_pipeline import dedupe, detection, rules

H = 3600


def rec(rid, ingested_s, emitted_s=None, file_mtime_s=None):
    return {"record_id": rid, "ingested_s": ingested_s, "emitted_s": emitted_s if emitted_s is not None else ingested_s,
            "file_mtime_s": file_mtime_s if file_mtime_s is not None else ingested_s}


DELAY = 3600  # rules.DEDUPE_WATERMARK


def test_silver_watermarks_on_ingestion_time():
    assert rules.DEDUPE_WATERMARK_COLUMN == "_ingested_at" and rules.DEDUPE_WATERMARK == "1 hour"


def test_delayed_file_discovery_is_kept_with_ingestion_watermark():
    # Batch 1 ingests newer files (mtime 10:00); a file written at 08:00 is only discovered in batch 2.
    t0 = 10 * H
    b1 = [rec(f"new-{i}", ingested_s=t0, file_mtime_s=t0) for i in range(3)]
    b2 = [rec(f"old-{i}", ingested_s=t0 + 60, emitted_s=8 * H, file_mtime_s=8 * H) for i in range(3)]
    kept, d = dedupe.run([b1, b2], DELAY, wm_col="ingested_s")
    assert {r["record_id"] for r in kept} == {"new-0", "new-1", "new-2", "old-0", "old-1", "old-2"}
    assert d.dropped_late == []
    # The previous design (watermark on file / delivery time) silently dropped the late-discovered file.
    kept_mtime, d2 = dedupe.run([b1, b2], 15 * 60, wm_col="file_mtime_s")
    assert len(kept_mtime) == 3 and len(d2.dropped_late) == 3


def test_redelivery_within_horizon_is_dropped():
    b1 = [rec("K-1", ingested_s=0)]
    b2 = [rec("K-1", ingested_s=600), rec("K-2", ingested_s=600)]  # generator redelivers 1-600 s later
    kept, d = dedupe.run([b1, b2], DELAY)
    assert [r["record_id"] for r in kept] == ["K-1", "K-2"] and len(d.dropped_dup) == 1
    assert dedupe.duplicate_audit(kept) == {}


def test_post_expiry_redelivery_is_admitted_and_audited():
    # The state for K-1 is evicted once the watermark passes it; a redelivery after that is admitted
    # (bounded state) and shows up in the duplicate audit (eval_dq_capture.n_single_copy_in_silver).
    batches = [[rec("K-1", 0)], [rec("K-9", 2 * H)], [rec("K-1", 2 * H + 60)]]
    kept, d = dedupe.run(batches, DELAY)
    assert "K-1" not in d.state or d.state["K-1"] == 2 * H + 60
    assert dedupe.duplicate_audit(kept) == {"K-1": 2}
    assert d.dropped_late == []  # still not "late": ingestion time only moves forward


def test_one_shot_backfill_dedupes_everything():
    # A full refresh ingests the whole history in one micro-batch: every redelivery is caught.
    b = [rec(f"K-{i % 50}", ingested_s=5) for i in range(100)]
    kept, d = dedupe.run([b], DELAY)
    assert len(kept) == 50 and len(d.dropped_dup) == 50


UTC = timezone.utc


@pytest.mark.parametrize("ts, tz, expected", [
    # Sydney (AEST +10): 13:30 UTC is 23:30 local, 14:30 UTC is 00:30 the next local day.
    ("2026-09-10T13:30:00", "Australia/Sydney", (date(2026, 9, 10), 23, "weekday")),
    ("2026-09-10T14:30:00", "Australia/Sydney", (date(2026, 9, 11), 0, "weekday")),
    # DST starts Sun 2026-10-04 02:00 AEST -> 03:00 AEDT (16:00 UTC Sat): 15:59 UTC is 01:59 Sunday,
    # 16:00 UTC is 03:00 Sunday (02:xx never exists).
    ("2026-10-03T15:59:00", "Australia/Sydney", (date(2026, 10, 4), 1, "weekend")),
    ("2026-10-03T16:00:00", "Australia/Sydney", (date(2026, 10, 4), 3, "weekend")),
    # After DST start local midnight is 13:00 UTC, not 14:00.
    ("2026-10-05T13:00:00", "Australia/Sydney", (date(2026, 10, 6), 0, "weekday")),
    ("2026-10-05T12:59:00", "Australia/Sydney", (date(2026, 10, 5), 23, "weekday")),
    # DST ends Sun 2026-04-05 03:00 AEDT -> 02:00 AEST (16:00 UTC Sat): 02:xx happens twice.
    ("2026-04-04T15:30:00", "Australia/Sydney", (date(2026, 4, 5), 2, "weekend")),
    ("2026-04-04T16:30:00", "Australia/Sydney", (date(2026, 4, 5), 2, "weekend")),
    # Brisbane: no DST, +10 all year; on the same instant as the Sydney DST start it is 02:00, not 03:00.
    ("2026-10-03T16:00:00", "Australia/Brisbane", (date(2026, 10, 4), 2, "weekend")),
    ("2026-10-04T13:59:00", "Australia/Brisbane", (date(2026, 10, 4), 23, "weekend")),
    ("2026-10-04T14:00:00", "Australia/Brisbane", (date(2026, 10, 5), 0, "weekday")),
    # Adelaide +9:30 (ACST) / +10:30 (ACDT from 2026-10-04): local midnight on a half hour.
    ("2026-09-10T14:29:00", "Australia/Adelaide", (date(2026, 9, 10), 23, "weekday")),
    ("2026-09-10T14:30:00", "Australia/Adelaide", (date(2026, 9, 11), 0, "weekday")),
    ("2026-10-05T13:30:00", "Australia/Adelaide", (date(2026, 10, 6), 0, "weekday")),
    # Perth +8: Friday 16:00 UTC is Saturday 00:00 local (weekend), though still Friday in UTC.
    ("2026-10-09T16:00:00", "Australia/Perth", (date(2026, 10, 10), 0, "weekend")),
])
def test_local_keys_around_midnight_and_dst(ts, tz, expected):
    t = datetime.fromisoformat(ts).replace(tzinfo=UTC)
    assert detection.local_keys(t, tz) == expected


def test_local_date_differs_from_utc_date_near_local_midnight():
    t = datetime(2026, 10, 5, 13, 30, tzinfo=UTC)  # 00:30 AEDT on 6 Oct
    local_date, hour, _ = detection.local_keys(t, "Australia/Sydney")
    assert t.date() == date(2026, 10, 5) and local_date == date(2026, 10, 6) and hour == 0
    # Its baseline comes from local days 22 Sep .. 5 Oct: the local day it belongs to is excluded.
    lo, hi = detection.baseline_window(local_date.toordinal())
    assert date.fromordinal(hi) == date(2026, 10, 5) and date.fromordinal(lo) == date(2026, 9, 22)


def test_every_local_hour_keyed_once_per_day_across_dst_start():
    # Hourly instants over the Sydney DST-start local day: 23 distinct local hours (02 is skipped).
    start = datetime(2026, 10, 3, 14, 0, tzinfo=UTC)  # 2026-10-04 00:00 AEST
    keys = [detection.local_keys(start + timedelta(hours=i), "Australia/Sydney") for i in range(23)]
    assert {k[0] for k in keys} == {date(2026, 10, 4)}
    assert sorted(k[1] for k in keys) == [h for h in range(24) if h != 2]


def test_sql_mirrors():
    assert detection.LOCAL_DATE_SQL.format(ts="event_ts") == "to_date(from_utc_timestamp(event_ts, timezone))"
    assert detection.DAY_TYPE_SQL.format(ts="x").startswith("CASE WHEN dayofweek(x) IN (1, 7)")
