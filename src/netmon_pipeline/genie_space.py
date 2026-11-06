"""Definition of the Banksia NOC Genie space, as code (step 5, docs/genie_space.md).

`build_space(catalog)` returns the serialized-space body the Genie API takes (version 2: tables, column configs,
general instructions, join hints, SQL snippets, trusted example SQL, sample questions and benchmark questions).
`scripts/genie_build_space.py` writes it to `resources/genie/noc_space.geniespace.json`, which the bundle's
`genie_spaces` resource (`resources/genie.yml`) deploys. A test checks the committed file matches this module.

Governance: every operational table is a `netmon_noc` view that applies the regional row filter for the user who
asks (Genie runs queries as the asking user), and none of them carries IMSI / MSISDN (no session table is in the
space). No ground truth: nothing in the space reads the `netmon_eval` schema (ground truth is used only to verify
the build, in the evidence scripts), which tests/test_no_ground_truth_surface.py enforces.
"""

from __future__ import annotations

import hashlib
import json

NOC = "netmon_noc"

TITLE = "Banksia NOC: incidents, network health and detection KPIs"
DESCRIPTION = (
    "Ask about Banksia Mobile's live network incidents: which element is failing, the root-cause ranker's top-3 "
    "suspects, element health along the core > aggregation router > backhaul > cell site > cell chain, customer "
    "impact by region (aggregate counts only), the Gen AI root-cause summaries and outage SMS drafts, and the "
    "detection KPIs (time to detect, share detected within 5 minutes). Regional NOC users only see their own "
    "region; subscriber identifiers are never available here."
)

# (view, description, {column: description}, entity-matching columns)
TABLES: list[tuple[str, str, str, dict[str, str], list[str]]] = [
    (NOC, "open_incidents",
     "One row per OPEN network incident: the root-cause ranker's alert on a case, with its top-3 suspected root "
     "elements and scores (suspect_1 = most likely root cause). Same data the topology app reads from Lakebase.",
     {"detected_ts": "UTC time the incident was opened (ranker alert)",
      "suspect_1_id": "Most likely root-cause element; use this for 'failing element' / 'root cause' questions"},
     ["region_code", "suspect_1_type", "status"]),
    (NOC, "element_status",
     "Live health of every network element (cell, cell site, backhaul link, aggregation router, UPF, AMF): state "
     "down / degraded / impacted / alarm / ok, impacted cell counts, alarms and the highest root-cause score.",
     {"state": "down > degraded > impacted > alarm > ok (worst first)",
      "rca_score": "Highest root-cause probability of this element in any current case (0-1)"},
     ["element_type", "state", "region_code"]),
    (NOC, "incident_ai_summary",
     "Latest Gen AI NOC summary per open incident: likely root cause, fault hypothesis, confidence, runbook next "
     "steps, estimated affected subscribers (aggregate) and the customer outage SMS draft (never sent).",
     {"est_affected_subscribers": "Estimated affected subscribers for the incident (aggregate count)",
      "fault_hypothesis": "Fault class, e.g. SITE_POWER_OUTAGE, BACKHAUL_DEGRADATION, CELL_OUTAGE, LONG_HAUL_FIBRE_CUT"},
     ["fault_hypothesis", "confidence", "region_code"]),
    (NOC, "customer_sms_drafts",
     "Every proactive customer outage SMS draft written for an incident (one per incident and region). Drafts "
     "only: the system never sends; approval decisions are made in the topology app.",
     {}, ["status", "region_code"]),
    (NOC, "incident_detection_times",
     "Operational detection timing per open incident from the build's own telemetry (no ground truth): first "
     "anomaly on the top-1 suspect's subtree, first customer-impact detection, time to detect (seconds) and "
     "whether it was within the 5-minute SLA.",
     {"time_to_detect_s": "Operational time to detect in seconds (MTTD = average of this)",
      "detected_within_5min": "True when time_to_detect_s <= 300 (the NOC's 5-minute SLA)"},
     ["region_code"]),
    (NOC, "gold_impact_detections",
     "Per-record customer-impact detections (degraded KPI minute of a cell, or an element-down alarm) from the "
     "streaming pipeline, with detection time, rules fired (flags) and the element's ancestors.",
     {"signal_source": "kpi (degraded cell KPI record) or alarm (element-down alarm)",
      "source_run": "Generator run; 'stream' is the live feed, history* are backfills"},
     ["signal_source", "element_type", "region_code", "source_run"]),
    (NOC, "silver_topology_nodes",
     "Network inventory: every element with type, name, parent, region, coordinates (lat / lon), vendor, "
     "technology (4G / 5G), urbanity and backhaul transport medium.",
     {"parent_id": "Parent element: CELL > SITE > BACKHAUL_LINK > AGG_ROUTER > UPF_SGW > AMF_MME",
      "name": "Human-readable element name, e.g. 'Sydney & NSW site 105'"},
     ["element_type", "region", "region_code", "urbanity", "transport_medium", "technology"]),
    (NOC, "gold_cell_health_5m",
     "5-minute cell KPI health windows: availability, attach / RRC success, latency, packet loss, throughput, "
     "drop rate, their baseline z-scores and whether the cell was degraded.",
     {"is_degraded": "True when the cell breached a detection rule in the window"},
     ["region_code", "source_run"]),
    (NOC, "silver_alarms",
     "Network alarms (fault management events) with severity, alarm code, element and its ancestors.",
     {"is_service_down": "True for element-down alarm codes (NODE_DOWN, NE_UNREACHABLE, CELL_OUT_OF_SERVICE, ...)"},
     ["alarm_code", "severity", "element_type", "region_code"]),
]

