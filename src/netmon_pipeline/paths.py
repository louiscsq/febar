"""Landing-path conventions: which generator run a file came from and when it landed (simulated time).

Streaming micro-batch files are named `batch-<YYYYmmddTHHMMSS>-<seq>.json` and land at the batch
start plus `step_seconds` of simulated time (data_model.md, "streaming emission ordering"). This is
when the evidence in the file became available to the NOC, which is what time-to-detect is measured
from. Batch history files (`part-*`) have no landing time; there the record's `emitted_ts` is used.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

BATCH_RE = r"batch-([0-9]{8}T[0-9]{6})-[0-9a-z]+[.]json$"
RUN_RE = r"/landing/([^/]+)/"


def run_name(path: str) -> str | None:
    m = re.search(RUN_RE, path)
    return m.group(1) if m else None


def landed_at(path: str, step_seconds: int) -> datetime | None:
    m = re.search(BATCH_RE, path)
    if not m:
        return None
    t = datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    return t + timedelta(seconds=step_seconds)


def run_name_sql(path_col: str = "_source_file") -> str:
    return f"regexp_extract({path_col}, '{RUN_RE}', 1)"


def landed_at_sql(path_col: str, step_seconds: int) -> str:
    """SQL TIMESTAMP (or NULL for non-stream files) mirroring `landed_at`."""
    stamp = f"nullif(regexp_extract({path_col}, '{BATCH_RE}', 1), '')"
    return f"try_to_timestamp({stamp}, \"yyyyMMdd'T'HHmmss\") + INTERVAL {int(step_seconds)} SECONDS"
