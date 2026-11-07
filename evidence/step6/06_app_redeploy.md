# Step 6 follow-up: topology app redeployed with the C1 Genie safety fix

Run 2026-11-07 04:00–04:12 UTC as `louis.chen@databricks.com` (CLI profile `febar`, CLI v1.19.0), from a clean
checkout of `main` at `53dcffd` (merge of PR #8, which carries the case-insensitive `safety.scrub_genie_answer`).
Only the app was deployed. No pipeline, job, model, serving endpoint, table or grant was changed or run, and no Genie
space configuration was changed; the Ask Genie smoke test created two Genie conversations (section 4).

## 1. Plan: a full bundle deploy would touch two other resources, so the deploy was limited to the app

```text
$ databricks bundle plan -t dev -p febar
update schemas.netmon_eval
update schemas.netmon_gold
Plan: 0 to add, 2 to change, 0 to delete, 35 unchanged
```

Both schema "updates" are drift in the server-computed `properties` map (`Predictive Optimization`, `owner`,
`unity.catalog.resourceId`); the declared name / catalog / comment are unchanged. They were still left out:

```text
$ databricks bundle plan -t dev -p febar --select apps.noc_topology
Plan: 0 to add, 0 to change, 0 to delete, 4 unchanged, 33 not selected
  apps.noc_topology                 skip
  apps.noc_topology.permissions     skip
  database_instances.netmon_lakebase skip   (dependency, unchanged)
  genie_spaces.noc_genie            skip   (dependency, unchanged)
```

## 2. Deploy and redeploy the app

```text
$ databricks bundle deploy -t dev -p febar --select apps.noc_topology
Building netmon_wheel...
Uploading dist/netmon_datagen-0.1.0-py3-none-any.whl...
Uploading bundle files to /Workspace/Users/louis.chen@databricks.com/.bundle/banksia_netmon/dev/files...
Files: 155 uploaded, 0 deleted
Resources: 0 created, 0 changed, 0 deleted, 4 unchanged, 33 not selected

$ databricks bundle run -t dev -p febar noc_topology
✓ Preparing source code for new app deployment.
✓ Deployment is pending
✓ Starting app with command: uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
✓ App started successfully
```

The file sync refreshed the shared bundle workspace files to the `main` `53dcffd` contents (code only). The unselected
pipeline and job resources were not deployed, updated or run. No non-app bundle resource was created, updated, deleted or run; only the app deployment was run.

## 3. App status and deployment

`databricks apps get banksia-noc-topology -p febar`:

| field | value |
|---|---|
| app status | `RUNNING`: App has status: App is running |
| compute status | `ACTIVE` |
| deployment id | `01f1da60a03b1d788cfb6fc9886060e5` (`SUCCEEDED`: App started successfully) |
| created | 2026-11-07T04:06:36Z by louis.chen@databricks.com, mode `SNAPSHOT` |
| source code path | `/Workspace/Users/louis.chen@databricks.com/.bundle/banksia_netmon/dev/files/app` |
| source snapshot | `/Workspace/Users/23923ae9-3de4-453b-b13f-b61f7ba84868/src/01f1da60a03b1d788cfb6fc9886060e5` |
| previous deployment | `01f1d9e4a21b1266bd7ce8f97e38e813` (2026-11-06 13:19 UTC) |

**The source matches `main` 53dcffd.** I exported every git-tracked file under `app/` (15 files: app.yaml, main.py, noc_app/{__init__,api,config,genie,lakebase,safety,service,topology,warehouse}.py, requirements.txt, static/{app.js,index.html,style.css}) from the
deployment snapshot and compared each one byte for byte with the `53dcffd` checkout. All 15 are identical.
`noc_app/safety.py` has SHA-256 `cf0d7f3198e48181cc163f9f8a5f5bf63a10b2fccea9996b44ab4002a6e65117` in both, and
git blob `c3b1921388d16ab3d6f01db54db64561a711b3c1`.

## 4. Smoke test as the signed-in user

Calls went through the Apps proxy to https://banksia-noc-topology-7474648429104135.aws.databricksapps.com with the user's
CLI OAuth token (`databricks auth token -p febar`). Every call was read-only except the one Genie question; no SMS
review was written. Latency is client wall-clock time, including the proxy. Pass 1 ran right after the
restart (cold Lakebase pool and region-scope cache); pass 2 followed straight after it.

| check | call | pass 1 | ms | pass 2 | ms | result |
|---|---|---|---|---|---|---|
| Health | `GET /api/health` | 200 | 3,109 | 200 | 1,105 | `status: ok`, Lakebase role = app SP, server-side `lakebase_ms` 1567 |
| Signed-in identity / region scope | `GET /api/me` | 200 | 9,525 | 200 | 1,035 | `louis.chen@databricks.com`, regions NQL, NSW, VIC, WA, `on_behalf_of_user: true` |
| Incident list (all regions in scope) | `GET /api/incidents` | 200 | 1,012 | 200 | 1,058 | 17 open incidents (NQL, NSW, VIC) |
| Incident list, NSW | `GET /api/incidents?region=NSW` | 200 | 1,035 | 200 | 1,038 | 9 open NSW incidents |
| Incident panel | `GET /api/incidents/RCA-cdc1224a2469350b` | 200 | 7,168 | 200 | 1,202 | `RCA-cdc1224a2469350b`: suspect 1 `BH-NSW-0015` (BACKHAUL_LINK), TTD 182.6 s, 6 cells / 480 subs, AI summary + SMS draft present: True/True |
| Topology, NSW overview | `GET /api/regions/NSW/topology` | 200 | 1,539 | 200 | 1,561 | 814 elements, 193 map points, graph keys ['edges', 'max_depth', 'nodes', 'view'] |
| Topology, NSW incident focus | `GET /api/regions/NSW/topology?incident_id=RCA-cdc1224a2469350b` | 200 | 1,532 | 200 | 1,529 | 814 elements, 193 map points, graph keys ['edges', 'max_depth', 'missing_suspects', 'nodes', 'path', 'pinpoint', 'view'] |
| Ask Genie | `POST /api/genie/ask` | 200 | 14,743 | 200 | 19,836 | `COMPLETED`, not withheld: "There are **9** open incidents in **NSW**." rows [['9']] |

Genie SQL (pass 1, conversation `01f1da60e9ab13cdb9cc7407ad19fac3`). It reads only the `netmon_noc` serving view, so
`scrub_genie_answer` let the answer through:

```sql
SELECT count(*) AS `open_incidents`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`open_incidents`
WHERE `region_code` = 'NSW'
```

The Genie count (9) matches the NSW incident list (9). The question added two conversations to the space (one per
pass); the space configuration was not changed.

## Result

`banksia-noc-topology` is RUNNING on deployment `01f1da60a03b1d788cfb6fc9886060e5`, built from `main` 53dcffd, so it now has the
PR #8 C1 guard (case-insensitive withholding of Genie answers that reference eval / ground-truth tables, label columns
or fault-class labels). All 8 smoke checks returned 200 in both passes.
