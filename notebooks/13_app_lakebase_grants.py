# Databricks notebook source
# MAGIC %md
# MAGIC # Lakebase grants for the NOC topology app's service principal (step 5)
# MAGIC
# MAGIC The app's `database` resource creates the app service principal's Postgres role (CONNECT + CREATE on
# MAGIC `netmon_serving`); the app creates and owns its own `netmon_app.sms_draft_reviews` table. This job grants
# MAGIC that role read access to the synced tables it serves (`netmon_rca.lb_open_incidents`, `lb_element_status`,
# MAGIC `netmon_genai.lb_incident_ai_latest`) and nothing else: no write on any synced table. Idempotent.
# MAGIC Connects with psycopg and a one-hour OAuth database credential of the job's own identity: no secrets.

# COMMAND ----------

import uuid

import psycopg
from psycopg import sql
from databricks.sdk import WorkspaceClient

for k, v in {"app_name": "banksia-noc-topology", "instance": "banksia-netmon-lakebase",
             "database": "netmon_serving"}.items():
    dbutils.widgets.text(k, v)
p = {k: dbutils.widgets.get(k) for k in ["app_name", "instance", "database"]}

w = WorkspaceClient()
app = w.apps.get(p["app_name"])
sp_role = app.service_principal_client_id
assert sp_role, f"app {p['app_name']} has no service principal yet"
inst = w.database.get_database_instance(p["instance"])
cred = w.database.generate_database_credential(request_id=str(uuid.uuid4()), instance_names=[p["instance"]])
me = w.current_user.me().user_name
print("app", app.name, "service principal role", sp_role, "granting as", me)

READ = {"netmon_rca": ["lb_open_incidents", "lb_element_status"], "netmon_genai": ["lb_incident_ai_latest"]}

# COMMAND ----------

with psycopg.connect(host=inst.read_write_dns, port=5432, dbname=p["database"], user=me, password=cred.token,
                     sslmode="require", autocommit=True) as c:
    roles = {r[0] for r in c.execute("SELECT rolname FROM pg_roles").fetchall()}
    assert sp_role in roles, f"Postgres role {sp_role} missing: deploy the app (database resource) first"
    for schema, tables in READ.items():
        c.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
            sql.Identifier(schema), sql.Identifier(sp_role)))
        for t in tables:
            c.execute(sql.SQL("GRANT SELECT ON {}.{} TO {}").format(
                sql.Identifier(schema), sql.Identifier(t), sql.Identifier(sp_role)))
            print("GRANT SELECT", f"{schema}.{t}", "->", sp_role)
    rows = c.execute("""
        SELECT table_schema, table_name, privilege_type FROM information_schema.role_table_grants
        WHERE grantee = %s ORDER BY 1, 2, 3""", (sp_role,)).fetchall()
    for r in rows:
        print(r)
    bad = [r for r in rows if r[0] in READ and r[2] != "SELECT"]
    assert not bad, f"unexpected write privileges on synced tables: {bad}"