INSTRUCTIONS = """\
You answer questions from Banksia Mobile's Network Operations Centre (NOC). All data is synthetic.

Network hierarchy (parent_id chains upward): CELL (a 4G/5G sector) > SITE (cell site / tower) > BACKHAUL_LINK
(fibre or microwave backhaul) > AGG_ROUTER (aggregation router) > UPF_SGW (core user plane) > AMF_MME (core control
plane, "the AMF" / "the MME"). "Core" means AMF_MME and UPF_SGW. "Cell site" or "tower" means SITE. "Backhaul" means
BACKHAUL_LINK. "Router" means AGG_ROUTER.

Regions: NSW = Sydney & NSW, VIC = Melbourne & Victoria, NQL = North Queensland, WA = Perth & South West WA. Filter
with region_code. Users only see the regions they are entitled to; never claim a region has no incidents when the
user may simply not be allowed to see it: say "in the regions you can see".

Incidents: open_incidents has one row per open incident; suspect_1_id is the most likely root-cause ("failing")
element, suspect_2/3 are the alternatives with lower scores. "Top-3 suspects" = suspect_1..3 with their scores. The
Gen AI explanation is in incident_ai_summary (same incident_id); always present the ranker's suspects first and the
AI summary as supporting text.

Time: all timestamps are UTC. The data is a replayed feed from 2026-10-08/09, so "now" / "currently" / "latest"
means max(last_scored_ts) of open_incidents, never current_timestamp(). Convert to local time with
from_utc_timestamp(ts, timezone) using silver_topology_nodes.timezone (NSW Australia/Sydney, VIC Australia/Melbourne,
NQL Australia/Brisbane, WA Australia/Perth) when the user asks for local time.

KPIs:
- Time to detect (TTD) per incident = incident_detection_times.time_to_detect_s (seconds). MTTD = AVG of it.
  "Detected within 5 minutes" = detected_within_5min (SLA 300 s). Report seconds and minutes. This operational TTD
  starts at the first anomaly visible in the telemetry, so for slowly ramping faults (backhaul degradation) the
  true time to detect is longer; mention that when the user asks about backhaul or about SLA compliance.
- Detection KPIs by fault type: group incident_detection_times joined to incident_ai_summary.fault_hypothesis
  (the assistant's fault class); this space has no scored / ground-truth figures, say so if asked for them.
- MTTR (mean time to repair / restore) cannot be computed: the space only holds currently open incidents, no
  resolved ones. Say so and offer the incident age instead (max(last_scored_ts) - detected_ts).
- Impacted subscribers: use incident_ai_summary.est_affected_subscribers (estimate, aggregate). Impacted cells:
  open_incidents.n_impacted_cells. There is no per-subscriber data in this space; refuse requests for IMSI, MSISDN,
  phone numbers or named customers.
- "Failing" / "worst" elements: element_status with state IN ('down','degraded'), ordered by state severity
  (down first) then rca_score DESC, then n_impacted_cells DESC.

Detections and KPI windows have several generator runs: default to source_run = 'stream' (the live feed) unless the
user asks about history.

SMS drafts are drafts: never describe one as sent. Drafts "waiting for approval" / "pending" are the CURRENT draft
of each open incident: incident_ai_summary.sms_draft_status = 'draft' (one per open incident).
customer_sms_drafts is the full draft history (several per incident, including superseded ones): use it only for
history questions such as "how many drafts were written".
"""

