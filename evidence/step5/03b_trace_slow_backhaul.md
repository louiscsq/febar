# End-to-end trace: BH-VIC-0005 slow backhaul degradation (Melbourne)

Captured 2026-11-06 13:47 UTC from workspace profile `febar` by `scripts/trace_end_to_end.py --incident RCA-27ed3e8af852d33a`. Every block below is the real output of that hop; nothing is hand-edited.

**The fault.** Incident `RCA-27ed3e8af852d33a` in `VIC`, live feed (`source_run = 'stream'`). The root-cause ranker's
suspect 1 is `BH-VIC-0005` (BACKHAUL_LINK). The trace starts from the first customer-impact detection on that
element's subtree and walks back to the raw file, then forward to the operator's screen and Genie.

## 1. Raw file in the Unity Catalog Volume

The generator's live stream writes one JSON-lines micro-batch per feed per simulated minute into
`/Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/`. The first detection on `BH-VIC-0005`'s subtree came from record `K-CELL-VIC-00009-4G2-202610082248`
(feed `kpis`). Its file, from the bronze row's `_source_file` (Auto Loader `_metadata.file_path`):

```text
path:  /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/kpis/date=2026-10-08/batch-20261008T224900-000234.json
lines: 1418 in the file
line with K-CELL-VIC-00009-4G2-202610082248:
{"record_id":"K-CELL-VIC-00009-4G2-202610082248","event_ts":"2026-10-08T22:48:00Z","cell_id":"CELL-VIC-00009-4G2","granularity_s":60,"availability_pct":100.0,"active_users":25,"prb_util_pct":17.46,"rrc_setup_success_pct":98.347,"attach_success_pct":99.81,"session_drop_rate_pct":1.386,"dl_throughput_mbps":29.68,"ul_throughput_mbps":4.4,"latency_ms":147.6,"packet_loss_pct":1.258,"emitted_ts":"2026-10-08T22:49:16Z"}
```

## 2. Bronze (Auto Loader, explicit schema, lineage columns)

The same record as bronze stores it:

```sql
SELECT * EXCEPT (_rescued_data) FROM telco_netmon_febar_catalog.netmon_bronze.bronze_kpis WHERE record_id = 'K-CELL-VIC-00009-4G2-202610082248' AND _source_run = 'stream'
```

| record_id | event_ts | emitted_ts | cell_id | granularity_s | availability_pct | active_users | prb_util_pct | rrc_setup_success_pct | attach_success_pct | session_drop_rate_pct | dl_throughput_mbps | ul_throughput_mbps | latency_ms | packet_loss_pct | _corrupt_record | _source_file | _file_modification_time | _ingested_at | _source_run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| K-CELL-VIC-00009-4G2-202610082248 | 2026-10-08T22:48:00Z | 2026-10-08T22:49:16Z | CELL-VIC-00009-4G2 | 60 | 100.0 | 25 | 17.46 | 98.347 | 99.81 | 1.386 | 29.68 | 4.4 | 147.6 | 1.258 | NULL | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/kpis/date=2026-10-08/batch-20261008T224900-0002… | 2026-10-08T19:15:17.000Z | 2026-10-08T19:15:43.415Z | stream |

_1 row(s)_

## 3. Silver (typed, deduplicated, topology-joined) and its data-quality outcome

Silver parses the UTC timestamps, deduplicates on `record_id`, joins the topology and applies the drop
expectations of `netmon_pipeline.rules` (failures go to `silver_quarantine`). Re-evaluating the pipeline's own rule
predicates on the raw line above: failed drop rules = `[]`, late
(`on_time` warn rule) = `False`. The silver row, the quarantine for this record (expected empty)
and what the quarantine caught from the same micro-batch file:

```sql
SELECT record_id, event_ts, availability_pct, attach_success_pct, rrc_setup_success_pct, latency_ms, is_late, lag_s, landed_ts, evidence_ts, cell_id, site_id, backhaul_id, router_id, region_code FROM telco_netmon_febar_catalog.netmon_silver.silver_kpis WHERE record_id = 'K-CELL-VIC-00009-4G2-202610082248' AND source_run = 'stream'
```

| record_id | event_ts | availability_pct | attach_success_pct | rrc_setup_success_pct | latency_ms | is_late | lag_s | landed_ts | evidence_ts | cell_id | site_id | backhaul_id | router_id | region_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| K-CELL-VIC-00009-4G2-202610082248 | 2026-10-08T22:48:00.000Z | 100.0 | 99.81 | 98.347 | 147.6 | false | 16 | 2026-10-08T22:50:00.000Z | 2026-10-08T22:50:00.000Z | CELL-VIC-00009-4G2 | SITE-VIC-00009 | BH-VIC-0005 | AGG-VIC-01 | VIC |

_1 row(s)_

```sql
SELECT count(*) AS n_quarantined FROM telco_netmon_febar_catalog.netmon_silver.silver_quarantine WHERE record_id = 'K-CELL-VIC-00009-4G2-202610082248'
```

| n_quarantined |
|---|
| 0 |

_1 row(s)_

```sql
SELECT feed, failed_rules, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_silver.silver_quarantine
              WHERE _source_file = '/Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/kpis/date=2026-10-08/batch-20261008T224900-000234.json' GROUP BY ALL ORDER BY n_rows DESC
```

| feed | failed_rules | n_rows |
|---|---|---|
| kpis | ["active_users_not_null"] | 4 |
| kpis | ["rrc_setup_success_pct_in_range"] | 2 |
| kpis | ["event_ts_valid"] | 1 |
| kpis | ["rrc_setup_success_pct_not_null"] | 1 |
| kpis | ["availability_pct_not_null"] | 1 |
| kpis | ["parseable_record"] | 1 |
| kpis | ["active_users_in_range"] | 1 |
| kpis | ["prb_util_pct_not_null"] | 1 |
| kpis | ["no_rescued_data","availability_pct_not_null"] | 1 |

