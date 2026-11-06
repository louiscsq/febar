"""Capture text evidence of step 5 (Genie space, topology app, SMS write-back, auth / governance) into evidence/step5/.

    python scripts/capture_evidence_step5.py --profile febar --warehouse <id> [--only genie,app,api,sms,governance]

The app is called through the Databricks Apps proxy with the capturing user's OAuth token (as a browser session
would be), so every response is what the signed-in user sees. `governance` temporarily moves the capturing user from
`noc_national` to `noc_region_nsw` (workspace-local groups) to show the regional view through the app and Genie, then
restores the membership, as step 2's evidence did. The Genie benchmark (02) and the traces (03*) have their own
scripts. No secret is read or written; client IP addresses are removed from the captured logs.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from capture_evidence import Runner  # noqa: E402
from trace_end_to_end import CAT, Trace, app_call, cli_token, pg_rows, topo_trim  # noqa: E402

APP = "banksia-noc-topology"
INCIDENT, OTHER_REGION_INCIDENT = "RCA-c7276c3238a27971", "RCA-27ed3e8af852d33a"  # NSW site power / VIC backhaul
NOC = f"{CAT}.netmon_noc"


class Doc(Trace):
    def __init__(self, r: Runner, title: str, intro: str):
        super().__init__(r, title, INCIDENT)
        self.parts = [f"# {title}\n", f"Captured {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC from workspace "
                      f"profile `{r.profile}` by `scripts/capture_evidence_step5.py`.\n", intro.strip() + "\n"]

    def h(self, title: str, text: str = "") -> None:
        self.parts.append(f"## {title}\n\n{text.strip()}\n" if text else f"## {title}\n")

    def http(self, label: str, res: tuple[int, dict, float], trim=None) -> dict:
        code, body, ms = res
        self.code({"request": label, "http_status": code, "latency_ms": round(ms),
                   "body": trim(body) if trim and code == 200 else body})
        return body


def bundle_summary(profile: str) -> dict:
    out = subprocess.run(["databricks", "bundle", "summary", "-t", "dev", "-p", profile, "-o", "json"],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)["resources"]


def cli_json(profile: str, *args: str) -> dict:
    out = subprocess.run(["databricks", *args, "-p", profile, "-o", "json"], capture_output=True, text=True,
                         check=True).stdout
    return json.loads(out) if out.strip() else {}


# ---------------------------------------------------------------------------------------------------------------------

def genie_doc(r: Runner, a, res: dict) -> None:
    sid = res["genie_spaces"]["noc_genie"]["id"]
    d = Doc(r, "Genie space: deployed configuration", f"""
The NOC Genie space as deployed by the bundle (`resources/genie.yml`, body generated from
`src/netmon_pipeline/genie_space.py`), read back from the Genie API (`GET /api/2.0/genie/spaces/{{id}}` with
`include_serialized_space`). It holds no credentials. Space `{sid}`: {res['genie_spaces']['noc_genie'].get('url')}""")
    sp = cli_json(a.profile, "genie", "get-space", sid, "--include-serialized-space")
    s = json.loads(sp.pop("serialized_space"))
    d.code({k: sp.get(k) for k in ("space_id", "title", "description", "warehouse_id", "parent_path", "create_time",
                                   "update_time")})
    d.h("Contents")
    d.table([{"tables": len(s["data_sources"]["tables"]), "sample_questions": len(s["config"]["sample_questions"]),
              "trusted_example_sql": len(s["instructions"]["example_question_sqls"]),
              "join_hints": len(s["instructions"]["join_specs"]),
              "sql_snippets": sum(len(v) for v in s["instructions"]["sql_snippets"].values()),
              "benchmark_questions": len(s["benchmarks"]["questions"])}])
    d.table([{"table": t["identifier"], "description": t["description"][0],
              "column_configs": len(t.get("column_configs", []))} for t in s["data_sources"]["tables"]],
            note="Tables (all region-filtered `netmon_noc` views; no ground-truth table):", max_cell=260)
    d.h("Sample questions")
    d.text("\n".join(f"- {q['question'][0]}" for q in s["config"]["sample_questions"]))
    d.h("General instructions")
    d.code("".join(s["instructions"]["text_instructions"][0]["content"]), lang="text")
    d.h("Space permissions")
    perms = cli_json(a.profile, "permissions", "get", "genie", sid)
    d.table([{"principal": x.get("group_name") or x.get("service_principal_name") or x.get("user_name"),
              "display_name": x.get("display_name"),
              "levels": ", ".join(p["permission_level"] for p in x.get("all_permissions", []))}
             for x in perms.get("access_control_list", [])], max_cell=80)
    d.h("Full serialized space (as deployed)")
    d.code(s)
    d.write("01_genie_space.md")


def app_doc(r: Runner, a, res: dict, tok: str) -> None:
    app = cli_json(a.profile, "apps", "get", APP)
    d = Doc(r, "Databricks App: deployment status, resources and logs", f"""
