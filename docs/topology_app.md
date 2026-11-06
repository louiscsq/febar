# NOC topology app (Databricks App)

Step 5 of the Banksia Mobile NOC build: the operator's screen. For a region it draws the network from the core to the
cells with live element health, and for a selected open incident it pinpoints the failing element (the ranker's
suspect 1) and highlights the other two suspects. It shows the detection time and time to detect, impacted counts, the
Gen AI root-cause summary and next steps. The operator can approve or reject the customer SMS draft, and the decision
is written back to Lakebase; nothing is ever sent. An "Ask Genie" panel puts questions to the NOC Genie space. The
roleplay demo runs from this app. Evidence: [`evidence/step5/`](../evidence/step5/) (`04`–`07`).

App: `banksia-noc-topology`, https://banksia-noc-topology-7474648429104135.aws.databricksapps.com (workspace login).

## Framework: FastAPI + a static page

- **FastAPI backend** (`app/noc_app/`): a small JSON API that is easy to unit-test with fakes and gives the evidence
  plain HTTP responses. The browser does no data access of its own.
- **Static HTML / JS / CSS** (`app/static/`), no build step: an SVG tree for the topology and Leaflet (OpenStreetMap
  tiles) for the geographic map. Streamlit or Dash would have needed re-running scripts around a stateful SMS review,
  and React would have added a build for one screen.

| file | what |
|---|---|
| `app/app.yaml` | command, and env mapped from the app resources (`valueFrom: sql-warehouse`, `genie-space`) |
| `app/main.py` | wires settings, Lakebase store, warehouse, Genie client into the service |
| `app/noc_app/lakebase.py` | psycopg 3 pool with OAuth credentials; the read SQL; the review table DDL and INSERT |
| `app/noc_app/warehouse.py` | Statement Execution API with the user's token; region scope, inventory, timing, KPIs |
| `app/noc_app/genie.py` | Genie Conversation API with the user's token; query results scrubbed |
| `app/noc_app/topology.py` | pure topology building: region overview, incident focus, tidy-tree layout, map points |
| `app/noc_app/service.py` | use cases and the region scope; validation of the SMS write |
| `app/noc_app/safety.py` | drops IMSI / MSISDN / ground-truth label columns and redacts raw identifiers in every response |
| `app/noc_app/api.py` | routes |
| `resources/app.yml` | bundle app resource (resources, `user_api_scopes`, permissions) and the `app_lakebase_grants` job |
| `notebooks/13_app_lakebase_grants.py` | Postgres SELECT grants for the app's service principal on the synced tables |

## API

| route | source | what |
|---|---|---|
| `GET /api/me` | UC (user) | user, region scope, which identity reads what |
| `GET /api/incidents?region=` | Lakebase | open incidents with suspect 1, impact counts, fault hypothesis, SMS decision |
| `GET /api/incidents/{id}` | Lakebase + UC (user) | the incident panel: detection, impact, pinpoint + path from core, top-3, AI summary, SMS draft |
| `GET /api/regions/{r}/topology[?incident_id=]` | UC inventory (user, cached) + Lakebase status | graph (overview or incident focus) and map points |
| `POST /api/incidents/{id}/sms-review` | Lakebase write | `{decision: approve|reject, summary_id, note}` |
| `GET /api/incidents/{id}/sms-reviews` | Lakebase | review history |
| `GET /api/kpis` | UC (user) | operational MTTD and share within 5 min per region; the scored scorecard (national only) |
| `POST /api/genie/ask` | Genie (user) | `{question, conversation_id?}` → text, SQL, result table |
| `GET /api/health` | Lakebase | round trip as the app service principal |

## Lakebase hot path, SQL warehouse for reference data and analytics

| data | read from | why |
|---|---|---|
| open incidents + top-3 suspects, element status, AI summary + SMS draft | **Lakebase** (`netmon_rca.lb_open_incidents`, `lb_element_status`, `netmon_genai.lb_incident_ai_latest`) | changes every scoring / assistant run, read on every click: millisecond Postgres lookups (server-side p50 10–29 ms per API call, `04_app_deployment.md`) with no warehouse to keep warm |
| SMS approve / reject | **Lakebase** write (`netmon_app.sms_draft_reviews`) | an operational, transactional write with who / when; Delta is not an OLTP store |
| region scope, network inventory (names, hierarchy, coordinates) | SQL warehouse, **as the user** | reference data that changes with network builds, not by the minute (cached 15 min per region); reading it as the user is also how Unity Catalog's row filter decides the user's regions |
| operational detection timing, KPI tiles, scorecard | SQL warehouse, as the user | analytics over gold detections; seconds are fine, and the scorecard needs the user's grants |
| Ask Genie | Genie, as the user | Genie generates and runs the SQL itself |

## Identity and governance