# Trusted example SQL (also used by Genie as patterns). Placeholder: {noc}.
EXAMPLE_SQL: list[tuple[str, str]] = [
    ("What is the time to detect for each open incident?",
     "SELECT incident_id, region_code, suspect_1_id, first_impact_signal_ts, first_detection_ts,\n"
     "       time_to_detect_s, round(time_to_detect_s / 60, 1) AS time_to_detect_min, detected_within_5min\n"
     "FROM {noc}.incident_detection_times\nORDER BY first_impact_signal_ts"),
    ("What share of open incidents was detected within 5 minutes, and what is the MTTD?",
     "SELECT count(*) AS n_incidents,\n"
     "       round(100 * avg(CASE WHEN detected_within_5min THEN 1 ELSE 0 END), 1) AS pct_detected_within_5min,\n"
     "       round(avg(time_to_detect_s), 1) AS mttd_s\nFROM {noc}.incident_detection_times"),
    ("What are the top failing network elements right now?",
     "SELECT element_id, element_type, region_code, state, round(rca_score, 2) AS rca_score, n_impacted_cells,\n"
     "       n_desc_cells, open_incident_id, suspect_rank\nFROM {noc}.element_status\n"
     "WHERE state IN ('down', 'degraded')\n"
     "ORDER BY CASE state WHEN 'down' THEN 0 ELSE 1 END, rca_score DESC NULLS LAST, n_impacted_cells DESC\nLIMIT 10"),
    ("How many subscribers are impacted by open incidents, by region?",
     "SELECT a.region_code, count(DISTINCT a.incident_id) AS open_incidents,\n"
     "       sum(a.est_affected_subscribers) AS est_affected_subscribers, sum(o.n_impacted_cells) AS impacted_cells\n"
     "FROM {noc}.incident_ai_summary a JOIN {noc}.open_incidents o ON o.incident_id = a.incident_id\n"
     "GROUP BY a.region_code ORDER BY est_affected_subscribers DESC"),
    ("What is the time to detect by fault type?",
     "SELECT a.fault_hypothesis, count(*) AS n_incidents, round(avg(d.time_to_detect_s), 1) AS mttd_s,\n"
     "       round(100 * avg(CASE WHEN d.detected_within_5min THEN 1 ELSE 0 END), 1) AS pct_detected_within_5min\n"
     "FROM {noc}.incident_detection_times d JOIN {noc}.incident_ai_summary a ON a.incident_id = d.incident_id\n"
     "GROUP BY a.fault_hypothesis ORDER BY mttd_s DESC"),
    ("Show the top-3 suspects of every open incident",
     "SELECT incident_id, region_code, detected_ts, suspect_1_id, round(suspect_1_score, 2) AS suspect_1_score,\n"
     "       suspect_2_id, round(suspect_2_score, 2) AS suspect_2_score, suspect_3_id,\n"
     "       round(suspect_3_score, 2) AS suspect_3_score, n_impacted_cells\n"
     "FROM {noc}.open_incidents ORDER BY detected_ts"),
    ("Which cell sites are down?",
     "SELECT s.element_id, n.name, s.region_code, s.n_desc_cells, s.n_impacted_cells, s.open_incident_id\n"
     "FROM {noc}.element_status s JOIN {noc}.silver_topology_nodes n ON n.element_id = s.element_id\n"
     "WHERE s.element_type = 'SITE' AND s.state = 'down' ORDER BY s.region_code, s.element_id"),
    ("What does the AI say caused each open incident and what should we do next?",
     "SELECT a.incident_id, a.region_code, o.suspect_1_id, a.likely_root_cause, a.fault_hypothesis, a.confidence,\n"
     "       a.summary, a.next_steps_json\nFROM {noc}.incident_ai_summary a\n"
     "JOIN {noc}.open_incidents o ON o.incident_id = a.incident_id ORDER BY o.detected_ts"),
]