`{APP}` deployed by the bundle (`resources/app.yml`, source `app/`, `app/app.yaml`). Status and configuration from
`GET /api/2.0/apps/{APP}`; deployments from `.../deployments`; logs from `databricks apps logs` (client IP addresses
removed).""")
    keep = ("name", "url", "description", "compute_status", "app_status", "compute_size", "service_principal_name",
            "service_principal_client_id", "user_api_scopes", "effective_user_api_scopes", "resources",
            "default_source_code_path", "create_time", "update_time", "creator")
    d.code({k: app.get(k) for k in keep})
    deps = cli_json(a.profile, "apps", "list-deployments", APP)
    deps = deps if isinstance(deps, list) else deps.get("app_deployments", [])
    d.h("Deployments (latest 5)")
    d.table([{"deployment_id": x["deployment_id"], "create_time": x.get("create_time"), "mode": x.get("mode"),
              "state": x["status"]["state"], "message": x["status"].get("message"),
              "source_code_path": x.get("source_code_path")} for x in deps[:5]], max_cell=120)
    d.h("Live checks through the Apps proxy",
        "`/api/health` round-trips to Lakebase as the app service principal; then 20 timed calls of the hot-path "
        "endpoints (warm):")
    d.http("GET /api/health", app_call(a.url, tok, "/api/health"))
    d.h("Forwarded-header trust boundary (spoofing attempt)",
        "The app takes the user's identity from `x-forwarded-email` / `x-forwarded-access-token`, set by the Databricks "
        "Apps proxy. Here the client sends its own (spoofed) values for both headers through the proxy, with a valid "
        "login token for the capturing user; `/api/me` reports which identity the backend actually received:")
    spoof = {"x-forwarded-email": "spoofed.attacker@banksia.example",
             "x-forwarded-preferred-username": "spoofed.attacker", "x-forwarded-access-token": "spoofed-token"}
    code, body, _ = app_call(a.url, tok, "/api/me", extra_headers=spoof)
    d.code({"request": "GET /api/me with spoofed x-forwarded-* headers", "sent_headers": spoof, "http_status": code,
            "body": body})
    seen = body.get("user") if isinstance(body, dict) else None
    d.text(f"Backend saw user `{seen}`: the spoofed email was "
           f"{'**overwritten by the proxy**' if seen != spoof['x-forwarded-email'] else '**NOT overwritten (finding)**'}"
           f"; the region scope {body.get('regions') if isinstance(body, dict) else None} came from Unity Catalog with "
           "the proxy-forwarded token (a spoofed token would have failed the UC query).")
    lat = {}
    for path in ("/api/incidents?region=NSW", f"/api/incidents/{INCIDENT}",
                 f"/api/regions/NSW/topology?incident_id={INCIDENT}"):
        ms = [app_call(a.url, tok, path)[2] for _ in range(20)]
        lat[path] = {"n": 20, "p50_ms": round(statistics.median(ms)), "p95_ms": round(sorted(ms)[18]),
                     "max_ms": round(max(ms))}
    d.table([{"endpoint": k, **v} for k, v in lat.items()],
            note="End-to-end latency measured from the capturing laptop (includes the internet round trip and the "
                 "Apps proxy):")
    logs = subprocess.run(["databricks", "apps", "logs", APP, "-p", a.profile, "--tail-lines", "400"],
                          capture_output=True, text=True, timeout=120).stdout
    logs = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "<ip>", logs)
    server: dict[str, list[float]] = {}
    for m in re.finditer(r"noc_app GET (\S+) -> 200 in (\d+) ms", logs):
        server.setdefault(m.group(1), []).append(float(m.group(2)))
    d.table([{"endpoint (path)": k, "n": len(v), "p50_ms": round(statistics.median(v)),
              "p95_ms": round(sorted(v)[max(0, int(len(v) * 0.95) - 1)]), "max_ms": round(max(v))}
             for k, v in sorted(server.items()) if len(v) >= 5],
            note="Server-side time inside the app for the same calls (from the app's own request log, "
                 "`noc_app ... -> 200 in N ms`): Lakebase queries plus, on a cold cache, the warehouse topology read:")
    d.h("App logs (last 60 lines)")
    d.code("\n".join(logs.strip().splitlines()[-60:]), lang="text")
    d.write("04_app_deployment.md")


def api_doc(r: Runner, a, tok: str) -> None:
    d = Doc(r, "App API responses (incident view)", f"""
