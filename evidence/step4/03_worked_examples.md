# Worked examples: context -> structured NOC summary -> SMS drafts

Captured 2026-11-06 08:12 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

Full examples from the final **dev** evaluation run (`genai_eval_results_dev`), across fault types: the grounded
context exactly as the model received it, the validated structured summary, the guard report and the SMS drafts.
The ground-truth line under each heading is shown for the reader only: it comes from `netmon_eval.genai_eval_labels`
and was used for scoring, never in a prompt. A live open incident (no ground truth) closes the file.

## Slow backhaul degradation (`EVAL-dev-01f8c728c6c3`)

Ground truth (scoring only): fault type `BACKHAUL_DEGRADATION`, valid roots `["BH-VIC-0017"]`. Ranker top-1 `BH-VIC-0017`; assistant `BH-VIC-0017` (high, `BACKHAUL_DEGRADATION`): **same**.

## Context (input)

```json
{
  "context_version": "ctx-v1",
  "incident": {
    "ref": "EVAL-dev-01f8c728c6c3",
    "region_code": "VIC",
    "region_name": "Melbourne & Victoria",
    "timezone": "Australia/Melbourne",
    "as_of": "2026-10-14T02:19:00Z",
    "detected_at": null,
    "minutes_since_detected": null,
    "minutes_since_first_anomaly": 58.0,
    "ranker_model_version": "5",
    "ranker_alert_threshold": 0.27,
    "n_candidates_ranked": 6
  },
  "suspects": [
    {
      "rank": 1,
      "element_id": "BH-VIC-0017",
      "element_type": "BACKHAUL_LINK",
      "ranker_score": 1.0,
      "signals": {
        "impacted_fraction": 0.33,
        "silent_fraction": 0.0,
        "degraded_fraction": 0.33,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 5,
        "parent_impacted_fraction": 0.09,
        "impacted_children_fraction": 1.0,
        "latency_z_now": 10.5,
        "latency_z_slope15": 0.9,
        "loss_z_now": 26.4,
        "loss_z_slope15": 2.3,
        "dl_throughput_z_now": -1.3,
        "rrc_success_z_now": -4.4,
        "drop_rate_z_now": 6.6,
        "attach_success_pct_now": 99.8,
        "availability_pct_now": 100.0,
        "prb_util_pct_now": 31.0,
        "minutes_since_first_anomaly": 0.0,
        "n_alarms": 2,
        "n_critical_alarms": 0,
        "n_service_down_alarms": 0,
        "n_subtree_alarms": 2,
        "alarmed_children_fraction": 0.0,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "VIC",
        "parent": {
          "element_id": "AGG-VIC-02",
          "element_type": "AGG_ROUTER"
        },
        "ancestors": [
          {
            "element_id": "AGG-VIC-02",
            "element_type": "AGG_ROUTER"
          },
          {
            "element_id": "UPF-VIC-01",
            "element_type": "UPF_SGW"
          },
          {
            "element_id": "AMF-VIC-01",
            "element_type": "AMF_MME"
          }
        ],
        "n_children": 3,
        "children_by_type": {
          "SITE": 3
        },
        "n_impacted_children": 1,
        "impacted_children": [
          {
            "element_id": "SITE-VIC-00033",
            "element_type": "SITE",
            "n_impacted_cells": 1
          }
        ],
        "n_desc_cells": 15,
        "n_impacted_desc_cells": 1,
        "transport_medium": "microwave",
        "urbanity": null,
        "technology": null
      }
    },
    {
      "rank": 2,
      "element_id": "SITE-VIC-00033",
      "element_type": "SITE",
      "ranker_score": 0.07,
      "signals": {
        "impacted_fraction": 0.33,
        "silent_fraction": 0.0,
        "degraded_fraction": 0.33,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 1,
        "parent_impacted_fraction": 0.33,
        "impacted_children_fraction": 0.33,
        "latency_z_now": 7.6,
        "latency_z_slope15": 0.7,
        "loss_z_now": 26.5,
        "loss_z_slope15": 2.3,
        "dl_throughput_z_now": -1.6,
        "rrc_success_z_now": -4.4,
        "drop_rate_z_now": 6.7,
        "attach_success_pct_now": 99.8,
        "availability_pct_now": 100.0,
        "prb_util_pct_now": 36.8,
        "minutes_since_first_anomaly": 0.0,
        "n_alarms": 0,
        "n_critical_alarms": 0,
        "n_service_down_alarms": 0,
        "n_subtree_alarms": 0,
        "alarmed_children_fraction": 0.0,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "VIC",
        "parent": {
          "element_id": "BH-VIC-0017",
          "element_type": "BACKHAUL_LINK"
        },
        "ancestors": [
          {
            "element_id": "BH-VIC-0017",
            "element_type": "BACKHAUL_LINK"
          },
          {
            "element_id": "AGG-VIC-02",
            "element_type": "AGG_ROUTER"
          },
          {
            "element_id": "UPF-VIC-01",
            "element_type": "UPF_SGW"
          },
          {
            "element_id": "AMF-VIC-01",
            "element_type": "AMF_MME"
          }
        ],
        "n_children": 3,
        "children_by_type": {
          "CELL": 3
        },
        "n_impacted_children": 1,
        "impacted_children": [
          {
            "element_id": "CELL-VIC-00033-4G3",
            "element_type": "CELL",
            "n_impacted_cells": 1
          }
        ],
        "n_desc_cells": 3,
        "n_impacted_desc_cells": 1,
        "transport_medium": null,
        "urbanity": "rural",
        "technology": "4G"
      }
    },
    {
      "rank": 3,
      "element_id": "AGG-VIC-02",
      "element_type": "AGG_ROUTER",
      "ranker_score": 0.0,
      "signals": {
        "impacted_fraction": 0.09,
        "silent_fraction": 0.01,
        "degraded_fraction": 0.09,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 12,
        "parent_impacted_fraction": 0.15,
        "impacted_children_fraction": 0.31,
        "latency_z_now": 2.3,
        "latency_z_slope15": 0.1,
        "loss_z_now": 6.8,
        "loss_z_slope15": 0.3,
        "dl_throughput_z_now": -0.2,
        "rrc_success_z_now": -1.0,
        "drop_rate_z_now": 1.6,
        "attach_success_pct_now": 99.8,
        "availability_pct_now": 100.0,
        "prb_util_pct_now": 44.1,
        "minutes_since_first_anomaly": 44.0,
        "n_alarms": 0,
        "n_critical_alarms": 0,
        "n_service_down_alarms": 0,
        "n_subtree_alarms": 6,
        "alarmed_children_fraction": 0.15,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "VIC",
        "parent": {
          "element_id": "UPF-VIC-01",
          "element_type": "UPF_SGW"
        },
        "ancestors": [
          {
            "element_id": "UPF-VIC-01",
            "element_type": "UPF_SGW"
          },
          {
            "element_id": "AMF-VIC-01",
            "element_type": "AMF_MME"
          }
        ],
        "n_children": 13,
        "children_by_type": {
          "BACKHAUL_LINK": 13
        },
        "n_impacted_children": 1,
        "impacted_children": [
          {
            "element_id": "BH-VIC-0017",
            "element_type": "BACKHAUL_LINK",
            "n_impacted_cells": 1
          }
        ],
        "n_desc_cells": 129,
        "n_impacted_desc_cells": 1,
        "transport_medium": "fibre",
        "urbanity": null,
        "technology": null
      }
    }
  ],
  "alarms": [
    {
      "element_id": "BH-VIC-0017",
      "element_type": "BACKHAUL_LINK",
      "alarm_code": "RSL_LOW",
      "alarm_severity": "MAJOR",
      "raised_min_before_as_of": 11.2,
      "active": true,
      "service_down": false,
      "text": "Receive level below threshold",
      "text_flagged": false
    },
    {
      "element_id": "BH-VIC-0016",
      "element_type": "BACKHAUL_LINK",
      "alarm_code": "HIGH_BER",
      "alarm_severity": "MAJOR",
      "raised_min_before_as_of": 51.3,
      "active": true,
      "service_down": false,
      "text": "Bit error rate above 1e-6",
      "text_flagged": false
    },
    {
      "element_id": "BH-VIC-0017",
      "element_type": "BACKHAUL_LINK",
      "alarm_code": "LINK_DEGRADED",
      "alarm_severity": "MINOR",
      "raised_min_before_as_of": 0.7,
      "active": true,
      "service_down": false,
      "text": "Link capacity degraded",
      "text_flagged": false
    },
    {
      "element_id": "BH-VIC-0016",
      "element_type": "BACKHAUL_LINK",
      "alarm_code": "LINK_DEGRADED",
      "alarm_severity": "MINOR",
      "raised_min_before_as_of": 39.3,
      "active": true,
      "service_down": false,
      "text": "Link capacity degraded",
      "text_flagged": false
    }
  ],
  "alarm_summary": {
    "n_alarms_in_scope": 4,
    "n_active": 4,
    "n_listed": 4,
    "n_text_flagged": 0,
    "by_code": {
      "LINK_DEGRADED": 2,
      "HIGH_BER": 1,
      "RSL_LOW": 1
    }
  },
  "kpi": {
    "n_cells": 1,
    "n_silent_cells": 0,
    "n_windows": 15,
    "window_minutes": 15,
    "first_window": "2026-10-14T02:02:00Z",
    "last_window": "2026-10-14T02:17:00Z",
    "share_cells_degraded_latest_window": 1.0,
    "median_z": {
      "latency": 1.6,
      "packet_loss": 8.3,
      "dl_throughput": -0.3,
      "rrc_success": -1.1,
      "drop_rate": 2.6
    },
    "z_change_second_half_vs_first_half": {
      "latency": 3.3,
      "packet_loss": 19.2,
      "dl_throughput": 0.0,
      "rrc_success": -2.9,
      "drop_rate": 4.7
    },
    "median_availability_pct": 100.0
  },
  "impact": {
    "n_impacted_cells": 1,
    "n_impacted_sites": 1,
    "regions": [
      "VIC"
    ],
    "est_affected_subscribers_total": 60,
    "by_region_segment": [
      {
        "region_code": "VIC",
        "segment": "rural",
        "n_cells": 1,
        "est_affected_subscribers": 60,
        "n_cells_without_user_data": 0
      }
    ],
    "estimate_method": "max connected users per impacted cell over the last hour of visible 1-minute windows, rounded to 10",
    "sessions_last_15min": {
      "window_minutes": 15,
      "sampled_sessions": 0,
      "sampled_failed_or_dropped": 0,
      "sampled_no_service": 0,
      "xdr_sample_rate": 0.01,
      "est_failed_or_dropped_sessions": 0
    }
  },
  "customer_areas": [
    "Melbourne"
  ],
  "maintenance": {
    "in_planned_window": false,
    "elements": [],
    "planned_end": null
  },
  "customer_eta": null
}
```

