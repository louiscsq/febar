# End-to-end trace: SITE-NSW-00105 site power outage (Sydney)

Captured 2026-11-06 11:24 UTC from workspace profile `febar` by `scripts/trace_end_to_end.py --incident RCA-c7276c3238a27971`. Every block below is the real output of that hop; nothing is hand-edited.

**The fault.** Incident `RCA-c7276c3238a27971` in `NSW`, live feed (`source_run = 'stream'`). The root-cause ranker's
suspect 1 is `SITE-NSW-00105` (SITE). The trace starts from the first customer-impact detection on that
element's subtree and walks back to the raw file, then forward to the operator's screen and Genie.

## 1. Raw file in the Unity Catalog Volume

The generator's live stream writes one JSON-lines micro-batch per feed per simulated minute into
`/Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/`. The first detection on `SITE-NSW-00105`'s subtree came from record `K-CELL-NSW-00105-4G1-202610090008`
(feed `kpis`). Its file, from the bronze row's `_source_file` (Auto Loader `_metadata.file_path`):

```text
path:  /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/kpis/date=2026-10-09/batch-20261009T000900-000314.json
lines: 1413 in the file
line with K-CELL-NSW-00105-4G1-202610090008:
{"record_id":"K-CELL-NSW-00105-4G1-202610090008","event_ts":"2026-10-09T00:08:00Z","cell_id":"CELL-NSW-00105-4G1","granularity_s":60,"availability_pct":63.33,"active_users":77,"prb_util_pct":27.72,"rrc_setup_success_pct":63.002,"attach_success_pct":63.218,"session_drop_rate_pct":0.44,"dl_throughput_mbps":55.56,"ul_throughput_mbps":6.34,"latency_ms":32.5,"packet_loss_pct":0.064,"emitted_ts":"2026-10-09T00:09:23Z"}
```

## 2. Bronze (Auto Loader, explicit schema, lineage columns)

The same record as bronze stores it:

```sql
SELECT * EXCEPT (_rescued_data) FROM telco_netmon_febar_catalog.netmon_bronze.bronze_kpis WHERE record_id = 'K-CELL-NSW-00105-4G1-202610090008' AND _source_run = 'stream'
```

| record_id | event_ts | emitted_ts | cell_id | granularity_s | availability_pct | active_users | prb_util_pct | rrc_setup_success_pct | attach_success_pct | session_drop_rate_pct | dl_throughput_mbps | ul_throughput_mbps | latency_ms | packet_loss_pct | _corrupt_record | _source_file | _file_modification_time | _ingested_at | _source_run |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| K-CELL-NSW-00105-4G1-202610090008 | 2026-10-09T00:08:00Z | 2026-10-09T00:09:23Z | CELL-NSW-00105-4G1 | 60 | 63.33 | 77 | 27.72 | 63.002 | 63.218 | 0.44 | 55.56 | 6.34 | 32.5 | 0.064 | NULL | /Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/kpis/date=2026-10-09/batch-20261009T000900-0003… | 2026-10-08T19:21:57.000Z | 2026-10-08T19:22:03.445Z | stream |

_1 row(s)_

## 3. Silver (typed, deduplicated, topology-joined) and its data-quality outcome

Silver parses the UTC timestamps, deduplicates on `record_id`, joins the topology and applies the drop
expectations of `netmon_pipeline.rules` (failures go to `silver_quarantine`). Re-evaluating the pipeline's own rule
predicates on the raw line above: failed drop rules = `[]`, late
(`on_time` warn rule) = `False`. The silver row, the quarantine for this record (expected empty)
and what the quarantine caught from the same micro-batch file:

```sql
SELECT record_id, event_ts, availability_pct, attach_success_pct, rrc_setup_success_pct, latency_ms, is_late, lag_s, landed_ts, evidence_ts, cell_id, site_id, backhaul_id, router_id, region_code FROM telco_netmon_febar_catalog.netmon_silver.silver_kpis WHERE record_id = 'K-CELL-NSW-00105-4G1-202610090008' AND source_run = 'stream'
```

| record_id | event_ts | availability_pct | attach_success_pct | rrc_setup_success_pct | latency_ms | is_late | lag_s | landed_ts | evidence_ts | cell_id | site_id | backhaul_id | router_id | region_code |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| K-CELL-NSW-00105-4G1-202610090008 | 2026-10-09T00:08:00.000Z | 63.33 | 63.218 | 63.002 | 32.5 | false | 23 | 2026-10-09T00:10:00.000Z | 2026-10-09T00:10:00.000Z | CELL-NSW-00105-4G1 | SITE-NSW-00105 | BH-NSW-0045 | AGG-NSW-04 | NSW |