What the operator's browser receives from `{a.url}` for the demo incident `{INCIDENT}` (SITE-NSW-00105, site power
outage), captured as the signed-in national NOC user. The page (`app/static/`) renders exactly these payloads.""")
    d.h("Who am I (identity, region scope from Unity Catalog)")
    d.http("GET /api/me", app_call(a.url, tok, "/api/me"))
    d.h("Open incidents in NSW (Lakebase)")
    d.http("GET /api/incidents?region=NSW", app_call(a.url, tok, "/api/incidents?region=NSW"))
    d.h("Incident panel", "Detection time and time to detect, impacted counts, the ranker's top-3 with scores, the "
        "pinpointed element with its path from the core, the Gen AI summary and next steps, the SMS draft:")
    d.http(f"GET /api/incidents/{INCIDENT}", app_call(a.url, tok, f"/api/incidents/{INCIDENT}"))
    d.h("Topology: incident focus (pinpoint highlighted)")
    d.http(f"GET /api/regions/NSW/topology?incident_id={INCIDENT}  (trimmed to the highlighted elements)",
           app_call(a.url, tok, f"/api/regions/NSW/topology?incident_id={INCIDENT}"), trim=topo_trim)
    code, full, ms = app_call(a.url, tok, f"/api/regions/NSW/topology?incident_id={INCIDENT}")
    d.code({"nodes": [{k: n.get(k) for k in ("id", "kind", "element_type", "state", "highlight", "depth", "x",
                                             "count")} for n in full["graph"]["nodes"]]},
           note="All drawn nodes of that view (healthy siblings collapsed into `+N` nodes), with their layout:")
    d.h("Topology: region overview")
    d.http("GET /api/regions/NSW/topology  (counts only)", app_call(a.url, tok, "/api/regions/NSW/topology"),
           trim=lambda b: {"view": b["graph"]["view"], "n_elements_in_region": b["n_elements"],
                           "n_nodes_drawn": len(b["graph"]["nodes"]), "state_counts": b["state_counts"],
                           "unhealthy_drawn": [n["id"] for n in b["graph"]["nodes"]
                                               if n.get("state") not in (None, "ok")][:40]})
    d.h("Detection KPIs (SQL warehouse as the user)")
    d.http("GET /api/kpis", app_call(a.url, tok, "/api/kpis"))
    d.h("Ask Genie from the app")
    d.http("POST /api/genie/ask {question: 'Which cell sites are down right now?'}",
           app_call(a.url, tok, "/api/genie/ask", {"question": "Which cell sites are down right now?"}))
    d.write("05_app_api_responses.md")


def sms_doc(r: Runner, a, w, tok: str) -> None:
    d = Doc(r, "SMS draft review: approve / reject written back to Lakebase", f"""
