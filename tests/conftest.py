from __future__ import annotations

import contextlib
import glob
import json
import os
import time
from pathlib import Path

import pandas as pd
import pytest

from netmon_datagen.batch import generate_history
from netmon_datagen.config import DQConfig, FaultConfig, GeneratorConfig

START = "2026-09-04"  # Friday: a 3-day window covers weekday and weekend
DAYS = 3


def tiny_cfg(**kw) -> GeneratorConfig:
    kw.setdefault("days", DAYS)
    kw.setdefault("start", START)
    return GeneratorConfig.for_scale("tiny", **kw)


def read_table(root: Path, name: str) -> pd.DataFrame:
    """Read every file of a table (parquet or JSON lines). Unparseable JSON lines are skipped."""
    files = sorted(glob.glob(str(root / name / "**" / "*.*"), recursive=True))
    frames = []
    for f in files:
        if f.endswith(".parquet"):
            frames.append(pd.read_parquet(f))
        elif f.endswith(".json"):
            rows = []
            with open(f) as fh:
                for line in fh:
                    with contextlib.suppress(json.JSONDecodeError):
                        rows.append(json.loads(line))
            frames.append(pd.DataFrame(rows))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def count_bad_json_lines(root: Path, name: str) -> int:
    bad = 0
    for f in glob.glob(str(root / name / "**" / "*.json"), recursive=True):
        with open(f) as fh:
            for line in fh:
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    bad += 1
    return bad


@pytest.fixture(scope="session")
def history_json(tmp_path_factory) -> tuple[Path, dict]:
    """Full-fat tiny history: faults + red herrings + DQ defects, JSON output."""
    out = tmp_path_factory.mktemp("hist_json")
    manifest = generate_history(tiny_cfg(fmt="json"), out, log=lambda *a: None)
    return out, manifest


@pytest.fixture(scope="session")
def counterfactual_pair(tmp_path_factory) -> tuple[Path, Path]:
    """Same seed with and without faults, no DQ defects, Parquet output."""
    with_f = tmp_path_factory.mktemp("with_faults")
    without_f = tmp_path_factory.mktemp("without_faults")
    generate_history(tiny_cfg(dq=DQConfig.none()), with_f, log=lambda *a: None)
    generate_history(tiny_cfg(dq=DQConfig.none(), faults=FaultConfig(enabled=False)), without_f, log=lambda *a: None)
    return with_f, without_f


# ---- local Spark (tests of the Spark transforms the pipeline runs; needs pyspark + Java 17/21) ----

def _java_home():
    for p in ("/opt/homebrew/opt/openjdk@17", "/opt/homebrew/Cellar/openjdk@17", "/usr/lib/jvm/java-17-openjdk-amd64",
              "/usr/lib/jvm/java-17-openjdk-arm64"):
        for cand in sorted(Path(p).glob("**/Contents/Home")) if Path(p).exists() and "Cellar" in p else [Path(p)]:
            if (cand / "bin" / "java").exists():
                return str(cand)
    return None


@pytest.fixture(scope="session")
def spark():
    pytest.importorskip("pyspark")
    jh = _java_home()
    if jh and "JAVA_HOME" not in os.environ:
        os.environ["JAVA_HOME"] = jh
    # pyspark returns naive datetimes in the process time zone: pin it to UTC
    os.environ["TZ"] = "UTC"
    time.tzset()
    from pyspark.sql import SparkSession

    s = (SparkSession.builder.master("local[1]").appName("netmon-windows-test")
         .config("spark.sql.session.timeZone", "UTC").config("spark.ui.enabled", "false")
         .config("spark.sql.shuffle.partitions", "1").getOrCreate())
    yield s
    s.stop()
