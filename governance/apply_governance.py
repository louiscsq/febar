# Databricks notebook source
# MAGIC %md
# MAGIC # Unity Catalog governance for the Banksia Mobile NOC tables
# MAGIC
# MAGIC Applies, idempotently, everything in `governance/sql/`:
# MAGIC
# MAGIC | stage | what | when |
# MAGIC |---|---|---|
# MAGIC | `functions` | `01_functions.sql`: IMSI / MSISDN column-mask functions and the regional row-filter function | before the pipeline runs (its tables declare `MASK` / `ROW FILTER` on them) |
# MAGIC | `policies` | NOC groups and persona service principals, `02_grants.sql` least-privilege grants, `03_comments_tags.sql` | after the pipeline has created its tables |
# MAGIC | `all` | both | |
# MAGIC
# MAGIC **Groups.** `noc_national`, `noc_region_<code>` (one per region) and `pii_privileged` are created as
# MAGIC workspace-local groups: this FEVM workspace does not allow creating account groups. The policy functions
# MAGIC test membership with both `is_account_group_member()` and `is_member()`, so they work with either.
# MAGIC Unity Catalog only accepts account-level principals as grantees, so each grant is attempted on the group
# MAGIC first and, if UC rejects it, applied to the group's member service principals ("personas"), which are
# MAGIC account-level identities. See docs/pipeline.md, "Governance".

# COMMAND ----------

import os
import re

from databricks.sdk import WorkspaceClient
from databricks.sdk.service import iam

for k, v in {"catalog": "", "raw_schema": "netmon_raw", "bronze_schema": "netmon_bronze",
             "silver_schema": "netmon_silver", "gold_schema": "netmon_gold", "eval_schema": "netmon_eval",
             "gov_schema": "netmon_gov", "volume": "landing", "stage": "all",
             "owner_in_national": "true"}.items():
    dbutils.widgets.text(k, v)
p = {k: dbutils.widgets.get(k) for k in ["catalog", "raw_schema", "bronze_schema", "silver_schema", "gold_schema",
                                         "eval_schema", "gov_schema", "volume", "stage", "owner_in_national"]}
assert p["catalog"], "catalog is required"
stage = p["stage"]


def q(*parts: str) -> str:
    return ".".join(f"`{x}`" for x in parts)


SUBS = {
    "catalog": q(p["catalog"]),
    "gov": q(p["catalog"], p["gov_schema"]),
    "gov_schema": q(p["catalog"], p["gov_schema"]),
    "raw_schema": q(p["catalog"], p["raw_schema"]),
    "bronze_schema": q(p["catalog"], p["bronze_schema"]),
    "silver_schema": q(p["catalog"], p["silver_schema"]),
    "gold_schema": q(p["catalog"], p["gold_schema"]),
    "eval_schema": q(p["catalog"], p["eval_schema"]),
    "landing_volume": q(p["catalog"], p["raw_schema"], p["volume"]),
}
SQL_DIR = os.path.join(os.getcwd(), "sql")

REGIONS = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT", "NQL", "PIL"]
GROUPS = ["noc_national", "pii_privileged", *[f"noc_region_{r.lower()}" for r in REGIONS]]
# Persona service principals (account-level identities) and the workspace groups they belong to.
PERSONAS = {
    "netmon-noc-national": ["noc_national"],
    "netmon-noc-nsw-analyst": ["noc_region_nsw"],
    "netmon-noc-wa-analyst": ["noc_region_wa"],
    "netmon-pii-officer": ["noc_national", "pii_privileged"],
}


def statements(name: str, extra: dict | None = None) -> list[str]:
    with open(os.path.join(SQL_DIR, name)) as f:
        text = f.read()
    for k, v in {**SUBS, **(extra or {})}.items():
        text = text.replace("${" + k + "}", v)
    text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("--"))
    return [s.strip() for s in re.split(r";\s*(?:\n|$)", text) if s.strip()]


