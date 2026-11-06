# App API responses (incident view)

Captured 2026-11-06 11:33 UTC from workspace profile `febar` by `scripts/capture_evidence_step5.py`.

What the operator's browser receives from `https://banksia-noc-topology-7474648429104135.aws.databricksapps.com` for the demo incident `RCA-c7276c3238a27971` (SITE-NSW-00105, site power
outage), captured as the signed-in national NOC user. The page (`app/static/`) renders exactly these payloads.

## Who am I (identity, region scope from Unity Catalog)

```json
{
  "request": "GET /api/me",
  "http_status": 200,
  "latency_ms": 1147,
  "body": {
    "user": "louis.chen@databricks.com",
    "name": "Louis Chen",
    "regions": [
      "NQL",
      "NSW",
      "VIC",
      "WA"
    ],
    "on_behalf_of_user": true,
    "identities": {
      "lakebase": "app service principal (23923ae9-3de4-453b-b13f-b61f7ba84868)",
      "sql_warehouse": "signed-in user (on-behalf-of token)",
      "genie": "signed-in user (on-behalf-of token)"
    }
  }
}
```

## Open incidents in NSW (Lakebase)

```json
{
  "request": "GET /api/incidents?region=NSW",
  "http_status": 200,
  "latency_ms": 1044,
  "body": {
    "incidents": [
      {
        "incident_id": "RCA-cdc1224a2469350b",
        "region_code": "NSW",
        "detected_ts": "2026-10-09T00:39:00+00:00",
        "suspect_1_id": "BH-NSW-0015",
        "suspect_1_type": "BACKHAUL_LINK",
        "suspect_1_score": 1.0,
        "n_impacted_cells": 6,
        "est_affected_subscribers": 480,
        "fault_hypothesis": "BACKHAUL_DEGRADATION",
        "sms_decision": "pending"
      },
      {
        "incident_id": "RCA-c068ecb5f659c20d",
        "region_code": "NSW",
        "detected_ts": "2026-10-09T00:37:00+00:00",
        "suspect_1_id": "CELL-NSW-00122-4G2",
        "suspect_1_type": "CELL",
        "suspect_1_score": 1.0,
        "n_impacted_cells": 1,
        "est_affected_subscribers": 60,
        "fault_hypothesis": "CELL_OUTAGE",
        "sms_decision": "pending"
      },
      {
        "incident_id": "RCA-ce4e7fd28bd45261",
        "region_code": "NSW",
        "detected_ts": "2026-10-09T00:32:00+00:00",
        "suspect_1_id": "BH-NSW-0041",
        "suspect_1_type": "BACKHAUL_LINK",
        "suspect_1_score": 1.0,
        "n_impacted_cells": 3,
        "est_affected_subscribers": 170,
        "fault_hypothesis": "BACKHAUL_DEGRADATION",
        "sms_decision": "pending"
      },
      {
        "incident_id": "RCA-e46db865d147fb84",
        "region_code": "NSW",
        "detected_ts": "2026-10-09T00:18:00+00:00",
        "suspect_1_id": "CELL-NSW-00051-4G3",
        "suspect_1_type": "CELL",
        "suspect_1_score": 1.0,
        "n_impacted_cells": 1,
        "est_affected_subscribers": 20,
        "fault_hypothesis": "CELL_OUTAGE",
        "sms_decision": "pending"
      },
      {
        "incident_id": "RCA-c7276c3238a27971",
        "region_code": "NSW",
        "detected_ts": "2026-10-09T00:10:00+00:00",
        "suspect_1_id": "SITE-NSW-00105",
        "suspect_1_type": "SITE",
        "suspect_1_score": 1.0,
        "n_impacted_cells": 3,
        "est_affected_subscribers": 420,
        "fault_hypothesis": "SITE_POWER_OUTAGE",
        "sms_decision": "pending"
      },
      {
        "incident_id": "RCA-fbd7ff66e62b0b42",
        "region_code": "NSW",
        "detected_ts": "2026-10-09T00:07:00+00:00",
        "suspect_1_id": "SITE-NSW-00009",
        "suspect_1_type": "SITE",
        "suspect_1_score": 1.0,
        "n_impacted_cells": 6,
        "est_affected_subscribers": 990,
        "fault_hypothesis": "SITE_POWER_OUTAGE",
        "sms_decision": "pending"
      },
      {
        "incident_id": "RCA-e909709b1c6a18fb",
        "region_code": "NSW",
        "detected_ts": "2026-10-08T23:59:00+00:00",
        "suspect_1_id": "BH-NSW-0013",
        "suspect_1_type": "BACKHAUL_LINK",
        "suspect_1_score": 1.0,
        "n_impacted_cells": 9,
        "est_affected_subscribers": 680,
        "fault_hypothesis": "BACKHAUL_DEGRADATION",
        "sms_decision": "pending"
      },
      {
        "incident_id": "RCA-4b24e8c0bfedac1a",
        "region_code": "NSW",
        "detected_ts": "2026-10-08T23:56:00+00:00",
        "suspect_1_id": "BH-NSW-0010",
        "suspect_1_type": "BACKHAUL_LINK",
        "suspect_1_score": 1.0,
        "n_impacted_cells": 3,
        "est_affected_subscribers": 240,
        "fault_hypothesis": "BACKHAUL_DEGRADATION",
        "sms_decision": "pending"
      },
      {
        "incident_id": "RCA-60fe3d71c22893d5",
        "region_code": "NSW",
        "detected_ts": "2026-10-08T23:56:00+00:00",
        "suspect_1_id": "CELL-NSW-00123-4G3",
        "suspect_1_type": "CELL",
        "suspect_1_score": 1.0,
        "n_impacted_cells": 1,
        "est_affected_subscribers": 0,
        "fault_hypothesis": "CELL_OUTAGE",
        "sms_decision": "pending"
      }
    ]
  }
}
```

