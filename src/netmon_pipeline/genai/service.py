"""On-demand entry point for the step-5 app: summarise one open incident now.

    from databricks.sdk import WorkspaceClient
    from netmon_pipeline.genai import service
    res = service.summarise_open_incident("RCA-1a2b3c4d5e6f7a8b", WorkspaceClient(), warehouse_id="...")
    res["summary"]["likely_root_cause"], res["sms"][0]["text"]

It reads the open incident and its scored case rows (`netmon_rca.open_incidents`, `rca_live_scores`), builds the
grounded context through a SQL warehouse, and calls the AI-Gateway-governed endpoint as the caller's identity
(the app's service principal or the signed-in user with on-behalf-of auth). For the latest pre-computed summary
the app should read Lakebase (`netmon_genai.lb_incident_ai_latest`, a few ms) and call this only when the user
asks for a refresh. Nothing is written by this function; the job (`notebooks/09_genai_assistant.py`) persists.
"""

from __future__ import annotations

import time

import pandas as pd

from netmon_pipeline.genai import assistant, gateway, sources
from netmon_pipeline.genai import context as C


def warehouse_sql(ws, warehouse_id: str):
    """`sql(query) -> DataFrame` over the SQL Statement Execution API (inline JSON results)."""

    def run(q: str) -> pd.DataFrame:
        r = ws.statement_execution.execute_statement(statement=q, warehouse_id=warehouse_id, wait_timeout="50s")
        while r.status.state.value in ("PENDING", "RUNNING"):
            time.sleep(1)
            r = ws.statement_execution.get_statement(r.statement_id)
        if r.status.state.value != "SUCCEEDED":
            raise RuntimeError(f"SQL failed: {r.status.error}")
        cols = [c.name for c in r.manifest.schema.columns]
        types = {c.name: c.type_name.value if c.type_name else "STRING" for c in r.manifest.schema.columns}
        rows = list(r.result.data_array or []) if r.result else []
        while r.result and r.result.next_chunk_index:
            r.result = ws.statement_execution.get_statement_result_chunk_n(r.statement_id, r.result.next_chunk_index)
            rows += list(r.result.data_array or [])
        df = pd.DataFrame(rows, columns=cols)
        for c, t in types.items():
            if t in ("DOUBLE", "FLOAT", "DECIMAL", "INT", "LONG", "SHORT", "BYTE"):
                df[c] = pd.to_numeric(df[c], errors="coerce")
            elif t == "BOOLEAN":
                df[c] = df[c].map(lambda v: None if v is None else str(v).lower() == "true")
            elif t == "TIMESTAMP":
                df[c] = pd.to_datetime(df[c], utc=True)
        return df

    return run


def load_open_incident_context(incident_id: str, sql, catalog: str, threshold: float | None = None) -> dict:
    q = sources.Queries(catalog)
    inc = sql(q.open_incident(incident_id))
    if inc.empty:
        raise KeyError(f"no open incident {incident_id}")
    row = inc.iloc[0].to_dict()
    ref = sources.ref_from_open_incident(row, threshold)
    case = sources.utc(sql(q.case_rows("rca_live_scores", row["source_run"], row["case_id"], ref.as_of,
                                       str(row["model_version"]))))
    case = case.drop_duplicates(["case_id", "element_id"])
    return C.build_context(sources.load_inputs(sql, q, ref, row["source_run"], case))


def summarise_open_incident(incident_id: str, ws, warehouse_id: str, catalog: str = "telco_netmon_febar_catalog",
                            endpoint: str = gateway.ASSISTANT_ENDPOINT, threshold: float | None = 0.32,
                            with_sms: bool = True) -> dict:
    ctx = load_open_incident_context(incident_id, warehouse_sql(ws, warehouse_id), catalog, threshold)
    res = assistant.run(ctx, ws, endpoint, with_sms=with_sms)
    return {**res.as_dict(), "context": ctx, "generated_at": assistant.generated_at()}