SAMPLE_QUESTIONS = [
    "Which network element is failing in each open incident?",
    "What are the top-3 suspects for the incident on SITE-NSW-00105?",
    "How many subscribers are impacted by open incidents in each region?",
    "What is our MTTD and the share of incidents detected within 5 minutes?",
    "Which cell sites are down right now?",
    "Which backhaul links are degraded?",
    "What does the AI summary recommend for the North Queensland incident?",
    "Show the customer SMS drafts waiting for approval",
    "What is the time to detect by fault type?",
    "Which alarms were raised on SITE-NSW-00105 and its cells?",
]

# (alias / display name, sql)
MEASURES = [
    ("mttd_s", "MTTD (s)", "avg(incident_detection_times.time_to_detect_s)"),
    ("pct_detected_within_5min", "% detected within 5 min",
     "100 * avg(CASE WHEN incident_detection_times.detected_within_5min THEN 1 ELSE 0 END)"),
    ("est_affected_subscribers", "estimated affected subscribers", "sum(incident_ai_summary.est_affected_subscribers)"),
]
FILTERS = [
    ("live feed", "gold_impact_detections.source_run = 'stream'"),
    ("failing elements", "element_status.state IN ('down', 'degraded')"),
]
EXPRESSIONS = [
    ("detected_sydney_time", "detected (Sydney time)", "from_utc_timestamp(open_incidents.detected_ts, 'Australia/Sydney')"),
]

# (left, right, left_col, right_col, relationship)
JOINS = [
    ("open_incidents", "incident_ai_summary", "incident_id", "incident_id", "ONE_TO_ONE"),
    ("open_incidents", "incident_detection_times", "incident_id", "incident_id", "ONE_TO_ONE"),
    ("element_status", "open_incidents", "open_incident_id", "incident_id", "MANY_TO_ONE"),
    ("element_status", "silver_topology_nodes", "element_id", "element_id", "ONE_TO_ONE"),
    ("open_incidents", "silver_topology_nodes", "suspect_1_id", "element_id", "MANY_TO_ONE"),
    ("customer_sms_drafts", "open_incidents", "incident_id", "incident_id", "MANY_TO_ONE"),
    ("gold_impact_detections", "silver_topology_nodes", "element_id", "element_id", "MANY_TO_ONE"),
    ("gold_cell_health_5m", "silver_topology_nodes", "cell_id", "element_id", "MANY_TO_ONE"),
    ("silver_alarms", "silver_topology_nodes", "element_id", "element_id", "MANY_TO_ONE"),
]

