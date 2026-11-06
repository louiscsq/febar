-- Step 5: region-filtered serving views for the NOC Genie space and the topology app (docs/genie_space.md,
-- docs/topology_app.md). Same rule as 02_noc_views.sql: every view keeps a region_code and applies
-- ${gov}.region_filter, evaluated for the user who queries the view (Genie and the app's analytics panels query
-- as the signed-in user), so noc_national sees every region, noc_region_<code> only its own, anyone else nothing.
-- The existing role grants already cover them: both roles hold SELECT on the whole ${noc_schema} schema.
--
-- None of these views reads ${eval_schema} (ground truth) or silver_sessions (subscriber identifiers). Subscriber
-- impact is only ever an aggregate count.

CREATE OR REPLACE VIEW ${noc_schema}.open_incidents (
  incident_id COMMENT 'Open incident reference (RCA-<hash>), one per alerting root-cause case',
  source_run COMMENT 'Generator run the telemetry came from (stream = live demo feed)',
  region_code COMMENT 'Banksia region code (NSW, VIC, NQL, WA, ...)',
  detected_ts COMMENT 'UTC time the root-cause ranker first alerted on this case (incident opened)',
  last_scored_ts COMMENT 'UTC decision time of the latest scoring run',
  status COMMENT 'open while the alert is active at the latest decision time',
  suspect_1_id COMMENT 'Top-1 suspected root-cause network element (highest ranker score)',
  suspect_1_type COMMENT 'Element type of suspect 1 (CELL, SITE, BACKHAUL_LINK, AGG_ROUTER, UPF_SGW, AMF_MME)',
  suspect_1_score COMMENT 'Ranker probability that suspect 1 is the root cause (0-1)',
  suspect_2_id, suspect_2_type, suspect_2_score,
  suspect_3_id, suspect_3_type, suspect_3_score,
  n_impacted_cells COMMENT 'Cells degraded or silent in the case at the latest decision time',
  n_candidates COMMENT 'Candidate elements the ranker scored for this case',
  model_version COMMENT 'UC version of rca_ranker that scored it (the champion)'
)
COMMENT 'Region-filtered open incidents with the RCA ranker top-3 suspects (source: netmon_rca.open_incidents, also served from Lakebase)'
AS SELECT incident_id, source_run, region_code, detected_ts, last_scored_ts, status,
          suspect_1_id, suspect_1_type, suspect_1_score, suspect_2_id, suspect_2_type, suspect_2_score,
          suspect_3_id, suspect_3_type, suspect_3_score, n_impacted_cells, n_candidates, model_version
FROM ${rca_schema}.open_incidents
WHERE ${gov}.region_filter(region_code);

CREATE OR REPLACE VIEW ${noc_schema}.element_status (
  element_id COMMENT 'Network element (AMF_MME > UPF_SGW > AGG_ROUTER > BACKHAUL_LINK > SITE > CELL)',
  element_type, parent_id COMMENT 'Parent element in the topology tree', region_code,
  n_desc_cells COMMENT 'Cells below this element', n_impacted_cells COMMENT 'Of those, degraded or silent now',
  impacted_fraction, silent_fraction COMMENT 'Share of descendant cells that stopped reporting (dark)',
  n_alarms, n_service_down_alarms,
  rca_score COMMENT 'Highest root-cause score of this element in any current case',
  state COMMENT 'down (>=80% descendant cells silent or service-down alarm), degraded (>=50% impacted), impacted, alarm or ok',
  open_incident_id COMMENT 'Open incident this element is a top-3 suspect of, if any',
  suspect_rank COMMENT '1-3 within that incident',
  last_updated_ts, model_version
)
COMMENT 'Region-filtered live health state of every network element (source: netmon_rca.element_status, also served from Lakebase)'
AS SELECT element_id, element_type, parent_id, region_code, n_desc_cells, n_impacted_cells, impacted_fraction,
          silent_fraction, n_alarms, n_service_down_alarms, rca_score, state, open_incident_id, suspect_rank,
          last_updated_ts, model_version
FROM ${rca_schema}.element_status
WHERE ${gov}.region_filter(region_code);

