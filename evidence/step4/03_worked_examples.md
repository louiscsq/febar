# Worked examples: context -> structured NOC summary -> SMS drafts

Captured 2026-11-06 02:26 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

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
    "ranker_model_version": "4",
    "ranker_alert_threshold": 0.32,
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
      "ranker_score": 0.02,
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
  "summary": "The strongest suspect is BH-VIC-0017: it has active RSL_LOW and LINK_DEGRADED alarms, and the impacted cell behind it shows rising latency and packet loss with reduced downlink throughput over the last 15 minutes. The pattern fits a degrading microwave backhaul link rather than a cell outage: availability stays 100.0%, no cells are silent, and the parent site/router are not dark.",
  "evidence": [
    {
      "statement": "BH-VIC-0017 has active RSL_LOW and LINK_DEGRADED alarms raised 11.2 and 0.7 minutes before as_of, respectively.",
      "context_fields": [
        "alarms[0].element_id",
        "alarms[0].alarm_code",
        "alarms[0].raised_min_before_as_of",
        "alarms[3].element_id",
        "alarms[3].alarm_code",
        "alarms[3].raised_min_before_as_of"
      ]
    },
    {
      "statement": "BH-VIC-0017 shows latency_z_now 10.5, loss_z_now 26.4, and dl_throughput_z_now -1.3 on the impacted path.",
      "context_fields": [
        "suspects[0].signals.latency_z_now",
        "suspects[0].signals.loss_z_now",
        "suspects[0].signals.dl_throughput_z_now"
      ]
    },
    {
      "statement": "The impacted child of BH-VIC-0017 is SITE-VIC-00033 with one impacted cell, and BH-VIC-0017 has n_impacted_children 1 out of 3 children.",
      "context_fields": [
        "suspects[0].neighbourhood.impacted_children[0].element_id",
        "suspects[0].neighbourhood.impacted_children[0].n_impacted_cells",
        "suspects[0].neighbourhood.n_impacted_children",
        "suspects[0].neighbourhood.n_children"
      ]
    },
    {
      "statement": "No cells are silent and availability is 100.0% for BH-VIC-0017 and SITE-VIC-00033.",
      "context_fields": [
        "suspects[0].signals.silent_fraction",
        "suspects[0].signals.availability_pct_now",
        "suspects[1].signals.silent_fraction",
        "suspects[1].signals.availability_pct_now"
      ]
    },
    {
      "statement": "The KPI window shows share_cells_degraded_latest_window 1.0 and median_z packet_loss 8.3 with latency 1.6.",
      "context_fields": [
        "kpi.share_cells_degraded_latest_window",
        "kpi.median_z.packet_loss",
        "kpi.median_z.latency"
      ]
    }
  ],
  "recommended_next_steps": [
    "Check BH-VIC-0017 microwave link health for interface errors, RSL, and BER trends.",
    "Validate whether a protection or reroute path exists for BH-VIC-0017 and move traffic if available.",
    "Inspect the affected child site SITE-VIC-00033 for whether the degraded backhaul is the only limiting factor on the impacted cell.",
    "Open a transport ticket for BH-VIC-0017 and monitor whether latency and packet loss continue to rise in the next KPI windows.",
    "If the link remains degraded, dispatch field support to the microwave hop for BH-VIC-0017."
  ],
  "customer_impact": {
    "estimated_affected_subscribers": 60,
    "impacted_cells": 1,
    "impacted_sites": 1,
    "description": "About 60 rural subscribers in VIC are seeing degraded service on one impacted cell/site area, with higher latency, packet loss, and lower downlink throughput."
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
  "Banksia Mobile: Slow mobile data and calls may drop or fail in Melbourne & Victoria. Sorry. We'll keep you updated."
]
```

## The assistant is uncertain (`EVAL-dev-0277797bad6f`)

Ground truth (scoring only): fault type `AMF_OVERLOAD`, valid roots `["AMF-VIC-01"]`. Ranker top-1 `AMF-VIC-01`; assistant `uncertain` (low, `UNCERTAIN`): **uncertain_on_correct**.

## Context (input)

```json
{
  "context_version": "ctx-v1",
  "incident": {
    "ref": "EVAL-dev-0277797bad6f",
    "region_code": "VIC",
    "region_name": "Melbourne & Victoria",
    "timezone": "Australia/Melbourne",
    "as_of": "2026-10-15T06:14:00Z",
    "detected_at": null,
    "minutes_since_detected": null,
    "minutes_since_first_anomaly": 43.0,
    "ranker_model_version": "4",
    "ranker_alert_threshold": 0.32,
    "n_candidates_ranked": 685
  },
  "suspects": [
    {
      "rank": 1,
      "element_id": "AMF-VIC-01",
      "element_type": "AMF_MME",
      "ranker_score": 1.0,
      "signals": {
        "impacted_fraction": 1.0,
        "silent_fraction": 0.0,
        "degraded_fraction": 1.0,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 528,
        "parent_impacted_fraction": null,
        "impacted_children_fraction": 1.0,
        "latency_z_now": -0.0,
        "latency_z_slope15": -0.0,
        "loss_z_now": -0.0,
        "loss_z_slope15": -0.0,
        "dl_throughput_z_now": 0.1,
        "rrc_success_z_now": -9.1,
        "drop_rate_z_now": -0.0,
        "attach_success_pct_now": 86.6,
        "availability_pct_now": 100.0,
        "prb_util_pct_now": 55.3,
        "minutes_since_first_anomaly": 2.0,
        "n_alarms": 1,
        "n_critical_alarms": 0,
        "n_service_down_alarms": 0,
        "n_subtree_alarms": 2,
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
            "n_impacted_cells": 528
          }
        ],
        "n_desc_cells": 528,
        "n_impacted_desc_cells": 528,
        "transport_medium": null,
        "urbanity": null,
        "technology": "4G/5G"
      }
    },
    {
      "rank": 2,
      "element_id": "UPF-VIC-01",
      "element_type": "UPF_SGW",
      "ranker_score": 0.0,
      "signals": {
        "impacted_fraction": 1.0,
        "silent_fraction": 0.0,
        "degraded_fraction": 1.0,
        "coverage_of_case": 1.0,
        "n_impacted_cells": 528,
        "parent_impacted_fraction": 1.0,
        "impacted_children_fraction": 1.0,
        "latency_z_now": -0.0,
        "latency_z_slope15": -0.0,
        "loss_z_now": -0.0,
        "loss_z_slope15": -0.0,
        "dl_throughput_z_now": 0.1,
        "rrc_success_z_now": -9.1,
        "drop_rate_z_now": -0.0,
        "attach_success_pct_now": 86.6,
        "availability_pct_now": 100.0,
        "prb_util_pct_now": 55.3,
        "minutes_since_first_anomaly": 2.0,
        "n_alarms": 0,
        "n_critical_alarms": 0,
        "n_service_down_alarms": 0,
        "n_subtree_alarms": 1,
        "alarmed_children_fraction": 0.0,
        "in_maintenance": false
      },
      "neighbourhood": {
        "region_code": "VIC",
        "parent": {
          "element_id": "AMF-VIC-01",
          "element_type": "AMF_MME"
        },
        "ancestors": [
          {
            "element_id": "AMF-VIC-01",
            "element_type": "AMF_MME"
          }
        ],
        "n_children": 4,
        "children_by_type": {
          "AGG_ROUTER": 4
        },
        "n_impacted_children": 4,
        "impacted_children": [
          {
            "element_id": "AGG-VIC-04",
            "element_type": "AGG_ROUTER",
            "n_impacted_cells": 216
          },
          {
            "element_id": "AGG-VIC-02",
            "element_type": "AGG_ROUTER",
            "n_impacted_cells": 129
          },
          {
            "element_id": "AGG-VIC-03",
            "element_type": "AGG_ROUTER",
            "n_impacted_cells": 114
          },
          {
            "element_id": "AGG-VIC-01",
            "element_type": "AGG_ROUTER",
            "n_impacted_cells": 69
          }
        ],
        "n_desc_cells": 528,
        "n_impacted_desc_cells": 528,
        "transport_medium": null,
        "urbanity": null,
        "technology": "4G/5G"
      }
    },
    {
      "rank": 3,
      "element_id": "AGG-VIC-01",
      "element_type": "AGG_ROUTER",
      "ranker_score": 0.0,
      "signals": {
        "impacted_fraction": 1.0,
        "silent_fraction": 0.01,
        "degraded_fraction": 1.0,
        "coverage_of_case": 0.13,
        "n_impacted_cells": 69,
        "parent_impacted_fraction": 1.0,
        "impacted_children_fraction": 1.0,
        "latency_z_now": 0.0,
        "latency_z_slope15": 0.0,
        "loss_z_now": -0.0,
        "loss_z_slope15": -0.0,
        "dl_throughput_z_now": -0.1,
        "rrc_success_z_now": -9.6,
        "drop_rate_z_now": 0.0,
        "attach_success_pct_now": 86.6,
        "availability_pct_now": 100.0,
        "prb_util_pct_now": 48.4,
        "minutes_since_first_anomaly": 2.0,
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
        "n_children": 6,
        "children_by_type": {
          "BACKHAUL_LINK": 6
        },
        "n_impacted_children": 6,
        "impacted_children": [
          {
            "element_id": "BH-VIC-0002",
            "element_type": "BACKHAUL_LINK",
            "n_impacted_cells": 18
          },
          {
            "element_id": "BH-VIC-0001",
            "element_type": "BACKHAUL_LINK",
            "n_impacted_cells": 12
          },
          {
            "element_id": "BH-VIC-0005",
            "element_type": "BACKHAUL_LINK",
            "n_impacted_cells": 12
          },
          {
            "element_id": "BH-VIC-0006",
            "element_type": "BACKHAUL_LINK",
            "n_impacted_cells": 12
          },
          {
            "element_id": "BH-VIC-0004",
            "element_type": "BACKHAUL_LINK",
            "n_impacted_cells": 9
          },
          {
            "element_id": "BH-VIC-0003",
            "element_type": "BACKHAUL_LINK",
            "n_impacted_cells": 6
          }
        ],
        "n_desc_cells": 69,
        "n_impacted_desc_cells": 69,
        "transport_medium": "fibre",
        "urbanity": null,
        "technology": null
      }
    }
  ],
  "alarms": [
    {
      "element_id": "AMF-VIC-01",
      "element_type": "AMF_MME",
      "alarm_code": "CORE_CPU_OVERLOAD",
      "alarm_severity": "MINOR",
      "raised_min_before_as_of": 2.9,
      "active": true,
      "service_down": false,
      "text": "CPU above 85 %",
      "text_flagged": false
    }
  ],
  "alarm_summary": {
    "n_alarms_in_scope": 1,
    "n_active": 1,
    "n_listed": 1,
    "n_text_flagged": 0,
    "by_code": {
      "CORE_CPU_OVERLOAD": 1
    }
  },
  "kpi": {
    "n_cells": 528,
    "n_silent_cells": 1,
    "n_windows": 15,
    "window_minutes": 15,
    "first_window": "2026-10-15T05:58:00Z",
    "last_window": "2026-10-15T06:12:00Z",
    "share_cells_degraded_latest_window": 1.0,
    "median_z": {
      "latency": -0.1,
      "packet_loss": -0.1,
      "dl_throughput": -0.0,
      "rrc_success": -0.1,
      "drop_rate": -0.1
    },
    "z_change_second_half_vs_first_half": {
      "latency": -0.0,
      "packet_loss": -0.0,
      "dl_throughput": 0.1,
      "rrc_success": -1.3,
      "drop_rate": -0.0
    },
    "median_availability_pct": 100.0
  },
  "impact": {
    "n_impacted_cells": 528,
    "n_impacted_sites": 107,
    "regions": [
      "VIC"
    ],
    "est_affected_subscribers_total": 104470,
    "by_region_segment": [
      {
        "region_code": "VIC",
        "segment": "urban",
        "n_cells": 318,
        "est_affected_subscribers": 80200,
        "n_cells_without_user_data": 0
      },
      {
        "region_code": "VIC",
        "segment": "suburban",
        "n_cells": 129,
        "est_affected_subscribers": 18940,
        "n_cells_without_user_data": 0
      },
      {
        "region_code": "VIC",
        "segment": "rural",
        "n_cells": 72,
        "est_affected_subscribers": 4900,
        "n_cells_without_user_data": 0
      },
      {
        "region_code": "VIC",
        "segment": "remote",
        "n_cells": 9,
        "est_affected_subscribers": 430,
        "n_cells_without_user_data": 0
      }
    ],
    "estimate_method": "max connected users per impacted cell over the last hour of visible 1-minute windows, rounded to 10",
    "sessions_last_15min": {
      "window_minutes": 15,
      "sampled_sessions": 394,
      "sampled_failed_or_dropped": 11,
      "sampled_no_service": 0,
      "xdr_sample_rate": 0.01,
      "est_failed_or_dropped_sessions": 1100
    }
  },
  "customer_areas": [
    "Melbourne",
    "Geelong"
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
  "likely_root_cause": "uncertain",
  "fault_hypothesis": "UNCERTAIN",
  "confidence": "low",
  "summary": "The current evidence does not single out one suspect cleanly. The top-ranked AMF-VIC-01 has a live CORE_CPU_OVERLOAD alarm and all 528 impacted cells show degraded service, but the KPI pattern is dominated by poor RRC success with little latency/loss change, which is not a clean match for the listed runbooks and also overlaps with its child UPF-VIC-01 and downstream AGG-VIC-01. Continued KPI sampling over the next few minutes, plus AMF and transport counters, would help confirm whether this is an AMF signalling issue or a broader downstream problem.",
  "evidence": [
    {
      "statement": "AMF-VIC-01 is the top-ranked suspect with ranker_score 1.0 and one active alarm, CORE_CPU_OVERLOAD.",
      "context_fields": [
        "suspects[0].element_id",
        "suspects[0].ranker_score",
        "suspects[0].signals.n_alarms",
        "alarms[0].alarm_code",
        "alarms[0].active"
      ]
    },
    {
      "statement": "All 528 impacted cells are attributed to AMF-VIC-01, and its impacted_children_fraction is 1.0 for its only child UPF-VIC-01.",
      "context_fields": [
        "suspects[0].signals.n_impacted_cells",
        "suspects[0].signals.impacted_children_fraction",
        "suspects[0].neighbourhood.impacted_children",
        "suspects[0].neighbourhood.n_impacted_desc_cells"
      ]
    },
    {
      "statement": "The impacted KPI pattern shows share_cells_degraded_latest_window 1.0 and median_z.rrc_success -0.1, while latency and packet loss median z are both -0.1.",
      "context_fields": [
        "kpi.share_cells_degraded_latest_window",
        "kpi.median_z.rrc_success",
        "kpi.median_z.latency",
        "kpi.median_z.packet_loss"
      ]
    },
    {
      "statement": "The second-ranked suspect UPF-VIC-01 has the same impacted-cell count of 528, but no alarms are listed on it.",
      "context_fields": [
        "suspects[1].element_id",
        "suspects[1].ranker_score",
        "suspects[1].signals.n_impacted_cells",
        "suspects[1].signals.n_alarms"
      ]
    },
    {
      "statement": "AGG-VIC-01 is a plausible downstream contributor because it has 69 impacted cells and is an ancestor path element under UPF-VIC-01, but it has no alarms and only covers 13% of the case.",
      "context_fields": [
        "suspects[2].element_id",
        "suspects[2].signals.n_impacted_cells",
        "suspects[2].signals.coverage_of_case",
        "suspects[2].neighbourhood.ancestors",
        "suspects[2].signals.n_alarms"
      ]
    }
  ],
  "recommended_next_steps": [
    "Check AMF-VIC-01 CPU and signalling counters, and verify whether the CORE_CPU_OVERLOAD condition is persisting or worsening.",
    "Compare AMF-VIC-01 attach/RRC signalling rates against the last few KPI windows to see whether the RRC success drop broadens further.",
    "Review UPF-VIC-01 and AGG-VIC-01 transport and session counters to determine whether the degradation is actually downstream rather than AMF-led.",
    "Watch the next KPI windows for changes in rrc_success, latency, and packet loss to see whether the pattern separates into a core-signalling issue or a transport issue.",
    "If customer impact remains at this scale, prepare major-incident communications and escalation for the Melbourne & Victoria region."
  ],
  "customer_impact": {
    "estimated_affected_subscribers": 104470,
    "impacted_cells": 528,
    "impacted_sites": 107,
    "description": "Customers in Melbourne & Victoria, mainly urban and suburban, are seeing degraded mobile service across 528 cells."
  },
  "alternative_suspects": [
    "UPF-VIC-01",
    "AGG-VIC-01"
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
  "Banksia Mobile: You may have intermittent mobile service in Melbourne and Geelong. Sorry. We'll keep you updated."
]
```

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
    "ranker_model_version": "4",
    "ranker_alert_threshold": 0.32,
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
  "summary": "The incident is most consistent with SITE-VIC-00095 losing mains power and going dark: it has MAINS_FAILURE, BATTERY_LOW, and NE_UNREACHABLE alarms, and all 3 cells in the site subtree are silent. The site is the top-ranked suspect and its impacted_children_fraction is 1.0, while the KPIs for the impacted cells do not show a separate backhaul-degradation pattern; continue to watch whether battery depletion worsens while recovery is attempted.",
  "evidence": [
    {
      "statement": "SITE-VIC-00095 has active MAINS_FAILURE, BATTERY_LOW, and NE_UNREACHABLE alarms.",
      "context_fields": [
        "alarms[0].element_id",
        "alarms[0].alarm_code",
        "alarms[1].element_id",
        "alarms[1].alarm_code",
        "alarms[2].element_id",
        "alarms[2].alarm_code",
        "alarm_summary.n_active"
      ]
    },
    {
      "statement": "SITE-VIC-00095 has 3 impacted children, and all 3 are impacted children cells.",
      "context_fields": [
        "suspects[0].signals.n_impacted_cells",
        "suspects[0].signals.impacted_children_fraction",
        "suspects[0].neighbourhood.impacted_children",
        "suspects[0].neighbourhood.n_impacted_children"
      ]
    },
    {
      "statement": "SITE-VIC-00095 is silent across its entire subtree, with silent_fraction 1.0 and impacted_fraction 1.0.",
      "context_fields": [
        "suspects[0].signals.silent_fraction",
        "suspects[0].signals.impacted_fraction"
      ]
    },
    {
      "statement": "The site's parent backhaul link BH-VIC-0041 is listed in the neighbourhood, but the site-level alarms are directly on SITE-VIC-00095.",
      "context_fields": [
        "suspects[0].neighbourhood.parent",
        "alarms[0].element_id",
        "alarms[1].element_id",
        "alarms[2].element_id"
      ]
    },
    {
      "statement": "The impacted area is 1 site and 3 cells, with an estimated 300 affected subscribers in VIC suburban cells.",
      "context_fields": [
        "impact.n_impacted_sites",
        "impact.n_impacted_cells",
        "impact.est_affected_subscribers_total",
        "impact.by_region_segment[0].segment",
        "impact.by_region_segment[0].n_cells"
      ]
    }
  ],
  "recommended_next_steps": [
    "Confirm the mains outage and battery status for SITE-VIC-00095; verify whether generator support is available.",
    "Check the site's remaining battery runtime and priority load status immediately because BATTERY_LOW is already active.",
    "Attempt remote recovery actions for the site management link if available, then verify whether NE_UNREACHABLE clears.",
    "Dispatch field technicians to SITE-VIC-00095 if power cannot be restored remotely.",
    "Monitor the three impacted child cells under SITE-VIC-00095 to confirm they recover together and that neighbouring sites absorb traffic.",
    "If outage duration extends, update incident communications for the estimated 300 affected subscribers in Melbourne & Victoria."
  ],
  "customer_impact": {
    "estimated_affected_subscribers": 300,
    "impacted_cells": 3,
    "impacted_sites": 1,
    "description": "About 300 subscribers in Melbourne & Victoria suburban coverage are affected by a single silent site with 3 impacted 4G cells."
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
  "Banksia Mobile: No mobile service in Melbourne and Victoria. Sorry for the disruption. We'll update you."
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
    "ranker_model_version": "4",
    "ranker_alert_threshold": 0.32,
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
      "ranker_score": 0.0,
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
  "summary": "The pattern fits an aggregation-router failure at AGG-WA-04: the router is NODE_DOWN, its upstream UPF-WA-01 has GTPU_PATH_FAILURE towards it, and all 36 impacted cells behind the router are degraded with service-down alarms on the dependent sites. The impacted footprint spans 7 sites and 3,030 estimated subscribers across Perth & South West WA; this is not a planned change, so the next check is router reachability/power and failover options.",
  "evidence": [
    {
      "statement": "AGG-WA-04 is the top-ranked suspect with ranker_score 1.0 and has a critical NODE_DOWN alarm active.",
      "context_fields": [
        "suspects[0].element_id",
        "suspects[0].ranker_score",
        "suspects[0].signals.n_alarms",
        "suspects[0].signals.n_critical_alarms",
        "alarms[7].element_id",
        "alarms[7].alarm_code",
        "alarms[7].alarm_severity",
        "alarms[7].active"
      ]
    },
    {
      "statement": "UPF-WA-01 has an active GTPU_PATH_FAILURE alarm that points towards AGG-WA-04.",
      "context_fields": [
        "alarms[8].element_id",
        "alarms[8].alarm_code",
        "alarms[8].alarm_severity",
        "alarms[8].text"
      ]
    },
    {
      "statement": "AGG-WA-04's neighbourhood shows 3 impacted backhaul children and 36 impacted descendant cells.",
      "context_fields": [
        "suspects[0].neighbourhood.n_impacted_children",
        "suspects[0].neighbourhood.impacted_children",
        "suspects[0].neighbourhood.n_impacted_desc_cells"
      ]
    },
    {
      "statement": "The impacted backhaul links BH-WA-0017, BH-WA-0018 and BH-WA-0019 are all up to LINK_DOWN with service down.",
      "context_fields": [
        "alarms[3].element_id",
        "alarms[4].element_id",
        "alarms[6].element_id",
        "alarms[3].alarm_code",
        "alarms[4].alarm_code",
        "alarms[6].alarm_code",
        "alarms[3].service_down",
        "alarms[4].service_down",
        "alarms[6].service_down"
      ]
    },
    {
      "statement": "The KPI summary shows all 36 cells degraded in the latest window, with median availability_pct 100.0 and no silent cells.",
      "context_fields": [
        "kpi.n_cells",
        "kpi.share_cells_degraded_latest_window",
        "kpi.median_availability_pct",
        "kpi.n_silent_cells"
      ]
    },
    {
      "statement": "The incident is not in a planned maintenance window and the estimated impact is 3,030 subscribers across 7 sites in WA.",
      "context_fields": [
        "maintenance.in_planned_window",
        "impact.est_affected_subscribers_total",
        "impact.n_impacted_sites",
        "impact.regions"
      ]
    }
  ],
  "recommended_next_steps": [
    "Check AGG-WA-04 reachability, power, and line-card status; attempt remote recovery or failover if available.",
    "Verify whether the NODE_DOWN on AGG-WA-04 cleared any protection or redundant path for BH-WA-0017, BH-WA-0018, and BH-WA-0019.",
    "Open an urgent transport/vendor ticket for the aggregation router fault and the three LINK_DOWN backhaul links.",
    "Monitor whether the 36 impacted cells recover service as the router comes back; confirm dependent sites clear S1_NG_LINK_FAILURE.",
    "If remote recovery fails, dispatch field/transport support for AGG-WA-04 and escalate as a major incident because 3,030 subscribers are estimated affected."
  ],
  "customer_impact": {
    "estimated_affected_subscribers": 3030,
    "impacted_cells": 36,
    "impacted_sites": 7,
    "description": "Customers in Perth & South West WA are seeing service loss or severe degradation across 36 cells at 7 sites, affecting both urban and suburban segments."
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
  "Banksia Mobile: Intermittent mobile service in Perth and Northam. Sorry for the disruption. We'll update you."
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
    "ranker_model_version": "4",
    "ranker_alert_threshold": 0.32,
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
  "summary": "The evidence points to a single cell outage on CELL-NQL-00012-5G2: it is the only impacted cell, is currently unavailable, and has active CELL_OUT_OF_SERVICE and RRU_FAILURE alarms. The parent site and upstream elements do not show matching failure patterns; if this is not a persistent hardware fault, the next KPI windows should confirm whether the cell remains silent after a reset attempt.",
  "evidence": [
    {
      "statement": "CELL-NQL-00012-5G2 has availability_pct_now 0.0 and attach_success_pct_now 0.0, with one impacted cell and one impacted descendant cell.",
      "context_fields": [
        "suspects[0].signals.availability_pct_now",
        "suspects[0].signals.attach_success_pct_now",
        "suspects[0].signals.n_impacted_cells",
        "suspects[0].neighbourhood.n_impacted_desc_cells"
      ]
    },
    {
      "statement": "The cell has 2 active alarms, including CELL_OUT_OF_SERVICE marked critical with service_down true and RRU_FAILURE marked major.",
      "context_fields": [
        "suspects[0].signals.n_alarms",
        "alarms[0].alarm_code",
        "alarms[0].alarm_severity",
        "alarms[0].service_down",
        "alarms[1].alarm_code",
        "alarms[1].alarm_severity"
      ]
    },
    {
      "statement": "The parent site SITE-NQL-00012 exists in the neighbourhood, but the suspect is the cell itself; the site is not listed as having an active alarm.",
      "context_fields": [
        "suspects[0].neighbourhood.parent.element_id",
        "alarms[0].element_id",
        "alarms[1].element_id"
      ]
    },
    {
      "statement": "The impact is limited to 1 impacted cell and 1 impacted site in region NQL.",
      "context_fields": [
        "impact.n_impacted_cells",
        "impact.n_impacted_sites",
        "impact.regions"
      ]
    },
    {
      "statement": "No planned maintenance is in progress for the impacted element.",
      "context_fields": [
        "maintenance.in_planned_window",
        "suspects[0].signals.in_maintenance"
      ]
    }
  ],
  "recommended_next_steps": [
    "Check CELL-NQL-00012-5G2 RRU and radio alarms, including RF/VSWR status.",
    "Attempt a remote cell lock/unlock or RRU reset on CELL-NQL-00012-5G2.",
    "Check the other sectors on SITE-NQL-00012 to confirm they remain healthy.",
    "If the reset fails or the cell does not recover, dispatch field tech to SITE-NQL-00012.",
    "Monitor whether neighbouring cells absorb traffic and whether availability returns in the next KPI windows."
  ],
  "customer_impact": {
    "estimated_affected_subscribers": 540,
    "impacted_cells": 1,
    "impacted_sites": 1,
    "description": "About 540 subscribers in North Queensland, concentrated in one urban cell around Townsville, are affected by a single-cell service outage."
  },
  "alternative_suspects": []
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
  "Banksia Mobile: You may have intermittent mobile service in Townsville, North Queensland. Sorry for the disruption. We'll update you."
]
```

## Live open incident `RCA-1073d4d88aa7e05b` (job `banksia-genai-assistant`, no ground truth)

Generated 2026-11-06T01:59:36.148Z: `CELL-VIC-00062-5G2` (high, `CELL_OUTAGE`).

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
    "ranker_model_version": "4",
    "ranker_alert_threshold": 0.32,
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
  "summary": "The evidence points to a single-cell outage on CELL-VIC-00062-5G2: it is fully impacted with 0.0% availability, 0.0% attach success, 0.0% PRB utilisation, and severe radio/service KPI collapse while its site context is otherwise not showing a broader site dark pattern. There are no active alarms in scope, so the strongest confirmation would be whether the cell remains silent or recovers in the next KPI windows, and whether the RRU/radio path shows a local fault.",
  "evidence": [
    {
      "statement": "CELL-VIC-00062-5G2 has 1.0 impacted_fraction, 1.0 degraded_fraction, 0.0% availability, and 0.0% attach success.",
      "context_fields": [
        "suspects[0].signals.impacted_fraction",
        "suspects[0].signals.degraded_fraction",
        "suspects[0].signals.availability_pct_now",
        "suspects[0].signals.attach_success_pct_now"
      ]
    },
    {
      "statement": "Its radio/service KPIs are severely collapsed, including dl_throughput_z_now of -9.0 and rrc_success_z_now of -496.5.",
      "context_fields": [
        "suspects[0].signals.dl_throughput_z_now",
        "suspects[0].signals.rrc_success_z_now"
      ]
    },
    {
      "statement": "The cell has n_alarms of 0, n_critical_alarms of 0, and n_service_down_alarms of 0.",
      "context_fields": [
        "suspects[0].signals.n_alarms",
        "suspects[0].signals.n_critical_alarms",
        "suspects[0].signals.n_service_down_alarms"
      ]
    },
    {
      "statement": "The site ancestor SITE-VIC-00062 shows only 0.17 parent_impacted_fraction for this suspect, which does not look like a whole-site outage pattern.",
      "context_fields": [
        "suspects[0].neighbourhood.parent.element_id",
        "suspects[0].signals.parent_impacted_fraction"
      ]
    },
    {
      "statement": "The incident has 1 impacted cell, 1 impacted site, and estimated affected subscribers total of 0.",
      "context_fields": [
        "impact.n_impacted_cells",
        "impact.n_impacted_sites",
        "impact.est_affected_subscribers_total"
      ]
    }
  ],
  "recommended_next_steps": [
    "Check CELL-VIC-00062-5G2 radio path for local CELL_OUTAGE indicators, including RRU/radio health and VSWR if available.",
    "Attempt a remote cell lock/unlock or RRU reset on CELL-VIC-00062-5G2.",
    "Verify the other sectors/cells at SITE-VIC-00062 remain healthy and are not showing a broader site-wide failure.",
    "If the cell does not recover after remote action, dispatch field support to SITE-VIC-00062.",
    "Monitor the next KPI windows to confirm whether availability and attach success recover or the cell remains silent."
  ]
}
```

## SMS drafts

```json
[
  {
    "region_code": "VIC",
    "text": "Banksia Mobile: No mobile service and calls and data may drop or fail in Melbourne and Victoria. Sorry. We'll update you.",
    "status": "draft",
    "requires_human_approval": "true",
    "sent_at": null
  },
  {
    "region_code": "VIC",
    "text": "Banksia Mobile: No mobile service in Melbourne & Victoria. Calls and data may drop or fail. Sorry. We'll keep you updated.",
    "status": "draft",
    "requires_human_approval": "true",
    "sent_at": null
  }
]
```