_1 row(s)_

```sql
SELECT count(*) AS n_quarantined FROM telco_netmon_febar_catalog.netmon_silver.silver_quarantine WHERE record_id = 'K-CELL-NSW-00105-4G1-202610090008'
```

| n_quarantined |
|---|
| 0 |

_1 row(s)_

```sql
SELECT feed, failed_rules, count(*) AS n_rows FROM telco_netmon_febar_catalog.netmon_silver.silver_quarantine
              WHERE _source_file = '/Volumes/telco_netmon_febar_catalog/netmon_raw/landing/stream/kpis/date=2026-10-09/batch-20261009T000900-000314.json' GROUP BY ALL ORDER BY n_rows DESC
```

| feed | failed_rules | n_rows |
|---|---|---|
| kpis | ["dl_throughput_mbps_not_null"] | 2 |
| kpis | ["no_rescued_data","dl_throughput_mbps_not_null"] | 2 |
| kpis | ["active_users_not_null"] | 2 |
| kpis | ["event_ts_valid"] | 1 |
| kpis | ["cell_id_not_null","known_element"] | 1 |
| kpis | ["availability_pct_not_null"] | 1 |
| kpis | ["parseable_record"] | 1 |
| kpis | ["availability_pct_in_range"] | 1 |
| kpis | ["active_users_in_range"] | 1 |
| kpis | ["rrc_setup_success_pct_in_range"] | 1 |

_10 row(s)_

## 4. Gold: customer-impact detections and time to detect

Stateless per-record detection (`netmon_pipeline.detection`) turns degraded KPI records and element-down alarms
into `gold_impact_detections` rows. Detections on `SITE-NSW-00105`'s subtree around the incident (first 12 by availability to
the NOC; `available_ts = evidence_ts + pipeline_latency_s`, the measured wall-clock pipeline latency):

```sql
SELECT signal_source, element_id, cell_id, signal_start_ts, evidence_ts, pipeline_latency_s,
               timestampadd(MILLISECOND, CAST(pipeline_latency_s * 1000 AS BIGINT), evidence_ts) AS available_ts,
               flags, in_maintenance
        FROM telco_netmon_febar_catalog.netmon_gold.gold_impact_detections
        WHERE source_run = 'stream' AND 'SITE-NSW-00105' IN (element_id, cell_id, site_id, backhaul_id, router_id)
          AND signal_start_ts BETWEEN timestamp'2026-10-09 00:10:00' - INTERVAL 2 HOURS
                                  AND timestamp'2026-10-09 00:10:00' + INTERVAL 10 MINUTES
        ORDER BY available_ts LIMIT 12
```

| signal_source | element_id | cell_id | signal_start_ts | evidence_ts | pipeline_latency_s | available_ts | flags | in_maintenance |
|---|---|---|---|---|---|---|---|---|
| kpi | CELL-NSW-00105-4G1 | CELL-NSW-00105-4G1 | 2026-10-09T00:08:00.000Z | 2026-10-09T00:10:00.000Z | 42.359000 | 2026-10-09T00:10:42.359Z | ["cell_unavailable","attach_failure","rrc_collapse","rrc_degradation"] | false |
| kpi | CELL-NSW-00105-4G3 | CELL-NSW-00105-4G3 | 2026-10-09T00:08:00.000Z | 2026-10-09T00:10:00.000Z | 42.359000 | 2026-10-09T00:10:42.359Z | ["cell_unavailable","attach_failure","rrc_collapse","rrc_degradation"] | false |
| kpi | CELL-NSW-00105-4G2 | CELL-NSW-00105-4G2 | 2026-10-09T00:08:00.000Z | 2026-10-09T00:10:00.000Z | 42.359000 | 2026-10-09T00:10:42.359Z | ["cell_unavailable","attach_failure","rrc_collapse","rrc_degradation"] | false |
| alarm | SITE-NSW-00105 | NULL | 2026-10-09T00:10:39.000Z | 2026-10-09T00:11:00.000Z | 65.097000 | 2026-10-09T00:12:05.097Z | ["NE_UNREACHABLE"] | false |