## NOC summary (validated output)

```json
{
  "likely_root_cause": "BH-VIC-0017",
  "fault_hypothesis": "BACKHAUL_DEGRADATION",
  "confidence": "high",
  "summary": "The strongest evidence points to backhaul degradation on BH-VIC-0017. It has active RSL_LOW and LINK_DEGRADED alarms, and the impacted child site CELL-VIC-00033-4G3 shows rising latency/loss with falling throughput and worsening RRC/drop KPIs, consistent with a degraded microwave link rather than a site-wide outage.",
  "evidence": [
    {
      "statement": "BH-VIC-0017 has active MAJOR RSL_LOW and MINOR LINK_DEGRADED alarms, with receive level below threshold and link capacity degraded.",
      "context_fields": [
        "alarms[0].element_id",
        "alarms[0].alarm_code",
        "alarms[0].alarm_severity",
        "alarms[0].text",
        "alarms[1].element_id",
        "alarms[1].alarm_code",
        "alarms[1].alarm_severity",
        "alarms[1].text"
      ]
    },
    {
      "statement": "BH-VIC-0017 shows latency_z_now 10.5, loss_z_now 26.4, dl_throughput_z_now -1.3, rrc_success_z_now -4.4 and drop_rate_z_now 6.6 on 5 impacted cells.",
      "context_fields": [
        "suspects[0].signals.latency_z_now",
        "suspects[0].signals.loss_z_now",
        "suspects[0].signals.dl_throughput_z_now",
        "suspects[0].signals.rrc_success_z_now",
        "suspects[0].signals.drop_rate_z_now",
        "suspects[0].signals.n_impacted_cells"
      ]
    },
    {
      "statement": "The degradation is on one child path: BH-VIC-0017 has 1 impacted child, SITE-VIC-00033, and that site has 1 impacted child cell, CELL-VIC-00033-4G3.",
      "context_fields": [
        "suspects[0].neighbourhood.n_impacted_children",
        "suspects[0].neighbourhood.impacted_children[0].element_id",
        "suspects[1].neighbourhood.n_impacted_children",
        "suspects[1].neighbourhood.impacted_children[0].element_id"
      ]
    },
    {
      "statement": "The impacted cell/site are not silent: availability_pct_now is 100.0 and silent_fraction is 0.0 for BH-VIC-0017 and SITE-VIC-00033.",
      "context_fields": [
        "suspects[0].signals.availability_pct_now",
        "suspects[0].signals.silent_fraction",
        "suspects[1].signals.availability_pct_now",
        "suspects[1].signals.silent_fraction"
      ]
    },
    {
      "statement": "The KPI window shows the whole impacted cell degraded in the latest window, with share_cells_degraded_latest_window 1.0 and median_z packet_loss 8.3.",
      "context_fields": [
        "kpi.share_cells_degraded_latest_window",
        "kpi.median_z.packet_loss",
        "kpi.median_z.latency",
        "kpi.median_z.rrc_success",
        "kpi.median_z.drop_rate"
      ]
    },
    {
      "statement": "The incident impact is limited to 1 impacted cell and 1 impacted site, with an estimated 60 affected subscribers in VIC rural.",
      "context_fields": [
        "impact.n_impacted_cells",
        "impact.n_impacted_sites",
        "impact.est_affected_subscribers_total",
        "impact.by_region_segment[0].segment",
        "impact.by_region_segment[0].n_cells"
      ]
    }
  ],
  "recommended_next_steps": [
    "Check BH-VIC-0017 microwave link RSL/BER and interface error counters, and compare with the adjacent backhaul link BH-VIC-0016.",
    "Verify whether the degradation is due to rain fade, interference, or transport congestion; confirm whether a protection path exists for BH-VIC-0017.",
    "If the link metrics continue to worsen, open a transport ticket and dispatch a field crew to BH-VIC-0017.",
    "Monitor SITE-VIC-00033 and CELL-VIC-00033-4G3 to confirm the affected cell remains up and neighbouring cells absorb traffic.",
    "If customer impact increases, notify the incident bridge and prepare customer-communication updates for the VIC rural area."
  ],
  "customer_impact": {
    "estimated_affected_subscribers": 60,
    "impacted_cells": 1,
    "impacted_sites": 1,
    "description": "One rural VIC site and one 4G cell in the Melbourne & Victoria region are experiencing degraded service, with latency and packet loss elevated and throughput/RRC performance reduced."
  },
  "alternative_suspects": [
    "SITE-VIC-00033",
    "AGG-VIC-02"
  ]
}
```

## Guard report

```json
{
  "root_not_in_context": null,
  "unknown_element_ids": [],
  "invalid_evidence_fields": [],
  "dropped_evidence": 0,
  "impact_corrected": {},
  "n_repairs": 0,
  "generated_by": "llm",
  "llm_status": "ok",
  "fallback_reason": null
}
```

## SMS drafts (status = draft, human approval required)

```json
[
  "Banksia Mobile: Slow mobile data and calls may drop or fail in Melbourne & Victoria, including Melbourne. Sorry. We'll keep you updated."
]
```

## The assistant is uncertain

(no case of this kind in the dev run)

## Site power outage (`EVAL-dev-01deab7e8391`)

Ground truth (scoring only): fault type `SITE_POWER_OUTAGE`, valid roots `["SITE-VIC-00095"]`. Ranker top-1 `SITE-VIC-00095`; assistant `SITE-VIC-00095` (high, `SITE_POWER_OUTAGE`): **same**.

## Context (input)

