# Databricks notebook source
# MAGIC %md
# MAGIC # Lakebase: the assistant's latest summary per open incident, read back with psycopg (OAuth)
# MAGIC
# MAGIC `netmon_genai.incident_ai_latest` (Delta, Change Data Feed) is synced in TRIGGERED mode into the Lakebase
# MAGIC Provisioned instance (`resources/genai.synced_tables.yml`, Postgres database `netmon_serving`, schema
# MAGIC `netmon_genai`, table `lb_incident_ai_latest`, PK `incident_id`). The step-5 app reads it next to step 3's
# MAGIC `netmon_rca.lb_open_incidents`. This notebook does exactly what the app will do: psycopg with a one-hour OAuth
# MAGIC database credential (nothing stored), row counts, a sample, the open-incident join, and point-lookup latency.
# MAGIC Results go to `netmon_genai.lakebase_ai_check`.

# COMMAND ----------

dbutils.widgets.text("catalog", "telco_netmon_febar_catalog")
dbutils.widgets.text("genai_schema", "netmon_genai")
dbutils.widgets.text("rca_schema", "netmon_rca")
dbutils.widgets.text("instance", "banksia-netmon-lakebase")
dbutils.widgets.text("database", "netmon_serving")
dbutils.widgets.text("n_lookups", "300")

# COMMAND ----------

import json
import random
import statistics
import time
import uuid

import pandas as pd
import psycopg
from databricks.sdk import WorkspaceClient

w = {k: dbutils.widgets.get(k) for k in ["catalog", "genai_schema", "rca_schema", "instance", "database", "n_lookups"]}
ws = WorkspaceClient()
inst = ws.database.get_database_instance(w["instance"])
user = ws.current_user.me().user_name
G, S = w["genai_schema"], w["rca_schema"]


def connect() -> psycopg.Connection:
    cred = ws.database.generate_database_credential(request_id=str(uuid.uuid4()), instance_names=[w["instance"]])
    return psycopg.connect(host=inst.read_write_dns, port=5432, dbname=w["database"], user=user, password=cred.token,
                           sslmode="require", connect_timeout=30)


APP_QUERY_BY_ID = f'SELECT * FROM "{G}"."lb_incident_ai_latest" WHERE incident_id = %s'
APP_QUERY_REGION = (f'SELECT i.incident_id, i.region_code, i.detected_ts, i.suspect_1_id, i.suspect_1_score, '
                    f'a.likely_root_cause, a.confidence, a.summary, a.next_steps_json, a.sms_draft_text, '
                    f'a.sms_draft_status, a.generated_at FROM "{S}"."lb_open_incidents" i '
                    f'LEFT JOIN "{G}"."lb_incident_ai_latest" a ON a.incident_id = i.incident_id '
                    f'WHERE i.region_code = %s ORDER BY i.suspect_1_score DESC')

res = {"run_at": pd.Timestamp.now(tz="UTC").isoformat(), "instance": inst.name, "database": w["database"]}
with connect() as conn:
    res["rows"] = conn.execute(f'SELECT count(*) FROM "{G}"."lb_incident_ai_latest"').fetchone()[0]
    cur = conn.execute(f'SELECT incident_id, region_code, likely_root_cause, fault_hypothesis, confidence, status, '
                       f'summary, sms_draft_text, sms_draft_status, generated_by, generated_at '
                       f'FROM "{G}"."lb_incident_ai_latest" ORDER BY incident_id LIMIT 5')
    cols = [d.name for d in cur.description]
    res["sample"] = [dict(zip(cols, map(str, r), strict=True)) for r in cur.fetchall()]
    res["open_incidents_without_summary"] = conn.execute(
        f'SELECT count(*) FROM "{S}"."lb_open_incidents" i LEFT JOIN "{G}"."lb_incident_ai_latest" a '
        f'ON a.incident_id = i.incident_id WHERE a.incident_id IS NULL').fetchone()[0]
    ids = [r[0] for r in conn.execute(f'SELECT incident_id FROM "{G}"."lb_incident_ai_latest"').fetchall()]
    regions = [r[0] for r in conn.execute(f'SELECT DISTINCT region_code FROM "{S}"."lb_open_incidents"').fetchall()]
    rng = random.Random(7)
    rows = []
    for name, (q, args) in {"ai summary by incident_id (PK)": (APP_QUERY_BY_ID, lambda: (rng.choice(ids),)),
                            "open incidents of a region + AI summary": (APP_QUERY_REGION,
                                                                        lambda: (rng.choice(regions),))}.items():
        for _ in range(10):
            conn.execute(q, args()).fetchall()
        lat = []
        for _ in range(int(w["n_lookups"])):
            t0 = time.perf_counter()
            conn.execute(q, args()).fetchall()
            lat.append((time.perf_counter() - t0) * 1000)
        qs = statistics.quantiles(lat, n=100)
        rows.append({"query": name, "n": len(lat), "p50_ms": round(statistics.median(lat), 2),
                     "p95_ms": round(qs[94], 2), "p99_ms": round(qs[98], 2), "max_ms": round(max(lat), 2)})
print(json.dumps({k: v for k, v in res.items()}, indent=1, default=str))
df = pd.DataFrame(rows).assign(run_at=res["run_at"], rows=res["rows"],
                               open_incidents_without_summary=res["open_incidents_without_summary"],
                               details=json.dumps(res, default=str))
spark.createDataFrame(df).write.mode("append").option("mergeSchema", "true") \
    .saveAsTable(f"`{w['catalog']}`.`{G}`.lakebase_ai_check")
print(df[["query", "n", "p50_ms", "p95_ms", "p99_ms", "max_ms"]].to_string(index=False))