_9 row(s)_

## 4. Gold: customer-impact detections and time to detect

Stateless per-record detection (`netmon_pipeline.detection`) turns degraded KPI records and element-down alarms
into `gold_impact_detections` rows. Detections on `BH-VIC-0005`'s subtree around the incident (first 12 by availability to
the NOC; `available_ts = evidence_ts + pipeline_latency_s`, the measured wall-clock pipeline latency):

```sql
SELECT signal_source, element_id, cell_id, signal_start_ts, evidence_ts, pipeline_latency_s,
               timestampadd(MILLISECOND, CAST(pipeline_latency_s * 1000 AS BIGINT), evidence_ts) AS available_ts,
               flags, in_maintenance
        FROM telco_netmon_febar_catalog.netmon_gold.gold_impact_detections
        WHERE source_run = 'stream' AND 'BH-VIC-0005' IN (element_id, cell_id, site_id, backhaul_id, router_id)
          AND signal_start_ts BETWEEN timestamp'2026-10-08 23:56:00' - INTERVAL 2 HOURS
                                  AND timestamp'2026-10-08 23:56:00' + INTERVAL 10 MINUTES
        ORDER BY available_ts LIMIT 12
```

| signal_source | element_id | cell_id | signal_start_ts | evidence_ts | pipeline_latency_s | available_ts | flags | in_maintenance |
|---|---|---|---|---|---|---|---|---|
| kpi | CELL-VIC-00009-4G2 | CELL-VIC-00009-4G2 | 2026-10-08T22:48:00.000Z | 2026-10-08T22:50:00.000Z | 83.599000 | 2026-10-08T22:51:23.599Z | ["latency_degradation"] | false |
| kpi | CELL-VIC-00010-5G3 | CELL-VIC-00010-5G3 | 2026-10-08T22:49:00.000Z | 2026-10-08T22:51:00.000Z | 78.599000 | 2026-10-08T22:52:18.599Z | ["latency_degradation"] | false |
| kpi | CELL-VIC-00009-4G2 | CELL-VIC-00009-4G2 | 2026-10-08T22:49:00.000Z | 2026-10-08T22:51:00.000Z | 78.599000 | 2026-10-08T22:52:18.599Z | ["latency_degradation"] | false |
| kpi | CELL-VIC-00009-4G3 | CELL-VIC-00009-4G3 | 2026-10-08T22:49:00.000Z | 2026-10-08T22:51:00.000Z | 78.599000 | 2026-10-08T22:52:18.599Z | ["latency_degradation"] | false |
| kpi | CELL-VIC-00010-5G2 | CELL-VIC-00010-5G2 | 2026-10-08T22:50:00.000Z | 2026-10-08T22:52:00.000Z | 73.599000 | 2026-10-08T22:53:13.599Z | ["packet_loss"] | false |
| kpi | CELL-VIC-00009-4G2 | CELL-VIC-00009-4G2 | 2026-10-08T22:50:00.000Z | 2026-10-08T22:52:00.000Z | 73.599000 | 2026-10-08T22:53:13.599Z | ["packet_loss"] | false |
| kpi | CELL-VIC-00009-4G1 | CELL-VIC-00009-4G1 | 2026-10-08T22:50:00.000Z | 2026-10-08T22:52:00.000Z | 73.599000 | 2026-10-08T22:53:13.599Z | ["latency_degradation"] | false |
| kpi | CELL-VIC-00010-4G1 | CELL-VIC-00010-4G1 | 2026-10-08T22:50:00.000Z | 2026-10-08T22:52:00.000Z | 73.599000 | 2026-10-08T22:53:13.599Z | ["packet_loss"] | false |
| kpi | CELL-VIC-00009-4G3 | CELL-VIC-00009-4G3 | 2026-10-08T22:50:00.000Z | 2026-10-08T22:52:00.000Z | 73.599000 | 2026-10-08T22:53:13.599Z | ["latency_degradation"] | false |
| kpi | CELL-VIC-00011-4G2 | CELL-VIC-00011-4G2 | 2026-10-08T22:51:00.000Z | 2026-10-08T22:53:00.000Z | 68.599000 | 2026-10-08T22:54:08.599Z | ["latency_degradation","packet_loss"] | false |
| kpi | CELL-VIC-00010-4G1 | CELL-VIC-00010-4G1 | 2026-10-08T22:51:00.000Z | 2026-10-08T22:53:00.000Z | 68.599000 | 2026-10-08T22:54:08.599Z | ["packet_loss"] | false |
| kpi | CELL-VIC-00009-4G1 | CELL-VIC-00009-4G1 | 2026-10-08T22:51:00.000Z | 2026-10-08T22:53:00.000Z | 68.599000 | 2026-10-08T22:54:08.599Z | ["latency_degradation","packet_loss"] | false |

_12 row(s)_

The operational (ground-truth-free) timing the app and Genie show, from the `netmon_noc` view:

```sql
SELECT * FROM telco_netmon_febar_catalog.netmon_noc.incident_detection_times WHERE incident_id = 'RCA-27ed3e8af852d33a'
```

| incident_id | source_run | region_code | suspect_1_id | first_impact_signal_ts | first_detection_ts | incident_detected_ts | time_to_detect_s | time_to_localise_s | detected_within_5min | n_detection_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| RCA-27ed3e8af852d33a | stream | VIC | BH-VIC-0005 | 2026-10-08T22:48:00.000Z | 2026-10-08T22:51:23.599Z | 2026-10-08T23:56:00.000Z | 203.6 | 4080 | true | 911 |

_1 row(s)_

## 5. RCA ranker: stored live scores and a fresh endpoint call