```json
{
  "context_version": "ctx-v1",
  "incident": {
    "ref": "EVAL-dev-01deab7e8391",
    "region_code": "VIC",
    "region_name": "Melbourne & Victoria",
    "timezone": "Australia/Melbourne",
    "as_of": "2026-10-14T23:53:00Z",
    "detected_at": null,
    "minutes_since_detected": null,
    "minutes_since_first_anomaly": 59.0,
    "ranker_model_version": "5",
    "ranker_alert_threshold": 0.27,
    "n_candidates_ranked": 8
  },
  "suspects": [
    {
      "rank": 1,
      "element_id": "SITE-VIC-00095",
      "element_type": "SITE",
      "ranker_score": 1.0,
      "signals": {
        "impacted_fraction": 1.0,
        "silent_fraction": 1.0,
        "degraded_fraction": 0.0,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 3,
        "parent_impacted_fraction": 0.19,
        "impacted_children_fraction": 1.0,
        "latency_z_now": null,
        "latency_z_slope15": 0.1,
        "loss_z_now": null,
        "loss_z_slope15": -0.0,
        "dl_throughput_z_now": null,
        "rrc_success_z_now": null,
        "drop_rate_z_now": null,
        "attach_success_pct_now": null,
        "availability_pct_now": null,
        "prb_util_pct_now": null,
        "minutes_since_first_anomaly": 4.0,
        "n_alarms": 3,
        "n_critical_alarms": 2,
        "n_service_down_alarms": 1,
        "n_subtree_alarms": 3,
        "alarmed_children_fraction": 0.0,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "VIC",
        "parent": {
          "element_id": "BH-VIC-0041",
          "element_type": "BACKHAUL_LINK"
        },
        "ancestors": [
          {
            "element_id": "BH-VIC-0041",
            "element_type": "BACKHAUL_LINK"
          },
          {
            "element_id": "AGG-VIC-04",
            "element_type": "AGG_ROUTER"
          },
          {
            "element_id": "UPF-VIC-01",
            "element_type": "UPF_SGW"
          },
          {
            "element_id": "AMF-VIC-01",
            "element_type": "AMF_MME"
          }
        ],
        "n_children": 3,
        "children_by_type": {
          "CELL": 3
        },
        "n_impacted_children": 3,
        "impacted_children": [
          {
            "element_id": "CELL-VIC-00095-4G1",
            "element_type": "CELL",
            "n_impacted_cells": 1
          },
          {
            "element_id": "CELL-VIC-00095-4G2",
            "element_type": "CELL",
            "n_impacted_cells": 1
          },
          {
            "element_id": "CELL-VIC-00095-4G3",
            "element_type": "CELL",
            "n_impacted_cells": 1
          }
        ],
        "n_desc_cells": 3,
        "n_impacted_desc_cells": 3,
        "transport_medium": null,
        "urbanity": "suburban",
        "technology": "4G"
      }
    },
    {
      "rank": 2,
      "element_id": "AGG-VIC-04",
      "element_type": "AGG_ROUTER",
      "ranker_score": 0.0,
      "signals": {
        "impacted_fraction": 0.03,
        "silent_fraction": 0.02,
        "degraded_fraction": 0.01,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 7,
        "parent_impacted_fraction": 0.26,
        "impacted_children_fraction": 0.19,
        "latency_z_now": -0.2,
        "latency_z_slope15": 0.0,
        "loss_z_now": -0.1,
        "loss_z_slope15": -0.0,
        "dl_throughput_z_now": -0.1,
        "rrc_success_z_now": -7.1,
        "drop_rate_z_now": -0.1,
        "attach_success_pct_now": 98.4,
        "availability_pct_now": 98.6,
        "prb_util_pct_now": 42.1,
        "minutes_since_first_anomaly": 59.0,
        "n_alarms": 0,
        "n_critical_alarms": 0,
        "n_service_down_alarms": 0,
        "n_subtree_alarms": 3,
        "alarmed_children_fraction": 0.0,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "VIC",
        "parent": {
          "element_id": "UPF-VIC-01",
          "element_type": "UPF_SGW"
        },
        "ancestors": [
          {
            "element_id": "UPF-VIC-01",
            "element_type": "UPF_SGW"
          },
          {
            "element_id": "AMF-VIC-01",
            "element_type": "AMF_MME"
          }
        ],
        "n_children": 16,
        "children_by_type": {
          "BACKHAUL_LINK": 16
        },
        "n_impacted_children": 1,
        "impacted_children": [
          {
            "element_id": "BH-VIC-0041",
            "element_type": "BACKHAUL_LINK",
            "n_impacted_cells": 3
          }
        ],
        "n_desc_cells": 216,
        "n_impacted_desc_cells": 3,
        "transport_medium": "fibre",
        "urbanity": null,
        "technology": null
      }
    },
    {
      "rank": 3,
      "element_id": "AMF-VIC-01",
      "element_type": "AMF_MME",
      "ranker_score": 0.0,
      "signals": {
        "impacted_fraction": 0.26,
        "silent_fraction": 0.01,
        "degraded_fraction": 0.25,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 138,
        "parent_impacted_fraction": null,
        "impacted_children_fraction": 1.0,
        "latency_z_now": -0.7,
        "latency_z_slope15": 0.0,
        "loss_z_now": -0.3,
        "loss_z_slope15": 0.0,
        "dl_throughput_z_now": -2.1,
        "rrc_success_z_now": -105.8,
        "drop_rate_z_now": 45.4,
        "attach_success_pct_now": 77.0,
        "availability_pct_now": 75.4,
        "prb_util_pct_now": 34.4,
        "minutes_since_first_anomaly": 59.0,
        "n_alarms": 0,
        "n_critical_alarms": 0,
        "n_service_down_alarms": 0,
        "n_subtree_alarms": 173,
        "alarmed_children_fraction": 1.0,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "VIC",
        "parent": null,
        "ancestors": [],
        "n_children": 1,
        "children_by_type": {
          "UPF_SGW": 1
        },
        "n_impacted_children": 1,
        "impacted_children": [
          {
            "element_id": "UPF-VIC-01",
            "element_type": "UPF_SGW",
            "n_impacted_cells": 3
          }
        ],
        "n_desc_cells": 528,
        "n_impacted_desc_cells": 3,
        "transport_medium": null,
        "urbanity": null,
        "technology": "4G/5G"
      }
    }
  ],
  "alarms": [
    {
      "element_id": "SITE-VIC-00095",
      "element_type": "SITE",
      "alarm_code": "NE_UNREACHABLE",
      "alarm_severity": "CRITICAL",
      "raised_min_before_as_of": 3.0,
      "active": true,
      "service_down": true,
      "text": "Management link lost",
      "text_flagged": false
    },
    {
      "element_id": "SITE-VIC-00095",
      "element_type": "SITE",
      "alarm_code": "BATTERY_LOW",
      "alarm_severity": "CRITICAL",
      "raised_min_before_as_of": 14.0,
      "active": true,
      "service_down": false,
      "text": "Battery below 20 %",
      "text_flagged": false
    },
    {
      "element_id": "UPF-VIC-01",
      "element_type": "UPF_SGW",
      "alarm_code": "GTPU_PATH_FAILURE",
      "alarm_severity": "MAJOR",
      "raised_min_before_as_of": 51.8,
      "active": true,
      "service_down": false,
      "text": "GTP-U path failure towards AGG-VIC-02",
      "text_flagged": false
    },
    {
      "element_id": "SITE-VIC-00095",
      "element_type": "SITE",
      "alarm_code": "MAINS_FAILURE",
      "alarm_severity": "MAJOR",
      "raised_min_before_as_of": 54.4,
      "active": true,
      "service_down": false,
      "text": "AC mains input lost, running on battery",
      "text_flagged": false
    },
    {
      "element_id": "BH-VIC-0043",
      "element_type": "BACKHAUL_LINK",
      "alarm_code": "LINK_DOWN",
      "alarm_severity": "MAJOR",
      "raised_min_before_as_of": 4.8,
      "active": false,
      "service_down": false,
      "text": "Intermittent link state change",
      "text_flagged": false
    },
    {
      "element_id": "BH-VIC-0043",
      "element_type": "BACKHAUL_LINK",
      "alarm_code": "LINK_DOWN",
      "alarm_severity": "MAJOR",
      "raised_min_before_as_of": 10.8,
      "active": false,
      "service_down": false,
      "text": "Intermittent link state change",
      "text_flagged": false
    },
    {
      "element_id": "UPF-VIC-01",
      "element_type": "UPF_SGW",
      "alarm_code": "GTPU_PATH_FAILURE",
      "alarm_severity": "MAJOR",
      "raised_min_before_as_of": 34.7,
      "active": false,
      "service_down": false,
      "text": "GTP-U path failure towards AGG-VIC-01",
      "text_flagged": false
    }
  ],
  "alarm_summary": {
    "n_alarms_in_scope": 7,
    "n_active": 4,
    "n_listed": 7,
    "n_text_flagged": 0,
    "by_code": {
      "GTPU_PATH_FAILURE": 2,
      "LINK_DOWN": 2,
      "BATTERY_LOW": 1,
      "MAINS_FAILURE": 1,
      "NE_UNREACHABLE": 1
    }
  },
  "kpi": {
    "n_cells": 3,
    "n_silent_cells": 3,
    "n_windows": 15,
    "window_minutes": 15,
    "first_window": "2026-10-14T23:33:00Z",
    "last_window": "2026-10-14T23:47:00Z",
    "share_cells_degraded_latest_window": 1.0,
    "median_z": {
      "latency": -0.1,
      "packet_loss": -0.0,
      "dl_throughput": -0.3,
      "rrc_success": 0.1,
      "drop_rate": 0.0
    },
    "z_change_second_half_vs_first_half": {
      "latency": 1.1,
      "packet_loss": -0.0,
      "dl_throughput": -0.2,
      "rrc_success": 0.1,
      "drop_rate": -0.4
    },
    "median_availability_pct": 100.0
  },
  "impact": {
    "n_impacted_cells": 3,
    "n_impacted_sites": 1,
    "regions": [
      "VIC"
    ],
    "est_affected_subscribers_total": 300,
    "by_region_segment": [
      {
        "region_code": "VIC",
        "segment": "suburban",
        "n_cells": 3,
        "est_affected_subscribers": 300,
        "n_cells_without_user_data": 0
      }
    ],
    "estimate_method": "max connected users per impacted cell over the last hour of visible 1-minute windows, rounded to 10",
    "sessions_last_15min": {
      "window_minutes": 15,
      "sampled_sessions": 1,
      "sampled_failed_or_dropped": 0,
      "sampled_no_service": 0,
      "xdr_sample_rate": 0.01,
      "est_failed_or_dropped_sessions": 0
    }
  },
  "customer_areas": [
    "Melbourne"
  ],
  "maintenance": {
    "in_planned_window": false,
    "elements": [],
    "planned_end": null
  },
  "customer_eta": null
}
```

## NOC summary (validated output)