def run(name: str, extra: dict | None = None, tolerate: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    """Run every statement of a SQL file; return (statement, error) for tolerated failures."""
    failed = []
    for s in statements(name, extra):
        try:
            spark.sql(s)
            print("OK  ", s.splitlines()[0][:150])
        except Exception as e:  # noqa: BLE001
            msg = str(e).splitlines()[0][:300]
            if any(t in msg for t in tolerate):
                print("SKIP", s.splitlines()[0][:150], "->", msg)
                failed.append((s, msg))
            else:
                raise
    return failed

# COMMAND ----------

# MAGIC %md ## Stage `functions`: mask and row-filter functions

# COMMAND ----------

if stage in ("functions", "all"):
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {SUBS['gov']}")
    run("01_functions.sql")
    display(spark.sql(f"SHOW USER FUNCTIONS IN {SUBS['gov']}"))

# COMMAND ----------

# MAGIC %md ## Stage `policies`: groups, personas, grants, comments and tags

# COMMAND ----------

w = WorkspaceClient()
PATCH = [iam.PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP]


def ensure_group(name: str) -> iam.Group:
    found = list(w.groups.list(filter=f'displayName eq "{name}"'))
    return found[0] if found else w.groups.create(display_name=name)


def ensure_sp(name: str) -> iam.ServicePrincipal:
    found = list(w.service_principals.list(filter=f'displayName eq "{name}"'))
    return found[0] if found else w.service_principals.create(display_name=name, active=True)


def add_member(group: iam.Group, member_id: str) -> None:
    current = {m.value for m in (w.groups.get(group.id).members or [])}
    if member_id not in current:
        w.groups.patch(group.id, schemas=PATCH, operations=[
            iam.Patch(op=iam.PatchOp.ADD, value={"members": [{"value": member_id}]})])


if stage in ("policies", "all"):
    groups = {g: ensure_group(g) for g in GROUPS}
    personas = {}
    for sp_name, member_of in PERSONAS.items():
        sp = ensure_sp(sp_name)
        personas[sp_name] = sp
        for g in member_of:
            add_member(groups[g], sp.id)
    if p["owner_in_national"] == "true":
        # The engineer who owns the pipeline reads all regions (row filter) but not raw PII.
        add_member(groups["noc_national"], w.current_user.me().id)

    grantees = {}  # group -> principals actually granted
    for g in GROUPS:
        members = [sp for sp_name, sp in personas.items() if g in PERSONAS[sp_name]]
        try:
            spark.sql(f"GRANT USE CATALOG ON CATALOG {SUBS['catalog']} TO `{g}`")
            grantees[g] = [g]
        except Exception as e:  # noqa: BLE001
            if "PRINCIPAL_DOES_NOT_EXIST" not in str(e):
                raise
            grantees[g] = [sp.application_id for sp in members]
    for g, principals in grantees.items():
        for principal in principals:
            print(f"-- grants for {g} -> {principal}")
            run("02_grants.sql", {"principal": principal})

    skipped = run("03_comments_tags.sql", tolerate=("TABLE_OR_VIEW_NOT_FOUND", "SCHEMA_NOT_FOUND",
                                                    "INVALID_PARAMETER_VALUE", "PERMISSION_DENIED"))
    print(f"{len(skipped)} tag/comment statements skipped")
    print({g: v for g, v in grantees.items() if v})

# COMMAND ----------

# MAGIC %md ## Verify: masks, filters, grants and tags in place

# COMMAND ----------

if stage in ("policies", "all"):
    cat = p["catalog"]
    display(spark.sql(f"""
        SELECT table_schema, table_name, column_name, mask_name FROM `{cat}`.information_schema.column_masks
        WHERE table_schema IN ('{p["silver_schema"]}', '{p["gold_schema"]}')"""))
    display(spark.sql(f"""
        SELECT table_schema, table_name, filter_name, target_columns FROM `{cat}`.information_schema.row_filters
        WHERE table_schema IN ('{p["silver_schema"]}', '{p["gold_schema"]}')"""))
    display(spark.sql(f"SHOW GRANTS ON SCHEMA {SUBS['gold_schema']}"))
    display(spark.sql(f"""
        SELECT schema_name, table_name, column_name, tag_name, tag_value FROM `{cat}`.information_schema.column_tags
        WHERE schema_name IN ('{p["bronze_schema"]}', '{p["silver_schema"]}') ORDER BY ALL"""))
