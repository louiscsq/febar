# Databricks notebook source
# MAGIC %md
# MAGIC # Lakebase: database setup and read-latency check (psycopg + OAuth)
# MAGIC
# MAGIC Connects to the Lakebase Provisioned instance with **psycopg** and a short-lived OAuth token from
# MAGIC `generate_database_credential` (no password or secret is stored anywhere; the token expires after an hour).
# MAGIC
# MAGIC - `stage = setup`: creates the Postgres database the synced tables write into (idempotent).
# MAGIC - `stage = check`: row counts and samples of the synced tables, then the latency of point lookups the
# MAGIC   topology app will make (element status by `element_id`, open incidents by region), measured from this
# MAGIC   serverless job. Results go to `netmon_rca.lakebase_latency_check` (one row per run and query).

# COMMAND ----------

dbutils.widgets.text("catalog", "telco_netmon_febar_catalog")
dbutils.widgets.text("rca_schema", "netmon_rca")
dbutils.widgets.text("instance", "banksia-netmon-lakebase")
dbutils.widgets.text("database", "netmon_serving")
dbutils.widgets.dropdown("stage", "check", ["setup", "check"])
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

w = {k: dbutils.widgets.get(k) for k in ["catalog", "rca_schema", "instance", "database", "stage", "n_lookups"]}
ws = WorkspaceClient()
inst = ws.database.get_database_instance(w["instance"])
user = ws.current_user.me().user_name


def connect(dbname: str) -> psycopg.Connection:
    # OAuth: a fresh database credential per connection, never persisted.
    cred = ws.database.generate_database_credential(request_id=str(uuid.uuid4()), instance_names=[w["instance"]])
    return psycopg.connect(host=inst.read_write_dns, port=5432, dbname=dbname, user=user, password=cred.token,
                           sslmode="require", connect_timeout=30)


print(json.dumps({"instance": inst.name, "state": str(inst.state), "capacity": inst.capacity,
                  "pg_version": inst.pg_version, "host": inst.read_write_dns, "user": user}, indent=1))

# COMMAND ----------

if w["stage"] == "setup":
    with connect("databricks_postgres") as conn:
        conn.autocommit = True
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (w["database"],)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{w["database"]}"')
        print("database", w["database"], "existed" if exists else "created")
    dbutils.notebook.exit("setup done")

# COMMAND ----------

# MAGIC %md ## Synced tables: counts and samples

# COMMAND ----------

S = w["rca_schema"]  # synced tables land in a Postgres schema named after the UC schema
results = {"run_at": pd.Timestamp.now(tz="UTC").isoformat(), "instance": inst.name, "database": w["database"]}
with connect(w["database"]) as conn:
    for t in ("lb_element_status", "lb_open_incidents"):
        n = conn.execute(f'SELECT count(*) FROM "{S}"."{t}"').fetchone()[0]
        results[f"{t}_rows"] = n
        cur = conn.execute(f'SELECT * FROM "{S}"."{t}" ORDER BY 1 LIMIT 5')
        cols = [d.name for d in cur.description]
        results[f"{t}_sample"] = [dict(zip(cols, map(str, r), strict=True)) for r in cur.fetchall()]
    ids = [r[0] for r in conn.execute(f'SELECT element_id FROM "{S}"."lb_element_status"').fetchall()]
    regions = [r[0] for r in conn.execute(f'SELECT DISTINCT region_code FROM "{S}"."lb_element_status"').fetchall()]
    print(json.dumps({k: v for k, v in results.items() if not k.endswith("_sample")}, indent=1))

    # COMMAND ----------

    # Point-lookup latency, measured end to end from this job (warm connection, as an app pool would be).
    rng = random.Random(7)
    queries = {
        "element_status by element_id (PK)": (f'SELECT * FROM "{S}"."lb_element_status" WHERE element_id = %s',
                                              lambda: (rng.choice(ids),)),
        "open_incidents by region_code": (f'SELECT * FROM "{S}"."lb_open_incidents" WHERE region_code = %s '
                                          "ORDER BY suspect_1_score DESC", lambda: (rng.choice(regions),)),
        "open_incident suspects joined to element_status": (
            f'SELECT i.incident_id, e.element_id, e.state FROM "{S}"."lb_open_incidents" i '
            f'JOIN "{S}"."lb_element_status" e ON e.element_id = i.suspect_1_id WHERE i.region_code = %s',
            lambda: (rng.choice(regions),)),
    }
    rows = []
    for name, (sql, args) in queries.items():
        for _ in range(10):  # warm-up
            conn.execute(sql, args()).fetchall()
        lat = []
        for _ in range(int(w["n_lookups"])):
            t0 = time.perf_counter()
            conn.execute(sql, args()).fetchall()
            lat.append((time.perf_counter() - t0) * 1000)
        q = statistics.quantiles(lat, n=100)
        rows.append({"query": name, "n": len(lat), "p50_ms": round(statistics.median(lat), 2),
                     "p95_ms": round(q[94], 2), "p99_ms": round(q[98], 2), "max_ms": round(max(lat), 2)})
    plan = conn.execute(f'EXPLAIN SELECT * FROM "{S}"."lb_element_status" WHERE element_id = %s',
                        (ids[0],)).fetchall()
    results["pk_lookup_plan"] = [r[0] for r in plan]

lat_df = pd.DataFrame(rows).assign(run_at=results["run_at"], instance=inst.name, database=w["database"],
                                   capacity=inst.capacity,
                                   element_status_rows=results["lb_element_status_rows"],
                                   open_incidents_rows=results["lb_open_incidents_rows"],
                                   details=json.dumps(results, default=str))
spark.createDataFrame(lat_df).write.mode("append").option("mergeSchema", "true") \
    .saveAsTable(f"`{w['catalog']}`.`{S}`.lakebase_latency_check")
print(lat_df[["query", "n", "p50_ms", "p95_ms", "p99_ms", "max_ms"]].to_string(index=False))