```json
{
  "likely_root_cause": "SITE-VIC-00095",
  "fault_hypothesis": "SITE_POWER_OUTAGE",
  "confidence": "high",
  "summary": "SITE-VIC-00095 is the strongest cause: all 3 child cells are silent, the site has active MAINS_FAILURE, BATTERY_LOW, and NE_UNREACHABLE alarms, and the impacted fraction on the site is 1.0. The pattern fits a site-level power loss rather than a broader transport or core issue; the next minutes of site/KPI recovery after power restoration would confirm it.",
  "evidence": [
    {
      "statement": "SITE-VIC-00095 has impacted_fraction 1.0, silent_fraction 1.0, n_impacted_cells 3, and impacted_children_fraction 1.0.",
      "context_fields": [
        "suspects[0].signals.impacted_fraction",
        "suspects[0].signals.silent_fraction",
        "suspects[0].signals.n_impacted_cells",
        "suspects[0].signals.impacted_children_fraction"
      ]
    },
    {
      "statement": "SITE-VIC-00095 has 3 impacted child cells: CELL-VIC-00095-4G1, CELL-VIC-00095-4G2, and CELL-VIC-00095-4G3.",
      "context_fields": [
        "suspects[0].neighbourhood.impacted_children",
        "suspects[0].neighbourhood.n_impacted_children"
      ]
    },
    {
      "statement": "The site has active CRITICAL NE_UNREACHABLE and BATTERY_LOW alarms, plus a MAJOR MAINS_FAILURE alarm.",
      "context_fields": [
        "alarms[0].element_id",
        "alarms[0].alarm_code",
        "alarms[0].alarm_severity",
        "alarms[1].element_id",
        "alarms[1].alarm_code",
        "alarms[1].alarm_severity",
        "alarms[2].element_id",
        "alarms[2].alarm_code",
        "alarms[2].alarm_severity"
      ]
    },
    {
      "statement": "The NE_UNREACHABLE alarm text says 'Management link lost', and the MAINS_FAILURE text says 'AC mains input lost, running on battery'.",
      "context_fields": [
        "alarms[0].text",
        "alarms[2].text"
      ]
    },
    {
      "statement": "The impact scope is 3 impacted cells across 1 impacted site, with an estimated 300 affected subscribers in VIC suburban areas.",
      "context_fields": [
        "impact.n_impacted_cells",
        "impact.n_impacted_sites",
        "impact.est_affected_subscribers_total",
        "impact.by_region_segment"
      ]
    }
  ],
  "recommended_next_steps": [
    "Confirm the mains-loss condition and battery status at SITE-VIC-00095; verify whether generator support is available.",
    "Check the site's other sectors/cells for any partial recovery or additional equipment alarms.",
    "Attempt remote cell recovery actions only if supported by local procedures; if no recovery, dispatch field tech to the site.",
    "Monitor whether CELL-VIC-00095-4G1, CELL-VIC-00095-4G2, and CELL-VIC-00095-4G3 regain service after power is restored.",
    "Escalate as a customer-impacting outage because the site currently has 3 silent cells and an estimated 300 affected subscribers."
  ],
  "customer_impact": {
    "estimated_affected_subscribers": 300,
    "impacted_cells": 3,
    "impacted_sites": 1,
    "description": "VIC suburban customers around Melbourne are affected by a single site outage, with all 3 cells at SITE-VIC-00095 silent."
  },
  "alternative_suspects": [
    "AGG-VIC-04",
    "AMF-VIC-01"
  ]
}
```

## Guard report

```json
{
  "root_not_in_context": null,
  "unknown_element_ids": [],
  "invalid_evidence_fields": [],
  "dropped_evidence": 0,
  "impact_corrected": {},
  "n_repairs": 0,
  "generated_by": "llm",
  "llm_status": "ok",
  "fallback_reason": null
}
```

## SMS drafts (status = draft, human approval required)

```json
[
  "Banksia Mobile: Customers in Melbourne & Victoria may have no mobile service. Sorry for the disruption. We'll keep you updated."
]
```

## Aggregation router failure (`EVAL-dev-086f792c44d3`)

Ground truth (scoring only): fault type `AGG_ROUTER_FAILURE`, valid roots `["AGG-WA-04"]`. Ranker top-1 `AGG-WA-04`; assistant `AGG-WA-04` (high, `AGG_ROUTER_FAILURE`): **same**.

## Context (input)

