"""Capture text evidence of the step-2 run into evidence/step2/ (markdown tables of SQL results).

Runs every query on a SQL warehouse through the Databricks CLI (`databricks api`), so it only needs a
configured CLI profile. Results are small samples and aggregates; IMSI / MSISDN only ever appear masked.

    python scripts/capture_evidence.py --profile febar --warehouse <id> [--only governance] [--governance-demo]

`--governance-demo` temporarily changes the current user's membership of the NOC groups to show the row
filter and the column masks taking effect, then restores it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "evidence" / "step2"
CAT = "telco_netmon_febar_catalog"
B, S, G, E, GOV = (f"{CAT}.netmon_bronze", f"{CAT}.netmon_silver", f"{CAT}.netmon_gold", f"{CAT}.netmon_eval",
                   f"{CAT}.netmon_gov")
EVENT_LOG = f"{E}.netmon_pipeline_event_log"
# Updates from the latest full refresh onwards (earlier full refreshes re-processed the same files).
SINCE_REFRESH = f"""timestamp >= (SELECT max(timestamp) FROM {EVENT_LOG} WHERE event_type = 'create_update'
                                   AND details:create_update:full_refresh::boolean)"""


class Runner:
    def __init__(self, profile: str, warehouse: str):
        self.profile, self.warehouse = profile, warehouse

    def cli(self, *args: str, body: dict | None = None) -> dict:
        cmd = ["databricks", *args, "-p", self.profile, "-o", "json"]
        if body is not None:
            cmd += ["--json", json.dumps(body)]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        return json.loads(out) if out.strip() else {}

    def sql(self, statement: str) -> tuple[list[str], list[list]]:
        d = self.cli("api", "post", "/api/2.0/sql/statements", body={
            "warehouse_id": self.warehouse, "statement": statement, "wait_timeout": "50s",
            "on_wait_timeout": "CONTINUE", "disposition": "INLINE", "format": "JSON_ARRAY"})
        while d.get("status", {}).get("state") in ("PENDING", "RUNNING"):
            time.sleep(3)
            d = self.cli("api", "get", f"/api/2.0/sql/statements/{d['statement_id']}")
        st = d.get("status", {})
        if st.get("state") != "SUCCEEDED":
            raise RuntimeError(f"{st.get('state')}: {st.get('error', {}).get('message', '')[:800]}\n{statement}")
        cols = [c["name"] for c in d.get("manifest", {}).get("schema", {}).get("columns", [])]
        return cols, d.get("result", {}).get("data_array") or []


def md_table(cols: list[str], rows: list[list], max_cell: int = 120) -> str:
    def cell(v):
        s = "NULL" if v is None else str(v)
        s = s.replace("|", "\\|").replace("\n", " ")
        return s if len(s) <= max_cell else s[: max_cell - 1] + "…"

    if not cols:
        return "_(no result set)_\n"
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]
    return "\n".join(lines) + f"\n\n_{len(rows)} row(s)_\n"


class Doc:
    def __init__(self, runner: Runner, name: str, title: str, intro: str = ""):
        self.r, self.path = runner, OUT / name
        self.parts = [f"# {title}\n", f"Captured {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC from workspace "
                      f"profile `{runner.profile}` (warehouse `{runner.warehouse}`) by "
                      f"`scripts/capture_evidence.py`.\n"]
        if intro:
            self.parts.append(intro.strip() + "\n")

    def query(self, heading: str, sql: str, note: str = "") -> list[list]:
        cols, rows = self.r.sql(sql)
        self.parts += [f"## {heading}\n", note.strip() + "\n" if note else "",
                       "```sql\n" + sql.strip() + "\n```\n", md_table(cols, rows)]
        return rows

    def query_or_error(self, heading: str, sql: str, note: str = "") -> None:
        """Run a statement whose failure is itself the evidence (e.g. UC rejecting a principal)."""
        try:
            cols, rows = self.r.sql(sql)
            result = md_table(cols, rows)
        except RuntimeError as e:
            result = "Error returned by Unity Catalog:\n\n```\n" + str(e).split("\n")[0][:400] + "\n```\n"
        self.parts += [f"## {heading}\n", note.strip() + "\n" if note else "", "```sql\n" + sql.strip() + "\n```\n",
                       result]

    def text(self, heading: str, body: str) -> None:
        self.parts += [f"## {heading}\n", body.strip() + "\n"]

    def write(self) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(p for p in self.parts if p))
        print("wrote", self.path)


# ---------------------------------------------------------------------------------------------------

def pipeline_status(r: Runner, pipeline_id: str) -> None:
    d = Doc(r, "01_pipeline_status.md", "Pipeline runs and update status")
    p = r.cli("pipelines", "get", pipeline_id)
    spec = p.get("spec", {})
    d.text("Pipeline", "\n".join([
        f"- name: `{p.get('name')}`", f"- pipeline_id: `{pipeline_id}`", f"- state: `{p.get('state')}`",
        f"- serverless: `{spec.get('serverless')}`, continuous: `{spec.get('continuous')}`, "
        f"channel: `{spec.get('channel')}`",
        f"- catalog / default schema: `{spec.get('catalog')}` / `{spec.get('schema')}`",
        f"- event log: `{EVENT_LOG}`"]))
    d.query("Updates (from the event log)", f"""
        SELECT origin.update_id, min(timestamp) AS started, max(timestamp) AS last_event,
               max_by(details:update_progress:state::string, timestamp)
                 FILTER (WHERE event_type = 'update_progress') AS final_state,
               max(CASE WHEN event_type = 'create_update' THEN details:create_update:cause::string END) AS cause,
               max(CASE WHEN event_type = 'create_update' THEN details:create_update:full_refresh::string END)
                 AS full_refresh
        FROM {EVENT_LOG} GROUP BY origin.update_id ORDER BY started""")
    d.query("Flows of the latest completed update", f"""
        WITH u AS (SELECT origin.update_id AS id FROM {EVENT_LOG}
                   WHERE event_type = 'update_progress' AND details:update_progress:state::string = 'COMPLETED'
                   ORDER BY timestamp DESC LIMIT 1)
        SELECT origin.flow_name, max_by(details:flow_progress:status::string, timestamp) AS final_status,
               sum(details:flow_progress:metrics:num_output_rows::bigint) AS output_rows
        FROM {EVENT_LOG} WHERE event_type = 'flow_progress' AND origin.update_id = (SELECT id FROM u)
        GROUP BY origin.flow_name ORDER BY origin.flow_name""")
    d.query("Pipeline errors, if any (last 10)", f"""
        SELECT timestamp, origin.update_id, origin.flow_name, left(message, 200) AS message
        FROM {EVENT_LOG} WHERE level = 'ERROR' ORDER BY timestamp DESC LIMIT 10""",
            note="Errors from the first deploy-and-fix iterations are kept here deliberately.")
    d.write()


def expectations(r: Runner) -> None:
    d = Doc(r, "02_expectations.md", "Expectation pass/fail metrics (pipeline event log)",
            "Summed over the latest full refresh and every update after it (history backfill + live stream), so "
            "each record is counted once. `drop` rules move rows to `silver_quarantine`; `on_time` is warn-only "
            "(late rows are kept, flagged `is_late`); topology rules are `expect_or_fail`.")
    d.query("Per dataset and rule", f"""
        WITH x AS (
          SELECT explode(from_json(details:flow_progress:data_quality:expectations,
                 'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) AS e
          FROM {EVENT_LOG} WHERE event_type = 'flow_progress' AND {SINCE_REFRESH}
            AND details:flow_progress:data_quality:expectations IS NOT NULL)
        SELECT e.dataset, e.name AS rule, sum(e.passed_records) AS passed, sum(e.failed_records) AS failed,
               round(100.0 * sum(e.failed_records) / nullif(sum(e.passed_records) + sum(e.failed_records), 0), 3)
                 AS failed_pct
        FROM x GROUP BY e.dataset, e.name ORDER BY e.dataset, failed DESC""")
    d.query("Dropped rows per silver flow", f"""
        SELECT origin.flow_name, sum(details:flow_progress:data_quality:dropped_records::bigint) AS dropped_records
        FROM {EVENT_LOG} WHERE event_type = 'flow_progress' AND {SINCE_REFRESH}
          AND details:flow_progress:data_quality:dropped_records IS NOT NULL
        GROUP BY origin.flow_name ORDER BY 1""")
    d.query("Quarantine by feed and failed rule", f"""
        SELECT feed, _source_run AS run, rule, count(*) AS n_rows
        FROM {S}.silver_quarantine LATERAL VIEW explode(failed_rules) t AS rule
        GROUP BY ALL ORDER BY feed, run, n_rows DESC""")
    d.query("Quarantine sample (PII redacted)", f"""
        SELECT feed, record_id, failed_rules, event_ts_raw, left(payload, 110) AS payload,
               left(_rescued_data, 60) AS rescued, left(_corrupt_record, 70) AS corrupt
        FROM {S}.silver_quarantine
        QUALIFY row_number() OVER (PARTITION BY feed, failed_rules[0] ORDER BY record_id) = 1
        ORDER BY feed LIMIT 25""")
    d.query("Injected defects (ground truth) vs pipeline handling — eval_dq_capture", f"""
        SELECT * FROM {E}.eval_dq_capture ORDER BY source_run, feed, defect_type, defect_subtype""",
            note="`handled_pct` = quarantined (malformed / null / out_of_range), flagged late (late_arrival) or "
                 "single copy in silver (duplicate). Session dedupe is the same code path and not re-scored.")
    d.write()


def row_counts(r: Runner) -> None:
    d = Doc(r, "03_row_counts.md", "Row counts per table")
    tables = [f"{B}.bronze_{t}" for t in ("kpis", "alarms", "sessions", "topology_nodes", "topology_edges",
                                           "maintenance_windows")]
    tables += [f"{S}.silver_{t}" for t in ("kpis", "alarms", "sessions", "quarantine", "topology_nodes",
                                            "topology_edges", "maintenance_windows")]
    tables += [f"{G}.gold_{t}" for t in ("cell_baseline", "cell_health_1m", "cell_health_5m", "impact_detections",
                                          "element_impact_5m", "cell_sessions_5m")]
    tables += [f"{E}.{t}" for t in ("bronze_gt_incidents", "bronze_gt_dq_injections", "eval_gt_incidents",
                                     "eval_detection_log", "eval_incident_detection", "eval_rca_baseline")]
    union = "\nUNION ALL ".join(f"SELECT '{t.split('.', 1)[1]}' AS table_name, count(*) AS n_rows FROM {t}"
                                for t in tables)
    d.query("All pipeline tables", union,
            note="Counts as seen by the capturing user (member of `noc_national`, so row filters pass every "
                 "region). silver_sessions / gold_impact_detections are row-filtered tables.")
    d.query("Bronze and silver by generator run", f"""
        SELECT 'kpis' AS feed, _source_run AS run, count(*) AS bronze FROM {B}.bronze_kpis GROUP BY 2
        UNION ALL SELECT 'alarms', _source_run, count(*) FROM {B}.bronze_alarms GROUP BY 2
        UNION ALL SELECT 'sessions', _source_run, count(*) FROM {B}.bronze_sessions GROUP BY 2
        ORDER BY 1, 2""")
    d.query("Silver by generator run", f"""
        SELECT 'kpis' AS feed, source_run AS run, count(*) AS silver, count_if(is_late) AS late_kept,
               min(event_ts) AS min_event_ts, max(event_ts) AS max_event_ts FROM {S}.silver_kpis GROUP BY 2
        UNION ALL SELECT 'alarms', source_run, count(*), count_if(is_late), min(event_ts), max(event_ts)
          FROM {S}.silver_alarms GROUP BY 2
        UNION ALL SELECT 'sessions', source_run, count(*), count_if(is_late), min(start_ts), max(start_ts)
          FROM {S}.silver_sessions GROUP BY 2
        ORDER BY 1, 2""")
    d.write()


def gold_samples(r: Runner) -> None:
    d = Doc(r, "04_gold_samples.md", "Sample gold rows")
    d.query("gold_cell_health_5m: degraded windows in the live stream", f"""
        SELECT window_start, cell_id, region_code, n_reports, round(availability_pct, 1) AS avail,
               round(latency_ms, 1) AS latency, round(b_latency_ms_mean, 1) AS base_latency,
               round(latency_ms_z, 1) AS latency_z, round(dl_throughput_mbps_z, 1) AS dl_z, flags
        FROM {G}.gold_cell_health_5m WHERE is_degraded
        ORDER BY window_start DESC, cell_id LIMIT 12""")
    d.query("gold_cell_health_1m: one healthy cell, latest windows", f"""
        WITH c AS (SELECT cell_id FROM {G}.gold_cell_health_1m WHERE granularity_s = 60 AND NOT is_degraded
                   ORDER BY window_start DESC, cell_id LIMIT 1)
        SELECT window_start, window_start_local, cell_id, round(latency_ms, 1) AS latency,
               round(b_latency_ms_mean, 1) AS base_mean, round(b_latency_ms_std, 2) AS base_std,
               round(latency_ms_z, 2) AS z, is_degraded
        FROM {G}.gold_cell_health_1m WHERE cell_id = (SELECT cell_id FROM c) ORDER BY window_start DESC LIMIT 8""")
    d.query("gold_cell_baseline: sample", f"""
        SELECT valid_date, cell_id, local_hour, day_type, n_days, n_samples, round(b_latency_ms_mean, 1) AS lat_mean,
               round(b_latency_ms_std, 2) AS lat_std, round(b_dl_throughput_mbps_mean, 1) AS dl_mean
        FROM {G}.gold_cell_baseline ORDER BY valid_date DESC, cell_id, local_hour LIMIT 6""")
    d.query("gold_impact_detections: latest live detections", f"""
        SELECT detected_ts, signal_source, element_type, element_id, region_code, signal_start_ts, evidence_ts,
               round(pipeline_latency_s, 1) AS pipeline_latency_s, flags, severity_score, in_maintenance
        FROM {G}.gold_impact_detections WHERE landed_ts IS NOT NULL ORDER BY detected_ts DESC LIMIT 12""")
    d.query("gold_impact_detections: pipeline latency (live files)", f"""
        SELECT signal_source, count(*) AS n, round(percentile(pipeline_latency_s, 0.5), 1) AS p50_s,
               round(percentile(pipeline_latency_s, 0.9), 1) AS p90_s, round(max(pipeline_latency_s), 1) AS max_s
        FROM {G}.gold_impact_detections WHERE landed_ts IS NOT NULL GROUP BY signal_source""")
    d.query("gold_element_impact_5m: top root-cause candidates in the live stream", f"""
        SELECT window_start, element_id, element_type, n_desc_cells, n_impacted_cells, n_silent_cells,
               round(impacted_fraction, 2) AS frac, n_impacted_children, n_children,
               round(parent_impacted_fraction, 2) AS parent_frac, n_alarms, n_service_down_alarms, alarm_codes
        FROM {G}.gold_element_impact_5m
        WHERE window_start >= (SELECT max(window_start) - INTERVAL 3 HOURS FROM {G}.gold_element_impact_5m)
          AND element_type <> 'CELL' AND n_impacted_cells >= 2
        ORDER BY n_impacted_cells DESC, level LIMIT 12""")
    d.query("gold_cell_sessions_5m: highest failure windows", f"""
        SELECT window_start, cell_id, region_code, n_sessions, n_setup_failed, n_dropped, n_no_service,
               n_subscribers_approx, round(failure_rate, 2) AS failure_rate
        FROM {G}.gold_cell_sessions_5m WHERE n_sessions >= 3 ORDER BY failure_rate DESC, window_start DESC LIMIT 8""")
    d.write()


def evaluation(r: Runner) -> None:
    d = Doc(r, "05_time_to_detect.md", "Time-to-detect, localisation and precision against ground truth",
            "Scored incidents: customer-impacting and not censored. Two separate metrics (docs/pipeline.md):\n\n"
            "- **(a) customer-impact detection** — first detection on any element of the incident's footprint; "
            "`impact_ttd_s` = (evidence time + measured pipeline latency for live files) − `impact_start_ts`. "
            "This is the 5-minute SLA metric.\n"
            "- **(b) root-element localisation** — a detection or the topology rollup lands on an element of "
            "`root_element_ids` (any one counts for cluster faults).\n\n"
            "`history` = 15-minute-ROP backfill (cannot meet a 5-minute SLA by construction); `stream` = 1-minute "
            "live feed. Fault-only rows (`event_class = fault`) are the headline; planned work is suppressed by "
            "the change calendar and reported separately.")
    cols = ("source_run, event_class, n_incidents, n_impact_detected, impact_detected_pct, impact_median_ttd_s, "
            "impact_p90_ttd_s, impact_within_5min_pct, n_root_localised, root_localised_pct, "
            "localisation_median_ttd_s, localised_within_5min_pct, median_evidence_lag_s, median_pipeline_latency_s")
    d.query("Headline: faults only", f"""
        SELECT {cols} FROM {E}.eval_ttd_summary WHERE event_class = 'fault' AND fault_type = 'ALL'
        ORDER BY source_run DESC""")
    d.query("All event classes", f"""
        SELECT {cols} FROM {E}.eval_ttd_summary WHERE fault_type = 'ALL'
        ORDER BY source_run DESC, CASE event_class WHEN 'fault' THEN 0 WHEN 'ALL' THEN 9 ELSE 1 END, event_class""")
    d.query("Per fault type", f"""
        SELECT source_run, event_class, fault_type, n_incidents, impact_detected_pct, impact_median_ttd_s,
               impact_within_5min_pct, root_localised_pct, localisation_median_ttd_s, localised_within_5min_pct
        FROM {E}.eval_ttd_summary WHERE fault_type <> 'ALL'
        ORDER BY source_run DESC, CASE event_class WHEN 'fault' THEN 0 ELSE 1 END, event_class, fault_type""")
    d.query("Live-stream fault incidents", f"""
        SELECT incident_id, fault_type, root_element_type, impact_start_ts, impact_detected, first_signal_source,
               first_element_type, round(evidence_lag_s, 0) AS evidence_lag_s,
               round(first_pipeline_latency_s, 1) AS pipeline_latency_s, round(impact_ttd_s, 1) AS impact_ttd_s,
               impact_within_sla, root_localised, localisation_source, round(localisation_ttd_s, 1) AS localisation_ttd_s
        FROM {E}.eval_incident_detection WHERE source_run = 'stream' AND event_class = 'fault'
        ORDER BY impact_start_ts""")
    d.query("Ground-truth incidents in the live stream (incl. censored and non-impacting)", f"""
        SELECT event_class, fault_type, is_customer_impacting, is_censored, count(*) AS n
        FROM {E}.eval_gt_incidents WHERE source_run = 'stream' GROUP BY ALL ORDER BY ALL""")
    d.query("Alert-level fault precision (detections grouped per element per episode)", f"""
        SELECT * FROM {E}.eval_alert_precision
        ORDER BY source_run DESC, CASE signal_source WHEN 'ALL' THEN 0 ELSE 1 END, signal_source""",
            note="An alert = the detections on one element of one run until one starts > 10 min after the previous "
                 "signal ended (one page). It takes "
                 "the highest-priority label of its rows; suppressed when its first row is in a change window. "
                 "`alert_fault_precision_pct` = TP alerts / (TP + FP alerts).")
    d.query("Detection-row fault precision and maintenance suppression", f"""
        SELECT * FROM {E}.eval_detection_precision
        ORDER BY source_run DESC, CASE signal_source WHEN 'ALL' THEN 0 ELSE 1 END, signal_source""",
            note="One row per detection (a degraded cell-minute or an alarm), so long incidents with many cells "
                 "weigh heavily. Labels in priority order: uncensored fault = TP; overlapping a censored incident "
                 "= excluded; planned work = suppressed when `in_maintenance` (else a false page); red herring "
                 "(e.g. TRAFFIC_SURGE) = FP; nothing = FP. `row_fault_precision_pct` = TP / (TP + FP).")
    d.query("RCA topology-heuristic baseline (hit@1 / hit@3 vs root_element_ids)", f"""
        SELECT source_run, fault_type, count(*) AS n, round(100.0 * avg(CAST(hit_at_1 AS INT)), 1) AS hit1_pct,
               round(100.0 * avg(CAST(hit_at_3 AS INT)), 1) AS hit3_pct
        FROM {E}.eval_rca_baseline GROUP BY GROUPING SETS ((source_run), (source_run, fault_type))
        ORDER BY source_run DESC, fault_type NULLS FIRST""")
    d.write()


NOC = f"{CAT}.netmon_noc"
NOC_VIEWS = ["silver_kpis", "silver_alarms", "silver_sessions", "silver_topology_nodes", "silver_topology_edges",
             "silver_maintenance_windows", "gold_cell_baseline", "gold_cell_health_1m", "gold_cell_health_5m",
             "gold_impact_detections", "gold_element_impact_5m", "gold_cell_sessions_5m"]


def governance(r: Runner, demo: bool) -> None:
    d = Doc(r, "06_governance.md", "Unity Catalog governance: masks, row filters, roles, grants, tags",
            "Masks and row filters are declared on the pipeline tables (`silver_sessions`, `gold_impact_detections`) "
            "and backed by `governance/sql/01_functions.sql`. Regional NOC roles read only the region-filtered views "
            "in `netmon_noc` (`02_noc_views.sql`); `noc_national` also reads gold and the operational silver tables; "
            "`pii_privileged` is granted nothing (`03_grants_*.sql`). Tags: `04_comments_tags.sql`.\n\n"
            "**Limitation, stated plainly:** every query below runs as one principal, the capturing user. "
            "Querying as a second principal (a persona service principal via OAuth M2M or a token) was not "
            "possible: creating credentials for a service principal was blocked in this environment. So "
            "(1) row-level behaviour is proven by changing the capturing user's group membership and querying "
            "every object a regional role can read, and (2) grant-level least privilege is proven from "
            "`information_schema` for each persona and from Unity Catalog rejecting the workspace-local groups "
            "as principals. The capturing user owns the catalog, so it can always read the base tables itself; "
            "that is why grant denial is shown from the privilege tables, not by a refused query.")
    d.query("Column masks", f"""
        SELECT table_schema, table_name, column_name, mask_name FROM {CAT}.information_schema.column_masks
        ORDER BY ALL""")
    d.query("Row filters", f"""
        SELECT table_schema, table_name, filter_name, target_columns FROM {CAT}.information_schema.row_filters
        ORDER BY ALL""")
    d.query("Region-filtered serving views (netmon_noc)", f"""
        SELECT table_name, left(replace(replace(view_definition, char(10), ' '), char(13), ' '), 170) AS definition
        FROM {CAT}.information_schema.views WHERE table_schema = 'netmon_noc' ORDER BY 1""")
    d.query("Policy function definitions", f"""
        SELECT routine_name, routine_definition FROM {CAT}.information_schema.routines
        WHERE routine_schema = 'netmon_gov' ORDER BY 1""")

    groups = {g["displayName"]: g["id"] for g in r.cli("groups", "list")}
    sps = {s["applicationId"]: s["displayName"] for s in r.cli("service-principals", "list")
           if s.get("displayName", "").startswith("netmon-")}
    lines = ["| group | role | members |", "|---|---|---|"]
    for g in sorted(x for x in groups if x.startswith(("noc_", "pii_"))):
        mem = r.cli("groups", "get", groups[g]).get("members") or []
        role = ("national NOC" if g == "noc_national" else "unmask only (no grants)" if g == "pii_privileged"
                else "regional NOC")
        lines.append(f"| `{g}` | {role} | {', '.join(m.get('display', '?') for m in mem) or '—'} |")
    d.text("Workspace-local groups, roles and members", "\n".join(lines))
    case = " ".join(f"WHEN '{a}' THEN '{n}'" for a, n in sps.items())
    ids = ", ".join(f"'{a}'" for a in sps)
    d.query("Privileges held by each persona (grantees; every netmon securable)", f"""
        WITH p AS (
          SELECT grantee, 'CATALOG' AS kind, catalog_name AS object, privilege_type
          FROM {CAT}.information_schema.catalog_privileges
          UNION ALL SELECT grantee, 'SCHEMA', schema_name, privilege_type FROM {CAT}.information_schema.schema_privileges
          UNION ALL SELECT grantee, 'TABLE', concat(table_schema, '.', table_name), privilege_type
            FROM {CAT}.information_schema.table_privileges
          UNION ALL SELECT grantee, 'FUNCTION', concat(routine_schema, '.', routine_name), privilege_type
            FROM {CAT}.information_schema.routine_privileges)
        SELECT persona, kind, object, array_sort(collect_set(privilege_type)) AS privileges FROM (
          SELECT CASE a.id {case} END AS persona, p.* FROM (SELECT explode(array({ids})) AS id) a
          LEFT JOIN p ON p.grantee = a.id)
        GROUP BY ALL ORDER BY persona, kind, object""",
            note="`netmon-pii-only` (member of `pii_privileged` only) has no privileges at all; the regional "
                 "analysts hold only the `netmon_noc` schema (plus USE CATALOG and the filter function).")
    base = "('netmon_bronze', 'netmon_silver', 'netmon_gold', 'netmon_eval')"
    regional_ids = ", ".join(f"'{a}'" for a, n in sps.items() if n in ("netmon-noc-nsw-analyst",
                                                                     "netmon-noc-wa-analyst", "netmon-pii-only"))
    region_groups = ", ".join(f"'{g}'" for g in groups if g.startswith("noc_region_") or g == "pii_privileged")
    d.query("Base-table privileges held by regional / pii-only principals (expected: no rows)", f"""
        SELECT grantee, 'SCHEMA' AS kind, schema_name AS object, privilege_type
        FROM {CAT}.information_schema.schema_privileges
        WHERE schema_name IN {base} AND grantee IN ({regional_ids}, {region_groups})
        UNION ALL
        SELECT grantee, 'TABLE', concat(table_schema, '.', table_name), privilege_type
        FROM {CAT}.information_schema.table_privileges
        WHERE table_schema IN {base} AND grantee IN ({regional_ids}, {region_groups})""",
            note="Covers the regional analyst personas, the pii-only persona, and every `noc_region_*` group and "
                 "`pii_privileged` by name. Zero rows: nobody but the national role can read a silver / gold "
                 "table directly; regional access is only through `netmon_noc`.")
    d.query("All grantees on the base schemas and their tables (who can read silver / gold directly)", f"""
        SELECT kind, grantee_name, array_sort(collect_set(object)) AS objects, array_sort(collect_set(privilege_type))
               AS privileges FROM (
          SELECT 'SCHEMA' AS kind, coalesce(CASE grantee {case} END, grantee) AS grantee_name, schema_name AS object,
                 privilege_type FROM {CAT}.information_schema.schema_privileges WHERE schema_name IN {base}
          UNION ALL
          SELECT 'TABLE', coalesce(CASE grantee {case} END, grantee), concat(table_schema, '.', table_name),
                 privilege_type FROM {CAT}.information_schema.table_privileges WHERE table_schema IN {base})
        WHERE grantee_name NOT LIKE '%@%' GROUP BY kind, grantee_name ORDER BY kind, grantee_name""",
            note="Besides the catalog owner (excluded: a user) and the FEVM platform service principal, only the "
                 "national personas appear.")
    d.query_or_error("SHOW GRANTS for a regional group (Unity Catalog view of the group)",
                     f"SHOW GRANTS `noc_region_nsw` ON SCHEMA {CAT}.netmon_silver",
                     note="Workspace-local groups are not UC principals, so they cannot hold, or keep, any grant; "
                          "the governance job also issues REVOKE ALL for every group and records this.")
    d.query("Tags: schemas and tables", f"""
        SELECT 'schema' AS level, schema_name AS object, tag_name, tag_value FROM {CAT}.information_schema.schema_tags
        UNION ALL
        SELECT 'table', concat(schema_name, '.', table_name), tag_name, tag_value
        FROM {CAT}.information_schema.table_tags WHERE schema_name LIKE 'netmon%'
        ORDER BY 1, 2, 3""")
    d.query("Tags: PII columns", f"""
        SELECT schema_name, table_name, column_name, tag_name, tag_value FROM {CAT}.information_schema.column_tags
        WHERE schema_name LIKE 'netmon%' ORDER BY ALL""")
    d.query("Table comments (key tables)", f"""
        SELECT table_schema, table_name, left(comment, 150) AS comment FROM {CAT}.information_schema.tables
        WHERE table_schema IN ('netmon_silver', 'netmon_gold', 'netmon_eval', 'netmon_noc') ORDER BY 1, 2""")
    d.query("Column comments on silver_sessions", f"""
        SELECT column_name, data_type, comment FROM {CAT}.information_schema.columns
        WHERE table_schema = 'netmon_silver' AND table_name = 'silver_sessions' AND comment IS NOT NULL
        ORDER BY ordinal_position""")

    who_sql = f"""
        SELECT current_user() AS user, is_member('noc_national') AS in_noc_national,
               is_member('noc_region_nsw') AS in_noc_region_nsw, is_member('pii_privileged') AS in_pii_privileged,
               {GOV}.is_pii_privileged() AS pii_privileged_fn"""
    views_sql = "\nUNION ALL ".join(
        f"SELECT '{v}' AS netmon_noc_view, count(*) AS visible_rows, "
        f"array_join(array_sort(collect_set(region_code)), ',') AS regions FROM {NOC}.{v}" for v in NOC_VIEWS)
    sample_sql = f"SELECT record_id, imsi, msisdn, region_code, outcome FROM {NOC}.silver_sessions ORDER BY record_id LIMIT 5"
    shape_sql = f"""
        SELECT count(*) AS n_rows,
               count_if(imsi RLIKE '^00101[0-9]{{10}}$') AS imsi_full_value,
               count_if(imsi RLIKE '^00101[*]{{8}}[0-9]{{2}}$') AS imsi_masked,
               count_if(msisdn RLIKE '^[+]999[0-9]{{9}}$') AS msisdn_full_value,
               count_if(msisdn RLIKE '^[+]999[*]{{6}}[0-9]{{3}}$') AS msisdn_masked
        FROM {NOC}.silver_sessions"""

    def state(title: str, note: str = "", masks: bool = False) -> None:
        d.query(f"{title}: principal", who_sql)
        d.query(f"{title}: rows visible in every object a regional role is granted", views_sql, note=note)
        if masks:
            d.query(f"{title}: IMSI / MSISDN shape (values never printed in full)", shape_sql)

    state("State 1 - noc_national (capturing user)", masks=True)
    d.query("State 1: masked sample for a NOC user outside pii_privileged", sample_sql)
    if demo:
        uid = r.cli("current-user", "me")["id"]

        def member(group: str, add: bool) -> None:
            op = {"op": "add", "path": "members", "value": [{"value": uid}]} if add else \
                {"op": "remove", "path": f'members[value eq "{uid}"]'}
            subprocess.run(["databricks", "groups", "patch", groups[group], "-p", r.profile, "--json", json.dumps(
                {"schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"], "Operations": [op]})], check=True)

        def settle(nat: bool, nsw: bool, pii: bool) -> None:
            want = (f"SELECT is_member('noc_national') = {nat} AND is_member('noc_region_nsw') = {nsw} "
                    f"AND is_member('pii_privileged') = {pii}")
            for _ in range(90):  # SCIM changes reach the warehouse's is_member() after a few minutes
                if r.sql(want)[1][0][0] in (True, "true"):
                    return
                time.sleep(10)
            raise RuntimeError(f"membership change not visible: {want}")

        try:
            member("noc_national", False)
            member("noc_region_nsw", True)
            settle(False, True, False)
            state("State 2 - noc_region_nsw only", note="Only NSW rows remain in every object.")
            member("noc_region_nsw", False)
            settle(False, False, False)
            state("State 3 - no NOC group", note="No rows in any object: the filter is false for every region.")
            member("pii_privileged", True)
            settle(False, False, True)
            state("State 4 - pii_privileged only (no NOC role)", masks=True,
                  note="Still no rows: pii_privileged grants no data access on its own (and holds no privileges, "
                       "see the persona table above).")
            member("noc_national", True)
            settle(True, False, True)
            state("State 5 - noc_national + pii_privileged", masks=True,
                  note="A NOC role plus pii_privileged: every region, and IMSI / MSISDN unmasked (checked by pattern).")
        finally:
            member("pii_privileged", False)
            member("noc_region_nsw", False)
            member("noc_national", True)
        settle(True, False, False)
        d.query("Restored membership", who_sql)
    d.write()


def lineage(r: Runner) -> None:
    d = Doc(r, "07_lineage.md", "Lineage: Volume → bronze → silver → gold",
            "Captured automatically by Unity Catalog; queried from `system.access.table_lineage`.")
    d.query("Table-level lineage edges for the netmon schemas", f"""
        SELECT coalesce(source_table_full_name, source_path) AS source, source_type,
               target_table_full_name AS target, target_type, entity_type, max(event_time) AS last_seen,
               count(*) AS n_events
        FROM system.access.table_lineage
        WHERE (target_table_full_name LIKE '{CAT}.netmon_%' OR source_table_full_name LIKE '{CAT}.netmon_%')
          AND event_date >= current_date() - INTERVAL 2 DAYS
          AND target_table_full_name IS NOT NULL
        GROUP BY ALL ORDER BY target, source""")
    d.text("Volume → bronze", "On this workspace `system.access.table_lineage` (and the lineage-tracking REST API) "
           "record the Auto Loader hop as a PIPELINE-entity edge into each bronze table with a NULL source "
           "(see the rows with `source = NULL` above): the Volume path is not populated as a lineage source. "
           "The hop is proven instead by `_source_file` (Auto Loader `_metadata.file_path`) on every bronze row:")
    d.query("Bronze rows by landing Volume directory (_metadata.file_path)", f"""
        SELECT 'bronze_kpis' AS table_name, regexp_replace(_source_file, '/date=.*', '/') AS volume_dir, count(*) AS n
        FROM {B}.bronze_kpis GROUP BY 2
        UNION ALL SELECT 'bronze_alarms', regexp_replace(_source_file, '/date=.*', '/'), count(*)
          FROM {B}.bronze_alarms GROUP BY 2
        UNION ALL SELECT 'bronze_sessions', regexp_replace(_source_file, '/date=.*', '/'), count(*)
          FROM {B}.bronze_sessions GROUP BY 2
        UNION ALL SELECT 'bronze_topology_nodes', regexp_replace(_source_file, '/[^/]*$', '/'), count(*)
          FROM {B}.bronze_topology_nodes GROUP BY 2
        UNION ALL SELECT 'bronze_gt_incidents', regexp_replace(_source_file, '/(date=.*|part-.*)$', '/'), count(*)
          FROM {E}.bronze_gt_incidents GROUP BY 2
        ORDER BY 1, 2""")
    d.write()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="febar")
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--pipeline-id", required=True)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--governance-demo", action="store_true")
    a = ap.parse_args()
    r = Runner(a.profile, a.warehouse)
    steps = {
        "status": lambda: pipeline_status(r, a.pipeline_id), "expectations": lambda: expectations(r),
        "counts": lambda: row_counts(r), "gold": lambda: gold_samples(r), "eval": lambda: evaluation(r),
        "governance": lambda: governance(r, a.governance_demo), "lineage": lambda: lineage(r),
    }
    for name, fn in steps.items():
        if not a.only or name in a.only:
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                print(f"[{name}] FAILED: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
