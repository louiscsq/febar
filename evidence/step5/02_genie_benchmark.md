# Genie benchmark: NOC space

Captured 2026-11-06 10:43 UTC from workspace profile `febar` by `scripts/genie_benchmark.py` (Genie eval-run API, run `01f1d9ce3b1c1a1eadf5595e3dda73ef`, space `01f1d9cd2ee0117c82252259a6bfd81f`).

**Score: 16 / 18 GOOD (89 %)**, 1 needs review, 1 bad. Graded by Genie against the expected SQL's result (run by the API as the capturing user, who is in `noc_national`, so all regions are visible). The questions and expected SQL are in `src/netmon_pipeline/genie_space.py` (`BENCHMARKS`); 4 of 18 are close paraphrases of a trusted example SQL, the rest are not.

## Summary

| question | assessment | reasons |
|---|---|---|
| How many incidents are open? | GOOD |  |
| How many open incidents are there per region? | GOOD |  |
| What is the most likely failing element of incident RCA-c7276c3238a27971? | GOOD |  |
| List the top-3 root-cause suspects with scores for the incident whose top suspect is SITE-NSW-00105 | GOOD |  |
| What is the average time to detect across open incidents in seconds? | NEEDS_REVIEW | LLM_JUDGE_FORMATTING_ERROR |
| What percentage of open incidents were detected within 5 minutes? | GOOD |  |
| Which incident took the longest to detect? | GOOD |  |
| How many estimated subscribers are affected in NSW? | GOOD |  |
| Which region has the most estimated affected subscribers? | GOOD |  |
| How many network elements are down, by element type? | GOOD |  |
| List the cell sites that are down | GOOD |  |
| Which backhaul links are the top suspect of an open incident? | GOOD |  |
| What fault does the AI assistant suspect for the North Queensland incident? | GOOD |  |
| How many SMS drafts are waiting for approval? | GOOD |  |
| What is the scored share of faults detected within 5 minutes on the live feed? | GOOD |  |
| What is the scored median time to detect per fault type on the live feed? | GOOD |  |
| How many customer-impact detections did the live feed produce per signal source? | GOOD |  |
| Which element types does the aggregation router AGG-NSW-04 serve directly? | BAD | RESULT_MISSING_COLUMNS, LLM_JUDGE_MISSING_OR_INCORRECT_AGGREGATION |

_18 row(s)_

## Per question (expected vs Genie, both executed)

### How many incidents are open?

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT count(*) AS open_incidents FROM telco_netmon_febar_catalog.netmon_noc.open_incidents
```

Genie's SQL:

```sql
SELECT COUNT(*) AS `open_incidents`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`open_incidents`
```

Expected result:

| open_incidents |
|---|
| 17 |

_1 row(s)_

Genie's result:

| open_incidents |
|---|
| 17 |

_1 row(s)_

### How many open incidents are there per region?

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT region_code, count(*) AS open_incidents FROM telco_netmon_febar_catalog.netmon_noc.open_incidents GROUP BY region_code ORDER BY region_code
```

Genie's SQL:

```sql
SELECT `region_code`, COUNT(*) AS `open_incidents`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`open_incidents`
WHERE `region_code` IS NOT NULL
GROUP BY `region_code`
ORDER BY `open_incidents` DESC, `region_code` ASC
```

Expected result:

| region_code | open_incidents |
|---|---|
| NQL | 1 |
| NSW | 9 |
| VIC | 7 |

_3 row(s)_

Genie's result:

| region_code | open_incidents |
|---|---|
| NSW | 9 |
| VIC | 7 |
| NQL | 1 |

_3 row(s)_

