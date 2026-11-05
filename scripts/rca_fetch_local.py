"""Developer helper: download the RCA inputs of one run (optionally one region) from a SQL warehouse into
local Parquet files, to iterate on features offline. Uses the CLI profile's OAuth credentials.

    python scripts/rca_fetch_local.py --profile febar --warehouse <id> --run history_1m --region WA --out /tmp/rca
"""

from __future__ import annotations

import argparse
import http.client
import io
import time
import urllib.request
from pathlib import Path

import pyarrow as pa
import pyarrow.ipc as ipc
import pyarrow.parquet as pq
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition, Format, StatementState

from netmon_pipeline.rca.sources import queries


def _download(url: str, tries: int = 5) -> bytes:
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:  # presigned URL, no auth header
                return resp.read()
        except (http.client.IncompleteRead, OSError):
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))
    raise AssertionError


def fetch(w: WorkspaceClient, warehouse: str, sql: str) -> pa.Table:
    r = w.statement_execution.execute_statement(statement=sql, warehouse_id=warehouse, wait_timeout="50s",
                                                disposition=Disposition.EXTERNAL_LINKS, format=Format.ARROW_STREAM)
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"{r.status.state}: {r.status.error}")
    tables = []
    chunk = r.result
    while chunk is not None:
        for link in chunk.external_links or []:
            tables.append(ipc.open_stream(io.BytesIO(_download(link.external_link))).read_all())
        nxt = (chunk.external_links or [None])[-1]
        idx = getattr(nxt, "next_chunk_index", None) if nxt else None
        chunk = w.statement_execution.get_statement_result_chunk_n(r.statement_id, idx) if idx is not None else None
    return pa.concat_tables(tables) if tables else pa.table({})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="febar")
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--catalog", default="telco_netmon_febar_catalog")
    ap.add_argument("--run", required=True)
    ap.add_argument("--region")
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", help="comma-separated subset of the queries")
    a = ap.parse_args()
    w = WorkspaceClient(profile=a.profile)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ap_only = set(a.only.split(",")) if a.only else None
    for name, sql in queries(a.catalog, a.run, a.region).items():
        if ap_only and name not in ap_only:
            continue
        t = fetch(w, a.warehouse, sql)
        pq.write_table(t, out / f"{name}.parquet")
        print(name, t.num_rows)


if __name__ == "__main__":
    main()