# Benchmark: question, expected SQL. Run by scripts/genie_benchmark.py (Genie eval-run API); results in
# evidence/step5/02_genie_benchmark.md. Phrased differently from the example SQL above on purpose.
BENCHMARKS: list[tuple[str, str]] = [
    ("How many incidents are open?", "SELECT count(*) AS open_incidents FROM {noc}.open_incidents"),
    ("How many open incidents are there per region?",
     "SELECT region_code, count(*) AS open_incidents FROM {noc}.open_incidents GROUP BY region_code "
     "ORDER BY region_code"),
    ("What is the most likely failing element of incident RCA-c7276c3238a27971?",
     "SELECT suspect_1_id, suspect_1_type, suspect_1_score FROM {noc}.open_incidents "
     "WHERE incident_id = 'RCA-c7276c3238a27971'"),
    ("List the top-3 root-cause suspects with scores for the incident whose top suspect is SITE-NSW-00105",
     "SELECT incident_id, suspect_1_id, suspect_1_score, suspect_2_id, suspect_2_score, suspect_3_id, "
     "suspect_3_score FROM {noc}.open_incidents WHERE suspect_1_id = 'SITE-NSW-00105'"),
    ("What is the average time to detect across open incidents in seconds?",
     "SELECT round(avg(time_to_detect_s), 1) AS mttd_s FROM {noc}.incident_detection_times"),
    ("What percentage of open incidents were detected within 5 minutes?",
     "SELECT round(100 * avg(CASE WHEN detected_within_5min THEN 1 ELSE 0 END), 1) AS pct_within_5min "
     "FROM {noc}.incident_detection_times"),
    ("Which incident took the longest to detect?",
     "SELECT incident_id, time_to_detect_s FROM {noc}.incident_detection_times "
     "ORDER BY time_to_detect_s DESC LIMIT 1"),
    ("How many estimated subscribers are affected in NSW?",
     "SELECT sum(est_affected_subscribers) AS est_affected_subscribers FROM {noc}.incident_ai_summary "
     "WHERE region_code = 'NSW'"),
    ("Which region has the most estimated affected subscribers?",
     "SELECT region_code, sum(est_affected_subscribers) AS est_affected_subscribers "
     "FROM {noc}.incident_ai_summary GROUP BY region_code ORDER BY est_affected_subscribers DESC LIMIT 1"),
    ("How many network elements are down, by element type?",
     "SELECT element_type, count(*) AS n_down FROM {noc}.element_status WHERE state = 'down' "
     "GROUP BY element_type ORDER BY n_down DESC"),
    ("List the cell sites that are down",
     "SELECT element_id FROM {noc}.element_status WHERE element_type = 'SITE' AND state = 'down' "
     "ORDER BY element_id"),
    ("Which backhaul links are the top suspect of an open incident?",
     "SELECT incident_id, suspect_1_id FROM {noc}.open_incidents WHERE suspect_1_type = 'BACKHAUL_LINK' "
     "ORDER BY incident_id"),
    ("What fault does the AI assistant suspect for the North Queensland incident?",
     "SELECT incident_id, likely_root_cause, fault_hypothesis FROM {noc}.incident_ai_summary "
     "WHERE region_code = 'NQL'"),
    ("How many SMS drafts are waiting for approval?",
     "SELECT count(*) AS n_drafts FROM {noc}.incident_ai_summary WHERE sms_draft_status = 'draft'"),
    ("What is the average time to detect per region, in seconds?",
     "SELECT region_code, round(avg(time_to_detect_s), 1) AS mttd_s FROM {noc}.incident_detection_times "
     "GROUP BY region_code ORDER BY region_code"),
    ("What is the average time to detect for backhaul incidents?",
     "SELECT round(avg(d.time_to_detect_s), 1) AS mttd_s FROM {noc}.incident_detection_times d "
     "JOIN {noc}.open_incidents o ON o.incident_id = d.incident_id WHERE o.suspect_1_type = 'BACKHAUL_LINK'"),
    ("How many customer-impact detections did the live feed produce per signal source?",
     "SELECT signal_source, count(*) AS n_detections FROM {noc}.gold_impact_detections "
     "WHERE source_run = 'stream' GROUP BY signal_source ORDER BY signal_source"),
    ("Which element types does the aggregation router AGG-NSW-04 serve directly?",
     "SELECT element_type, count(*) AS n FROM {noc}.silver_topology_nodes WHERE parent_id = 'AGG-NSW-04' "
     "GROUP BY element_type"),
]

