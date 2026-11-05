-- Region-filtered serving views: the only data regional NOC groups can read (02 grants them this schema).
-- Every view keeps a region_code and applies ${gov}.region_filter, so a member of noc_region_<code> sees
-- only that region, noc_national sees all regions, and anyone in no NOC group sees no rows. Tables without
-- a region column get it from the topology. silver_sessions and gold_impact_detections also carry the row
-- filter (and the IMSI / MSISDN masks) on the table itself; masks and filters are evaluated for the user
-- querying the view.
--
-- Why views rather than row filters on every pipeline table: the pipeline streams from silver_kpis,
-- silver_alarms, the topology and the gold health tables. A filter on those would be evaluated as the
-- pipeline owner inside the pipeline, so its output would depend on the owner's group memberships.
-- Policy-protected pipeline tables are therefore leaves only (docs/pipeline.md, "Governance").

CREATE OR REPLACE VIEW ${noc_schema}.silver_kpis COMMENT 'Region-filtered silver_kpis' AS
SELECT * FROM ${silver_schema}.silver_kpis WHERE ${gov}.region_filter(region_code);

CREATE OR REPLACE VIEW ${noc_schema}.silver_alarms COMMENT 'Region-filtered silver_alarms' AS
SELECT * FROM ${silver_schema}.silver_alarms WHERE ${gov}.region_filter(region_code);

CREATE OR REPLACE VIEW ${noc_schema}.silver_sessions COMMENT 'silver_sessions: row filter and IMSI/MSISDN masks of the table apply' AS
SELECT * FROM ${silver_schema}.silver_sessions WHERE ${gov}.region_filter(region_code);

CREATE OR REPLACE VIEW ${noc_schema}.silver_topology_nodes COMMENT 'Region-filtered network inventory' AS
SELECT * FROM ${silver_schema}.silver_topology_nodes WHERE ${gov}.region_filter(region_code);

CREATE OR REPLACE VIEW ${noc_schema}.silver_topology_edges COMMENT 'Region-filtered topology edges (region of the child element)' AS
SELECT e.*, n.region_code
FROM ${silver_schema}.silver_topology_edges e
JOIN ${silver_schema}.silver_topology_nodes n ON n.element_id = e.child_id
WHERE ${gov}.region_filter(n.region_code);

CREATE OR REPLACE VIEW ${noc_schema}.silver_maintenance_windows COMMENT 'Region-filtered change calendar' AS
SELECT m.*, n.region_code
FROM ${silver_schema}.silver_maintenance_windows m
JOIN ${silver_schema}.silver_topology_nodes n ON n.element_id = m.element_id
WHERE ${gov}.region_filter(n.region_code);

CREATE OR REPLACE VIEW ${noc_schema}.gold_cell_baseline COMMENT 'Region-filtered cell baseline' AS
SELECT b.*, n.region_code
FROM ${gold_schema}.gold_cell_baseline b
JOIN ${silver_schema}.silver_topology_nodes n ON n.element_id = b.cell_id
WHERE ${gov}.region_filter(n.region_code);

CREATE OR REPLACE VIEW ${noc_schema}.gold_cell_health_1m COMMENT 'Region-filtered 1-minute cell health' AS
SELECT * FROM ${gold_schema}.gold_cell_health_1m WHERE ${gov}.region_filter(region_code);

CREATE OR REPLACE VIEW ${noc_schema}.gold_cell_health_5m COMMENT 'Region-filtered 5-minute cell health' AS
SELECT * FROM ${gold_schema}.gold_cell_health_5m WHERE ${gov}.region_filter(region_code);

CREATE OR REPLACE VIEW ${noc_schema}.gold_impact_detections COMMENT 'gold_impact_detections: row filter of the table applies' AS
SELECT * FROM ${gold_schema}.gold_impact_detections WHERE ${gov}.region_filter(region_code);

CREATE OR REPLACE VIEW ${noc_schema}.gold_element_impact_5m COMMENT 'Region-filtered topology rollup' AS
SELECT * FROM ${gold_schema}.gold_element_impact_5m WHERE ${gov}.region_filter(region_code);

CREATE OR REPLACE VIEW ${noc_schema}.gold_cell_sessions_5m COMMENT 'Region-filtered per-cell session outcomes' AS
SELECT * FROM ${gold_schema}.gold_cell_sessions_5m WHERE ${gov}.region_filter(region_code);