The scoring job ranks every candidate element of the case with `rca_ranker@champion` (v5) and
publishes `open_incidents`. Below: the case's top candidates at its latest decision time as stored in
`rca_live_scores`, then the same feature rows (the model's 55 feature columns) sent to the
serving endpoint `banksia-rca-ranker`.

`rca_live_scores`, case `stream|VIC|20261009T0056|BH-VIC-0005`, model version 5 (19 candidates; open_incidents.n_candidates = 19):

| decision_ts | element_id | element_type | impacted_fraction | silent_fraction | n_alarms | n_service_down_alarms | score |
|---|---|---|---|---|---|---|---|
| 2026-10-09T00:56:00.000Z | BH-VIC-0005 | BACKHAUL_LINK | 1.0 | 0.0 | 0.0 | 0.0 | 1.0 |
| 2026-10-09T00:56:00.000Z | AGG-VIC-01 | AGG_ROUTER | 0.1884058 | 0.0 | 0.0 | 0.0 | 0.0 |
| 2026-10-09T00:56:00.000Z | AMF-VIC-01 | AMF_MME | 0.035984848 | 0.0 | 0.0 | 0.0 | 0.0 |
| 2026-10-09T00:56:00.000Z | CELL-VIC-00009-4G1 | CELL | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 2026-10-09T00:56:00.000Z | CELL-VIC-00009-4G2 | CELL | 1.0 | 0.0 | 0.0 | 0.0 | 0.0 |

_5 row(s)_

```json
{
  "endpoint": "banksia-rca-ranker",
  "request": {
    "dataframe_records": "19 records x 55 features (first record below)",
    "first_record": {
      "level": 3.0,
      "log_n_desc_cells": 2.5649493,
      "n_children": 3.0,
      "n_impacted_cells": 12.0,
      "impacted_fraction": 1.0,
      "degraded_fraction": 1.0,
      "silent_fraction": 0.0,
      "coverage": 1.0,
      "child_max_coverage": 0.5,
      "impacted_children_fraction": 1.0,
      "parent_impacted_fraction": 0.1884058,
      "parent_coverage": 1.0,
      "lat_now": 14.194491,
      "lat_slope5": 0.08915243,
      "lat_slope15": 0.013962303,
      "lat_vs_parent": 11.89964,
      "loss_now": 99.348305,
      "loss_slope5": -0.08345108,
      "loss_slope15": 0.013658115,
      "loss_vs_parent": 82.06066,
      "thr_now": -5.3169837,
      "thr_slope5": 0.0062319757,
      "thr_slope15": 0.00377646,
      "thr_vs_parent": -4.211172,
      "rrc_now": -16.363798,
      "rrc_slope5": 0.028040696,
      "rrc_slope15": -0.00074607984,
      "rrc_vs_parent": -6.072089,
      "drop_now": 24.76409,
      "drop_slope5": 0.03580761,
      "drop_slope15": -0.017522935,
      "drop_vs_parent": 20.413788,
      "attach_now": 99.80481,
      "attach_vs_parent": 1.4868088,
      "avail_now": 100.0,
      "prb_now": 24.251364,
      "prb_slope15": -0.06667713,
      "impacted_fraction_slope15": 0.00059523946,
      "minutes_since_first_anomaly": 59.0,
      "n_alarms": 0.0,
      "n_critical_alarms": 0.0,
      "n_major_alarms": 0.0,
      "n_service_down_alarms": 0.0,
      "n_alarms_link": 0.0,
      "n_alarms_power": 0.0,
      "n_alarms_unreach": 0.0,
      "n_alarms_core": 0.0,
      "alarm_age_min": 0.0,
      "n_subtree_alarms": 0.0,
      "n_subtree_service_down_alarms": 0.0,
      "alarmed_children_fraction": 0.0,
      "parent_n_alarms": 0.0,
      "in_maintenance": 0.0,
      "log_case_impacted_cells": 2.5649493,
      "n_case_candidates": 19.0
    }
  },
  "latency_ms": 528,
  "response_top3": [
    {
      "element_id": "BH-VIC-0005",
      "element_type": "BACKHAUL_LINK",
      "endpoint_p_root": 1.0,
      "stored_score": 1.0
    },
    {
      "element_id": "AGG-VIC-01",
      "element_type": "AGG_ROUTER",
      "endpoint_p_root": 0.0,
      "stored_score": 0.0
    },
    {
      "element_id": "AMF-VIC-01",
      "element_type": "AMF_MME",
      "endpoint_p_root": 0.0,
      "stored_score": 0.0
    }
  ]
}
```

Endpoint top-1 `BH-VIC-0005` vs Lakebase suspect 1 `BH-VIC-0005`: match.

## 6. Lakebase (Postgres, read with psycopg + OAuth)

The synced tables (Delta -> Postgres, TRIGGERED by the scoring and assistant jobs) the app reads on its hot path, and
the app's own SMS review table. Read here with psycopg as the capturing user:

`netmon_rca.lb_open_incidents`:

| incident_id | source_run | region_code | case_id | detected_ts | last_scored_ts | status | suspect_1_id | suspect_1_type | suspect_1_score | suspect_2_id | suspect_2_type | suspect_2_score | suspect_3_id | suspect_3_type | suspect_3_score | n_impacted_cells | n_candidates | model_version | refreshed_at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RCA-27ed3e8af852d33a | stream | VIC | stream\|VIC\|20261009T0056\|BH-VIC-0005 | 2026-10-08 23:56:00+00:00 | 2026-10-09 00:56:00+00:00 | open | BH-VIC-0005 | BACKHAUL_LINK | 1.0 | AGG-VIC-01 | AGG_ROUTER | 0.0 | CELL-VIC-00010-5G2 | CELL | 0.0 | 12 | 19 | 5 | 2026-11-06 07:41:11.906121+00:00 |

_1 row(s)_

`netmon_rca.lb_element_status` (the suspects and the root's children):

| element_id | element_type | parent_id | state | rca_score | n_impacted_cells | n_desc_cells | silent_fraction | n_alarms | n_service_down_alarms | open_incident_id | suspect_rank |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BH-VIC-0005 | BACKHAUL_LINK | AGG-VIC-01 | degraded | 1.0 | 12.0 | 11.999999046325684 | 0.0 | 0.0 | 0.0 | RCA-27ed3e8af852d33a | 1.0 |
| AGG-VIC-01 | AGG_ROUTER | UPF-VIC-01 | impacted | 0.0 | 13.0 | 68.99999237060547 | 0.0 | 0.0 | 0.0 | RCA-9737805189832cde | 2.0 |
| CELL-VIC-00010-5G2 | CELL | SITE-VIC-00010 | degraded | 0.0 | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 | RCA-27ed3e8af852d33a | 3.0 |
| SITE-VIC-00009 | SITE | BH-VIC-0005 | degraded | 0.0 | 3.0 | 3.0 | 0.0 | 0.0 | 0.0 | NULL | NULL |
| SITE-VIC-00010 | SITE | BH-VIC-0005 | degraded | 0.0 | 6.0 | 6.000000476837158 | 0.0 | 0.0 | 0.0 | NULL | NULL |
| SITE-VIC-00011 | SITE | BH-VIC-0005 | degraded | 0.0 | 3.0 | 3.0 | 0.0 | 0.0 | 0.0 | NULL | NULL |

_6 row(s)_

`netmon_genai.lb_incident_ai_latest`:

| incident_id | summary_id | generated_at | likely_root_cause | fault_hypothesis | confidence | est_affected_subscribers | impacted_cells | impacted_sites | sms_draft_status | generated_by |
|---|---|---|---|---|---|---|---|---|---|---|
| RCA-27ed3e8af852d33a | d0343475-e664-4368-8de2-dbcf667a58e2 | 2026-11-06 07:42:33.256247+00:00 | BH-VIC-0005 | BACKHAUL_DEGRADATION | high | 550 | 12 | 3 | draft | llm |

_1 row(s)_

`netmon_app.sms_draft_reviews` (written by the app; empty until reviewed):

_(no result set)_

## 7. Gen AI NOC summary and customer SMS draft (Unity Catalog)

The assistant (`databricks-gpt-5-4-mini` through AI Gateway) wrote, for this incident, the summary and the SMS draft
(status `draft`, never sent). Latest versions:

```sql
SELECT summary_id, generated_at, status, likely_root_cause, fault_hypothesis, confidence, summary,
                     next_steps_json, latency_ms, prompt_tokens, completion_tokens, noc_prompt_version
              FROM telco_netmon_febar_catalog.netmon_genai.incident_ai_summaries WHERE incident_id = 'RCA-27ed3e8af852d33a' ORDER BY generated_at DESC LIMIT 1
```

| summary_id | generated_at | status | likely_root_cause | fault_hypothesis | confidence | summary | next_steps_json | latency_ms | prompt_tokens | completion_tokens | noc_prompt_version |
|---|---|---|---|---|---|---|---|---|---|---|---|
| d0343475-e664-4368-8de2-dbcf667a58e2 | 2026-11-06T07:42:33.256Z | draft | BH-VIC-0005 | BACKHAUL_DEGRADATION | high | The strongest fit is a degradation on backhaul link BH-VIC-0005 affecting all 12 impacted cells behind it, with very high latency and loss plus reduced downlink throughput and RRC success. The evidence points to a transport issue rather than a cell or site outage: the link shows no active alarms, the impact spans all impacted children under the link, and the KPI pattern is severe but not silent. If this is correct, the next minutes should keep showing degraded KPIs across those cells until the backhaul recovers or is rerouted. | ["Check BH-VIC-0005 transport interface errors and link health, including any fibre-level error indicators or congestion counters.", "Assess whether BH-VIC-0005 has a protection path or reroute option and move traffic if available.", "Correlate the degraded KPIs on the impacted cells with the backhaul link and confirm whether recovery begins in the next measurement windows.", "Open a transport ticket for BH-VIC-0005 and escalate to the transport team if the degradation persists.", "Monitor SITE-VIC-00010, SITE-VIC-00009, and SITE-VIC-00011 to confirm their cells continue to absorb traffic without becoming silent.", "If customer impact grows beyond the current estimate, trigger major-inciden… | 7414.3 | 4762 | 948 | noc_summary_v3@cfda4dd5 |

_1 row(s)_

```sql
SELECT draft_id, generated_at, status, requires_human_approval, approved_by, sent_at, chars, text
              FROM telco_netmon_febar_catalog.netmon_genai.customer_notice_drafts WHERE incident_id = 'RCA-27ed3e8af852d33a' ORDER BY generated_at DESC LIMIT 1
```

| draft_id | generated_at | status | requires_human_approval | approved_by | sent_at | chars | text |
|---|---|---|---|---|---|---|---|
| c02c79dc-0de5-4093-ad29-8d72bfca0dfa | 2026-11-06T07:42:33.256Z | draft | true | NULL | NULL | 140 | Banksia Mobile: Slow mobile data and calls and data may drop or fail in Melbourne & Victoria, incl Melbourne. Sorry. We'll keep you updated. |

_1 row(s)_

## 8. The deployed app: incident panel and topology pinpoint

`https://banksia-noc-topology-7474648429104135.aws.databricksapps.com` called with the capturing user's token through the Databricks Apps proxy (the proxy forwards the user's
identity and on-behalf-of token to the app). Incident panel (`GET /api/incidents/RCA-27ed3e8af852d33a`):

```json
{
  "http_status": 200,
  "latency_ms": 3559,
  "body": {
    "incident_id": "RCA-27ed3e8af852d33a",
    "region_code": "VIC",
    "status": "open",
    "detected_ts": "2026-10-08T23:56:00+00:00",
    "last_scored_ts": "2026-10-09T00:56:00+00:00",
    "model_version": "5",
    "detection": {
      "available": true,
      "incident_id": "RCA-27ed3e8af852d33a",
      "suspect_1_id": "BH-VIC-0005",
      "first_impact_signal_ts": "2026-10-08T22:48:00.000Z",
      "first_detection_ts": "2026-10-08T22:51:23.599Z",
      "incident_detected_ts": "2026-10-08T23:56:00.000Z",
      "time_to_detect_s": 203.6,
      "time_to_localise_s": 4080,
      "detected_within_5min": true,
      "n_detection_rows": 911
    },
    "impact": {
      "impacted_cells": 12,
      "impacted_sites": 3,
      "est_affected_subscribers": 550,
      "description": "About 550 customers across Melbourne & Victoria are seeing degraded service on 12 cells at 3 sites, mainly in rural and suburban areas."
    },
    "pinpoint": {
      "element_id": "BH-VIC-0005",
      "element_type": "BACKHAUL_LINK",
      "rank": 1,
      "score": 1.0,
      "name": "satellite backhaul BH-VIC-0005",
      "state": "degraded",
      "lat": -37.26157,
      "lon": 145.47927,
      "n_impacted_cells": 12.0,
      "n_desc_cells": 11.999999046325684,
      "n_alarms": 0.0
    },
    "path_from_core": [
      {
        "element_id": "AMF-VIC-01",
        "element_type": "AMF_MME",
        "name": "Melbourne & Victoria AMF/MME 1",
        "state": "impacted"
      },
      {
        "element_id": "UPF-VIC-01",
        "element_type": "UPF_SGW",
        "name": "Melbourne & Victoria UPF/SGW 1",
        "state": "impacted"
      },
      {
        "element_id": "AGG-VIC-01",
        "element_type": "AGG_ROUTER",
        "name": "Melbourne & Victoria agg router 1",
        "state": "impacted"
      },
      {
        "element_id": "BH-VIC-0005",
        "element_type": "BACKHAUL_LINK",
        "name": "satellite backhaul BH-VIC-0005",
        "state": "degraded"
      }
    ],
    "suspects": [
      {
        "element_id": "BH-VIC-0005",
        "element_type": "BACKHAUL_LINK",
        "rank": 1,
        "score": 1.0,
        "name": "satellite backhaul BH-VIC-0005",
        "state": "degraded",
        "lat": -37.26157,
        "lon": 145.47927,
        "n_impacted_cells": 12.0,
        "n_desc_cells": 11.999999046325684,
        "n_alarms": 0.0
      },
      {
        "element_id": "AGG-VIC-01",
        "element_type": "AGG_ROUTER",
        "rank": 2,
        "score": 0.0,
        "name": "Melbourne & Victoria agg router 1",
        "state": "impacted",
        "lat": -37.67641,
        "lon": 145.12499,
        "n_impacted_cells": 13.0,
        "n_desc_cells": 68.99999237060547,
        "n_alarms": 0.0
      },
      {
        "element_id": "CELL-VIC-00010-5G2",
        "element_type": "CELL",
        "rank": 3,
        "score": 0.0,
        "name": "SITE-VIC-00010 5G sector 2",
        "state": "degraded",
        "lat": -37.43926,
        "lon": 145.3163,
        "n_impacted_cells": 1.0,
        "n_desc_cells": 1.0,
        "n_alarms": 0.0
      }
    ],
    "ai": {
      "summary_id": "d0343475-e664-4368-8de2-dbcf667a58e2",
      "generated_at": "2026-11-06T07:42:33.256247+00:00",
      "likely_root_cause": "BH-VIC-0005",
      "fault_hypothesis": "BACKHAUL_DEGRADATION",
      "confidence": "high",
      "summary": "The strongest fit is a degradation on backhaul link BH-VIC-0005 affecting all 12 impacted cells behind it, with very high latency and loss plus reduced downlink throughput and RRC success. The evidence points to a transport issue rather than a cell or site outage: the link shows no active alarms, the impact spans all impacted children under the link, and the KPI pattern is severe but not silent. If this is correct, the next minutes should keep showing degraded KPIs across those cells until the backhaul recovers or is rerouted.",
      "next_steps": [
        "Check BH-VIC-0005 transport interface errors and link health, including any fibre-level error indicators or congestion counters.",
        "Assess whether BH-VIC-0005 has a protection path or reroute option and move traffic if available.",
        "Correlate the degraded KPIs on the impacted cells with the backhaul link and confirm whether recovery begins in the next measurement windows.",
        "Open a transport ticket for BH-VIC-0005 and escalate to the transport team if the degradation persists.",
        "Monitor SITE-VIC-00010, SITE-VIC-00009, and SITE-VIC-00011 to confirm their cells continue to absorb traffic without becoming silent.",
        "If customer impact grows beyond the current estimate, trigger major-incident communication for the VIC region."
      ],
      "generated_by": "llm",
      "prompt_version": "noc_summary_v3@cfda4dd5",
      "agrees_with_ranker": true
    },
    "sms": {
      "summary_id": "d0343475-e664-4368-8de2-dbcf667a58e2",
      "text": "Banksia Mobile: Slow mobile data and calls and data may drop or fail in Melbourne & Victoria, incl Melbourne. Sorry. We'll keep you updated.",
      "draft_status": "draft",
      "draft_sha256": "689ba2957b1a94293e2cfa62f4455d466b4f0d14dfaddcf41662e20c7b936916",
      "decision": "pending",
      "reviewed_by": null,
      "reviewed_at": null,
      "sent": false,
      "note": "Draft only: this system never sends messages."
    }
  }
}
```

Topology for the incident (`GET /api/regions/VIC/topology?incident_id=RCA-27ed3e8af852d33a`):

```json
{
  "http_status": 200,
  "latency_ms": 1613,
  "body (trimmed to the highlighted elements)": {
    "region": "VIC",
    "incident_id": "RCA-27ed3e8af852d33a",
    "view": "incident",
    "pinpoint": "BH-VIC-0005",
    "path": [
      "AMF-VIC-01",
      "UPF-VIC-01",
      "AGG-VIC-01",
      "BH-VIC-0005"
    ],
    "n_nodes_drawn": 21,
    "n_edges": 20,
    "highlighted": [
      {
        "id": "AMF-VIC-01",
        "element_type": "AMF_MME",
        "state": "impacted",
        "highlight": "path",
        "suspect_rank": null,
        "suspect_score": null,
        "lat": -37.8136,
        "lon": 144.9631
      },
      {
        "id": "UPF-VIC-01",
        "element_type": "UPF_SGW",
        "state": "impacted",
        "highlight": "path",
        "suspect_rank": null,
        "suspect_score": null,
        "lat": -37.81729,
        "lon": 144.96647
      },
      {
        "id": "AGG-VIC-01",
        "element_type": "AGG_ROUTER",
        "state": "impacted",
        "highlight": "suspect",
        "suspect_rank": 2,
        "suspect_score": 0.0,
        "lat": -37.67641,
        "lon": 145.12499
      },
      {
        "id": "BH-VIC-0005",
        "element_type": "BACKHAUL_LINK",
        "state": "degraded",
        "highlight": "pinpoint",
        "suspect_rank": 1,
        "suspect_score": 1.0,
        "lat": -37.26157,
        "lon": 145.47927
      },
      {
        "id": "CELL-VIC-00010-5G2",
        "element_type": "CELL",
        "state": "degraded",
        "highlight": "suspect",
        "suspect_rank": 3,
        "suspect_score": 0.0,
        "lat": -37.43926,
        "lon": 145.3163
      }
    ],
    "map_suspects": [
      {
        "id": "AGG-VIC-01",
        "element_type": "AGG_ROUTER",
        "name": "Melbourne & Victoria agg router 1",
        "lat": -37.67641,
        "lon": 145.12499,
        "state": "impacted",
        "suspect_rank": 2,
        "parent_id": "UPF-VIC-01"
      },
      {
        "id": "BH-VIC-0005",
        "element_type": "BACKHAUL_LINK",
        "name": "satellite backhaul BH-VIC-0005",
        "lat": -37.26157,
        "lon": 145.47927,
        "state": "degraded",
        "suspect_rank": 1,
        "parent_id": "AGG-VIC-01"
      },
      {
        "id": "SITE-VIC-00010",
        "element_type": "SITE",
        "name": "Melbourne & Victoria site 10",
        "lat": -37.43926,
        "lon": 145.3163,
        "state": "degraded",
        "suspect_rank": 3,
        "parent_id": "BH-VIC-0005"
      }
    ]
  }
}
```

## 9. Genie, asked through the app

`POST /api/genie/ask` on the app, which calls the Genie Conversation API on the NOC space as the signed-in user.
Question: *For the open incident whose top suspect is BH-VIC-0005: what is the failing element, how long did it take to detect, and how many subscribers are affected?*

```json
{
  "http_status": 200,
  "latency_ms": 25507,
  "answer_text": [
    "For open incident **RCA-27ed3e8af852d33a**, the failing element is **BH-VIC-0005**, named **satellite backhaul BH-VIC-0005**, with element type **BACKHAUL_LINK**. The detection time was **203.6 seconds** (**3.4 minutes**), **detected within 5 minutes = true**, and the estimated affected subscribers count is **550**.",
    "Would you like to see similar details for all incidents in the same region as BH-VIC-0005?"
  ],
  "columns": [
    "incident_id",
    "failing_element_id",
    "failing_element_type",
    "failing_element_name",
    "time_to_detect_s",
    "time_to_detect_min",
    "detected_within_5min",
    "est_affected_subscribers"
  ],
  "rows": [
    [
      "RCA-27ed3e8af852d33a",
      "BH-VIC-0005",
      "BACKHAUL_LINK",
      "satellite backhaul BH-VIC-0005",
      "203.6",
      "3.4",
      "true",
      "550"
    ]
  ],
  "conversation_id": "01f1d9e8bae41619917599b984081dd6"
}
```

SQL Genie generated and ran:

```sql
SELECT `o`.`incident_id`, `o`.`suspect_1_id` AS `failing_element_id`, `o`.`suspect_1_type` AS `failing_element_type`, `t`.`name` AS `failing_element_name`, `d`.`time_to_detect_s`, ROUND(try_divide(`d`.`time_to_detect_s`,60), 1) AS `time_to_detect_min`, `d`.`detected_within_5min`, `a`.`est_affected_subscribers`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`open_incidents` AS `o`
LEFT JOIN `telco_netmon_febar_catalog`.`netmon_noc`.`incident_detection_times` AS `d`
  ON `o`.`incident_id` = `d`.`incident_id`
LEFT JOIN `telco_netmon_febar_catalog`.`netmon_noc`.`incident_ai_summary` AS `a`
  ON `o`.`incident_id` = `a`.`incident_id`
LEFT JOIN `telco_netmon_febar_catalog`.`netmon_noc`.`silver_topology_nodes` AS `t`
  ON `o`.`suspect_1_id` = `t`.`element_id`
WHERE `o`.`suspect_1_id` = 'BH-VIC-0005'
```

## 10. Unity Catalog lineage linking the tables

Captured automatically by Unity Catalog (`system.access.table_lineage`, filtered to this workspace). Edges between the
tables this trace touched (the Volume -> bronze hop has a NULL source on this workspace and is shown by `_source_file`
above; Lakebase synced tables are written by their sync pipelines):

```sql
SELECT source_table_full_name AS source, target_table_full_name AS target, entity_type,
               max(event_time) AS last_seen, count(*) AS n_events
        FROM system.access.table_lineage
        WHERE workspace_id = '7474648429104135' AND event_date >= current_date() - INTERVAL 60 DAYS
          AND target_table_full_name IN ('telco_netmon_febar_catalog.netmon_bronze.bronze_kpis', 'telco_netmon_febar_catalog.netmon_silver.silver_kpis', 'telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes', 'telco_netmon_febar_catalog.netmon_gold.gold_impact_detections', 'telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m', 'telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m', 'telco_netmon_febar_catalog.netmon_rca.rca_live_scores', 'telco_netmon_febar_catalog.netmon_rca.open_incidents', 'telco_netmon_febar_catalog.netmon_rca.element_status', 'telco_netmon_febar_catalog.netmon_rca.lb_open_incidents', 'telco_netmon_febar_catalog.netmon_rca.lb_element_status', 'telco_netmon_febar_catalog.netmon_genai.incident_ai_summaries', 'telco_netmon_febar_catalog.netmon_genai.incident_ai_latest', 'telco_netmon_febar_catalog.netmon_genai.customer_notice_drafts', 'telco_netmon_febar_catalog.netmon_genai.lb_incident_ai_latest', 'telco_netmon_febar_catalog.netmon_noc.open_incidents', 'telco_netmon_febar_catalog.netmon_noc.incident_detection_times', 'telco_netmon_febar_catalog.netmon_noc.incident_ai_summary', 'telco_netmon_febar_catalog.netmon_noc.element_status') AND source_table_full_name IN ('telco_netmon_febar_catalog.netmon_bronze.bronze_kpis', 'telco_netmon_febar_catalog.netmon_silver.silver_kpis', 'telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes', 'telco_netmon_febar_catalog.netmon_gold.gold_impact_detections', 'telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m', 'telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m', 'telco_netmon_febar_catalog.netmon_rca.rca_live_scores', 'telco_netmon_febar_catalog.netmon_rca.open_incidents', 'telco_netmon_febar_catalog.netmon_rca.element_status', 'telco_netmon_febar_catalog.netmon_rca.lb_open_incidents', 'telco_netmon_febar_catalog.netmon_rca.lb_element_status', 'telco_netmon_febar_catalog.netmon_genai.incident_ai_summaries', 'telco_netmon_febar_catalog.netmon_genai.incident_ai_latest', 'telco_netmon_febar_catalog.netmon_genai.customer_notice_drafts', 'telco_netmon_febar_catalog.netmon_genai.lb_incident_ai_latest', 'telco_netmon_febar_catalog.netmon_noc.open_incidents', 'telco_netmon_febar_catalog.netmon_noc.incident_detection_times', 'telco_netmon_febar_catalog.netmon_noc.incident_ai_summary', 'telco_netmon_febar_catalog.netmon_noc.element_status')
        GROUP BY ALL ORDER BY target, source
```

| source | target | entity_type | last_seen | n_events |
|---|---|---|---|---|
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | PIPELINE | 2026-10-08T18:58:41.889Z | 6 |
| telco_netmon_febar_catalog.netmon_genai.incident_ai_latest | telco_netmon_febar_catalog.netmon_genai.lb_incident_ai_latest | PIPELINE | 2026-11-06T00:53:27.602Z | 1 |
| telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | PIPELINE | 2026-10-08T19:12:49.412Z | 3 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m | PIPELINE | 2026-11-06T09:45:38.846Z | 512 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | telco_netmon_febar_catalog.netmon_gold.gold_element_impact_5m | PIPELINE | 2026-11-06T09:45:49.141Z | 24 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | PIPELINE | 2026-10-08T17:33:58.190Z | 4 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | PIPELINE | 2026-11-06T09:45:40.154Z | 1028 |
| telco_netmon_febar_catalog.netmon_rca.element_status | telco_netmon_febar_catalog.netmon_noc.element_status | NULL | 2026-11-06T13:25:51.732Z | 40 |
| telco_netmon_febar_catalog.netmon_rca.element_status | telco_netmon_febar_catalog.netmon_noc.element_status | JOB | 2026-11-06T13:18:43.706Z | 3 |
| telco_netmon_febar_catalog.netmon_genai.incident_ai_latest | telco_netmon_febar_catalog.netmon_noc.incident_ai_summary | NULL | 2026-11-06T13:36:20.017Z | 84 |
| telco_netmon_febar_catalog.netmon_genai.incident_ai_latest | telco_netmon_febar_catalog.netmon_noc.incident_ai_summary | JOB | 2026-11-06T13:18:44.903Z | 3 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | telco_netmon_febar_catalog.netmon_noc.incident_detection_times | NULL | 2026-11-06T13:36:38.893Z | 76 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | telco_netmon_febar_catalog.netmon_noc.incident_detection_times | JOB | 2026-11-06T13:18:47.755Z | 3 |
| telco_netmon_febar_catalog.netmon_rca.open_incidents | telco_netmon_febar_catalog.netmon_noc.incident_detection_times | NULL | 2026-11-06T13:36:38.893Z | 76 |
| telco_netmon_febar_catalog.netmon_rca.open_incidents | telco_netmon_febar_catalog.netmon_noc.incident_detection_times | JOB | 2026-11-06T13:18:47.755Z | 3 |
| telco_netmon_febar_catalog.netmon_rca.open_incidents | telco_netmon_febar_catalog.netmon_noc.open_incidents | NULL | 2026-11-06T13:36:32.730Z | 150 |
| telco_netmon_febar_catalog.netmon_rca.open_incidents | telco_netmon_febar_catalog.netmon_noc.open_incidents | JOB | 2026-11-06T13:18:42.363Z | 3 |
| telco_netmon_febar_catalog.netmon_rca.element_status | telco_netmon_febar_catalog.netmon_rca.lb_element_status | PIPELINE | 2026-11-05T15:05:21.413Z | 1 |
| telco_netmon_febar_catalog.netmon_rca.open_incidents | telco_netmon_febar_catalog.netmon_rca.lb_open_incidents | PIPELINE | 2026-11-05T15:05:20.243Z | 1 |
| telco_netmon_febar_catalog.netmon_bronze.bronze_kpis | telco_netmon_febar_catalog.netmon_silver.silver_kpis | PIPELINE | 2026-11-06T09:45:22.241Z | 619 |
| telco_netmon_febar_catalog.netmon_silver.silver_kpis | telco_netmon_febar_catalog.netmon_silver.silver_kpis | PIPELINE | 2026-10-08T19:08:29.631Z | 3 |
| telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes | telco_netmon_febar_catalog.netmon_silver.silver_kpis | PIPELINE | 2026-11-06T09:45:22.241Z | 619 |

_22 row(s)_

**Across the job boundary.** The RCA scoring job and the Gen AI assistant read Delta into pandas and write back through
a Parquet scratch file, so Unity Catalog records their reads with a NULL target and their writes with a NULL (or Volume
path) source: there is no direct table-to-table edge into `rca_live_scores` / `open_incidents` / `incident_ai_latest`.
The link is still in `system.access.table_lineage`: the read and write events of one job run share `entity_run_id`.
Latest run of each job that writes the incident tables, with everything that run read and wrote:

```sql
WITH ev AS (
          SELECT entity_id, entity_run_id, event_time, source_table_full_name AS s, target_table_full_name AS t
          FROM system.access.table_lineage
          WHERE workspace_id = '7474648429104135' AND event_date >= current_date() - INTERVAL 60 DAYS AND entity_type = 'JOB'),
        runs AS (
          SELECT entity_id AS job_id, entity_run_id AS job_run_id, max(event_time) AS last_seen,
                 array_sort(collect_set(s)) AS tables_read, array_sort(collect_set(t)) AS tables_written
          FROM ev GROUP BY 1, 2)
        SELECT * FROM runs
        WHERE array_contains(tables_written, 'telco_netmon_febar_catalog.netmon_rca.open_incidents')
           OR array_contains(tables_written, 'telco_netmon_febar_catalog.netmon_genai.incident_ai_latest')
        QUALIFY row_number() OVER (PARTITION BY job_id ORDER BY last_seen DESC) = 1
```

| job_id | job_run_id | last_seen | tables_read | tables_written |
|---|---|---|---|---|
| 282645727011052 | 584238101020942 | 2026-11-06T07:45:54.077Z | ["telco_netmon_febar_catalog.netmon_genai.incident_ai_latest","telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m","telco_netmon_febar_catalog.netmon_gold.gold_cell_sessions_5m","telco_netmon_febar_catalog.netmon_rca.open_incidents","telco_netmon_febar_catalog.netmon_rca.rca_live_scores","telco_netmon_febar_catalog.netmon_silver.silver_alarms","telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes"] | ["telco_netmon_febar_catalog.netmon_genai.customer_notice_drafts","telco_netmon_febar_catalog.netmon_genai.incident_ai_latest","telco_netmon_febar_catalog.netmon_genai.incident_ai_summaries","telco_netmon_febar_catalog.netmon_genai.noc_assistant_request_log"] |
| 508373316044745 | 731820231606620 | 2026-11-06T07:41:40.933Z | ["telco_netmon_febar_catalog.netmon_gold.gold_cell_health_1m","telco_netmon_febar_catalog.netmon_silver.silver_alarms","telco_netmon_febar_catalog.netmon_silver.silver_topology_nodes"] | ["telco_netmon_febar_catalog.netmon_rca.element_status","telco_netmon_febar_catalog.netmon_rca.open_incidents","telco_netmon_febar_catalog.netmon_rca.rca_live_scores"] |

_2 row(s)_

Job IDs: `282645727011052` = `banksia-genai-assistant`, `508373316044745` = `banksia-rca-score-live`.

## 11. FINAL VERIFICATION against the generator's ground truth (not part of the operational path)

Everything above is operational: the app, the Genie space, the ranker's features and the assistant never read
`netmon_eval`, and no number above comes from it (enforced by `tests/test_no_ground_truth_surface.py`). This section
alone reads ground truth, after the fact, to confirm the trace followed a real fault:

```sql
SELECT incident_id, event_class, fault_type, root_element_ids, impact_start_ts, impact_end_ts,
                          is_censored, n_affected_cells, estimated_impacted_subscribers, description
                   FROM telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents
                   WHERE source_run = 'stream' AND array_contains(root_element_ids, 'BH-VIC-0005')
                     AND is_customer_impacting ORDER BY impact_start_ts DESC LIMIT 1
```

| incident_id | event_class | fault_type | root_element_ids | impact_start_ts | impact_end_ts | is_censored | n_affected_cells | estimated_impacted_subscribers | description |
|---|---|---|---|---|---|---|---|---|---|
| INC-2026100822-00008 | fault | BACKHAUL_DEGRADATION | ["BH-VIC-0005"] | 2026-10-08T22:42:53.000Z | 2026-10-09T00:55:00.000Z | true | 12 | 359 | Rising BER / microwave fading: latency, loss and drops on chained sites |

_1 row(s)_

Ground-truth time to detect = first detection available (22:51:23) - true impact start (22:42:53) = **511 s** (5-minute SLA: missed), against the operational time to detect of 204 s shown by the app and Genie, which can only start at the first anomaly visible in the telemetry (a lower bound when a fault ramps up slowly before any KPI rule fires). The incident is `is_censored` when the live run ended before the fault cleared; censored incidents are excluded from the scored KPIs (`eval_ttd_summary`, an offline evaluation table), which is why this open incident is not in them.