The operator reviews the customer SMS draft of `{INCIDENT}` in the app. Each decision is an INSERT into the Lakebase
table `netmon_app.sms_draft_reviews` (append-only audit; who = the identity the Apps proxy forwards, when = the
database clock), done by the app's service principal. Nothing is ever sent: the table cannot hold a send
(`CHECK (sent_at IS NULL)`, `CHECK (send_channel = 'none')`) and the app has no messaging integration. Rows below are
read with psycopg as the capturing user, before and after.""")
    q = """SELECT review_id, incident_id, summary_id, region_code, left(draft_sha256, 12) AS draft_sha256_12, decision,
                  note, reviewed_by, reviewed_at, app_identity, sent_at, send_channel
           FROM netmon_app.sms_draft_reviews WHERE incident_id = %(i)s ORDER BY reviewed_at"""
    d.h("Table definition (owned by the app's Postgres role)")
    d.table(pg_rows(w, """SELECT conname, pg_get_constraintdef(oid) AS definition FROM pg_constraint
                          WHERE conrelid = 'netmon_app.sms_draft_reviews'::regclass ORDER BY conname"""), max_cell=200)
    d.table(pg_rows(w, """SELECT tableowner FROM pg_tables WHERE schemaname = 'netmon_app'
                          AND tablename = 'sms_draft_reviews'"""), note="Owner (the app service principal's role):")
    d.h("Before")
    before = pg_rows(w, q, {"i": INCIDENT})
    d.table(before) if before else d.text("_(no review rows for this incident)_")
    _, inc, _ = app_call(a.url, tok, f"/api/incidents/{INCIDENT}")
    d.code(inc["sms"], note="The draft as the app shows it (`GET /api/incidents/{id}` -> `sms`):")
    d.h("Approve, then reject (two operator actions)")
    d.http("POST /api/incidents/{id}/sms-review {decision: approve}", app_call(
        a.url, tok, f"/api/incidents/{INCIDENT}/sms-review",
        {"decision": "approve", "summary_id": inc["sms"]["summary_id"], "note": "evidence capture: approve"}))
    d.http("POST /api/incidents/{id}/sms-review {decision: reject}", app_call(
        a.url, tok, f"/api/incidents/{INCIDENT}/sms-review",
        {"decision": "reject", "summary_id": inc["sms"]["summary_id"], "note": "evidence capture: wording"}))
    d.h("Refused writes")
    d.http("POST ... {decision: approve, summary_id: <stale>}  (draft changed since the operator opened it)",
           app_call(a.url, tok, f"/api/incidents/{INCIDENT}/sms-review",
                    {"decision": "approve", "summary_id": "stale-summary-id"}))
    d.http("POST ... {decision: send}", app_call(a.url, tok, f"/api/incidents/{INCIDENT}/sms-review",
                                                 {"decision": "send", "summary_id": inc["sms"]["summary_id"]}))
    d.h("After")
    d.table(pg_rows(w, q, {"i": INCIDENT}))
    d.http(f"GET /api/incidents/{INCIDENT}  -> sms", app_call(a.url, tok, f"/api/incidents/{INCIDENT}"),
           trim=lambda b: b["sms"])
    d.http(f"GET /api/incidents/{INCIDENT}/sms-reviews", app_call(a.url, tok, f"/api/incidents/{INCIDENT}/sms-reviews"))
    d.h("The table cannot record a send",
        "Even a privileged database user trying to mark a review as sent is stopped by the constraint (run in a "
        "transaction):")
    import psycopg

    inst = w.database.get_database_instance("banksia-netmon-lakebase")
    cred = w.database.generate_database_credential(request_id=str(uuid.uuid4()),
                                                   instance_names=["banksia-netmon-lakebase"])
    stmt = "UPDATE netmon_app.sms_draft_reviews SET sent_at = now() WHERE incident_id = %(i)s"
    with psycopg.connect(host=inst.read_write_dns, port=5432, dbname="netmon_serving", user=w.current_user.me().user_name,
                         password=cred.token, sslmode="require") as c:
        try:
            c.execute(stmt, {"i": INCIDENT})
            outcome = "UPDATE succeeded (unexpected)"
        except psycopg.Error as e:
            outcome = f"{type(e).__name__}: {str(e).splitlines()[0]}"
        finally:
            c.rollback()  # never keep anything from this probe
    d.code(f"{stmt}\n-> {outcome}\n(transaction rolled back)", lang="text")
    d.write("06_sms_review_writeback.md")


def governance_doc(r: Runner, a, w, tok: str, res: dict) -> None:
    from databricks.sdk.service import iam

    app = w.apps.get(APP)
    sp = app.service_principal_client_id
    me = w.current_user.me()
    d = Doc(r, "Auth and governance: who reads what, and what a regional user sees", f"""
**Identities.**

| path | identity | enforcement |
|---|---|---|
| Lakebase reads (incidents, suspects, element status, AI summary) and the SMS review write | app service principal `{sp}` (`{app.service_principal_name}`), OAuth database credential | Postgres grants: SELECT on the three synced tables, own `netmon_app` schema; rows restricted in SQL to the user's UC region scope |
| Unity Catalog reads through the SQL warehouse (region scope, inventory, detection timing, KPIs) | signed-in user, on-behalf-of token (`user_api_scopes: sql`) | UC grants + the `netmon_noc` views' `region_filter` + IMSI / MSISDN masks, evaluated for the user |
| Genie questions | signed-in user, on-behalf-of token (`dashboards.genie`) | Genie runs the SQL as the user: same UC enforcement |
| App access | NOC groups CAN_USE on the app; Genie space CAN_RUN | workspace permissions |