CREATE OR REPLACE VIEW ${noc_schema}.incident_ai_summary (
  incident_id, region_code,
  generated_at COMMENT 'UTC time the Gen AI assistant wrote this summary',
  likely_root_cause COMMENT 'Element the assistant names as root cause (always one of the ranker suspects, or uncertain)',
  fault_hypothesis COMMENT 'Assistant fault class, e.g. SITE_POWER_OUTAGE, BACKHAUL_DEGRADATION, CELL_OUTAGE',
  confidence COMMENT 'high / medium / low',
  summary COMMENT 'Root-cause summary for the NOC engineer',
  next_steps_json COMMENT 'Runbook next steps (JSON array)',
  est_affected_subscribers COMMENT 'Estimated affected subscribers (aggregate count, peak connected users of impacted cells)',
  impacted_cells, impacted_sites, impact_description,
  sms_draft_text COMMENT 'Proactive customer outage SMS DRAFT (never sent by the system; needs human approval)',
  sms_draft_status COMMENT 'draft until a human decides in the topology app',
  generated_by COMMENT 'llm or fallback', noc_prompt_version
)
COMMENT 'Region-filtered latest Gen AI NOC summary and SMS draft per open incident (source: netmon_genai.incident_ai_latest)'
AS SELECT incident_id, region_code, generated_at, likely_root_cause, fault_hypothesis, confidence, summary,
          next_steps_json, est_affected_subscribers, impacted_cells, impacted_sites, impact_description,
          sms_draft_text, sms_draft_status, generated_by, noc_prompt_version
FROM ${genai_schema}.incident_ai_latest
WHERE ${gov}.region_filter(region_code);

CREATE OR REPLACE VIEW ${noc_schema}.customer_sms_drafts (
  draft_id, incident_id, region_code, generated_at,
  status COMMENT 'Always draft in this table: the system never sends; reviews are recorded by the app in Lakebase',
  requires_human_approval, text COMMENT 'SMS draft text (no subscriber data)', chars,
  est_affected_customers COMMENT 'Aggregate count of customers the notice would go to', generated_by
)
COMMENT 'Region-filtered history of every customer outage SMS draft (source: netmon_genai.customer_notice_drafts)'
AS SELECT draft_id, incident_id, region_code, generated_at, status, requires_human_approval, text, chars,
          est_affected_customers, generated_by
FROM ${genai_schema}.customer_notice_drafts
WHERE ${gov}.region_filter(region_code);

-- Operational detection timing per open incident, from the build's own telemetry only (no ground truth):
-- the first customer-impact detection row (step 2) on the top-1 suspect or anything below it, in the two hours
-- before the incident opened. available_ts = evidence arrival + measured pipeline latency (docs/pipeline.md).
CREATE OR REPLACE VIEW ${noc_schema}.incident_detection_times (
  incident_id, source_run, region_code,
  suspect_1_id COMMENT 'Top-1 suspect the timing is measured on (its subtree)',
  first_impact_signal_ts COMMENT 'Start of the first anomalous KPI period or alarm on the suspect subtree (UTC)',
  first_detection_ts COMMENT 'When the first customer-impact detection was available to the NOC (UTC)',
  incident_detected_ts COMMENT 'When the ranker opened the incident and named the suspects (UTC)',
  time_to_detect_s COMMENT 'Operational MTTD sample: first_detection_ts - first_impact_signal_ts, seconds. Starts at the first anomaly visible in telemetry, so a lower bound for slowly ramping faults',
  time_to_localise_s COMMENT 'incident_detected_ts - first_impact_signal_ts, seconds (minute resolution)',
  detected_within_5min COMMENT 'time_to_detect_s <= 300',
  n_detection_rows COMMENT 'Detection rows (KPI or alarm) on the suspect subtree in that window'
)
COMMENT 'Operational time to detect / localise per open incident (GT-free; the ground-truth-scored KPI is netmon_eval.eval_ttd_summary)'
AS WITH d AS (
  SELECT i.incident_id, i.source_run, i.region_code, i.suspect_1_id, i.detected_ts AS incident_detected_ts,
         g.signal_start_ts,
         timestampadd(MILLISECOND, CAST(coalesce(g.pipeline_latency_s, 0) * 1000 AS BIGINT), g.evidence_ts) AS available_ts
  FROM ${rca_schema}.open_incidents i
  JOIN ${gold_schema}.gold_impact_detections g
    ON g.source_run = i.source_run
   AND i.suspect_1_id IN (g.element_id, g.cell_id, g.site_id, g.backhaul_id, g.router_id, g.upf_id, g.amf_id)
   AND g.signal_start_ts BETWEEN i.detected_ts - INTERVAL 2 HOURS AND i.detected_ts + INTERVAL 10 MINUTES
   AND NOT g.in_maintenance
  WHERE ${gov}.region_filter(i.region_code)
)
SELECT incident_id, source_run, region_code, suspect_1_id,
       min(signal_start_ts) AS first_impact_signal_ts,
       min(available_ts) AS first_detection_ts,
       max(incident_detected_ts) AS incident_detected_ts,
       round(timestampdiff(MILLISECOND, min(signal_start_ts), min(available_ts)) / 1000.0, 1) AS time_to_detect_s,
       timestampdiff(SECOND, min(signal_start_ts), max(incident_detected_ts)) AS time_to_localise_s,
       timestampdiff(MILLISECOND, min(signal_start_ts), min(available_ts)) <= 300000 AS detected_within_5min,
       count(*) AS n_detection_rows
FROM d
GROUP BY incident_id, source_run, region_code, suspect_1_id;