### What is the most likely failing element of incident RCA-c7276c3238a27971?

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT suspect_1_id, suspect_1_type, suspect_1_score FROM telco_netmon_febar_catalog.netmon_noc.open_incidents WHERE incident_id = 'RCA-c7276c3238a27971'
```

Genie's SQL:

```sql
SELECT `incident_id`, `region_code`, `suspect_1_id` AS `most_likely_failing_element`, `suspect_1_type` AS `element_type`, `suspect_1_score` AS `root_cause_score`, `detected_ts`, `last_scored_ts`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`open_incidents`
WHERE `incident_id` = 'RCA-c7276c3238a27971'
```

Expected result:

| suspect_1_id | suspect_1_type | suspect_1_score |
|---|---|---|
| SITE-NSW-00105 | SITE | 1.0 |

_1 row(s)_

Genie's result:

| incident_id | region_code | most_likely_failing_element | element_type | root_cause_score | detected_ts | last_scored_ts |
|---|---|---|---|---|---|---|
| RCA-c7276c3238a27971 | NSW | SITE-NSW-00105 | SITE | 1.0 | 2026-10-09T00:10:00.000Z | 2026-10-09T00:56:00.000Z |

_1 row(s)_

### List the top-3 root-cause suspects with scores for the incident whose top suspect is SITE-NSW-00105

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT incident_id, suspect_1_id, suspect_1_score, suspect_2_id, suspect_2_score, suspect_3_id, suspect_3_score FROM telco_netmon_febar_catalog.netmon_noc.open_incidents WHERE suspect_1_id = 'SITE-NSW-00105'
```

Genie's SQL:

```sql
SELECT
  `incident_id`,
  `region_code`,
  `detected_ts`,
  `suspect_1_id`,
  ROUND(`suspect_1_score`, 2) AS `suspect_1_score`,
  `suspect_2_id`,
  ROUND(`suspect_2_score`, 2) AS `suspect_2_score`,
  `suspect_3_id`,
  ROUND(`suspect_3_score`, 2) AS `suspect_3_score`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`open_incidents`
WHERE `suspect_1_id` = 'SITE-NSW-00105'
  AND `detected_ts` IS NOT NULL
ORDER BY `detected_ts` DESC
LIMIT 1
```

Expected result:

| incident_id | suspect_1_id | suspect_1_score | suspect_2_id | suspect_2_score | suspect_3_id | suspect_3_score |
|---|---|---|---|---|---|---|
| RCA-c7276c3238a27971 | SITE-NSW-00105 | 1.0 | AGG-NSW-04 | 0.0 | AMF-NSW-01 | 0.0 |

_1 row(s)_

Genie's result:

| incident_id | region_code | detected_ts | suspect_1_id | suspect_1_score | suspect_2_id | suspect_2_score | suspect_3_id | suspect_3_score |
|---|---|---|---|---|---|---|---|---|
| RCA-c7276c3238a27971 | NSW | 2026-10-09T00:10:00.000Z | SITE-NSW-00105 | 1.0 | AGG-NSW-04 | 0.0 | AMF-NSW-01 | 0.0 |

_1 row(s)_

### What is the average time to detect across open incidents in seconds?

Genie assessment: **NEEDS_REVIEW** (LLM_JUDGE_FORMATTING_ERROR)

Expected SQL:

```sql
SELECT round(avg(time_to_detect_s), 1) AS mttd_s FROM telco_netmon_febar_catalog.netmon_noc.incident_detection_times
```

Genie's SQL:

```sql
SELECT AVG(`time_to_detect_s`) AS `avg_time_to_detect_s`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`incident_detection_times`
WHERE `time_to_detect_s` IS NOT NULL
```

Expected result:

| mttd_s |
|---|
| 165.8 |

_1 row(s)_

Genie's result:

| avg_time_to_detect_s |
|---|
| 165.82941 |

_1 row(s)_

### What percentage of open incidents were detected within 5 minutes?

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT round(100 * avg(CASE WHEN detected_within_5min THEN 1 ELSE 0 END), 1) AS pct_within_5min FROM telco_netmon_febar_catalog.netmon_noc.incident_detection_times
```

Genie's SQL:

```sql
SELECT 100 * AVG(CASE WHEN `detected_within_5min` THEN 1 ELSE 0 END) AS `pct_detected_within_5min`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`incident_detection_times`
```

Expected result:

| pct_within_5min |
|---|
| 100.0 |

_1 row(s)_

Genie's result:

| pct_detected_within_5min |
|---|
| 100.0 |

_1 row(s)_

### Which incident took the longest to detect?

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT incident_id, time_to_detect_s FROM telco_netmon_febar_catalog.netmon_noc.incident_detection_times ORDER BY time_to_detect_s DESC LIMIT 1
```