The capturing user is `{me.user_name}`: a member of `noc_national` (sees every region) and NOT of `pii_privileged`
(sees masked identifiers). It is also the catalog owner, which limits what it can demonstrate (see the end).""")

    d.h("App service principal: no Unity Catalog data grants",
        "The app's own identity holds no SELECT anywhere in the catalog (all UC data access is the user's):")
    d.sql(f"""SELECT 'table' AS kind, table_schema AS schema_name, table_name, privilege_type
              FROM {CAT}.information_schema.table_privileges WHERE grantee = '{sp}'
              UNION ALL SELECT 'schema', schema_name, NULL, privilege_type
              FROM {CAT}.information_schema.schema_privileges WHERE grantee = '{sp}'
              UNION ALL SELECT 'catalog', NULL, NULL, privilege_type
              FROM {CAT}.information_schema.catalog_privileges WHERE grantee = '{sp}'""")
    d.table(pg_rows(w, """SELECT table_schema, table_name, string_agg(privilege_type, ', ' ORDER BY privilege_type) AS privileges
                          FROM information_schema.role_table_grants WHERE grantee = %(g)s GROUP BY 1, 2 ORDER BY 1, 2""",
                    {"g": sp}), note="Its Postgres privileges in `netmon_serving` (read-only on the synced tables; "
                                     "full rights only on its own review table):")
    wh = cli_json(a.profile, "permissions", "get", "warehouses", a.warehouse)
    d.table([{"principal": x.get("group_name") or x.get("service_principal_name") or x.get("user_name"),
              "levels": ", ".join(p["permission_level"] for p in x.get("all_permissions", []))}
             for x in wh.get("access_control_list", [])], note="SQL warehouse permissions:")

    d.h("PII masking for a non-privileged reader",
        "The app and the Genie space never touch `silver_sessions` (tested). For reference, the same user querying the "
        "masked view directly:")
    d.sql(f"SELECT imsi, msisdn, region_code FROM {NOC}.silver_sessions LIMIT 3")
    d.sql("SELECT is_member('noc_national') AS in_noc_national, is_member('noc_region_nsw') AS in_noc_region_nsw, "
          "is_member('pii_privileged') AS in_pii_privileged")

    def snapshot(label: str) -> None:
        d.h(label)
        d.http("GET /api/me", app_call(a.url, tok, "/api/me"))
        d.http("GET /api/incidents", app_call(a.url, tok, "/api/incidents"),
               trim=lambda b: {"n": len(b["incidents"]), "regions": sorted({i["region_code"] for i in b["incidents"]}),
                               "incident_ids": [i["incident_id"] for i in b["incidents"]]})
        d.http(f"GET /api/incidents/{OTHER_REGION_INCIDENT}  (a VIC incident)",
               app_call(a.url, tok, f"/api/incidents/{OTHER_REGION_INCIDENT}"),
               trim=lambda b: {"incident_id": b["incident_id"], "region_code": b["region_code"]})
        d.http("GET /api/regions/VIC/topology", app_call(a.url, tok, "/api/regions/VIC/topology"),
               trim=lambda b: {"region": b["region"], "n_elements": b["n_elements"]})
        d.http("GET /api/kpis", app_call(a.url, tok, "/api/kpis"))
        res_ = app_call(a.url, tok, "/api/genie/ask", {"question": "How many open incidents are there per region?"})
        d.http("POST /api/genie/ask {How many open incidents are there per region?}", res_,
               trim=lambda b: {k: b.get(k) for k in ("text", "sql", "columns", "rows")})
        d.sql(f"SELECT region_code, count(*) AS n FROM {NOC}.open_incidents GROUP BY 1 ORDER BY 1",
              note="Direct query of the view as the same user:")

    snapshot("As a national NOC user (noc_national)")

    g_nat = next(iter(w.groups.list(filter='displayName eq "noc_national"')))
    g_nsw = next(iter(w.groups.list(filter='displayName eq "noc_region_nsw"')))
    patch = [iam.PatchSchema.URN_IETF_PARAMS_SCIM_API_MESSAGES_2_0_PATCH_OP]
    try:
        w.groups.patch(g_nat.id, schemas=patch, operations=[
            iam.Patch(op=iam.PatchOp.REMOVE, path=f'members[value eq "{me.id}"]')])
        w.groups.patch(g_nsw.id, schemas=patch, operations=[
            iam.Patch(op=iam.PatchOp.ADD, value={"members": [{"value": me.id}]})])
        t0 = time.time()
        regions = None
        while time.time() - t0 < 900:  # UC membership and the app's 5-minute scope cache must both catch up
            _, body, _ = app_call(a.url, tok, "/api/me")
            regions = body.get("regions")
            if regions == ["NSW"]:
                break
            time.sleep(30)
        d.text(f"**Membership switched**: capturing user removed from `noc_national` and added to `noc_region_nsw` "
               f"(SCIM PATCH on the workspace groups). The app reported region scope {regions} after "
               f"{time.time() - t0:.0f} s (UC membership propagation + the app's 5-minute scope cache).")
        d.sql("SELECT is_member('noc_national') AS in_noc_national, is_member('noc_region_nsw') AS in_noc_region_nsw")
        snapshot("As a regional NOC user (noc_region_nsw only)")
    finally:
        w.groups.patch(g_nsw.id, schemas=patch, operations=[
            iam.Patch(op=iam.PatchOp.REMOVE, path=f'members[value eq "{me.id}"]')])
        w.groups.patch(g_nat.id, schemas=patch, operations=[
            iam.Patch(op=iam.PatchOp.ADD, value={"members": [{"value": me.id}]})])
    d.h("Restored")
    t0 = time.time()
    while time.time() - t0 < 600:  # wait for UC to see the restored membership before recording it
        _, rows = r.sql("SELECT is_member('noc_national'), is_member('noc_region_nsw')")
        if rows and rows[0] == ["true", "false"]:
            break
        time.sleep(20)
    d.text(f"Membership restored (back in `noc_national`, out of `noc_region_nsw`); visible to UC after "
           f"{time.time() - t0:.0f} s:")
    d.sql("SELECT is_member('noc_national') AS in_noc_national, is_member('noc_region_nsw') AS in_noc_region_nsw")

    d.h("Genie and subscriber identifiers")
    d.http("POST /api/genie/ask {List the IMSI and MSISDN of the subscribers on SITE-NSW-00105}",
           app_call(a.url, tok, "/api/genie/ask",
                    {"question": "List the IMSI and MSISDN of the subscribers on SITE-NSW-00105"}),
           trim=lambda b: {k: b.get(k) for k in ("text", "sql", "columns", "rows")})

    d.h("Limits of this demonstration (workspace)", """