_4 row(s)_

The operational (ground-truth-free) timing the app and Genie show, from the `netmon_noc` view:

```sql
SELECT * FROM telco_netmon_febar_catalog.netmon_noc.incident_detection_times WHERE incident_id = 'RCA-c7276c3238a27971'
```

| incident_id | source_run | region_code | suspect_1_id | first_impact_signal_ts | first_detection_ts | incident_detected_ts | time_to_detect_s | time_to_localise_s | detected_within_5min | n_detection_rows |
|---|---|---|---|---|---|---|---|---|---|---|
| RCA-c7276c3238a27971 | stream | NSW | SITE-NSW-00105 | 2026-10-09T00:08:00.000Z | 2026-10-09T00:10:42.359Z | 2026-10-09T00:10:00.000Z | 162.4 | 120 | true | 4 |

_1 row(s)_

## 5. RCA ranker: stored live scores and a fresh endpoint call

The scoring job ranks every candidate element of the case with `rca_ranker@champion` (v5) and
publishes `open_incidents`. Below: the case's top candidates at its latest decision time as stored in
`rca_live_scores`, then the same feature rows (the model's 55 feature columns) sent to the
serving endpoint `banksia-rca-ranker`.

`rca_live_scores`, case `stream|NSW|20261009T0056|SITE-NSW-00105`, model version 5 (8 candidates; open_incidents.n_candidates = 8):

| decision_ts | element_id | element_type | impacted_fraction | silent_fraction | n_alarms | n_service_down_alarms | score |
|---|---|---|---|---|---|---|---|
| 2026-10-09T00:56:00.000Z | SITE-NSW-00105 | SITE | 1.0 | 1.0 | 2.0 | 1.0 | 1.0 |
| 2026-10-09T00:56:00.000Z | AGG-NSW-04 | AGG_ROUTER | 0.043715846 | 0.016393442 | 0.0 | 0.0 | 0.0 |
| 2026-10-09T00:56:00.000Z | AMF-NSW-01 | AMF_MME | 0.053140096 | 0.014492754 | 0.0 | 0.0 | 0.0 |
| 2026-10-09T00:56:00.000Z | BH-NSW-0045 | BACKHAUL_LINK | 0.125 | 0.125 | 0.0 | 0.0 | 0.0 |
| 2026-10-09T00:56:00.000Z | CELL-NSW-00105-4G1 | CELL | 1.0 | 1.0 | 0.0 | 0.0 | 0.0 |

_5 row(s)_

```json
{
  "endpoint": "banksia-rca-ranker",
  "request": {
    "dataframe_records": "8 records x 55 features (first record below)",
    "first_record": {
      "level": 4.0,
      "log_n_desc_cells": 1.3862944,
      "n_children": 3.0,
      "n_impacted_cells": 3.0,
      "impacted_fraction": 1.0,
      "degraded_fraction": 0.0,
      "silent_fraction": 1.0,
      "coverage": 1.0,
      "child_max_coverage": 0.33333334,
      "impacted_children_fraction": 1.0,
      "parent_impacted_fraction": 0.125,
      "parent_coverage": 1.0,
      "lat_now": null,
      "lat_slope5": null,
      "lat_slope15": null,
      "lat_vs_parent": null,
      "loss_now": null,
      "loss_slope5": null,
      "loss_slope15": null,
      "loss_vs_parent": null,
      "thr_now": null,
      "thr_slope5": null,
      "thr_slope15": null,
      "thr_vs_parent": null,
      "rrc_now": null,
      "rrc_slope5": null,
      "rrc_slope15": null,
      "rrc_vs_parent": null,
      "drop_now": null,
      "drop_slope5": null,
      "drop_slope15": null,
      "drop_vs_parent": null,
      "attach_now": null,
      "attach_vs_parent": null,
      "avail_now": null,
      "prb_now": null,
      "prb_slope15": null,
      "impacted_fraction_slope15": 0.0,
      "minutes_since_first_anomaly": 46.0,
      "n_alarms": 2.0,
      "n_critical_alarms": 2.0,
      "n_major_alarms": 0.0,
      "n_service_down_alarms": 1.0,
      "n_alarms_link": 0.0,
      "n_alarms_power": 1.0,
      "n_alarms_unreach": 1.0,
      "n_alarms_core": 0.0,
      "alarm_age_min": 55.633335,
      "n_subtree_alarms": 2.0,
      "n_subtree_service_down_alarms": 1.0,
      "alarmed_children_fraction": 0.0,
      "parent_n_alarms": 0.0,
      "in_maintenance": 0.0,
      "log_case_impacted_cells": 1.3862944,
      "n_case_candidates": 8.0
    }
  },
  "latency_ms": 360,
  "response_top3": [
    {
      "element_id": "SITE-NSW-00105",
      "element_type": "SITE",
      "endpoint_p_root": 1.0,
      "stored_score": 1.0
    },
    {
      "element_id": "AGG-NSW-04",
      "element_type": "AGG_ROUTER",
      "endpoint_p_root": 0.0,
      "stored_score": 0.0
    },
    {
      "element_id": "AMF-NSW-01",
      "element_type": "AMF_MME",
      "endpoint_p_root": 0.0,
      "stored_score": 0.0
    }
  ]
}
```

Endpoint top-1 `SITE-NSW-00105` vs Lakebase suspect 1 `SITE-NSW-00105`: match.

## 6. Lakebase (Postgres, read with psycopg + OAuth)

The synced tables (Delta -> Postgres, TRIGGERED by the scoring and assistant jobs) the app reads on its hot path, and
the app's own SMS review table. Read here with psycopg as the capturing user:

`netmon_rca.lb_open_incidents`:

| incident_id | source_run | region_code | case_id | detected_ts | last_scored_ts | status | suspect_1_id | suspect_1_type | suspect_1_score | suspect_2_id | suspect_2_type | suspect_2_score | suspect_3_id | suspect_3_type | suspect_3_score | n_impacted_cells | n_candidates | model_version | refreshed_at |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RCA-c7276c3238a27971 | stream | NSW | stream\|NSW\|20261009T0056\|SITE-NSW-00105 | 2026-10-09 00:10:00+00:00 | 2026-10-09 00:56:00+00:00 | open | SITE-NSW-00105 | SITE | 1.0 | AGG-NSW-04 | AGG_ROUTER | 0.0 | AMF-NSW-01 | AMF_MME | 0.0 | 3 | 8 | 5 | 2026-11-06 07:41:11.906121+00:00 |

_1 row(s)_

`netmon_rca.lb_element_status` (the suspects and the root's children):

| element_id | element_type | parent_id | state | rca_score | n_impacted_cells | n_desc_cells | silent_fraction | n_alarms | n_service_down_alarms | open_incident_id | suspect_rank |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SITE-NSW-00105 | SITE | BH-NSW-0045 | down | 1.0 | 3.0 | 3.0 | 1.0 | 2.0 | 1.0 | RCA-c7276c3238a27971 | 1.0 |
| AGG-NSW-04 | AGG_ROUTER | UPF-NSW-01 | impacted | 0.0 | 8.0 | 183.0 | 0.016393441706895828 | 0.0 | 0.0 | RCA-c7276c3238a27971 | 2.0 |
| AMF-NSW-01 | AMF_MME | NULL | impacted | 0.0 | 33.0 | 620.9999389648438 | 0.014492753893136978 | 0.0 | 0.0 | RCA-c7276c3238a27971 | 3.0 |
| CELL-NSW-00105-4G1 | CELL | SITE-NSW-00105 | down | 0.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | NULL | NULL |
| CELL-NSW-00105-4G2 | CELL | SITE-NSW-00105 | down | 0.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | NULL | NULL |
| CELL-NSW-00105-4G3 | CELL | SITE-NSW-00105 | down | 0.0 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0 | NULL | NULL |

_6 row(s)_

`netmon_genai.lb_incident_ai_latest`:

| incident_id | summary_id | generated_at | likely_root_cause | fault_hypothesis | confidence | est_affected_subscribers | impacted_cells | impacted_sites | sms_draft_status | generated_by |
|---|---|---|---|---|---|---|---|---|---|---|
| RCA-c7276c3238a27971 | 7666c930-7fe7-4859-90fd-c181533b052f | 2026-11-06 07:42:33.256247+00:00 | SITE-NSW-00105 | SITE_POWER_OUTAGE | high | 420 | 3 | 1 | draft | llm |

_1 row(s)_

`netmon_app.sms_draft_reviews` (written by the app; empty until reviewed):

_(no result set)_

## 7. Gen AI NOC summary and customer SMS draft (Unity Catalog)

The assistant (`databricks-gpt-5-4-mini` through AI Gateway) wrote, for this incident, the summary and the SMS draft
(status `draft`, never sent). Latest versions:

```sql
SELECT summary_id, generated_at, status, likely_root_cause, fault_hypothesis, confidence, summary,
                     next_steps_json, latency_ms, prompt_tokens, completion_tokens, noc_prompt_version
              FROM telco_netmon_febar_catalog.netmon_genai.incident_ai_summaries WHERE incident_id = 'RCA-c7276c3238a27971' ORDER BY generated_at DESC LIMIT 1
```

| summary_id | generated_at | status | likely_root_cause | fault_hypothesis | confidence | summary | next_steps_json | latency_ms | prompt_tokens | completion_tokens | noc_prompt_version |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 7666c930-7fe7-4859-90fd-c181533b052f | 2026-11-06T07:42:33.256Z | draft | SITE-NSW-00105 | SITE_POWER_OUTAGE | high | SITE-NSW-00105 is the best match: all 3 cells under the site are silent, the site has a CRITICAL NE_UNREACHABLE alarm with service down, and BATTERY_LOW was raised beforehand. The neighbouring suspects do not explain the full pattern as well: AGG-NSW-04 has no active alarms and only a small impacted subset, while AMF-NSW-01 shows broader but weaker regional signalling effects. | ["Confirm mains loss / site power status for SITE-NSW-00105 and check the site power alarms feed.", "Check battery state and any generator availability for SITE-NSW-00105.", "Attempt remote recovery actions for the site if available; if the site stays dark, dispatch field tech to restore power.", "Verify whether the 3 cells under SITE-NSW-00105 remain silent and whether nearby sites in Sydney are absorbing traffic.", "If restoration is delayed, escalate for customer-impact management because the incident is affecting 420 subscribers."] | 6189.7 | 4885 | 736 | noc_summary_v3@cfda4dd5 |

_1 row(s)_

```sql
SELECT draft_id, generated_at, status, requires_human_approval, approved_by, sent_at, chars, text
              FROM telco_netmon_febar_catalog.netmon_genai.customer_notice_drafts WHERE incident_id = 'RCA-c7276c3238a27971' ORDER BY generated_at DESC LIMIT 1
```

| draft_id | generated_at | status | requires_human_approval | approved_by | sent_at | chars | text |
|---|---|---|---|---|---|---|---|
| b1730785-f21a-4856-b8f3-c660e5940ad9 | 2026-11-06T07:42:33.256Z | draft | true | NULL | NULL | 95 | Banksia Mobile: Sorry, no mobile service in Sydney and NSW. We'll update you as soon as we can. |

_1 row(s)_

## 8. The deployed app: incident panel and topology pinpoint

`https://banksia-noc-topology-7474648429104135.aws.databricksapps.com` called with the capturing user's token through the Databricks Apps proxy (the proxy forwards the user's
identity and on-behalf-of token to the app). Incident panel (`GET /api/incidents/RCA-c7276c3238a27971`):

```json
{
  "http_status": 200,
  "latency_ms": 2864,
  "body": {
    "incident_id": "RCA-c7276c3238a27971",
    "region_code": "NSW",
    "status": "open",
    "detected_ts": "2026-10-09T00:10:00+00:00",
    "last_scored_ts": "2026-10-09T00:56:00+00:00",
    "model_version": "5",
    "detection": {
      "available": true,
      "incident_id": "RCA-c7276c3238a27971",
      "suspect_1_id": "SITE-NSW-00105",
      "first_impact_signal_ts": "2026-10-09T00:08:00.000Z",
      "first_detection_ts": "2026-10-09T00:10:42.359Z",
      "incident_detected_ts": "2026-10-09T00:10:00.000Z",
      "time_to_detect_s": 162.4,
      "time_to_localise_s": 120,
      "detected_within_5min": true,
      "n_detection_rows": 4
    },
    "impact": {
      "impacted_cells": 3,
      "impacted_sites": 1,
      "est_affected_subscribers": 420,
      "description": "In Sydney, 3 urban 4G cells at one site are silent, affecting an estimated 420 subscribers."
    },
    "pinpoint": {
      "element_id": "SITE-NSW-00105",
      "element_type": "SITE",
      "rank": 1,
      "score": 1.0,
      "name": "Sydney & NSW site 105",
      "state": "down",
      "lat": -33.86795,
      "lon": 151.13944,
      "n_impacted_cells": 3.0,
      "n_desc_cells": 3.0,
      "n_alarms": 2.0
    },
    "path_from_core": [
      {
        "element_id": "AMF-NSW-01",
        "element_type": "AMF_MME",
        "name": "Sydney & NSW AMF/MME 1",
        "state": "impacted"
      },
      {
        "element_id": "UPF-NSW-01",
        "element_type": "UPF_SGW",
        "name": "Sydney & NSW UPF/SGW 1",
        "state": "impacted"
      },
      {
        "element_id": "AGG-NSW-04",
        "element_type": "AGG_ROUTER",
        "name": "Sydney & NSW agg router 4",
        "state": "impacted"
      },
      {
        "element_id": "BH-NSW-0045",
        "element_type": "BACKHAUL_LINK",
        "name": "fibre backhaul BH-NSW-0045",
        "state": "impacted"
      },
      {
        "element_id": "SITE-NSW-00105",
        "element_type": "SITE",
        "name": "Sydney & NSW site 105",
        "state": "down"
      }
    ],
    "suspects": [
      {
        "element_id": "SITE-NSW-00105",
        "element_type": "SITE",
        "rank": 1,
        "score": 1.0,
        "name": "Sydney & NSW site 105",
        "state": "down",
        "lat": -33.86795,
        "lon": 151.13944,
        "n_impacted_cells": 3.0,
        "n_desc_cells": 3.0,
        "n_alarms": 2.0
      },
      {
        "element_id": "AGG-NSW-04",
        "element_type": "AGG_ROUTER",
        "rank": 2,
        "score": 0.0,
        "name": "Sydney & NSW agg router 4",
        "state": "impacted",
        "lat": -33.91285,
        "lon": 151.10021,
        "n_impacted_cells": 8.0,
        "n_desc_cells": 183.0,
        "n_alarms": 0.0
      },
      {
        "element_id": "AMF-NSW-01",
        "element_type": "AMF_MME",
        "rank": 3,
        "score": 0.0,
        "name": "Sydney & NSW AMF/MME 1",
        "state": "impacted",
        "lat": -33.8688,
        "lon": 151.2093,
        "n_impacted_cells": 33.0,
        "n_desc_cells": 620.9999389648438,
        "n_alarms": 0.0
      }
    ],
    "ai": {
      "summary_id": "7666c930-7fe7-4859-90fd-c181533b052f",
      "generated_at": "2026-11-06T07:42:33.256247+00:00",
      "likely_root_cause": "SITE-NSW-00105",
      "fault_hypothesis": "SITE_POWER_OUTAGE",
      "confidence": "high",
      "summary": "SITE-NSW-00105 is the best match: all 3 cells under the site are silent, the site has a CRITICAL NE_UNREACHABLE alarm with service down, and BATTERY_LOW was raised beforehand. The neighbouring suspects do not explain the full pattern as well: AGG-NSW-04 has no active alarms and only a small impacted subset, while AMF-NSW-01 shows broader but weaker regional signalling effects.",
      "next_steps": [
        "Confirm mains loss / site power status for SITE-NSW-00105 and check the site power alarms feed.",
        "Check battery state and any generator availability for SITE-NSW-00105.",
        "Attempt remote recovery actions for the site if available; if the site stays dark, dispatch field tech to restore power.",
        "Verify whether the 3 cells under SITE-NSW-00105 remain silent and whether nearby sites in Sydney are absorbing traffic.",
        "If restoration is delayed, escalate for customer-impact management because the incident is affecting 420 subscribers."
      ],
      "generated_by": "llm",
      "prompt_version": "noc_summary_v3@cfda4dd5",
      "agrees_with_ranker": true
    },
    "sms": {
      "summary_id": "7666c930-7fe7-4859-90fd-c181533b052f",
      "text": "Banksia Mobile: Sorry, no mobile service in Sydney and NSW. We'll update you as soon as we can.",
      "draft_status": "draft",
      "draft_sha256": "69bb4b6cfb851b899d55b5c8f5ff44a582a8a244ab3d09ef9b9022524ded7242",
      "decision": "pending",
      "reviewed_by": null,
      "reviewed_at": null,
      "sent": false,
      "note": "Draft only: this system never sends messages."
    }
  }
}
```

Topology for the incident (`GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971`):

```json
{
  "http_status": 200,
  "latency_ms": 1870,
  "body (trimmed to the highlighted elements)": {
    "region": "NSW",
    "incident_id": "RCA-c7276c3238a27971",
    "view": "incident",
    "pinpoint": "SITE-NSW-00105",
    "path": [
      "AMF-NSW-01",
      "UPF-NSW-01",
      "AGG-NSW-04",
      "BH-NSW-0045",
      "SITE-NSW-00105"
    ],
    "n_nodes_drawn": 21,
    "n_edges": 20,
    "highlighted": [
      {
        "id": "AMF-NSW-01",
        "element_type": "AMF_MME",
        "state": "impacted",
        "highlight": "suspect",
        "suspect_rank": 3,
        "suspect_score": 0.0,
        "lat": -33.8688,
        "lon": 151.2093
      },
      {
        "id": "UPF-NSW-01",
        "element_type": "UPF_SGW",
        "state": "impacted",
        "highlight": "path",
        "suspect_rank": null,
        "suspect_score": null,
        "lat": -33.82147,
        "lon": 151.21161
      },
      {
        "id": "AGG-NSW-04",
        "element_type": "AGG_ROUTER",
        "state": "impacted",
        "highlight": "suspect",
        "suspect_rank": 2,
        "suspect_score": 0.0,
        "lat": -33.91285,
        "lon": 151.10021
      },
      {
        "id": "BH-NSW-0045",
        "element_type": "BACKHAUL_LINK",
        "state": "impacted",
        "highlight": "path",
        "suspect_rank": null,
        "suspect_score": null,
        "lat": -33.85801,
        "lon": 151.11715
      },
      {
        "id": "SITE-NSW-00105",
        "element_type": "SITE",
        "state": "down",
        "highlight": "pinpoint",
        "suspect_rank": 1,
        "suspect_score": 1.0,
        "lat": -33.86795,
        "lon": 151.13944
      }
    ],
    "map_suspects": [
      {
        "id": "AGG-NSW-04",
        "element_type": "AGG_ROUTER",
        "name": "Sydney & NSW agg router 4",
        "lat": -33.91285,
        "lon": 151.10021,
        "state": "impacted",
        "suspect_rank": 2,
        "parent_id": "UPF-NSW-01"
      },
      {
        "id": "AMF-NSW-01",
        "element_type": "AMF_MME",
        "name": "Sydney & NSW AMF/MME 1",
        "lat": -33.8688,
        "lon": 151.2093,
        "state": "impacted",
        "suspect_rank": 3,
        "parent_id": null
      },
      {
        "id": "SITE-NSW-00105",
        "element_type": "SITE",
        "name": "Sydney & NSW site 105",
        "lat": -33.86795,
        "lon": 151.13944,
        "state": "down",
        "suspect_rank": 1,
        "parent_id": "BH-NSW-0045"
      }
    ]
  }
}
```

## 9. Genie, asked through the app

`POST /api/genie/ask` on the app, which calls the Genie Conversation API on the NOC space as the signed-in user.
Question: *For the open incident whose top suspect is SITE-NSW-00105: what is the failing element, how long did it take to detect, and how many subscribers are affected?*

```json
{
  "http_status": 200,
  "latency_ms": 20160,
  "answer_text": [
    "For open incident **RCA-c7276c3238a27971**, the failing element is **SITE-NSW-00105** and the failing element type is **SITE**. The detection time for incident **RCA-c7276c3238a27971** was **162.4 seconds** (**2.7 minutes**), which is **within 5 minutes**, and the estimated affected subscribers for incident **RCA-c7276c3238a27971** is **420**."
  ],
  "columns": [
    "incident_id",
    "region_code",
    "failing_element",
    "failing_element_type",
    "time_to_detect_s",
    "time_to_detect_min",
    "detected_within_5min",
    "est_affected_subscribers"
  ],
  "rows": [
    [
      "RCA-c7276c3238a27971",
      "NSW",
      "SITE-NSW-00105",
      "SITE",
      "162.4",
      "2.7",
      "true",
      "420"
    ]
  ],
  "conversation_id": "01f1d9d4c2381c75a354cb03e9e5c91c"
}
```

SQL Genie generated and ran:

```sql
SELECT `o`.`incident_id`, `o`.`region_code`, `o`.`suspect_1_id` AS `failing_element`, `o`.`suspect_1_type` AS `failing_element_type`, `idt`.`time_to_detect_s`, ROUND(try_divide(`idt`.`time_to_detect_s`,60), 1) AS `time_to_detect_min`, `idt`.`detected_within_5min`, `ias`.`est_affected_subscribers` FROM `telco_netmon_febar_catalog`.`netmon_noc`.`open_incidents` AS `o` JOIN `telco_netmon_febar_catalog`.`netmon_noc`.`incident_detection_times` AS `idt` ON `o`.`incident_id` = `idt`.`incident_id` JOIN `telco_netmon_febar_catalog`.`netmon_noc`.`incident_ai_summary` AS `ias` ON `o`.`incident_id` = `ias`.`incident_id` WHERE `o`.`suspect_1_id` = 'SITE-NSW-00105'
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
| telco_netmon_febar_catalog.netmon_rca.element_status | telco_netmon_febar_catalog.netmon_noc.element_status | NULL | 2026-11-06T11:08:15.194Z | 20 |
| telco_netmon_febar_catalog.netmon_rca.element_status | telco_netmon_febar_catalog.netmon_noc.element_status | JOB | 2026-11-06T10:25:33.003Z | 1 |
| telco_netmon_febar_catalog.netmon_genai.incident_ai_latest | telco_netmon_febar_catalog.netmon_noc.incident_ai_summary | NULL | 2026-11-06T10:43:19.987Z | 27 |
| telco_netmon_febar_catalog.netmon_genai.incident_ai_latest | telco_netmon_febar_catalog.netmon_noc.incident_ai_summary | JOB | 2026-11-06T10:25:34.015Z | 1 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | telco_netmon_febar_catalog.netmon_noc.incident_detection_times | NULL | 2026-11-06T11:08:06.451Z | 21 |
| telco_netmon_febar_catalog.netmon_gold.gold_impact_detections | telco_netmon_febar_catalog.netmon_noc.incident_detection_times | JOB | 2026-11-06T10:25:36.519Z | 1 |
| telco_netmon_febar_catalog.netmon_rca.open_incidents | telco_netmon_febar_catalog.netmon_noc.incident_detection_times | NULL | 2026-11-06T11:08:06.451Z | 21 |
| telco_netmon_febar_catalog.netmon_rca.open_incidents | telco_netmon_febar_catalog.netmon_noc.incident_detection_times | JOB | 2026-11-06T10:25:36.519Z | 1 |
| telco_netmon_febar_catalog.netmon_rca.open_incidents | telco_netmon_febar_catalog.netmon_noc.open_incidents | NULL | 2026-11-06T10:43:19.987Z | 48 |
| telco_netmon_febar_catalog.netmon_rca.open_incidents | telco_netmon_febar_catalog.netmon_noc.open_incidents | JOB | 2026-11-06T10:25:32.051Z | 1 |
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

## 11. Check against the generator's ground truth (evaluation only)

Not used by anything above: the app, Genie's operational views, the ranker's features and the assistant never read
`netmon_eval`. Shown here only to confirm the trace followed a real fault:

```sql
SELECT incident_id, event_class, fault_type, root_element_ids, impact_start_ts, impact_end_ts,
                          is_censored, n_affected_cells, estimated_impacted_subscribers, description
                   FROM telco_netmon_febar_catalog.netmon_eval.eval_gt_incidents
                   WHERE source_run = 'stream' AND array_contains(root_element_ids, 'SITE-NSW-00105')
                     AND is_customer_impacting ORDER BY impact_start_ts DESC LIMIT 1
```

| incident_id | event_class | fault_type | root_element_ids | impact_start_ts | impact_end_ts | is_censored | n_affected_cells | estimated_impacted_subscribers | description |
|---|---|---|---|---|---|---|---|---|---|
| INC-2026100823-00002 | fault | SITE_POWER_OUTAGE | ["SITE-NSW-00105"] | 2026-10-09T00:08:38.000Z | 2026-10-09T00:55:00.000Z | true | 3 | 367 | Mains failure; site runs on battery, then goes dark (cells stop reporting) |

_1 row(s)_

Ground-truth time to detect = first detection available (00:10:42) - true impact start (00:08:38) = **124 s** (5-minute SLA: met). The incident is `is_censored` when the live run ended before the fault cleared; censored incidents are excluded from the scored KPIs (`eval_ttd_summary`), which is why this open incident is not in that scorecard.