Genie's SQL:

```sql
WITH `ranked_incidents` AS (
  SELECT
    `incident_id`,
    `source_run`,
    `region_code`,
    `suspect_1_id`,
    `first_impact_signal_ts`,
    `first_detection_ts`,
    `incident_detected_ts`,
    `time_to_detect_s`,
    ROUND(try_divide(`time_to_detect_s`,60), 1) AS `time_to_detect_min`,
    `detected_within_5min`,
    RANK() OVER (ORDER BY `time_to_detect_s` DESC) AS `rnk`
  FROM `telco_netmon_febar_catalog`.`netmon_noc`.`incident_detection_times`
  WHERE `time_to_detect_s` IS NOT NULL
)
SELECT
  `incident_id`,
  `source_run`,
  `region_code`,
  `suspect_1_id`,
  `first_impact_signal_ts`,
  `first_detection_ts`,
  `incident_detected_ts`,
  `time_to_detect_s`,
  `time_to_detect_min`,
  `detected_within_5min`
FROM `ranked_incidents`
WHERE `rnk` = 1
ORDER BY `incident_id`
```

Expected result:

| incident_id | time_to_detect_s |
|---|---|
| RCA-27ed3e8af852d33a | 203.6 |

_1 row(s)_

Genie's result:

| incident_id | source_run | region_code | suspect_1_id | first_impact_signal_ts | first_detection_ts | incident_detected_ts | time_to_detect_s | time_to_detect_min | detected_within_5min |
|---|---|---|---|---|---|---|---|---|---|
| RCA-27ed3e8af852d33a | stream | VIC | BH-VIC-0005 | 2026-10-08T22:48:00.000Z | 2026-10-08T22:51:23.599Z | 2026-10-08T23:56:00.000Z | 203.6 | 3.4 | true |

_1 row(s)_

### How many estimated subscribers are affected in NSW?

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT sum(est_affected_subscribers) AS est_affected_subscribers FROM telco_netmon_febar_catalog.netmon_noc.incident_ai_summary WHERE region_code = 'NSW'
```

Genie's SQL:

```sql
SELECT SUM(`incident_ai_summary`.`est_affected_subscribers`) AS `est_affected_subscribers`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`incident_ai_summary` AS `incident_ai_summary`
JOIN `telco_netmon_febar_catalog`.`netmon_noc`.`open_incidents` AS `open_incidents`
  ON `incident_ai_summary`.`incident_id` = `open_incidents`.`incident_id`
WHERE `incident_ai_summary`.`region_code` = 'NSW'
```

Expected result:

| est_affected_subscribers |
|---|
| 3060 |

_1 row(s)_

Genie's result:

| est_affected_subscribers |
|---|
| 3060 |

_1 row(s)_

### Which region has the most estimated affected subscribers?

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT region_code, sum(est_affected_subscribers) AS est_affected_subscribers FROM telco_netmon_febar_catalog.netmon_noc.incident_ai_summary GROUP BY region_code ORDER BY est_affected_subscribers DESC LIMIT 1
```

Genie's SQL:

```sql
WITH `regional_totals` AS (
  SELECT
    `a`.`region_code`,
    SUM(`a`.`est_affected_subscribers`) AS `est_affected_subscribers`
  FROM `telco_netmon_febar_catalog`.`netmon_noc`.`incident_ai_summary` AS `a`
  INNER JOIN `telco_netmon_febar_catalog`.`netmon_noc`.`open_incidents` AS `o`
    ON `a`.`incident_id` = `o`.`incident_id`
  WHERE `a`.`region_code` IS NOT NULL
    AND `a`.`est_affected_subscribers` IS NOT NULL
  GROUP BY `a`.`region_code`
), `ranked_regions` AS (
  SELECT
    `region_code`,
    `est_affected_subscribers`,
    RANK() OVER (ORDER BY `est_affected_subscribers` DESC) AS `rnk`
  FROM `regional_totals`
)
SELECT
  `region_code`,
  `est_affected_subscribers`
FROM `ranked_regions`
WHERE `rnk` = 1
```

