# Step 5 evidence: Genie space, NOC topology app, end-to-end trace

Everything here is text, captured from workspace profile `febar` on 2026-11-06 by the scripts named in each file.
All files were regenerated in one sequential pass from the code at this commit, after the PR #7 review fixes (bundle
deployed, app redeployed and the `serving_views` governance stage re-run first). `02a` is the exception: it is kept
on purpose as history and predates both the SMS-draft instruction fix and the removal of the ground-truth scorecard
from the Genie space.

**Ground truth is not part of anything Genie or the app shows.** Nothing in the Genie space, no app SQL and no API
response reads `netmon_eval` (`tests/test_no_ground_truth_surface.py`). Ground truth appears only in the
**FINAL VERIFICATION** section at the end of the two trace files.
Docs: [`docs/architecture.md`](../../docs/architecture.md), [`docs/genie_space.md`](../../docs/genie_space.md),
[`docs/topology_app.md`](../../docs/topology_app.md).

## Files

| file | what | written by |
|---|---|---|
| `01_genie_space.md` | deployed Genie space read back from the API: title, warehouse, 9 `netmon_noc` views with descriptions, 10 sample questions, the general instructions, permissions, full serialized space (no secrets) | `scripts/capture_evidence_step5.py` |
| `02_genie_benchmark.md` | final benchmark run (Genie eval-run API, 18 questions): per question Genie's assessment, expected vs generated SQL, both results executed | `scripts/genie_benchmark.py` |
| `02b_genie_benchmark_rerun1.md`, `02c_genie_benchmark_rerun2.md` | the two earlier runs on the same (current) question set, to show run-to-run variance | `scripts/genie_benchmark.py` |
| `02a_genie_benchmark_run1.md` | history: first run, before the SMS-draft fix and with the old scorecard questions | `scripts/genie_benchmark.py` |
| `03_trace_site_power_outage.md` | **the end-to-end trace**: SITE-NSW-00105 site power outage through every layer, then a labelled final verification against ground truth | `scripts/trace_end_to_end.py` |
| `03b_trace_slow_backhaul.md` | the same trace for BH-VIC-0005, a slowly degrading backhaul link | `scripts/trace_end_to_end.py` |
| `04_app_deployment.md` | app status, resources, OAuth scopes, service principal, deployments, `/api/health` (role and time only), the spoofed forwarded-header call, client- and server-side latency, app logs (IPs removed) | `scripts/capture_evidence_step5.py` |
| `05_app_api_responses.md` | HTTP responses the browser gets for the incident view: `/api/me`, incidents, incident panel, topology (focus + overview), KPIs, Ask Genie | `scripts/capture_evidence_step5.py` |
| `06_sms_review_writeback.md` | SMS approve then reject through the app, Lakebase rows before / after, refused writes (stale draft 409, `send` 400), a privileged `UPDATE sent_at` rejected by the CHECK constraint | `scripts/capture_evidence_step5.py` |
| `07_auth_governance.md` | which identity reads what; app SP has no UC data grants and read-only Postgres grants; masked IMSI / MSISDN; the same app and Genie calls as a national and as a regional (NSW-only) user; Genie refusing identifier requests; demo limits | `scripts/capture_evidence_step5.py` |

## Headline results

**Genie benchmark.** Final run 16/18; post-fix runs varied 16–18/18 (`02b` 18, `02c` 17, `02` 16). All 18
questions are over the `netmon_noc` views. The final run's two marked-down answers:

- *"What is the average time to detect across open incidents in seconds?"*: correct but unrounded (165.83 vs 165.8,
  `NEEDS_REVIEW`). This is the only miss in `02c`.
- *"Which element types does the aggregation router AGG-NSW-04 serve directly?"*: the right type (BACKHAUL_LINK)
  without the count column the expected SQL has (`BAD`, `RESULT_MISSING_COLUMNS`).

History (`02a`): before the SMS-draft fix and the scorecard removal, run 1 scored 17/18. It had a real miss: it counted
68 historical drafts instead of the 17 current ones. Four of the current 18 questions are close paraphrases of a
trusted example SQL.

**App latency** (`04`). Server-side inside the app, from its own request log: p50 **12 ms** for the incident list,
**27 ms** for the incident panel and **36 ms** for the topology. These are Lakebase reads plus, on a cold cache, the
warehouse inventory read; its occasional multi-second max is the cached warehouse timing query refreshing. Measured from the capturing laptop through the Apps proxy, the same calls take about
1.1–1.8 s p50. That is internet and proxy overhead with a fresh TLS connection per call, not app time. Ask Genie takes
about 10–26 s per question.

**End-to-end trace** (`03`, incident `RCA-c7276c3238a27971`):