FORBIDDEN_IDENTIFIERS = ("silver_sessions", "bronze_", "netmon_eval", "eval_ttd_summary", "eval_gt_incidents",
                         "bronze_gt_incidents", "eval_incident_detection", "genai_eval_labels", "rca_training_labels")


def _id(*parts: str) -> str:
    """Deterministic 32-hex id, so the generated file only changes when the content does."""
    return hashlib.md5("\x1f".join(parts).encode()).hexdigest()  # noqa: S324 - an id, not security


def _lines(text: str) -> list[str]:
    """Genie stores text as a list of lines (with their newlines)."""
    parts = text.splitlines(keepends=True)
    return parts or [""]


def build_space(catalog: str) -> dict:
    noc = f"{catalog}.{NOC}"

    def fill(sql: str) -> str:
        return sql.format(noc=noc)

    tables = []
    for schema, name, desc, cols, entity in TABLES:
        col_names = sorted(set(cols) | set(entity))
        column_configs = []
        for c in col_names:
            cfg: dict = {"column_name": c}
            if c in cols:
                cfg["description"] = [cols[c]]
            if c in entity:
                cfg["enable_format_assistance"] = True
                cfg["enable_entity_matching"] = True
            column_configs.append(cfg)
        t = {"identifier": f"{catalog}.{schema}.{name}", "description": [desc]}
        if column_configs:
            t["column_configs"] = column_configs
        tables.append(t)
    tables.sort(key=lambda t: t["identifier"])

    def by_id(items: list[dict]) -> list[dict]:
        return sorted(items, key=lambda x: x["id"])

    ident = {name: f"{catalog}.{schema}.{name}" for schema, name, *_ in TABLES}
    joins = by_id([{
        "id": _id("join", lt, rt, lc, rc),
        "left": {"identifier": ident[lt], "alias": lt},
        "right": {"identifier": ident[rt], "alias": rt},
        "sql": [f"`{lt}`.`{lc}` = `{rt}`.`{rc}`", f"--rt=FROM_RELATIONSHIP_TYPE_{rel}--"],
    } for lt, rt, lc, rc, rel in JOINS])

    return {
        "version": 2,
        "config": {"sample_questions": by_id([{"id": _id("sample", q), "question": [q]} for q in SAMPLE_QUESTIONS])},
        "data_sources": {"tables": tables},
        "instructions": {
            "text_instructions": [{"id": _id("instructions"), "content": _lines(INSTRUCTIONS)}],
            "example_question_sqls": by_id([{"id": _id("example", q), "question": [q], "sql": _lines(fill(s))}
                                            for q, s in EXAMPLE_SQL]),
            "join_specs": joins,
            "sql_snippets": {
                "filters": by_id([{"id": _id("filter", n), "sql": [s], "display_name": n} for n, s in FILTERS]),
                "expressions": by_id([{"id": _id("expr", a), "alias": a, "sql": [s], "display_name": n}
                                      for a, n, s in EXPRESSIONS]),
                "measures": by_id([{"id": _id("measure", a), "alias": a, "sql": [s], "display_name": n}
                                   for a, n, s in MEASURES]),
            },
        },
        "benchmarks": {"questions": by_id([{
            "id": _id("bench", q), "question": [q],
            "answer": [{"format": "SQL", "content": _lines(fill(s))}]} for q, s in BENCHMARKS])},
    }


def to_json(catalog: str) -> str:
    return json.dumps(build_space(catalog), indent=2) + "\n"


def benchmark_sql(catalog: str) -> dict[str, str]:
    """question -> expected SQL (catalog-qualified)."""
    noc = f"{catalog}.{NOC}"
    return {q: s.format(noc=noc) for q, s in BENCHMARKS}