```json
{
  "context_version": "ctx-v1",
  "incident": {
    "ref": "EVAL-dev-086f792c44d3",
    "region_code": "WA",
    "region_name": "Perth & South West WA",
    "timezone": "Australia/Perth",
    "as_of": "2026-10-15T22:37:00Z",
    "detected_at": null,
    "minutes_since_detected": null,
    "minutes_since_first_anomaly": 37.0,
    "ranker_model_version": "5",
    "ranker_alert_threshold": 0.27,
    "n_candidates_ranked": 49
  },
  "suspects": [
    {
      "rank": 1,
      "element_id": "AGG-WA-04",
      "element_type": "AGG_ROUTER",
      "ranker_score": 1.0,
      "signals": {
        "impacted_fraction": 1.0,
        "silent_fraction": 0.0,
        "degraded_fraction": 1.0,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 36,
        "parent_impacted_fraction": 0.2,
        "impacted_children_fraction": 1.0,
        "latency_z_now": -1.8,
        "latency_z_slope15": -0.1,
        "loss_z_now": -0.6,
        "loss_z_slope15": -0.0,
        "dl_throughput_z_now": -8.7,
        "rrc_success_z_now": -431.6,
        "drop_rate_z_now": 192.4,
        "attach_success_pct_now": 13.0,
        "availability_pct_now": 6.3,
        "prb_util_pct_now": 1.8,
        "minutes_since_first_anomaly": 3.0,
        "n_alarms": 1,
        "n_critical_alarms": 1,
        "n_service_down_alarms": 1,
        "n_subtree_alarms": 47,
        "alarmed_children_fraction": 1.0,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "WA",
        "parent": {
          "element_id": "UPF-WA-01",
          "element_type": "UPF_SGW"
        },
        "ancestors": [
          {
            "element_id": "UPF-WA-01",
            "element_type": "UPF_SGW"
          },
          {
            "element_id": "AMF-WA-01",
            "element_type": "AMF_MME"
          }
        ],
        "n_children": 3,
        "children_by_type": {
          "BACKHAUL_LINK": 3
        },
        "n_impacted_children": 3,
        "impacted_children": [
          {
            "element_id": "BH-WA-0019",
            "element_type": "BACKHAUL_LINK",
            "n_impacted_cells": 18
          },
          {
            "element_id": "BH-WA-0018",
            "element_type": "BACKHAUL_LINK",
            "n_impacted_cells": 12
          },
          {
            "element_id": "BH-WA-0017",
            "element_type": "BACKHAUL_LINK",
            "n_impacted_cells": 6
          }
        ],
        "n_desc_cells": 36,
        "n_impacted_desc_cells": 36,
        "transport_medium": "fibre",
        "urbanity": null,
        "technology": null
      }
    },
    {
      "rank": 2,
      "element_id": "BH-WA-0019",
      "element_type": "BACKHAUL_LINK",
      "ranker_score": 0.07,
      "signals": {
        "impacted_fraction": 1.0,
        "silent_fraction": 0.0,
        "degraded_fraction": 1.0,
        "coverage_of_case": 0.5,
        "n_impacted_cells": 18,
        "parent_impacted_fraction": 1.0,
        "impacted_children_fraction": 1.0,
        "latency_z_now": -2.1,
        "latency_z_slope15": -0.1,
        "loss_z_now": -0.6,
        "loss_z_slope15": -0.0,
        "dl_throughput_z_now": -8.7,
        "rrc_success_z_now": -436.8,
        "drop_rate_z_now": 194.8,
        "attach_success_pct_now": 11.9,
        "availability_pct_now": 5.1,
        "prb_util_pct_now": 1.7,
        "minutes_since_first_anomaly": 3.0,
        "n_alarms": 1,
        "n_critical_alarms": 1,
        "n_service_down_alarms": 1,
        "n_subtree_alarms": 23,
        "alarmed_children_fraction": 1.0,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "WA",
        "parent": {
          "element_id": "AGG-WA-04",
          "element_type": "AGG_ROUTER"
        },
        "ancestors": [
          {
            "element_id": "AGG-WA-04",
            "element_type": "AGG_ROUTER"
          },
          {
            "element_id": "UPF-WA-01",
            "element_type": "UPF_SGW"
          },
          {
            "element_id": "AMF-WA-01",
            "element_type": "AMF_MME"
          }
        ],
        "n_children": 4,
        "children_by_type": {
          "SITE": 4
        },
        "n_impacted_children": 4,
        "impacted_children": [
          {
            "element_id": "SITE-WA-00039",
            "element_type": "SITE",
            "n_impacted_cells": 6
          },
          {
            "element_id": "SITE-WA-00040",
            "element_type": "SITE",
            "n_impacted_cells": 6
          },
          {
            "element_id": "SITE-WA-00037",
            "element_type": "SITE",
            "n_impacted_cells": 3
          },
          {
            "element_id": "SITE-WA-00038",
            "element_type": "SITE",
            "n_impacted_cells": 3
          }
        ],
        "n_desc_cells": 18,
        "n_impacted_desc_cells": 18,
        "transport_medium": "fibre",
        "urbanity": null,
        "technology": null
      }
    },
    {
      "rank": 3,
      "element_id": "AMF-WA-01",
      "element_type": "AMF_MME",
      "ranker_score": 0.0,
      "signals": {
        "impacted_fraction": 0.2,
        "silent_fraction": 0.0,
        "degraded_fraction": 0.2,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 37,
        "parent_impacted_fraction": null,
        "impacted_children_fraction": 1.0,
        "latency_z_now": -0.4,
        "latency_z_slope15": -0.0,
        "loss_z_now": -0.2,
        "loss_z_slope15": -0.0,
        "dl_throughput_z_now": -1.6,
        "rrc_success_z_now": -87.0,
        "drop_rate_z_now": 37.5,
        "attach_success_pct_now": 82.3,
        "availability_pct_now": 81.1,
        "prb_util_pct_now": 23.3,
        "minutes_since_first_anomaly": 3.0,
        "n_alarms": 1,
        "n_critical_alarms": 0,
        "n_service_down_alarms": 0,
        "n_subtree_alarms": 49,
        "alarmed_children_fraction": 1.0,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "WA",
        "parent": null,
        "ancestors": [],
        "n_children": 1,
        "children_by_type": {
          "UPF_SGW": 1
        },
        "n_impacted_children": 1,
        "impacted_children": [
          {
            "element_id": "UPF-WA-01",
            "element_type": "UPF_SGW",
            "n_impacted_cells": 36
          }
        ],
        "n_desc_cells": 183,
        "n_impacted_desc_cells": 36,
        "transport_medium": null,
        "urbanity": null,
        "technology": "4G/5G"
      }
    }
  ],
  "alarms": [
    {
      "element_id": "SITE-WA-00037",
      "element_type": "SITE",
      "alarm_code": "S1_NG_LINK_FAILURE",
      "alarm_severity": "CRITICAL",
      "raised_min_before_as_of": 3.5,
      "active": true,
      "service_down": true,
      "text": "S1/NG interface to core lost",
      "text_flagged": false
    },
    {
      "element_id": "SITE-WA-00039",
      "element_type": "SITE",
      "alarm_code": "S1_NG_LINK_FAILURE",
      "alarm_severity": "CRITICAL",
      "raised_min_before_as_of": 4.1,
      "active": true,
      "service_down": true,
      "text": "S1/NG interface to core lost",
      "text_flagged": false
    },
    {
      "element_id": "SITE-WA-00040",
      "element_type": "SITE",
      "alarm_code": "S1_NG_LINK_FAILURE",
      "alarm_severity": "CRITICAL",
      "raised_min_before_as_of": 4.3,
      "active": true,
      "service_down": true,
      "text": "S1/NG interface to core lost",
      "text_flagged": false
    },
    {
      "element_id": "BH-WA-0017",
      "element_type": "BACKHAUL_LINK",
      "alarm_code": "LINK_DOWN",
      "alarm_severity": "CRITICAL",
      "raised_min_before_as_of": 5.5,
      "active": true,
      "service_down": true,
      "text": "Interface operationally down",
      "text_flagged": false
    },
    {
      "element_id": "BH-WA-0019",
      "element_type": "BACKHAUL_LINK",
      "alarm_code": "LINK_DOWN",
      "alarm_severity": "CRITICAL",
      "raised_min_before_as_of": 5.5,
      "active": true,
      "service_down": true,
      "text": "Interface operationally down",
      "text_flagged": false
    },
    {
      "element_id": "SITE-WA-00038",
      "element_type": "SITE",
      "alarm_code": "S1_NG_LINK_FAILURE",
      "alarm_severity": "CRITICAL",
      "raised_min_before_as_of": 5.6,
      "active": true,
      "service_down": true,
      "text": "S1/NG interface to core lost",
      "text_flagged": false
    },
    {
      "element_id": "BH-WA-0018",
      "element_type": "BACKHAUL_LINK",
      "alarm_code": "LINK_DOWN",
      "alarm_severity": "CRITICAL",
      "raised_min_before_as_of": 5.8,
      "active": true,
      "service_down": true,
      "text": "Interface operationally down",
      "text_flagged": false
    },
    {
      "element_id": "AGG-WA-04",
      "element_type": "AGG_ROUTER",
      "alarm_code": "NODE_DOWN",
      "alarm_severity": "CRITICAL",
      "raised_min_before_as_of": 5.9,
      "active": true,
      "service_down": true,
      "text": "Node unreachable (heartbeat lost)",
      "text_flagged": false
    },
    {
      "element_id": "UPF-WA-01",
      "element_type": "UPF_SGW",
      "alarm_code": "GTPU_PATH_FAILURE",
      "alarm_severity": "MAJOR",
      "raised_min_before_as_of": 6.0,
      "active": true,
      "service_down": false,
      "text": "GTP-U path failure towards AGG-WA-04",
      "text_flagged": false
    },
    {
      "element_id": "AMF-WA-01",
      "element_type": "AMF_MME",
      "alarm_code": "N2_S1MME_ASSOC_DOWN",
      "alarm_severity": "MINOR",
      "raised_min_before_as_of": 19.4,
      "active": true,
      "service_down": false,
      "text": "Threshold crossed",
      "text_flagged": false
    },
    {
      "element_id": "UPF-WA-01",
      "element_type": "UPF_SGW",
      "alarm_code": "NTP_SYNC_LOSS",
      "alarm_severity": "MAJOR",
      "raised_min_before_as_of": 37.0,
      "active": false,
      "service_down": false,
      "text": "Threshold crossed",
      "text_flagged": false
    }
  ],
  "alarm_summary": {
    "n_alarms_in_scope": 11,
    "n_active": 10,
    "n_listed": 11,
    "n_text_flagged": 0,
    "by_code": {
      "S1_NG_LINK_FAILURE": 4,
      "LINK_DOWN": 3,
      "GTPU_PATH_FAILURE": 1,
      "N2_S1MME_ASSOC_DOWN": 1,
      "NODE_DOWN": 1,
      "NTP_SYNC_LOSS": 1
    }
  },
  "kpi": {
    "n_cells": 36,
    "n_silent_cells": 0,
    "n_windows": 15,
    "window_minutes": 15,
    "first_window": "2026-10-15T22:21:00Z",
    "last_window": "2026-10-15T22:35:00Z",
    "share_cells_degraded_latest_window": 1.0,
    "median_z": {
      "latency": -0.4,
      "packet_loss": -0.1,
      "dl_throughput": -0.4,
      "rrc_success": -0.1,
      "drop_rate": 0.1
    },
    "z_change_second_half_vs_first_half": {
      "latency": -0.6,
      "packet_loss": -0.1,
      "dl_throughput": -1.3,
      "rrc_success": -1.1,
      "drop_rate": 1.8
    },
    "median_availability_pct": 100.0
  },
  "impact": {
    "n_impacted_cells": 36,
    "n_impacted_sites": 7,
    "regions": [
      "WA"
    ],
    "est_affected_subscribers_total": 3030,
    "by_region_segment": [
      {
        "region_code": "WA",
        "segment": "urban",
        "n_cells": 18,
        "est_affected_subscribers": 1530,
        "n_cells_without_user_data": 0
      },
      {
        "region_code": "WA",
        "segment": "suburban",
        "n_cells": 18,
        "est_affected_subscribers": 1500,
        "n_cells_without_user_data": 0
      }
    ],
    "estimate_method": "max connected users per impacted cell over the last hour of visible 1-minute windows, rounded to 10",
    "sessions_last_15min": {
      "window_minutes": 15,
      "sampled_sessions": 10,
      "sampled_failed_or_dropped": 4,
      "sampled_no_service": 2,
      "xdr_sample_rate": 0.01,
      "est_failed_or_dropped_sessions": 400
    }
  },
  "customer_areas": [
    "Perth",
    "Northam"
  ],
  "maintenance": {
    "in_planned_window": false,
    "elements": [],
    "planned_end": null
  },
  "customer_eta": null
}
```

## NOC summary (validated output)