## Incident panel

Detection time and time to detect, impacted counts, the ranker's top-3 with scores, the pinpointed element with its path from the core, the Gen AI summary and next steps, the SMS draft:

```json
{
  "request": "GET /api/incidents/RCA-c7276c3238a27971",
  "http_status": 200,
  "latency_ms": 1063,
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

## Topology: incident focus (pinpoint highlighted)

```json
{
  "request": "GET /api/regions/NSW/topology?incident_id=RCA-c7276c3238a27971  (trimmed to the highlighted elements)",
  "http_status": 200,
  "latency_ms": 1559,
  "body": {
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

All drawn nodes of that view (healthy siblings collapsed into `+N` nodes), with their layout:

```json
{
  "nodes": [
    {
      "id": "AMF-NSW-01",
      "kind": "element",
      "element_type": "AMF_MME",
      "state": "impacted",
      "highlight": "suspect",
      "depth": 0,
      "x": 0.5,
      "count": null
    },
    {
      "id": "UPF-NSW-01",
      "kind": "element",
      "element_type": "UPF_SGW",
      "state": "impacted",
      "highlight": "path",
      "depth": 1,
      "x": 0.5,
      "count": null
    },
    {
      "id": "AGG-NSW-01",
      "kind": "element",
      "element_type": "AGG_ROUTER",
      "state": "impacted",
      "highlight": null,
      "depth": 2,
      "x": 0.0,
      "count": null
    },
    {
      "id": "AGG-NSW-02",
      "kind": "element",
      "element_type": "AGG_ROUTER",
      "state": "impacted",
      "highlight": null,
      "depth": 2,
      "x": 0.0667,
      "count": null
    },
    {
      "id": "AGG-NSW-04",
      "kind": "element",
      "element_type": "AGG_ROUTER",
      "state": "impacted",
      "highlight": "suspect",
      "depth": 2,
      "x": 0.5333,
      "count": null
    },
    {
      "id": "AGG-NSW-03",
      "kind": "element",
      "element_type": "AGG_ROUTER",
      "state": "ok",
      "highlight": null,
      "depth": 2,
      "x": 1.0,
      "count": null
    },
    {
      "id": "BH-NSW-0041",
      "kind": "element",
      "element_type": "BACKHAUL_LINK",
      "state": "degraded",
      "highlight": null,
      "depth": 3,
      "x": 0.1333,
      "count": null
    },
    {
      "id": "BH-NSW-0045",
      "kind": "element",
      "element_type": "BACKHAUL_LINK",
      "state": "impacted",
      "highlight": "path",
      "depth": 3,
      "x": 0.4333,
      "count": null
    },
    {
      "id": "BH-NSW-0055",
      "kind": "element",
      "element_type": "BACKHAUL_LINK",
      "state": "impacted",
      "highlight": null,
      "depth": 3,
      "x": 0.6667,
      "count": null
    },
    {
      "id": "BH-NSW-0039",
      "kind": "element",
      "element_type": "BACKHAUL_LINK",
      "state": "ok",
      "highlight": null,
      "depth": 3,
      "x": 0.7333,
      "count": null
    },
    {
      "id": "BH-NSW-0040",
      "kind": "element",
      "element_type": "BACKHAUL_LINK",
      "state": "ok",
      "highlight": null,
      "depth": 3,
      "x": 0.8,
      "count": null
    },
    {
      "id": "BH-NSW-0042",
      "kind": "element",
      "element_type": "BACKHAUL_LINK",
      "state": "ok",
      "highlight": null,
      "depth": 3,
      "x": 0.8667,
      "count": null
    },
    {
      "id": "SITE-NSW-00105",
      "kind": "element",
      "element_type": "SITE",
      "state": "down",
      "highlight": "pinpoint",
      "depth": 4,
      "x": 0.2667,
      "count": null
    },
    {
      "id": "SITE-NSW-00104",
      "kind": "element",
      "element_type": "SITE",
      "state": "ok",
      "highlight": null,
      "depth": 4,
      "x": 0.4,
      "count": null
    },
    {
      "id": "SITE-NSW-00106",
      "kind": "element",
      "element_type": "SITE",
      "state": "ok",
      "highlight": null,
      "depth": 4,
      "x": 0.4667,
      "count": null
    },
    {
      "id": "SITE-NSW-00107",
      "kind": "element",
      "element_type": "SITE",
      "state": "ok",
      "highlight": null,
      "depth": 4,
      "x": 0.5333,
      "count": null
    },
    {
      "id": "CELL-NSW-00105-4G1",
      "kind": "element",
      "element_type": "CELL",
      "state": "down",
      "highlight": null,
      "depth": 5,
      "x": 0.2,
      "count": null
    },
    {
      "id": "CELL-NSW-00105-4G2",
      "kind": "element",
      "element_type": "CELL",
      "state": "down",
      "highlight": null,
      "depth": 5,
      "x": 0.2667,
      "count": null
    },
    {
      "id": "CELL-NSW-00105-4G3",
      "kind": "element",
      "element_type": "CELL",
      "state": "down",
      "highlight": null,
      "depth": 5,
      "x": 0.3333,
      "count": null
    },
    {
      "id": "AGG-NSW-04::ok",
      "kind": "collapsed",
      "element_type": "BACKHAUL_LINK",
      "state": "ok",
      "highlight": null,
      "depth": 3,
      "x": 0.9333,
      "count": 13
    },
    {
      "id": "BH-NSW-0045::ok",
      "kind": "collapsed",
      "element_type": "SITE",
      "state": "ok",
      "highlight": null,
      "depth": 4,
      "x": 0.6,
      "count": 1
    }
  ]
}
```

## Topology: region overview

```json
{
  "request": "GET /api/regions/NSW/topology  (counts only)",
  "http_status": 200,
  "latency_ms": 1576,
  "body": {
    "view": "region",
    "n_elements_in_region": 814,
    "n_nodes_drawn": 57,
    "state_counts": {
      "BACKHAUL_LINK": {
        "ok": 49,
        "impacted": 4,
        "degraded": 4
      },
      "AMF_MME": {
        "impacted": 1
      },
      "AGG_ROUTER": {
        "impacted": 3,
        "ok": 1
      },
      "CELL": {
        "alarm": 2,
        "ok": 586,
        "down": 11,
        "degraded": 22
      },
      "SITE": {
        "ok": 116,
        "alarm": 4,
        "down": 2,
        "degraded": 5,
        "impacted": 3
      },
      "UPF_SGW": {
        "impacted": 1
      }
    },
    "unhealthy_drawn": [
      "AMF-NSW-01",
      "UPF-NSW-01",
      "AGG-NSW-01",
      "AGG-NSW-02",
      "AGG-NSW-04",
      "BH-NSW-0010",
      "BH-NSW-0013",
      "BH-NSW-0004",
      "BH-NSW-0015",
      "BH-NSW-0021",
      "BH-NSW-0041",
      "BH-NSW-0045",
      "BH-NSW-0055",
      "SITE-NSW-00025",
      "SITE-NSW-00030",
      "SITE-NSW-00031",
      "SITE-NSW-00009",
      "SITE-NSW-00008",
      "SITE-NSW-00036",
      "SITE-NSW-00051",
      "SITE-NSW-00045",
      "SITE-NSW-00052",
      "SITE-NSW-00059",
      "SITE-NSW-00097",
      "SITE-NSW-00105",
      "SITE-NSW-00122",
      "SITE-NSW-00123"
    ]
  }
}
```

## Detection KPIs (SQL warehouse as the user)

```json
{
  "request": "GET /api/kpis",
  "http_status": 200,
  "latency_ms": 3662,
  "body": {
    "operational": [
      {
        "region_code": "NQL",
        "n_open_incidents": 1,
        "mttd_s": 193.5,
        "pct_detected_within_5min": 100.0
      },
      {
        "region_code": "NSW",
        "n_open_incidents": 9,
        "mttd_s": 160.7,
        "pct_detected_within_5min": 100.0
      },
      {
        "region_code": "VIC",
        "n_open_incidents": 7,
        "mttd_s": 168.5,
        "pct_detected_within_5min": 100.0
      }
    ],
    "scorecard": {
      "available": true,
      "n_incidents": 26,
      "impact_detected_pct": 100.0,
      "impact_median_ttd_s": 141.4,
      "impact_p90_ttd_s": 430.4,
      "impact_within_5min_pct": 88.5,
      "root_localised_pct": 100.0,
      "localised_within_5min_pct": 88.5
    }
  }
}
```

## Ask Genie from the app

```json
{
  "request": "POST /api/genie/ask {question: 'Which cell sites are down right now?'}",
  "http_status": 200,
  "latency_ms": 20505,
  "body": {
    "conversation_id": "01f1d9d5fa7919b1833ed851e1a5b59e",
    "message_id": "01f1d9d5fa8e15d4bdfc1bb4ac41b8b2",
    "status": "COMPLETED",
    "text": [
      "There are **3 cell sites** currently marked **down** in the regions you can see: **North Queensland site 6** (NQL, **3 impacted cells**), **Sydney & NSW site 9** (NSW, **6 impacted cells**), and **Sydney & NSW site 105** (NSW, **3 impacted cells**). The largest current site outage in this result is **Sydney & NSW site 9** with **6 impacted cells**, while the other two each have **3 impacted cells**."
    ],
    "sql": "SELECT `s`.`element_id`, `n`.`name`, `s`.`region_code`, `s`.`n_desc_cells`, `s`.`n_impacted_cells`, `s`.`open_incident_id`\nFROM `telco_netmon_febar_catalog`.`netmon_noc`.`element_status` AS `s`\nJOIN `telco_netmon_febar_catalog`.`netmon_noc`.`silver_topology_nodes` AS `n`\n  ON `n`.`element_id` = `s`.`element_id`\nWHERE `s`.`element_type` = 'SITE'\n  AND `s`.`state` = 'down'\n  AND `s`.`element_id` IS NOT NULL\n  AND `n`.`name` IS NOT NULL\n  AND `s`.`region_code` IS NOT NULL\nORDER BY `s`.`region_code`, `s`.`element_id`",
    "description": "You want to see a list of all cell sites that are currently down, including their IDs, names, region codes, the number of cells they contain, how many of those cells are impacted, and any open incident IDs associated with them.",
    "columns": [
      "element_id",
      "name",
      "region_code",
      "n_desc_cells",
      "n_impacted_cells",
      "open_incident_id"
    ],
    "rows": [
      [
        "SITE-NQL-00006",
        "North Queensland site 6",
        "NQL",
        "3.0",
        "3.0",
        "RCA-d28473ab1bd7b846"
      ],
      [
        "SITE-NSW-00009",
        "Sydney & NSW site 9",
        "NSW",
        "6.000000476837158",
        "6.0",
        "RCA-fbd7ff66e62b0b42"
      ],
      [
        "SITE-NSW-00105",
        "Sydney & NSW site 105",
        "NSW",
        "3.0",
        "3.0",
        "RCA-c7276c3238a27971"
      ]
    ],
    "row_count": 3,
    "error": null
  }
}
```
