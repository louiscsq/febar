"""Pipeline settings, read from the pipeline `configuration` block (resources/netmon.pipeline.yml)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    catalog: str
    landing_root: str  # /Volumes/<catalog>/<schema>/<volume>; generator runs live in sub-directories
    bronze: str  # fully qualified schemas, e.g. `cat`.`netmon_bronze`
    silver: str
    gold: str
    eval: str
    gov: str
    stream_step_seconds: int = 60

    @classmethod
    def from_conf(cls, get: Callable[[str], str]) -> Settings:
        cat = get("netmon.catalog")

        def fq(key: str) -> str:
            return f"`{cat}`.`{get(key)}`"

        return cls(
            catalog=cat,
            landing_root=get("netmon.landing_root").rstrip("/"),
            bronze=fq("netmon.bronze_schema"),
            silver=fq("netmon.silver_schema"),
            gold=fq("netmon.gold_schema"),
            eval=fq("netmon.eval_schema"),
            gov=fq("netmon.gov_schema"),
            stream_step_seconds=int(get("netmon.stream_step_seconds")),
        )

    def feed_path(self, feed: str) -> str:
        """Glob over every generator run (history, stream, ...) for one feed."""
        return f"{self.landing_root}/*/{feed}/"