Expected result:

| region_code | est_affected_subscribers |
|---|---|
| NSW | 3060 |

_1 row(s)_

Genie's result:

| region_code | est_affected_subscribers |
|---|---|
| NSW | 3060 |

_1 row(s)_

### How many network elements are down, by element type?

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT element_type, count(*) AS n_down FROM telco_netmon_febar_catalog.netmon_noc.element_status WHERE state = 'down' GROUP BY element_type ORDER BY n_down DESC
```

Genie's SQL:

```sql
SELECT `element_type`, COUNT(*) AS `down_elements`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`element_status`
WHERE `state` IS NOT NULL
  AND `element_type` IS NOT NULL
  AND `state` = 'down'
GROUP BY `element_type`
ORDER BY `down_elements` DESC, `element_type`
```

Expected result:

| element_type | n_down |
|---|---|
| CELL | 18 |
| SITE | 3 |
| BACKHAUL_LINK | 1 |
| AGG_ROUTER | 1 |

_4 row(s)_

Genie's result:

| element_type | down_elements |
|---|---|
| CELL | 18 |
| SITE | 3 |
| AGG_ROUTER | 1 |
| BACKHAUL_LINK | 1 |

_4 row(s)_

### List the cell sites that are down

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT element_id FROM telco_netmon_febar_catalog.netmon_noc.element_status WHERE element_type = 'SITE' AND state = 'down' ORDER BY element_id
```

Genie's SQL:

```sql
SELECT `s`.`element_id`, `n`.`name`, `s`.`region_code`, `s`.`n_desc_cells`, `s`.`n_impacted_cells`, `s`.`open_incident_id`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`element_status` AS `s`
JOIN `telco_netmon_febar_catalog`.`netmon_noc`.`silver_topology_nodes` AS `n`
  ON `s`.`element_id` = `n`.`element_id`
WHERE `s`.`element_type` = 'SITE'
  AND `s`.`state` = 'down'
  AND `s`.`element_id` IS NOT NULL
  AND `s`.`region_code` IS NOT NULL
ORDER BY `s`.`region_code`, `s`.`element_id`
```

Expected result:

| element_id |
|---|
| SITE-NQL-00006 |
| SITE-NSW-00009 |
| SITE-NSW-00105 |

_3 row(s)_

Genie's result:

| element_id | name | region_code | n_desc_cells | n_impacted_cells | open_incident_id |
|---|---|---|---|---|---|
| SITE-NQL-00006 | North Queensland site 6 | NQL | 3.0 | 3.0 | RCA-d28473ab1bd7b846 |
| SITE-NSW-00009 | Sydney & NSW site 9 | NSW | 6.000000476837158 | 6.0 | RCA-fbd7ff66e62b0b42 |
| SITE-NSW-00105 | Sydney & NSW site 105 | NSW | 3.0 | 3.0 | RCA-c7276c3238a27971 |

_3 row(s)_

### Which backhaul links are the top suspect of an open incident?

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT incident_id, suspect_1_id FROM telco_netmon_febar_catalog.netmon_noc.open_incidents WHERE suspect_1_type = 'BACKHAUL_LINK' ORDER BY incident_id
```

Genie's SQL:

```sql
SELECT `o`.`incident_id`, `o`.`region_code`, `o`.`detected_ts`, `o`.`suspect_1_id` AS `backhaul_link_id`, `t`.`name` AS `backhaul_link_name`, `o`.`suspect_1_score`, `o`.`n_impacted_cells`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`open_incidents` AS `o`
JOIN `telco_netmon_febar_catalog`.`netmon_noc`.`silver_topology_nodes` AS `t`
  ON `o`.`suspect_1_id` = `t`.`element_id`
WHERE `o`.`suspect_1_type` = 'BACKHAUL_LINK'
  AND `o`.`detected_ts` IS NOT NULL
  AND `o`.`incident_id` IS NOT NULL
  AND `o`.`suspect_1_id` IS NOT NULL