```json
{
  "likely_root_cause": "AGG-WA-04",
  "fault_hypothesis": "AGG_ROUTER_FAILURE",
  "confidence": "high",
  "summary": "The strongest evidence points to AGG-WA-04 as the failing aggregation router: it is NODE_DOWN, has 36 impacted cells across all 3 child backhaul links, and its entire impacted subtree is degraded. The pattern also fits an upstream aggregation fault rather than a single link or site issue, with GTPU_PATH_FAILURE on UPF-WA-01 and S1/NG link failures on four downstream sites.",
  "evidence": [
    {
      "statement": "AGG-WA-04 is rank 1 with ranker_score 1.0 and has n_impacted_cells 36 with impacted_children_fraction 1.0.",
      "context_fields": [
        "suspects[0].rank",
        "suspects[0].ranker_score",
        "suspects[0].signals.n_impacted_cells",
        "suspects[0].signals.impacted_children_fraction"
      ]
    },
    {
      "statement": "AGG-WA-04 has an active critical NODE_DOWN alarm with service_down true.",
      "context_fields": [
        "alarms[7].element_id",
        "alarms[7].alarm_code",
        "alarms[7].alarm_severity",
        "alarms[7].active",
        "alarms[7].service_down"
      ]
    },
    {
      "statement": "All 3 children of AGG-WA-04 are BACKHAUL_LINK elements, and all 3 are impacted.",
      "context_fields": [
        "suspects[0].neighbourhood.n_children",
        "suspects[0].neighbourhood.children_by_type",
        "suspects[0].neighbourhood.n_impacted_children",
        "suspects[0].neighbourhood.impacted_children"
      ]
    },
    {
      "statement": "The impacted backhaul links BH-WA-0017, BH-WA-0018 and BH-WA-0019 each have active critical LINK_DOWN alarms.",
      "context_fields": [
        "alarms[3].element_id",
        "alarms[3].alarm_code",
        "alarms[4].element_id",
        "alarms[4].alarm_code",
        "alarms[6].element_id",
        "alarms[6].alarm_code"
      ]
    },
    {
      "statement": "UPF-WA-01 has an active GTPU_PATH_FAILURE alarm towards AGG-WA-04, which matches an upstream transport/core adjacency problem.",
      "context_fields": [
        "alarms[8].element_id",
        "alarms[8].alarm_code",
        "alarms[8].text"
      ]
    },
    {
      "statement": "The impacted customer base is 3030 subscribers across 36 cells in 7 sites in WA.",
      "context_fields": [
        "impact.est_affected_subscribers_total",
        "impact.n_impacted_cells",
        "impact.n_impacted_sites"
      ]
    }
  ],
  "recommended_next_steps": [
    "Check AGG-WA-04 reachability, power, and line-card status; attempt remote recovery/failover if available.",
    "Inspect the three child backhaul links BH-WA-0017, BH-WA-0018 and BH-WA-0019 for common transport failure symptoms and confirm the LINK_DOWN condition.",
    "Verify whether the downstream S1/NG link failures on SITE-WA-00037, SITE-WA-00038, SITE-WA-00039 and SITE-WA-00040 clear after router recovery.",
    "Engage the transport vendor and open a major incident/transport ticket given the 3030 affected subscribers and 7 impacted sites.",
    "If remote recovery does not restore service, dispatch field support for AGG-WA-04 and the affected transport path."
  ],
  "customer_impact": {
    "estimated_affected_subscribers": 3030,
    "impacted_cells": 36,
    "impacted_sites": 7,
    "description": "Customers in WA, including Perth and Northam areas, are seeing widespread service loss/degradation across 36 cells in 7 sites."
  },
  "alternative_suspects": [
    "BH-WA-0019",
    "AMF-WA-01"
  ]
}
```

## Guard report

```json
{
  "root_not_in_context": null,
  "unknown_element_ids": [],
  "invalid_evidence_fields": [],
  "dropped_evidence": 0,
  "impact_corrected": {},
  "n_repairs": 0,
  "generated_by": "llm",
  "llm_status": "ok",
  "fallback_reason": null
}
```

## SMS drafts (status = draft, human approval required)

```json
[
  "Banksia Mobile: Some customers in Perth and Northam may have intermittent mobile service. Sorry for the disruption. We'll keep you updated."
]
```

## Cell outage (`EVAL-dev-01c93fe0605b`)

Ground truth (scoring only): fault type `CELL_OUTAGE`, valid roots `["CELL-NQL-00012-5G2"]`. Ranker top-1 `CELL-NQL-00012-5G2`; assistant `CELL-NQL-00012-5G2` (high, `CELL_OUTAGE`): **same**.

## Context (input)

```json
{
  "context_version": "ctx-v1",
  "incident": {
    "ref": "EVAL-dev-01c93fe0605b",
    "region_code": "NQL",
    "region_name": "North Queensland",
    "timezone": "Australia/Brisbane",
    "as_of": "2026-10-15T02:19:00Z",
    "detected_at": null,
    "minutes_since_detected": null,
    "minutes_since_first_anomaly": 27.0,
    "ranker_model_version": "5",
    "ranker_alert_threshold": 0.27,
    "n_candidates_ranked": 6
  },
  "suspects": [
    {
      "rank": 1,
      "element_id": "CELL-NQL-00012-5G2",
      "element_type": "CELL",
      "ranker_score": 1.0,
      "signals": {
        "impacted_fraction": 1.0,
        "silent_fraction": 0.0,
        "degraded_fraction": 1.0,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 1,
        "parent_impacted_fraction": 0.17,
        "impacted_children_fraction": 0.0,
        "latency_z_now": -4.3,
        "latency_z_slope15": -0.5,
        "loss_z_now": -4.1,
        "loss_z_slope15": -0.4,
        "dl_throughput_z_now": -5.3,
        "rrc_success_z_now": -98.5,
        "drop_rate_z_now": -3.4,
        "attach_success_pct_now": 0.0,
        "availability_pct_now": 0.0,
        "prb_util_pct_now": 0.0,
        "minutes_since_first_anomaly": 4.0,
        "n_alarms": 2,
        "n_critical_alarms": 1,
        "n_service_down_alarms": 1,
        "n_subtree_alarms": 2,
        "alarmed_children_fraction": 0.0,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "NQL",
        "parent": {
          "element_id": "SITE-NQL-00012",
          "element_type": "SITE"
        },
        "ancestors": [
          {
            "element_id": "SITE-NQL-00012",
            "element_type": "SITE"
          },
          {
            "element_id": "BH-NQL-0008",
            "element_type": "BACKHAUL_LINK"
          },
          {
            "element_id": "AGG-NQL-03",
            "element_type": "AGG_ROUTER"
          },
          {
            "element_id": "UPF-NQL-01",
            "element_type": "UPF_SGW"
          },
          {
            "element_id": "AMF-NQL-01",
            "element_type": "AMF_MME"
          }
        ],
        "n_children": 0,
        "children_by_type": {},
        "n_impacted_children": 0,
        "impacted_children": [],
        "n_desc_cells": 1,
        "n_impacted_desc_cells": 1,
        "transport_medium": null,
        "urbanity": "urban",
        "technology": "5G"
      }
    },
    {
      "rank": 2,
      "element_id": "AGG-NQL-03",
      "element_type": "AGG_ROUTER",
      "ranker_score": 0.0,
      "signals": {
        "impacted_fraction": 0.04,
        "silent_fraction": 0.0,
        "degraded_fraction": 0.04,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 1,
        "parent_impacted_fraction": 0.01,
        "impacted_children_fraction": 0.25,
        "latency_z_now": -0.2,
        "latency_z_slope15": -0.0,
        "loss_z_now": -0.1,
        "loss_z_slope15": -0.0,
        "dl_throughput_z_now": -0.3,
        "rrc_success_z_now": -3.6,
        "drop_rate_z_now": -0.2,
        "attach_success_pct_now": 96.0,
        "availability_pct_now": 96.2,
        "prb_util_pct_now": 44.3,
        "minutes_since_first_anomaly": 4.0,
        "n_alarms": 0,
        "n_critical_alarms": 0,
        "n_service_down_alarms": 0,
        "n_subtree_alarms": 2,
        "alarmed_children_fraction": 0.0,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "NQL",
        "parent": {
          "element_id": "UPF-NQL-01",
          "element_type": "UPF_SGW"
        },
        "ancestors": [
          {
            "element_id": "UPF-NQL-01",
            "element_type": "UPF_SGW"
          },
          {
            "element_id": "AMF-NQL-01",
            "element_type": "AMF_MME"
          }
        ],
        "n_children": 4,
        "children_by_type": {
          "BACKHAUL_LINK": 4
        },
        "n_impacted_children": 1,
        "impacted_children": [
          {
            "element_id": "BH-NQL-0008",
            "element_type": "BACKHAUL_LINK",
            "n_impacted_cells": 1
          }
        ],
        "n_desc_cells": 27,
        "n_impacted_desc_cells": 1,
        "transport_medium": "fibre",
        "urbanity": null,
        "technology": null
      }
    },
    {
      "rank": 3,
      "element_id": "AMF-NQL-01",
      "element_type": "AMF_MME",
      "ranker_score": 0.0,
      "signals": {
        "impacted_fraction": 0.01,
        "silent_fraction": 0.0,
        "degraded_fraction": 0.01,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 1,
        "parent_impacted_fraction": null,
        "impacted_children_fraction": 1.0,
        "latency_z_now": -0.2,
        "latency_z_slope15": -0.0,
        "loss_z_now": -0.1,
        "loss_z_slope15": -0.0,
        "dl_throughput_z_now": -0.0,
        "rrc_success_z_now": -0.9,
        "drop_rate_z_now": -0.1,
        "attach_success_pct_now": 98.8,
        "availability_pct_now": 99.0,
        "prb_util_pct_now": 37.7,
        "minutes_since_first_anomaly": 27.0,
        "n_alarms": 0,
        "n_critical_alarms": 0,
        "n_service_down_alarms": 0,
        "n_subtree_alarms": 7,
        "alarmed_children_fraction": 0.0,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "NQL",
        "parent": null,
        "ancestors": [],
        "n_children": 1,
        "children_by_type": {
          "UPF_SGW": 1
        },
        "n_impacted_children": 1,
        "impacted_children": [
          {
            "element_id": "UPF-NQL-01",
            "element_type": "UPF_SGW",
            "n_impacted_cells": 1
          }
        ],
        "n_desc_cells": 99,
        "n_impacted_desc_cells": 1,
        "transport_medium": null,
        "urbanity": null,
        "technology": "4G/5G"
      }
    }
  ],
  "alarms": [
    {
      "element_id": "CELL-NQL-00012-5G2",
      "element_type": "CELL",
      "alarm_code": "CELL_OUT_OF_SERVICE",
      "alarm_severity": "CRITICAL",
      "raised_min_before_as_of": 5.2,
      "active": true,
      "service_down": true,
      "text": "Cell disabled",
      "text_flagged": false
    },
    {
      "element_id": "CELL-NQL-00012-5G2",
      "element_type": "CELL",
      "alarm_code": "RRU_FAILURE",
      "alarm_severity": "MAJOR",
      "raised_min_before_as_of": 6.8,
      "active": true,
      "service_down": false,
      "text": "Radio unit failure detected",
      "text_flagged": false
    },
    {
      "element_id": "AMF-NQL-01",
      "element_type": "AMF_MME",
      "alarm_code": "CORE_CPU_OVERLOAD",
      "alarm_severity": "WARNING",
      "raised_min_before_as_of": 29.0,
      "active": false,
      "service_down": false,
      "text": "Threshold crossed",
      "text_flagged": false
    }
  ],
  "alarm_summary": {
    "n_alarms_in_scope": 3,
    "n_active": 2,
    "n_listed": 3,
    "n_text_flagged": 0,
    "by_code": {
      "CELL_OUT_OF_SERVICE": 1,
      "CORE_CPU_OVERLOAD": 1,
      "RRU_FAILURE": 1
    }
  },
  "kpi": {
    "n_cells": 1,
    "n_silent_cells": 0,
    "n_windows": 15,
    "window_minutes": 15,
    "first_window": "2026-10-15T02:03:00Z",
    "last_window": "2026-10-15T02:17:00Z",
    "share_cells_degraded_latest_window": 1.0,
    "median_z": {
      "latency": 0.5,
      "packet_loss": 0.6,
      "dl_throughput": -0.5,
      "rrc_success": -0.7,
      "drop_rate": 0.6
    },
    "z_change_second_half_vs_first_half": {
      "latency": -5.2,
      "packet_loss": -4.6,
      "dl_throughput": -4.2,
      "rrc_success": -92.8,
      "drop_rate": -4.0
    },
    "median_availability_pct": 100.0
  },
  "impact": {
    "n_impacted_cells": 1,
    "n_impacted_sites": 1,
    "regions": [
      "NQL"
    ],
    "est_affected_subscribers_total": 540,
    "by_region_segment": [
      {
        "region_code": "NQL",
        "segment": "urban",
        "n_cells": 1,
        "est_affected_subscribers": 540,
        "n_cells_without_user_data": 0
      }
    ],
    "estimate_method": "max connected users per impacted cell over the last hour of visible 1-minute windows, rounded to 10",
    "sessions_last_15min": {
      "window_minutes": 15,
      "sampled_sessions": 0,
      "sampled_failed_or_dropped": 0,
      "sampled_no_service": 0,
      "xdr_sample_rate": 0.01,
      "est_failed_or_dropped_sessions": 0
    }
  },
  "customer_areas": [
    "Townsville"
  ],
  "maintenance": {
    "in_planned_window": false,
    "elements": [],
    "planned_end": null
  },
  "customer_eta": null
}
```

