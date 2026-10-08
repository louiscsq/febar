"""Writers: atomic Parquet / JSON-lines files, date partitioning by emission time, and a spool that
holds records until their (possibly late) emission time has been reached."""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from netmon_datagen.kpis import to_iso

EXT = {"parquet": "parquet", "json": "json"}


def _public(df: pd.DataFrame) -> pd.DataFrame:
    return df[[c for c in df.columns if not c.startswith("_")]]


def write_frame(df: pd.DataFrame, path: Path, fmt: str) -> Path:
    """Write atomically (temp file + rename) so streaming readers never see partial files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp"
    if fmt == "parquet":
        _public(df).to_parquet(tmp, index=False, engine="pyarrow")
    elif fmt == "json":
        truncate = df["_truncate"].to_numpy(dtype=bool) if "_truncate" in df else None
        text = _public(df).to_json(orient="records", lines=True, date_format="iso") if len(df) else ""
        if truncate is not None and truncate.any():
            lines = text.splitlines()
            for i in np.flatnonzero(truncate):
                lines[i] = lines[i][: max(1, len(lines[i]) // 2)]
            text = "\n".join(lines) + "\n"
        tmp.write_text(text)
    else:
        raise ValueError(f"unsupported format {fmt!r}")
    os.replace(tmp, path)
    return path


def write_partitioned(df: pd.DataFrame, root: Path, feed: str, fmt: str, stem: str) -> list[Path]:
    """Write `df` under root/feed/date=YYYY-MM-DD/ partitioned by emission date."""
    if df.empty:
        return []
    df = df.copy()
    df["emitted_ts"] = to_iso(df["_emitted"].to_numpy())
    day = df["_emitted"].to_numpy().astype("datetime64[D]").astype(str)
    out = []
    for d in np.unique(day):
        part = df[day == d]
        out.append(write_frame(part, root / feed / f"date={d}" / f"{stem}.{EXT[fmt]}", fmt))
    return out


def ordered(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    extra = [c for c in df.columns if c.startswith("_")]
    for c in columns:
        if c not in df.columns:
            df[c] = None
    return df[columns + extra]


class Spool:
    """Per-feed buffer of records keyed by emission time."""

    def __init__(self) -> None:
        self._pending: dict[str, list[pd.DataFrame]] = {}

    def push(self, feed: str, df: pd.DataFrame) -> None:
        if len(df):
            self._pending.setdefault(feed, []).append(df)

    def release(self, feed: str, until: np.datetime64 | None) -> pd.DataFrame:
        parts = self._pending.get(feed, [])
        if not parts:
            return pd.DataFrame()
        df = pd.concat(parts, ignore_index=True) if len(parts) > 1 else parts[0]
        if until is None:
            self._pending[feed] = []
            return df.sort_values("_emitted", kind="stable").reset_index(drop=True)
        due = df["_emitted"].to_numpy() < np.datetime64(until, "s")
        self._pending[feed] = [df[~due]] if (~due).any() else []
        return df[due].sort_values("_emitted", kind="stable").reset_index(drop=True)

    def feeds(self) -> list[str]:
        return list(self._pending)


def write_json_manifest(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp"
    tmp.write_text(json.dumps(obj, indent=2, default=str))
    os.replace(tmp, path)
