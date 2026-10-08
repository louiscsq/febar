"""Command-line entry point: `netmon-datagen batch ...` / `netmon-datagen stream ...`."""

from __future__ import annotations

import argparse
import json

from netmon_datagen.config import PRESETS, DQConfig, FaultConfig, GeneratorConfig


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--out", required=True, help="output directory (local path or /Volumes/<cat>/<schema>/<vol>/...)")
    p.add_argument("--scale", default="large", choices=sorted(PRESETS))
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--dq-scale", type=float, default=1.0, help="multiply all DQ defect rates (0 disables)")
    p.add_argument("--fault-rate-multiplier", type=float, default=1.0)
    p.add_argument("--no-faults", action="store_true", help="disable faults and red herrings (clean baseline)")
    p.add_argument("--no-red-herrings", action="store_true")
    p.add_argument("--min-per-type", type=int, default=None,
                   help="guarantee N incidents of every fault type (default: 1 for tiny, else 0)")


def _config(a: argparse.Namespace, **extra) -> GeneratorConfig:
    min_per_type = a.min_per_type if a.min_per_type is not None else (1 if a.scale == "tiny" else 0)
    faults = FaultConfig(enabled=not a.no_faults, rate_multiplier=a.fault_rate_multiplier,
                         red_herrings=not a.no_red_herrings, min_per_type=min_per_type)
    return GeneratorConfig.for_scale(a.scale, seed=a.seed, dq=DQConfig().scaled(a.dq_scale), faults=faults, **extra)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="netmon-datagen", description=__doc__)
    sub = ap.add_subparsers(dest="mode", required=True)

    b = sub.add_parser("batch", help="generate N days of history as date-partitioned files")
    _common(b)
    b.add_argument("--days", type=int, default=30)
    b.add_argument("--start", default=None, help="UTC start date (YYYY-MM-DD); default today minus --days")
    b.add_argument("--step-minutes", type=int, default=15, help="KPI reporting period")
    b.add_argument("--format", dest="fmt", default="parquet", choices=["parquet", "json"])

    s = sub.add_parser("stream", help="emit JSON micro-batches to a landing directory")
    _common(s)
    s.add_argument("--start", default=None, help="simulated start time (UTC ISO); default now. Set for determinism")
    s.add_argument("--step-seconds", type=int, default=60, help="simulated time per micro-batch")
    s.add_argument("--interval-seconds", type=float, default=60.0, help="wall-clock seconds between batches")
    s.add_argument("--max-batches", type=int, default=None, help="stop after N batches (default: run forever)")

    a = ap.parse_args(argv)
    if a.mode == "batch":
        from netmon_datagen.batch import generate_history

        cfg = _config(a, days=a.days, start=a.start, step_minutes=a.step_minutes, fmt=a.fmt)
        manifest = generate_history(cfg, a.out)
        print(json.dumps(manifest["counts"], indent=2, default=str))
    else:
        from netmon_datagen.stream import run_stream

        cfg = _config(a)
        print(json.dumps(run_stream(cfg, a.out, step_seconds=a.step_seconds, interval_seconds=a.interval_seconds,
                                    max_batches=a.max_batches, start=a.start), default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