## NOC summary (validated output)

```json
{
  "likely_root_cause": "CELL-NQL-00012-5G2",
  "fault_hypothesis": "CELL_OUTAGE",
  "confidence": "high",
  "summary": "The evidence points to a single-cell outage on CELL-NQL-00012-5G2 in North Queensland. The cell has active CELL_OUT_OF_SERVICE and RRU_FAILURE alarms, availability is 0.0%, and the affected pattern is isolated to one cell/site with only 540 estimated subscribers impacted around Townsville.",
  "evidence": [
    {
      "statement": "CELL-NQL-00012-5G2 has active CELL_OUT_OF_SERVICE and RRU_FAILURE alarms, with the service_down flag set on the CELL_OUT_OF_SERVICE alarm.",
      "context_fields": [
        "alarms[0].element_id",
        "alarms[0].alarm_code",
        "alarms[0].active",
        "alarms[0].service_down",
        "alarms[1].element_id",
        "alarms[1].alarm_code",
        "alarms[1].active"
      ]
    },
    {
      "statement": "The cell's availability_pct_now is 0.0% and attach_success_pct_now is 0.0%, while impacted_fraction is 1.0.",
      "context_fields": [
        "suspects[0].signals.availability_pct_now",
        "suspects[0].signals.attach_success_pct_now",
        "suspects[0].signals.impacted_fraction"
      ]
    },
    {
      "statement": "The impacted scope is limited to one cell and one site: n_impacted_cells is 1 and n_impacted_sites is 1.",
      "context_fields": [
        "impact.n_impacted_cells",
        "impact.n_impacted_sites"
      ]
    },
    {
      "statement": "The cell's parent SITE-NQL-00012 has parent_impacted_fraction 0.17, while impacted_children_fraction is 0.0, which fits a localized child-cell issue rather than a wider parent outage.",
      "context_fields": [
        "suspects[0].neighbourhood.parent.element_id",
        "suspects[0].signals.parent_impacted_fraction",
        "suspects[0].signals.impacted_children_fraction"
      ]
    },
    {
      "statement": "The affected customer estimate is 540 subscribers in the NQL urban segment, with customer areas listed as Townsville.",
      "context_fields": [
        "impact.est_affected_subscribers_total",
        "impact.by_region_segment[0].segment",
        "impact.by_region_segment[0].est_affected_subscribers",
        "customer_areas"
      ]
    }
  ],
  "recommended_next_steps": [
    "Check CELL-NQL-00012-5G2 RRU/radio alarms and related radio health signals, including VSWR if available.",
    "Attempt a remote cell lock/unlock or RRU reset on CELL-NQL-00012-5G2.",
    "Verify the other sectors on SITE-NQL-00012 remain healthy and continue carrying traffic.",
    "Dispatch field support to SITE-NQL-00012 if the remote reset does not clear CELL_OUT_OF_SERVICE / RRU_FAILURE.",
    "Monitor neighbouring cells for traffic absorption while the cell is restored.",
    "If the outage persists, escalate as a customer-impacting cell fault for the 540 affected subscribers."
  ],
  "customer_impact": {
    "estimated_affected_subscribers": 540,
    "impacted_cells": 1,
    "impacted_sites": 1,
    "description": "One urban 5G cell in North Queensland, around Townsville, is out of service and affecting an estimated 540 subscribers."
  },
  "alternative_suspects": [
    "AGG-NQL-03",
    "AMF-NQL-01"
  ]
}
```

## Guard report

```json
{
  "root_not_in_context": null,
  "unknown_element_ids": [],
  "invalid_evidence_fields": [],
  "dropped_evidence": 0,
  "impact_corrected": {},
  "n_repairs": 0,
  "generated_by": "llm",
  "llm_status": "ok",
  "fallback_reason": null
}
```

## SMS drafts (status = draft, human approval required)

```json
[
  "Banksia Mobile: Intermittent mobile service in Townsville, North Queensland. Sorry for the trouble. We'll keep you updated."
]
```

## Live open incident `RCA-1073d4d88aa7e05b` (job `banksia-genai-assistant`, no ground truth)

Generated 2026-11-06T07:42:33.256Z: `CELL-VIC-00062-5G2` (high, `CELL_OUTAGE`).

## Context (input)