1. Raw line `K-CELL-NSW-00105-4G1-202610090008` sits in
   `/Volumes/…/landing/stream/kpis/date=2026-10-09/batch-20261009T000900-000314.json`, showing availability at 63 %.
2. In bronze, `_source_file` is that file.
3. In silver, the pipeline's drop rules re-evaluated on the raw line all pass, it is not late, and it is not in the
   quarantine.
4. In gold, the first customer-impact detection was available at 00:10:42. The operational TTD is 162 s.
5. The ranker's stored scores and a fresh `banksia-rca-ranker` endpoint call on the same 55 features agree:
   top-1 SITE-NSW-00105 (p = 1.00), then AGG-NSW-04 and AMF-NSW-01.
6. Lakebase holds `lb_open_incidents`, `lb_element_status` (the site `down`, 3/3 cells), `lb_incident_ai_latest` and
   the app's reviews.
7. The Gen AI summary says SITE_POWER_OUTAGE with high confidence (NE_UNREACHABLE + BATTERY_LOW, "dispatch field
   tech"), and the SMS draft has status `draft`.
8. The app API pinpoints SITE-NSW-00105 with the path AMF-NSW-01 → UPF-NSW-01 → AGG-NSW-04 → BH-NSW-0045 → site.
9. Asked through the app, Genie answers "SITE-NSW-00105, 162.4 s, within 5 minutes, 420 subscribers" and shows the
   SQL it ran.
10. UC lineage: table edges bronze → silver → gold → `netmon_noc` views and Delta → Lakebase, plus the
    `banksia-rca-score-live` / `banksia-genai-assistant` job runs' read and write sets.
11. **Final verification** against ground truth (the only place it is read): SITE_POWER_OUTAGE on SITE-NSW-00105. Impact started at 00:08:38,
    so the TTD against ground truth is **124 s**, within the 5-minute SLA.

The slow-backhaul trace (`03b`) also pinpoints BH-VIC-0005 correctly. Its operational TTD is 204 s, but against
ground truth (final verification) it is **511 s**, which misses the SLA (see caveats).

**Forwarded-header trust** (`04`). A call through the Apps proxy that sent spoofed `x-forwarded-email`,
`x-forwarded-preferred-username` and `x-forwarded-access-token` headers had them overwritten by the proxy: the backend
saw the real signed-in user, and the region scope came from UC with the proxy's token.

**SMS write-back** (`06`). Approve and reject each insert a row in `netmon_app.sms_draft_reviews` with `reviewed_by`
(the forwarded user), `reviewed_at`, `app_identity` (the app SP), `sent_at = NULL` and `send_channel = 'none'`. The
table is append-only, so the "before" table already holds the rows from earlier capture runs.

**Governance** (`07`). As `noc_national` the user sees 17 incidents in 3 regions. As `noc_region_nsw` only (a
temporary membership switch, restored afterwards and confirmed by UC):

- `/api/me` shows the scope `["NSW"]` and the incident list has 9 NSW incidents;
- a VIC incident returns 404 and the VIC topology returns 403;
- Genie answers "NSW 9" only.

The app SP holds no UC data grant. `/api/health` returns only the Postgres role and time, with no unscoped counts.
Genie refuses an IMSI / MSISDN request.

## Caveats

- **Operational time to detect is a lower bound for slow faults.** It starts at the first anomalous KPI period, so for
  BH-VIC-0005 the app and Genie show 204 s while the true impact started 5.5 minutes earlier: 511 s against ground
  truth. For an abrupt fault it can instead read slightly long, because it starts at the minute boundary
  (SITE-NSW-00105: 162 s operational vs 124 s against ground truth). The ground-truth SLA figures are offline evaluation
  (steps 2–3) and are deliberately not shown by the app or Genie.
- **Time to localise** reads up to 68 minutes for incidents that were already open when live scoring started
  (23:56). That is the scorer's first decision time, not the ranker's speed.
- **Open incidents are censored.** The live run ended while they were still active, so they are not in the scored
  KPI tables. The traces use ground truth only as a labelled check.
- **Data is a replayed feed** (live run ended 2026-10-09 00:56 UTC). Nothing new streams in during the demo unless the
  generator and scoring jobs are run.
- **Regional view, demonstrated with one user.** It was shown by switching the capturing user's workspace-group
  membership. That user owns the catalog, so it could still read base tables a real regional member has no grant on.
  The app and Genie read only `netmon_noc` views, where the row filter (not ownership) decides. Persona service principals could not be used
  interactively.
- **Genie scores vary run to run** (16–18/18 on the current question set).
- **UC lineage breaks at the jobs' pandas / Parquet boundary.** The scoring and assistant jobs are linked by matching
  their read and write events per job run, not by a direct table edge.
- **SMS decisions are in Lakebase only.** No `CREATE CATALOG` means no Lakebase database catalog, so Genie and UC
  cannot see the decisions.
