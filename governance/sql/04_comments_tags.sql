-- Comments and tags on the schemas and key tables. Table-level comments of pipeline tables are set in the
-- pipeline code (`comment=` / column COMMENTs in the declared schema); tags are set here.
--
-- The metastore enforces governed tag policies (e.g. `domain`, `layer`, `pii`, `row_filter`, `classification`
-- only accept listed values), so governed keys use allowed values and project detail goes in `netmon_*` keys.

COMMENT ON SCHEMA ${gold_schema} IS 'Banksia Mobile NOC gold layer: per-cell health windows with baseline deviation, customer-impact detections (5-minute SLA) and topology rollups used as root-cause features.';
COMMENT ON SCHEMA ${eval_schema} IS 'Ground truth from the synthetic generator and scoring of detection and DQ handling. Labels only, never features.';
COMMENT ON VOLUME ${landing_volume} IS 'Generator output, one sub-directory per run (history/, stream/): JSON lines partitioned by emitted date.';

ALTER SCHEMA ${raw_schema} SET TAGS ('domain' = 'operations', 'netmon_layer' = 'landing');
ALTER SCHEMA ${bronze_schema} SET TAGS ('domain' = 'operations', 'layer' = 'bronze', 'contains_pii' = 'true');
ALTER SCHEMA ${silver_schema} SET TAGS ('domain' = 'operations', 'layer' = 'silver', 'contains_pii' = 'true');
ALTER SCHEMA ${gold_schema} SET TAGS ('domain' = 'operations', 'layer' = 'gold', 'contains_pii' = 'false');
ALTER SCHEMA ${noc_schema} SET TAGS ('domain' = 'operations', 'netmon_layer' = 'serving', 'row_filter' = 'by_region', 'consumer' = 'regional_noc');
ALTER SCHEMA ${eval_schema} SET TAGS ('domain' = 'operations', 'netmon_layer' = 'evaluation', 'ground_truth' = 'true');

-- PII: IMSI and MSISDN, raw in bronze (no grants), masked in silver.
ALTER TABLE ${bronze_schema}.bronze_sessions SET TAGS ('domain' = 'operations', 'netmon_domain' = 'customer_experience', 'contains_pii' = 'true', 'classification' = 'restricted', 'access' = 'engineering_only');
ALTER TABLE ${bronze_schema}.bronze_sessions ALTER COLUMN imsi SET TAGS ('netmon_pii' = 'imsi', 'classification' = 'restricted');
ALTER TABLE ${bronze_schema}.bronze_sessions ALTER COLUMN msisdn SET TAGS ('netmon_pii' = 'msisdn', 'class.phone_number' = '', 'classification' = 'restricted');

ALTER TABLE ${silver_schema}.silver_sessions SET TAGS ('domain' = 'operations', 'netmon_domain' = 'customer_experience', 'contains_pii' = 'true', 'classification' = 'confidential', 'masked' = 'imsi,msisdn', 'row_filter' = 'by_region');
ALTER TABLE ${silver_schema}.silver_sessions ALTER COLUMN imsi SET TAGS ('netmon_pii' = 'imsi', 'classification' = 'confidential', 'masked' = 'mask_imsi');
ALTER TABLE ${silver_schema}.silver_sessions ALTER COLUMN msisdn SET TAGS ('netmon_pii' = 'msisdn', 'class.phone_number' = '', 'classification' = 'confidential', 'masked' = 'mask_msisdn');
ALTER TABLE ${silver_schema}.silver_sessions ALTER COLUMN subscriber_key SET TAGS ('netmon_pii' = 'pseudonymous');
ALTER TABLE ${silver_schema}.silver_quarantine SET TAGS ('domain' = 'quality', 'access' = 'engineering_only', 'classification' = 'restricted');
ALTER TABLE ${silver_schema}.silver_kpis SET TAGS ('domain' = 'operations', 'netmon_domain' = 'network_performance', 'contains_pii' = 'false');
ALTER TABLE ${silver_schema}.silver_alarms SET TAGS ('domain' = 'operations', 'netmon_domain' = 'fault_management', 'contains_pii' = 'false');
ALTER TABLE ${silver_schema}.silver_topology_nodes SET TAGS ('domain' = 'operations', 'netmon_domain' = 'network_inventory');

ALTER TABLE ${gold_schema}.gold_impact_detections SET TAGS ('domain' = 'operations', 'netmon_domain' = 'service_assurance', 'sla' = '5min', 'row_filter' = 'by_region', 'consumer' = 'noc,lakebase,app');
ALTER TABLE ${gold_schema}.gold_cell_health_1m SET TAGS ('domain' = 'operations', 'netmon_domain' = 'network_performance', 'grain' = 'cell_1m');
ALTER TABLE ${gold_schema}.gold_cell_health_5m SET TAGS ('domain' = 'operations', 'netmon_domain' = 'network_performance', 'grain' = 'cell_5m');
ALTER TABLE ${gold_schema}.gold_cell_health_5m_retrospective SET TAGS ('domain' = 'operations', 'netmon_domain' = 'network_performance', 'grain' = 'cell_5m', 'use' = 'retrospective_only');
ALTER TABLE ${gold_schema}.gold_cell_baseline SET TAGS ('domain' = 'operations', 'netmon_domain' = 'network_performance', 'grain' = 'cell_hour_daytype');
ALTER TABLE ${gold_schema}.gold_element_impact_5m SET TAGS ('domain' = 'operations', 'netmon_domain' = 'root_cause_analysis', 'consumer' = 'ml_rca_model', 'grain' = 'element_5m');
ALTER TABLE ${gold_schema}.gold_cell_sessions_5m SET TAGS ('domain' = 'operations', 'netmon_domain' = 'customer_experience', 'grain' = 'cell_5m', 'contains_pii' = 'false');

ALTER TABLE ${eval_schema}.eval_gt_incidents SET TAGS ('ground_truth' = 'true', 'use' = 'evaluation_only');
ALTER TABLE ${eval_schema}.eval_incident_detection SET TAGS ('ground_truth' = 'true', 'use' = 'evaluation_only');