```json
{
  "context_version": "ctx-v1",
  "incident": {
    "ref": "RCA-1073d4d88aa7e05b",
    "region_code": "VIC",
    "region_name": "Melbourne & Victoria",
    "timezone": "Australia/Melbourne",
    "as_of": "2026-10-09T00:56:00Z",
    "detected_at": "2026-10-08T23:56:00Z",
    "minutes_since_detected": 60.0,
    "minutes_since_first_anomaly": 59.0,
    "ranker_model_version": "5",
    "ranker_alert_threshold": 0.27,
    "n_candidates_ranked": 6
  },
  "suspects": [
    {
      "rank": 1,
      "element_id": "CELL-VIC-00062-5G2",
      "element_type": "CELL",
      "ranker_score": 1.0,
      "signals": {
        "impacted_fraction": 1.0,
        "silent_fraction": 0.0,
        "degraded_fraction": 1.0,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 1,
        "parent_impacted_fraction": 0.17,
        "impacted_children_fraction": 0.0,
        "latency_z_now": -2.6,
        "latency_z_slope15": -0.0,
        "loss_z_now": -1.0,
        "loss_z_slope15": 0.0,
        "dl_throughput_z_now": -9.0,
        "rrc_success_z_now": -496.5,
        "drop_rate_z_now": -1.1,
        "attach_success_pct_now": 0.0,
        "availability_pct_now": 0.0,
        "prb_util_pct_now": 0.0,
        "minutes_since_first_anomaly": 59.0,
        "n_alarms": 0,
        "n_critical_alarms": 0,
        "n_service_down_alarms": 0,
        "n_subtree_alarms": 0,
        "alarmed_children_fraction": 0.0,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "VIC",
        "parent": {
          "element_id": "SITE-VIC-00062",
          "element_type": "SITE"
        },
        "ancestors": [
          {
            "element_id": "SITE-VIC-00062",
            "element_type": "SITE"
          },
          {
            "element_id": "BH-VIC-0028",
            "element_type": "BACKHAUL_LINK"
          },
          {
            "element_id": "AGG-VIC-03",
            "element_type": "AGG_ROUTER"
          },
          {
            "element_id": "UPF-VIC-01",
            "element_type": "UPF_SGW"
          },
          {
            "element_id": "AMF-VIC-01",
            "element_type": "AMF_MME"
          }
        ],
        "n_children": 0,
        "children_by_type": {},
        "n_impacted_children": 0,
        "impacted_children": [],
        "n_desc_cells": 1,
        "n_impacted_desc_cells": 1,
        "transport_medium": null,
        "urbanity": "urban",
        "technology": "5G"
      }
    },
    {
      "rank": 2,
      "element_id": "AGG-VIC-03",
      "element_type": "AGG_ROUTER",
      "ranker_score": 0.0,
      "signals": {
        "impacted_fraction": 0.01,
        "silent_fraction": 0.0,
        "degraded_fraction": 0.01,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 1,
        "parent_impacted_fraction": 0.04,
        "impacted_children_fraction": 0.11,
        "latency_z_now": 0.0,
        "latency_z_slope15": 0.0,
        "loss_z_now": 0.0,
        "loss_z_slope15": 0.0,
        "dl_throughput_z_now": -0.3,
        "rrc_success_z_now": -4.5,
        "drop_rate_z_now": 0.1,
        "attach_success_pct_now": 98.9,
        "availability_pct_now": 99.1,
        "prb_util_pct_now": 56.3,
        "minutes_since_first_anomaly": 59.0,
        "n_alarms": 0,
        "n_critical_alarms": 0,
        "n_service_down_alarms": 0,
        "n_subtree_alarms": 0,
        "alarmed_children_fraction": 0.0,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "VIC",
        "parent": {
          "element_id": "UPF-VIC-01",
          "element_type": "UPF_SGW"
        },
        "ancestors": [
          {
            "element_id": "UPF-VIC-01",
            "element_type": "UPF_SGW"
          },
          {
            "element_id": "AMF-VIC-01",
            "element_type": "AMF_MME"
          }
        ],
        "n_children": 9,
        "children_by_type": {
          "BACKHAUL_LINK": 9
        },
        "n_impacted_children": 1,
        "impacted_children": [
          {
            "element_id": "BH-VIC-0028",
            "element_type": "BACKHAUL_LINK",
            "n_impacted_cells": 1
          }
        ],
        "n_desc_cells": 114,
        "n_impacted_desc_cells": 1,
        "transport_medium": "fibre",
        "urbanity": null,
        "technology": null
      }
    },
    {
      "rank": 3,
      "element_id": "AMF-VIC-01",
      "element_type": "AMF_MME",
      "ranker_score": 0.0,
      "signals": {
        "impacted_fraction": 0.04,
        "silent_fraction": 0.0,
        "degraded_fraction": 0.04,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 19,
        "parent_impacted_fraction": null,
        "impacted_children_fraction": 1.0,
        "latency_z_now": 0.3,
        "latency_z_slope15": 0.0,
        "loss_z_now": 2.3,
        "loss_z_slope15": 0.0,
        "dl_throughput_z_now": -0.4,
        "rrc_success_z_now": -6.2,
        "drop_rate_z_now": 0.6,
        "attach_success_pct_now": 98.6,
        "availability_pct_now": 98.8,
        "prb_util_pct_now": 46.5,
        "minutes_since_first_anomaly": 59.0,
        "n_alarms": 0,
        "n_critical_alarms": 0,
        "n_service_down_alarms": 0,
        "n_subtree_alarms": 7,
        "alarmed_children_fraction": 0.0,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "VIC",
        "parent": null,
        "ancestors": [],
        "n_children": 1,
        "children_by_type": {
          "UPF_SGW": 1
        },
        "n_impacted_children": 1,
        "impacted_children": [
          {
            "element_id": "UPF-VIC-01",
            "element_type": "UPF_SGW",
            "n_impacted_cells": 1
          }
        ],
        "n_desc_cells": 528,
        "n_impacted_desc_cells": 1,
        "transport_medium": null,
        "urbanity": null,
        "technology": "4G/5G"
      }
    }
  ],
  "alarms": [],
  "alarm_summary": {
    "n_alarms_in_scope": 0,
    "n_active": 0,
    "n_listed": 0,
    "n_text_flagged": 0,
    "by_code": {}
  },
  "kpi": {
    "n_cells": 1,
    "n_silent_cells": 0,
    "n_windows": 15,
    "window_minutes": 15,
    "first_window": "2026-10-09T00:40:00Z",
    "last_window": "2026-10-09T00:54:00Z",
    "share_cells_degraded_latest_window": 1.0,
    "median_z": {
      "latency": -2.2,
      "packet_loss": -0.9,
      "dl_throughput": -9.0,
      "rrc_success": -496.5,
      "drop_rate": -0.8
    },
    "z_change_second_half_vs_first_half": {
      "latency": -0.1,
      "packet_loss": 0.1,
      "dl_throughput": 0.0,
      "rrc_success": 0.0,
      "drop_rate": 0.5
    },
    "median_availability_pct": 0.0
  },
  "impact": {
    "n_impacted_cells": 1,
    "n_impacted_sites": 1,
    "regions": [
      "VIC"
    ],
    "est_affected_subscribers_total": 0,
    "by_region_segment": [
      {
        "region_code": "VIC",
        "segment": "urban",
        "n_cells": 1,
        "est_affected_subscribers": 0,
        "n_cells_without_user_data": 0
      }
    ],
    "estimate_method": "max connected users per impacted cell over the last hour of visible 1-minute windows, rounded to 10",
    "sessions_last_15min": {
      "window_minutes": 15,
      "sampled_sessions": 0,
      "sampled_failed_or_dropped": 0,
      "sampled_no_service": 0,
      "xdr_sample_rate": 0.01,
      "est_failed_or_dropped_sessions": 0
    }
  },
  "customer_areas": [
    "Melbourne"
  ],
  "maintenance": {
    "in_planned_window": false,
    "elements": [],
    "planned_end": null
  },
  "customer_eta": null
}
```

## Summary

```json
{
  "summary": "The impacted pattern is confined to one 5G cell, with availability at 0.0 and a fully degraded KPI profile on that cell, while the parent site and upstream elements are mostly unaffected. There are no active alarms in scope, so this looks like a cell-level outage rather than a broader transport, core, or site power problem.",
  "evidence": [
    {
      "statement": "Suspect #1 is a single cell with ranker_score 1.0 and n_impacted_cells 1.",
      "context_fields": [
        "suspects[0].element_id",
        "suspects[0].ranker_score",
        "suspects[0].signals.n_impacted_cells"
      ]
    },
    {
      "statement": "The cell's availability_pct_now is 0.0 and its degraded_fraction is 1.0.",
      "context_fields": [
        "suspects[0].signals.availability_pct_now",
        "suspects[0].signals.degraded_fraction"
      ]
    },
    {
      "statement": "The cell shows severe service KPI degradation, including dl_throughput_z_now -9.0, rrc_success_z_now -496.5, and attach_success_pct_now 0.0.",
      "context_fields": [
        "suspects[0].signals.dl_throughput_z_now",
        "suspects[0].signals.rrc_success_z_now",
        "suspects[0].signals.attach_success_pct_now"
      ]
    },
    {
      "statement": "There are no active alarms in scope and the cell has n_alarms 0, n_critical_alarms 0, and n_service_down_alarms 0.",
      "context_fields": [
        "alarm_summary.n_active",
        "suspects[0].signals.n_alarms",
        "suspects[0].signals.n_critical_alarms",
        "suspects[0].signals.n_service_down_alarms"
      ]
    },
    {
      "statement": "The parent site is only partially impacted, with parent_impacted_fraction 0.17, while the cell has no impacted children.",
      "context_fields": [
        "suspects[0].signals.parent_impacted_fraction",
        "suspects[0].signals.impacted_children_fraction",
        "suspects[0].neighbourhood.parent.element_id"
      ]
    }
  ],
  "recommended_next_steps": [
    "Check CELL-VIC-00062-5G2 radio and RRU alarms, plus VSWR if available.",
    "Attempt a remote cell lock/unlock or RRU reset on CELL-VIC-00062-5G2.",
    "Verify the other sectors at SITE-VIC-00062 are healthy and confirm they are carrying traffic.",
    "If the reset does not recover service, dispatch field tech to SITE-VIC-00062.",
    "Monitor neighbouring cells in the area to confirm they are absorbing traffic while the cell is down."
  ]
}
```

## SMS drafts

```json
[
  {
    "region_code": "VIC",
    "text": "Banksia Mobile: No mobile service and calls and data may drop or fail in Melbourne & Victoria. Sorry. We'll update you.",
    "status": "draft",
    "requires_human_approval": "true",
    "sent_at": null
  },
  {
    "region_code": "VIC",
    "text": "Banksia Mobile: No mobile service and calls and data may drop or fail in Melbourne and Victoria. Sorry. We'll keep you updated.",
    "status": "draft",
    "requires_human_approval": "true",
    "sent_at": null
  },
  {
    "region_code": "VIC",
    "text": "Banksia Mobile: No mobile service and calls and data may drop or fail in Melbourne and Victoria. Sorry. We'll update you.",
    "status": "draft",
    "requires_human_approval": "true",
    "sent_at": null
  }
]
```