| path | identity | how access is limited |
|---|---|---|
| Lakebase reads and the review write | the **app service principal**: its Postgres role comes from the `database` app resource (`CAN_CONNECT_AND_CREATE`); the password is a one-hour OAuth token from `generate_database_credential`, minted per pooled connection (recycled after 45 min) | Postgres: SELECT only on the three synced tables (`app_lakebase_grants` job); owner of its own `netmon_app` schema. **Rows are restricted in SQL to the user's region scope** (`region_code = ANY(%(regions)s)`) because Lakebase has no UC row filters |
| UC reads (warehouse) | the **signed-in user**, on-behalf-of token forwarded by the Apps proxy (`user_api_scopes: [sql]`) | UC grants, the `netmon_noc` views' `region_filter`, IMSI / MSISDN masks, all evaluated for that user |
| Genie | the **signed-in user** (`dashboards.genie`) | as above; the app SP also holds CAN_RUN on the space (app resource) but never asks as itself |
| opening the app / the space | NOC groups: CAN_USE on the app, CAN_RUN on the space (bundle permissions) | workspace permissions |

The app SP holds **no Unity Catalog data grant** (`07_auth_governance.md`): every UC read is the user's. The region
scope is "the regions whose rows the `netmon_noc` views return for this user", queried with the user's token and
cached 5 minutes, and is applied to every Lakebase read and write: an NSW analyst gets 404 for a VIC incident and 403
for the VIC topology (shown in `07`). The SMS review records `reviewed_by` from the identity the Apps proxy forwards
(`x-forwarded-email`); a request without one is refused (401).

**No subscriber data and no ground truth.** The app's sources hold neither: the Lakebase tables carry the ranker's
and the assistant's outputs, the UC reads are the `netmon_noc` views (never `silver_sessions`), and the only eval-schema
read is the labelled KPI scorecard. On top of that, `safety.scrub` drops any IMSI / MSISDN / subscriber-key column and
every ground-truth label column (step 3's `LABEL_COLUMNS`) at any depth of every response, Genie results included, and
redacts raw IMSI- or MSISDN-shaped strings (`tests/test_app_api_safety.py` poisons every source with them).

**Never sends.** The review table has `CHECK (sent_at IS NULL)` and `CHECK (send_channel = 'none')`; the app has no
messaging integration; a privileged `UPDATE … SET sent_at = now()` is rejected by the constraint
(`06_sms_review_writeback.md`). A review is bound to the exact draft (`summary_id` + SHA-256 of the text): approving a
draft that changed since the operator opened it returns 409.

## Deploy and run

```bash
databricks bundle deploy -t dev -p febar                       # Genie space, app, grants job (+ everything else)
databricks bundle run -p febar netmon_governance --params stage=serving_views   # netmon_noc views for app + Genie
databricks bundle run -p febar noc_topology                     # start / redeploy the app
databricks bundle run -p febar app_lakebase_grants              # Postgres SELECT for the app SP (after first deploy)

python scripts/genie_build_space.py                             # after editing src/netmon_pipeline/genie_space.py
python scripts/genie_benchmark.py --warehouse <id>             # evidence/step5/02_genie_benchmark.md
python scripts/trace_end_to_end.py --warehouse <id> --incident RCA-c7276c3238a27971 \
    --out 03_trace_site_power_outage.md --title "SITE-NSW-00105 site power outage (Sydney)"
python scripts/capture_evidence_step5.py --warehouse <id>      # evidence/step5/01, 04-07
```

Local development: `cd app && NOC_DEV_REGIONS=NSW,VIC DATABRICKS_CONFIG_PROFILE=febar LAKEBASE_INSTANCE=banksia-netmon-lakebase
DATABRICKS_WAREHOUSE_ID=<id> GENIE_SPACE_ID=<id> uvicorn main:app`. Without a forwarded user token the UC reads fall
back to the developer's own CLI identity and the region scope to `NOC_DEV_REGIONS`, which is never set on the app.

## Known limits

- **Replayed live feed.** The open incidents are step 3's `stream` run (ended 2026-10-09 00:56 UTC). The app shows that
  state; nothing streams in during the demo unless the stream generator and scoring job are run.
- **Time to localise** for incidents already open when live scoring started (23:56) reads as up to 68 minutes: the
  scorer's first decision, not the ranker's speed.
- **Operational time to detect** starts at the first anomaly visible in the telemetry, so it is a lower bound for
  slowly ramping faults (backhaul: 204 s shown, 511 s against ground truth).
- **Topology map tiles** come from OpenStreetMap in the browser; without internet access the map pane says so and the
  SVG topology still works.
- **SMS decisions are in Lakebase only** (no Lakebase database catalog without `CREATE CATALOG`), so Genie and UC
  queries do not see them.
- **Single app instance**, scope cache in process memory: fine for a NOC desk, not for many replicas.