ORDER BY `o`.`detected_ts` DESC, `o`.`incident_id` ASC
```

Expected result:

| incident_id | suspect_1_id |
|---|---|
| RCA-27ed3e8af852d33a | BH-VIC-0005 |
| RCA-4b24e8c0bfedac1a | BH-NSW-0010 |
| RCA-cdc1224a2469350b | BH-NSW-0015 |
| RCA-ce4e7fd28bd45261 | BH-NSW-0041 |
| RCA-e909709b1c6a18fb | BH-NSW-0013 |

_5 row(s)_

Genie's result:

| incident_id | region_code | detected_ts | backhaul_link_id | backhaul_link_name | suspect_1_score | n_impacted_cells |
|---|---|---|---|---|---|---|
| RCA-cdc1224a2469350b | NSW | 2026-10-09T00:39:00.000Z | BH-NSW-0015 | microwave backhaul BH-NSW-0015 | 1.0 | 6 |
| RCA-ce4e7fd28bd45261 | NSW | 2026-10-09T00:32:00.000Z | BH-NSW-0041 | fibre backhaul BH-NSW-0041 | 1.0 | 3 |
| RCA-e909709b1c6a18fb | NSW | 2026-10-08T23:59:00.000Z | BH-NSW-0013 | microwave backhaul BH-NSW-0013 | 1.0 | 9 |
| RCA-27ed3e8af852d33a | VIC | 2026-10-08T23:56:00.000Z | BH-VIC-0005 | satellite backhaul BH-VIC-0005 | 1.0 | 12 |
| RCA-4b24e8c0bfedac1a | NSW | 2026-10-08T23:56:00.000Z | BH-NSW-0010 | fibre backhaul BH-NSW-0010 | 1.0 | 3 |

_5 row(s)_

### What fault does the AI assistant suspect for the North Queensland incident?

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT incident_id, likely_root_cause, fault_hypothesis FROM telco_netmon_febar_catalog.netmon_noc.incident_ai_summary WHERE region_code = 'NQL'
```

Genie's SQL:

```sql
SELECT `o`.`incident_id`, `o`.`region_code`, `a`.`fault_hypothesis`, `a`.`likely_root_cause`, `a`.`confidence`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`open_incidents` AS `o`
JOIN `telco_netmon_febar_catalog`.`netmon_noc`.`incident_ai_summary` AS `a`
  ON `o`.`incident_id` = `a`.`incident_id`
WHERE `o`.`region_code` = 'NQL'
  AND `a`.`fault_hypothesis` IS NOT NULL
ORDER BY `o`.`detected_ts` DESC
```

Expected result:

| incident_id | likely_root_cause | fault_hypothesis |
|---|---|---|
| RCA-d28473ab1bd7b846 | AGG-NQL-02 | LONG_HAUL_FIBRE_CUT |

_1 row(s)_

Genie's result:

| incident_id | region_code | fault_hypothesis | likely_root_cause | confidence |
|---|---|---|---|---|
| RCA-d28473ab1bd7b846 | NQL | LONG_HAUL_FIBRE_CUT | AGG-NQL-02 | high |

_1 row(s)_

### How many SMS drafts are waiting for approval?

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT count(*) AS n_drafts FROM telco_netmon_febar_catalog.netmon_noc.incident_ai_summary WHERE sms_draft_status = 'draft'
```

Genie's SQL:

```sql
SELECT COUNT(*) AS `sms_drafts_waiting_for_approval`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`incident_ai_summary`
WHERE `sms_draft_status` = 'draft'
```

Expected result:

| n_drafts |
|---|
| 17 |

_1 row(s)_

Genie's result:

| sms_drafts_waiting_for_approval |
|---|
| 17 |

_1 row(s)_

### What is the scored share of faults detected within 5 minutes on the live feed?

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT impact_within_5min_pct FROM telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary WHERE source_run = 'stream' AND event_class = 'fault' AND fault_type = 'ALL'
```

Genie's SQL:

