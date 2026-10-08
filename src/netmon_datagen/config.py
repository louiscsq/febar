"""Generator configuration: scale presets, fault rates, data-quality defect rates, RNG helpers."""

from __future__ import annotations

import dataclasses
import zlib
from dataclasses import dataclass, field, replace

import numpy as np


@dataclass(frozen=True)
class ScalePreset:
    """Size of the simulated network and subscriber base."""

    name: str
    regions: int  # number of regions taken (in order) from the region catalogue
    sites: int  # total base-station sites across all regions
    upf_per_region: int  # user-plane core nodes per region
    routers_per_region: int  # aggregation routers per region
    sites_per_backhaul: float  # mean sites chained behind one backhaul link
    subscribers: int  # synthetic subscriber population
    session_sample_rate: float  # fraction of real session volume emitted as xDRs
    # Explicit region codes (in catalogue order otherwise): small presets pick regions that cover every
    # time zone class and fault type (metro + tropical/long-haul north) rather than just the biggest cities.
    region_codes: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.region_codes is not None and len(self.region_codes) != self.regions:
            raise ValueError(f"preset {self.name!r}: regions={self.regions} but {len(self.region_codes)} codes")


PRESETS: dict[str, ScalePreset] = {
    # Unit tests: ~25 sites / ~100 cells over Sydney (DST) and North Queensland (no DST, tropical, long-haul).
    "tiny": ScalePreset("tiny", regions=2, sites=24, upf_per_region=1, routers_per_region=2,
                        sites_per_backhaul=2.0, subscribers=3_000, session_sample_rate=0.02,
                        region_codes=("NSW", "NQL")),
    # Dev / quick demo: ~300 sites / ~1.3k cells over four time zones (UTC+8 .. +11).
    "small": ScalePreset("small", regions=4, sites=300, upf_per_region=1, routers_per_region=4,
                         sites_per_backhaul=2.5, subscribers=100_000, session_sample_rate=0.01,
                         region_codes=("NSW", "VIC", "WA", "NQL")),
    # Default: a ~5k-site national footprint (~22k cells) across all ten regions.
    "large": ScalePreset("large", regions=10, sites=5_000, upf_per_region=2, routers_per_region=10,
                         sites_per_backhaul=2.5, subscribers=2_000_000, session_sample_rate=0.0025),
    # Full national footprint of a tier-1 operator (~20k sites / ~85k cells). Use with fewer days.
    "xl": ScalePreset("xl", regions=10, sites=20_000, upf_per_region=3, routers_per_region=30,
                      sites_per_backhaul=2.5, subscribers=8_000_000, session_sample_rate=0.001),
}


def get_preset(name: str) -> ScalePreset:
    try:
        return PRESETS[name]
    except KeyError:
        raise ValueError(f"unknown scale preset {name!r}; choose from {sorted(PRESETS)}") from None


@dataclass(frozen=True)
class DQConfig:
    """Per-record probabilities of injected data-quality defects (applied to kpis/alarms/sessions)."""

    duplicate_rate: float = 0.005  # exact re-delivery of a record (same record_id)
    late_rate: float = 0.01  # emitted 30 min .. 36 h after the event
    malformed_rate: float = 0.002  # unparseable timestamp / type mismatch / truncated JSON line
    null_rate: float = 0.005  # one mandatory field nulled
    out_of_range_rate: float = 0.002  # physically impossible value (e.g. success rate 140%)

    def __post_init__(self) -> None:
        # Defects are disjoint per record (drawn from one permutation), so the rates must partition at
        # most the whole population; otherwise later defect types would be silently under-delivered.
        rates = dataclasses.asdict(self)
        bad = {k: v for k, v in rates.items() if not 0.0 <= v <= 1.0}
        if bad:
            raise ValueError(f"DQ rates must be within [0, 1], got {bad}")
        if self.total > 1.0 + 1e-9:
            raise ValueError(f"DQ rates must sum to <= 1 (each record gets at most one defect); got "
                             f"{self.total:.4f} from {rates}. Lower the rates or the --dq-scale factor.")

    @classmethod
    def none(cls) -> DQConfig:
        return cls(0.0, 0.0, 0.0, 0.0, 0.0)

    def scaled(self, factor: float) -> DQConfig:
        """Multiply every rate by `factor` (raises ValueError if the result is not a valid config)."""
        if factor < 0:
            raise ValueError(f"DQ scale factor must be >= 0, got {factor}")
        return DQConfig(*(v * factor for v in (
            self.duplicate_rate, self.late_rate, self.malformed_rate, self.null_rate, self.out_of_range_rate)))

    @property
    def total(self) -> float:
        return self.duplicate_rate + self.late_rate + self.malformed_rate + self.null_rate + self.out_of_range_rate


@dataclass(frozen=True)
class FaultConfig:
    """Fault and red-herring injection controls (per-type base rates live in `faults.FAULT_SPECS`)."""

    enabled: bool = True
    rate_multiplier: float = 1.0  # scales every fault / red-herring rate
    red_herrings: bool = True  # alarm storms, planned maintenance, traffic surges, flapping elements
    min_per_type: int = 1  # batch: guarantee >= N incidents of every type per run (ignored when streaming)
    flapping_fraction: float = 0.001  # share of cells/sites/links that are chronically flapping


@dataclass(frozen=True)
class GeneratorConfig:
    scale: ScalePreset = field(default_factory=lambda: PRESETS["large"])
    seed: int = 42
    days: int = 30
    start: str | None = None  # ISO date/datetime (UTC); default = today 00:00 UTC minus `days`
    step_minutes: int = 15  # KPI reporting period for batch history (3GPP ROP = 15 min)
    fmt: str = "parquet"  # parquet | json
    dq: DQConfig = field(default_factory=DQConfig)
    faults: FaultConfig = field(default_factory=FaultConfig)

    def with_(self, **kwargs) -> GeneratorConfig:
        return replace(self, **kwargs)

    @classmethod
    def for_scale(cls, scale: str, **kwargs) -> GeneratorConfig:
        return cls(scale=get_preset(scale), **kwargs)


def rng_for(seed: int, *keys: object) -> np.random.Generator:
    """Independent, reproducible RNG stream for (seed, *keys).

    Separate streams per component mean that e.g. turning faults off leaves baseline KPI noise
    bit-identical, which is what makes counterfactual comparisons (and the propagation test) possible.
    """
    words = [seed & 0xFFFFFFFF] + [zlib.crc32(str(k).encode()) for k in keys]
    return np.random.default_rng(np.random.SeedSequence(words))
