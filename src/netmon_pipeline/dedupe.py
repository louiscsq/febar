"""Reference model of the silver deduplication (`dropDuplicatesWithinWatermark` on `record_id`).

Spark semantics, per micro-batch: rows whose watermark column is older than the current watermark are
dropped as late; a row whose key is still in state is dropped as a duplicate; otherwise it is emitted and
its key kept in state until the watermark passes its time. After the batch the watermark advances to
max(watermark column) - delay.

Silver watermarks on the **ingestion time** (`_ingested_at`, set by bronze when Auto Loader picks the file
up). That clock only moves forward, so no valid row is ever "late" for the deduper, however late its file
is discovered and however old its event or delivery time. Watermarking on the file modification time or
the delivery time instead drops a file that is discovered after newer files (see the tests). The price of
bounded state is the horizon: a redelivery ingested more than `delay` after the original is admitted
again. `duplicate_audit` is how that is measured (`eval_dq_capture`, n_single_copy_in_silver).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field


@dataclass
class WatermarkDeduper:
    delay_s: float
    wm_col: str = "ingested_s"
    watermark: float = float("-inf")
    state: dict[str, float] = field(default_factory=dict)
    dropped_late: list[dict] = field(default_factory=list)
    dropped_dup: list[dict] = field(default_factory=list)

    def batch(self, rows: Sequence[dict]) -> list[dict]:
        out = []
        for r in rows:
            t = r[self.wm_col]
            if t < self.watermark:
                self.dropped_late.append(r)
                continue
            if r["record_id"] in self.state:
                self.dropped_dup.append(r)
                continue
            self.state[r["record_id"]] = t
            out.append(r)
        if rows:
            self.watermark = max(self.watermark, max(r[self.wm_col] for r in rows) - self.delay_s)
        self.state = {k: t for k, t in self.state.items() if t >= self.watermark}
        return out


def run(batches: Iterable[Sequence[dict]], delay_s: float, wm_col: str = "ingested_s") -> tuple[list[dict], WatermarkDeduper]:
    d = WatermarkDeduper(delay_s, wm_col)
    out: list[dict] = []
    for b in batches:
        out += d.batch(b)
    return out, d


def duplicate_audit(rows: Iterable[dict]) -> dict[str, int]:
    """record_id -> copies, for ids that reached silver more than once."""
    n = Counter(r["record_id"] for r in rows)
    return {k: v for k, v in n.items() if v > 1}