```sql
SELECT `n_incidents`, `impact_within_5min_pct`
FROM `telco_netmon_febar_catalog`.`netmon_eval`.`eval_ttd_summary`
WHERE `source_run` = 'stream'
  AND `event_class` = 'fault'
  AND `fault_type` = 'ALL'
```

Expected result:

| impact_within_5min_pct |
|---|
| 88.5 |

_1 row(s)_

Genie's result:

| n_incidents | impact_within_5min_pct |
|---|---|
| 26 | 88.5 |

_1 row(s)_

### What is the scored median time to detect per fault type on the live feed?

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT fault_type, impact_median_ttd_s FROM telco_netmon_febar_catalog.netmon_eval.eval_ttd_summary WHERE source_run = 'stream' AND event_class = 'fault' AND fault_type <> 'ALL' ORDER BY fault_type
```

Genie's SQL:

```sql
SELECT `fault_type`, `impact_median_ttd_s`, ROUND(try_divide(`impact_median_ttd_s`,60), 1) AS `impact_median_ttd_min`, `n_incidents`
FROM `telco_netmon_febar_catalog`.`netmon_eval`.`eval_ttd_summary`
WHERE `source_run` = 'stream'
  AND `event_class` = 'fault'
  AND `fault_type` IS NOT NULL
  AND `fault_type` <> 'ALL'
ORDER BY `fault_type`
```

Expected result:

| fault_type | impact_median_ttd_s |
|---|---|
| AGG_ROUTER_FAILURE | 23.4 |
| BACKHAUL_DEGRADATION | 807.9 |
| CELL_OUTAGE | 132.7 |
| SITE_POWER_OUTAGE | 235.5 |

_4 row(s)_

Genie's result:

| fault_type | impact_median_ttd_s | impact_median_ttd_min | n_incidents |
|---|---|---|---|
| AGG_ROUTER_FAILURE | 23.4 | 0.4 | 1 |
| BACKHAUL_DEGRADATION | 807.9 | 13.5 | 3 |
| CELL_OUTAGE | 132.7 | 2.2 | 20 |
| SITE_POWER_OUTAGE | 235.5 | 3.9 | 2 |

_4 row(s)_

### How many customer-impact detections did the live feed produce per signal source?

Genie assessment: **GOOD**

Expected SQL:

```sql
SELECT signal_source, count(*) AS n_detections FROM telco_netmon_febar_catalog.netmon_noc.gold_impact_detections WHERE source_run = 'stream' GROUP BY signal_source ORDER BY signal_source
```

Genie's SQL:

```sql
SELECT `signal_source`, COUNT(*) AS `n_customer_impact_detections`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`gold_impact_detections`
WHERE `source_run` = 'stream'
  AND `signal_source` IS NOT NULL
GROUP BY `signal_source`
ORDER BY `n_customer_impact_detections` DESC, `signal_source` ASC
```

Expected result:

| signal_source | n_detections |
|---|---|
| alarm | 73 |
| kpi | 8262 |

_2 row(s)_

Genie's result:

| signal_source | n_customer_impact_detections |
|---|---|
| kpi | 8262 |
| alarm | 73 |

_2 row(s)_

### Which element types does the aggregation router AGG-NSW-04 serve directly?

Genie assessment: **BAD** (RESULT_MISSING_COLUMNS, LLM_JUDGE_MISSING_OR_INCORRECT_AGGREGATION)

Expected SQL:

```sql
SELECT element_type, count(*) AS n FROM telco_netmon_febar_catalog.netmon_noc.silver_topology_nodes WHERE parent_id = 'AGG-NSW-04' GROUP BY element_type
```

Genie's SQL:

```sql
SELECT DISTINCT `child`.`element_type`
FROM `telco_netmon_febar_catalog`.`netmon_noc`.`silver_topology_nodes` AS `child`
WHERE `child`.`parent_id` = 'AGG-NSW-04'
  AND `child`.`element_type` IS NOT NULL
ORDER BY `child`.`element_type`
```

Expected result:

| element_type | n |
|---|---|
| BACKHAUL_LINK | 19 |

_1 row(s)_

Genie's result:

| element_type |
|---|
| BACKHAUL_LINK |

_1 row(s)_