- **Workspace-local groups.** This FEVM workspace cannot create account groups, so the NOC roles are workspace-local
  groups (docs/pipeline.md). Unity Catalog cannot grant to them; the row filter tests their membership with
  `is_member()`, which is what changes the regional view above. With account groups nothing in the app changes.
- **Grant-level denial is not visible with this user.** The capturing user owns the catalog, so after the switch it
  could still read base tables a real `noc_region_nsw` member has no grant on. The app and Genie only read
  `netmon_noc` views, where the row filter (not ownership) decides, so the regional view above is what a regional
  member gets; regional roles' grants are `netmon_noc` only (`governance/sql/03_grants_regional.sql`).
- **No second human user / persona login.** The persona service principals (`netmon-noc-nsw-analyst`, ...) cannot be
  used interactively here (no OAuth secret creation for this session, as in step 2), and the Apps proxy forwards a
  user token only for interactive users, so the regional view is shown by changing the capturing user's membership.
- **Lakebase has no UC row filters.** The app enforces the UC-derived region scope in its Lakebase SQL
  (`region_code = ANY(...)`); the app service principal itself can read all regions of the three synced tables.
""")
    d.write("07_auth_governance.md")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="febar")
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--only", default="genie,app,api,sms,governance")
    a = ap.parse_args()
    from databricks.sdk import WorkspaceClient

    r = Runner(a.profile, a.warehouse)
    w = WorkspaceClient(profile=a.profile)
    res = bundle_summary(a.profile)
    a.url = w.apps.get(APP).url
    tok = cli_token(a.profile)
    steps = {"genie": lambda: genie_doc(r, a, res), "app": lambda: app_doc(r, a, res, tok),
             "api": lambda: api_doc(r, a, tok), "sms": lambda: sms_doc(r, a, w, tok),
             "governance": lambda: governance_doc(r, a, w, tok, res)}
    for name in a.only.split(","):
        steps[name]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
