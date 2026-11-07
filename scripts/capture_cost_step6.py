"""C2: platform running cost of this workspace from `system.billing` (usage x list prices) into evidence/step6/cost.md.

    python scripts/capture_cost_step6.py --profile febar --warehouse <id>

Every figure is a query result. The steady-state estimate multiplies MEASURED rates (DBU per hour of each always-on or
on-demand component, from the same billing rows) by the stated assumptions below; nothing else is assumed.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture_evidence import Runner, md_table  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "evidence" / "step6" / "cost.md"
WORKSPACE_URL = "https://fevm-telco-netmon-febar.cloud.databricks.com"
LIVE_UPDATE = "c6b8b8f3-d608-4c8e-ad14-e41778fbbdad"  # the continuous update of the published live run (step 2)
EVENT_LOG = "telco_netmon_febar_catalog.netmon_eval.netmon_pipeline_event_log"

# Assumptions of the steady-state day (stated in the output).
SQL_ACTIVE_HOURS = 8  # NOC use of the serverless warehouse (app KPIs, Genie, dashboards); auto-stop otherwise
TRIGGERED_UPDATES_PER_DAY = 96  # pipeline triggered every 15 min, as the alternative to continuous mode

PRICED = """
  FROM system.billing.usage u
  LEFT JOIN system.billing.list_prices p ON p.sku_name = u.sku_name AND p.cloud = u.cloud AND p.usage_unit = u.usage_unit
   AND u.usage_start_time >= p.price_start_time AND (p.price_end_time IS NULL OR u.usage_start_time < p.price_end_time)
  WHERE u.workspace_id = '{ws}'"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="febar")
    ap.add_argument("--warehouse", default="d7fa853ab15b20a3")
    a = ap.parse_args()
    r = Runner(a.profile, a.warehouse)
    parts = [f"# Platform running cost (C2)\n\nGenerated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by "
             "`scripts/capture_cost_step6.py` from `system.billing.usage` joined to `system.billing.list_prices` (list "
             "price in force at each usage record, `pricing.default`, USD). DBUs and USD at **list price**; no discounts.\n"]

    def q(title: str, sql: str, note: str = "") -> list[list]:
        cols, rows = r.sql(sql)
        parts.append(f"## {title}\n\n" + (note.strip() + "\n\n" if note else "") + "```sql\n" + sql.strip() + "\n```\n\n"
                     + md_table(cols, rows) + "\n")
        return rows

    ws_rows = q("Workspace", f"""
SELECT workspace_id, workspace_name, workspace_url, create_time
FROM system.access.workspaces_latest WHERE workspace_url = '{WORKSPACE_URL}'""")
    ws = ws_rows[0][0]
    priced = PRICED.format(ws=ws)
    span = q("Billing coverage", f"""
SELECT min(usage_start_time) AS first_usage, max(usage_end_time) AS last_usage, count(DISTINCT usage_date) AS days_with_usage,
       count(*) AS n_records
FROM system.billing.usage WHERE workspace_id = '{ws}'""",
             "Billing rows arrive with a lag; the step-6 experiment queries of this session (2026-11-07 UTC) are not in it yet.")
    total = q("Total since the workspace was created", f"""
SELECT round(sum(CASE WHEN u.usage_unit = 'DBU' THEN u.usage_quantity END), 1) AS dbu,
       round(sum(u.usage_quantity * p.pricing.default), 2) AS usd_list,
       round(sum(CASE WHEN p.sku_name IS NULL THEN u.usage_quantity END), 1) AS unpriced_quantity
{priced}""")
    q("By product and SKU", f"""
SELECT u.billing_origin_product AS product, u.sku_name, u.usage_unit, round(sum(u.usage_quantity), 2) AS quantity,
       round(sum(u.usage_quantity * p.pricing.default), 2) AS usd_list, min(u.usage_date) AS first_day, max(u.usage_date) AS last_day
{priced}
GROUP BY ALL ORDER BY usd_list DESC NULLS LAST""",
      "`GENIE_FREE_USAGE` has no list price (free Genie usage tier), so it adds DBUs but no USD.")
    q("By resource (pipelines, model serving incl. the RCA endpoint, Lakebase, app, SQL warehouse, jobs, foundation models)",
      f"""
SELECT u.billing_origin_product AS product,
       coalesce(u.usage_metadata.endpoint_name, u.usage_metadata.job_name, u.usage_metadata.app_name,
                u.usage_metadata.dlt_pipeline_id, u.usage_metadata.warehouse_id, u.usage_metadata.database_instance_id,
                '(workspace)') AS resource,
       u.product_features.serving_type AS serving_type, round(sum(u.usage_quantity), 2) AS quantity, u.usage_unit,
       round(sum(u.usage_quantity * p.pricing.default), 2) AS usd_list
{priced}
GROUP BY ALL HAVING sum(u.usage_quantity) > 0.01 ORDER BY usd_list DESC NULLS LAST""",
      "Pipeline `80449004-...` is `banksia-netmon-pipeline`; warehouse `d7fa853ab15b20a3` is the project's serverless SQL "
      "warehouse; `banksia-rca-ranker` is the RCA serving endpoint; `databricks-*` endpoints are foundation-model "
      "pay-per-token (step 4 assistant and its evaluation).")
    q("By day", f"""
SELECT u.usage_date, round(sum(CASE WHEN u.usage_unit = 'DBU' THEN u.usage_quantity END), 1) AS dbu,
       round(sum(u.usage_quantity * p.pricing.default), 2) AS usd_list
{priced}
GROUP BY 1 ORDER BY 1""", "Usage is concentrated on the build / run days; the days between carry storage only.")

    rates = q("Measured rates used for the steady-state estimate", f"""
WITH u AS (SELECT * FROM system.billing.usage WHERE workspace_id = '{ws}'),
lb AS (SELECT (unix_timestamp(max(usage_end_time)) - unix_timestamp(min(usage_start_time))) / 3600 AS h FROM u
       WHERE billing_origin_product = 'LAKEBASE'),
live AS (SELECT (unix_millis(max(timestamp)) - unix_millis(min(timestamp))) / 3600000 AS h FROM {EVENT_LOG}
         WHERE origin.update_id = '{LIVE_UPDATE}')
SELECT 'lakebase_database_dbu_per_h' AS rate,
       sum(CASE WHEN billing_origin_product = 'LAKEBASE' AND sku_name LIKE '%DATABASE%' THEN usage_quantity END) / (SELECT h FROM lb)
         AS value, 'Lakebase instance compute over its whole billed span (always on)' AS basis FROM u
UNION ALL SELECT 'lakebase_synced_tables_dbu_per_h',
       sum(CASE WHEN billing_origin_product = 'LAKEBASE' AND sku_name LIKE '%JOBS%' THEN usage_quantity END) / (SELECT h FROM lb),
       'synced-table pipelines (Lakebase sync), same span' FROM u
UNION ALL SELECT 'app_dbu_per_h', sum(usage_quantity) / count(DISTINCT date_trunc('hour', usage_start_time)),
       'app compute per billed hour' FROM u WHERE billing_origin_product = 'APPS'
UNION ALL SELECT 'rca_endpoint_dbu_per_active_h', sum(usage_quantity) / count(DISTINCT date_trunc('hour', usage_start_time)),
       'banksia-rca-ranker per billed hour (scale-to-zero when idle)' FROM u WHERE usage_metadata.endpoint_name = 'banksia-rca-ranker'
UNION ALL SELECT 'sql_warehouse_dbu_per_active_h', sum(usage_quantity) / count(DISTINCT date_trunc('hour', usage_start_time)),
       'serverless SQL warehouse per billed hour' FROM u WHERE billing_origin_product = 'SQL'
UNION ALL SELECT 'pipeline_continuous_dbu_per_h', sum(usage_quantity) / (SELECT h FROM live),
       'the continuous live update of the step-2 stream (12x accelerated feed, 34 min)' FROM u
       WHERE usage_metadata.dlt_update_id = '{LIVE_UPDATE}'
UNION ALL SELECT 'pipeline_triggered_update_dbu', percentile(dbu, 0.5),
       'median incremental triggered update (not full refresh, not continuous), 2026-11-05 .. 06' FROM (
         SELECT usage_metadata.dlt_update_id, sum(usage_quantity) AS dbu FROM u
         WHERE billing_origin_product = 'DLT' AND usage_date >= '2026-11-05' AND usage_metadata.dlt_update_id IS NOT NULL
         GROUP BY 1)
UNION ALL SELECT 'predictive_optimization_dbu_per_day', sum(usage_quantity) / 30, 'whole period / 30 days' FROM u
       WHERE billing_origin_product = 'PREDICTIVE_OPTIMIZATION'
UNION ALL SELECT 'storage_dsu_per_day', sum(usage_quantity), 'latest full day (2026-11-06)' FROM u
       WHERE billing_origin_product = 'DEFAULT_STORAGE' AND usage_date = '2026-11-06'""")
    prices = dict((row[0], float(row[1])) for row in r.sql("""
SELECT sku_name, pricing.default FROM system.billing.list_prices WHERE price_end_time IS NULL AND cloud = 'AWS'
 AND sku_name IN ('ENTERPRISE_DATABASE_SERVERLESS_COMPUTE_US_EAST_N_VIRGINIA', 'ENTERPRISE_JOBS_SERVERLESS_COMPUTE_US_EAST_N_VIRGINIA',
                  'ENTERPRISE_ALL_PURPOSE_SERVERLESS_COMPUTE_US_EAST_N_VIRGINIA', 'ENTERPRISE_SERVERLESS_REAL_TIME_INFERENCE_US_EAST_N_VIRGINIA',
                  'ENTERPRISE_SERVERLESS_SQL_COMPUTE_US_EAST_N_VIRGINIA', 'PREMIUM_DATABRICKS_STORAGE_US_EAST_N_VIRGINIA')""")[1])
    v = {row[0]: float(row[1]) for row in rates}
    fm = r.sql(f"""SELECT round(sum(usage_quantity), 1), min(usage_start_time), max(usage_end_time) FROM system.billing.usage
                   WHERE workspace_id = '{ws}' AND product_features.serving_type = 'FOUNDATION_MODEL'""")[1][0]
    p_db, p_jobs = prices["ENTERPRISE_DATABASE_SERVERLESS_COMPUTE_US_EAST_N_VIRGINIA"], prices["ENTERPRISE_JOBS_SERVERLESS_COMPUTE_US_EAST_N_VIRGINIA"]
    p_app, p_rt = prices["ENTERPRISE_ALL_PURPOSE_SERVERLESS_COMPUTE_US_EAST_N_VIRGINIA"], prices["ENTERPRISE_SERVERLESS_REAL_TIME_INFERENCE_US_EAST_N_VIRGINIA"]
    p_sql, p_st = prices["ENTERPRISE_SERVERLESS_SQL_COMPUTE_US_EAST_N_VIRGINIA"], prices["PREMIUM_DATABRICKS_STORAGE_US_EAST_N_VIRGINIA"]
    items = [
        ("Lakebase instance (CU_1, always on)", "24 h", 24 * v["lakebase_database_dbu_per_h"], p_db),
        ("Lakebase synced tables", "24 h at the measured rate", 24 * v["lakebase_synced_tables_dbu_per_h"], p_jobs),
        ("Databricks App (banksia-noc-topology)", "running 24 h", 24 * v["app_dbu_per_h"], p_app),
        ("SQL warehouse (serverless)", f"{SQL_ACTIVE_HOURS} active h/day", SQL_ACTIVE_HOURS * v["sql_warehouse_dbu_per_active_h"], p_sql),
        ("RCA serving endpoint (Small, scale-to-zero)", "idle: scales to zero", 0.0, p_rt),
        ("Predictive optimization", "measured daily average", v["predictive_optimization_dbu_per_day"], p_jobs),
        ("Storage (DSU)", "latest full day", v["storage_dsu_per_day"], p_st),
    ]
    base_dbu = sum(x[2] for x in items if "DSU" not in x[0])
    base_usd = sum(x[2] * x[3] for x in items)
    opt = [
        ("+ RCA endpoint warm 24 h", 24 * v["rca_endpoint_dbu_per_active_h"], p_rt),
        (f"+ pipeline triggered every 15 min ({TRIGGERED_UPDATES_PER_DAY} incremental updates)",
         TRIGGERED_UPDATES_PER_DAY * v["pipeline_triggered_update_dbu"], p_jobs),
        ("+ pipeline continuous 24 h at the measured live rate (12x accelerated feed: an upper bound)",
         24 * v["pipeline_continuous_dbu_per_h"], p_jobs),
    ]
    rows = [[n, a_, round(d, 2), p, round(d * p, 2)] for n, a_, d, p in items]
    rows.append(["**serving platform, steady state (sum)**", "", round(base_dbu, 1), "", round(base_usd, 2)])
    rows += [[n, "", round(d, 1), p, round(d * p, 2)] for n, d, p in opt]
    parts.append(f"""## Steady-state estimate per day

What it costs to keep the deployed platform running for one day with no build, backfill, retraining or evaluation:
measured rate (table above) x the stated assumption, priced at today's list price per SKU.

Assumptions: the Lakebase instance and the app run 24 h (both billed continuously while up); the serverless SQL
warehouse is active {SQL_ACTIVE_HOURS} h/day for NOC use and auto-stops otherwise; the RCA endpoint scales to zero when not
called (warm 24 h shown as an add-on); the pipeline is either triggered every 15 min or continuous (add-ons, measured on
this workspace: the continuous figure comes from the 12x-accelerated live demo, so it over-states a 1x live feed).
Not estimated: foundation-model pay-per-token for the live assistant (all {fm[0]} DBU of it on record falls between
{fm[1]} and {fm[2]}, the step-4 evaluation runs, and pay-per-token rows carry no job id, so the live assistant's own
share is not separable) and Genie (free usage tier, no list price).

""" + md_table(["component", "assumption", "DBU (DSU for storage) / day", "USD / unit (list)", "USD / day (list)"], rows)
                 + "\n")
    trig_usd = opt[1][1] * opt[1][2]
    cont_usd = opt[2][1] * opt[2][2]
    summary = f"""## Summary

- Since the workspace was created ({ws_rows[0][3]}) to the last billed record ({span[0][1]}): **{total[0][0]} DBU,
  USD {total[0][1]} at list price**. **{total[0][2]} units have no list price** (`GENIE_FREE_USAGE`, the free Genie
  tier), so they are counted in the DBUs but not in the USD.
- Steady state per day, at list price, under the assumptions stated in "Steady-state estimate per day":
  - **serving components, excluding ingestion: about USD {base_usd:.0f} / day** ({base_dbu:.0f} DBU: Lakebase, app, SQL
    warehouse {SQL_ACTIVE_HOURS} h, RCA endpoint at zero when idle, predictive optimization, storage);
  - **with the pipeline triggered every 15 min: about USD {base_usd + trig_usd:.0f} / day** (+USD {trig_usd:.0f});
  - upper bound with a continuous pipeline at the measured, 12x-accelerated live rate: about USD
    {base_usd + cont_usd:.0f} / day (+USD {cont_usd:.0f}); a 1x live feed would cost less, but that was not measured;
  - a warm RCA endpoint adds about USD {opt[0][1] * opt[0][2]:.0f} / day.
"""
    parts.insert(1, summary)  # headline first
    parts.append(summary.replace("## Summary", "## Summary (repeated)"))
    OUT.write_text("\n".join(parts))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
