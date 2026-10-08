-- Comments and tags on the schemas and key tables. Table-level comments of pipeline tables are set in the
-- pipeline code (`comment=` / column COMMENTs in the declared schema); tags are set here.

COMMENT ON SCHEMA ${gold_schema} IS 'Banksia Mobile NOC gold layer: per-cell health windows with baseline deviation, customer-impact detections (5-minute SLA) and topology rollups used as root-cause features.';
COMMENT ON SCHEMA ${eval_schema} IS 'Ground truth from the synthetic generator and scoring of detection and DQ handling. Labels only, never features.';
COMMENT ON VOLUME ${landing_volume} IS 'Generator output, one sub-directory per run (history/, stream/): JSON lines partitioned by emitted date.';

ALTER SCHEMA ${raw_schema} SET TAGS ('domain' = 'network_operations', 'layer' = 'landing');
ALTER SCHEMA ${bronze_schema} SET TAGS ('domain' = 'network_operations', 'layer' = 'bronze', 'contains_pii' = 'true');
ALTER SCHEMA ${silver_schema} SET TAGS ('domain' = 'network_operations', 'layer' = 'silver', 'contains_pii' = 'true');
ALTER SCHEMA ${gold_schema} SET TAGS ('domain' = 'network_operations', 'layer' = 'gold', 'contains_pii' = 'false');
ALTER SCHEMA ${eval_schema} SET TAGS ('domain' = 'network_operations', 'layer' = 'evaluation', 'ground_truth' = 'true');

ALTER TABLE ${bronze_schema}.bronze_sessions SET TAGS ('domain' = 'customer_experience', 'contains_pii' = 'true', 'access' = 'engineering_only');
ALTER TABLE ${bronze_schema}.bronze_sessions ALTER COLUMN imsi SET TAGS ('pii' = 'imsi', 'classification' = 'confidential');
ALTER TABLE ${bronze_schema}.bronze_sessions ALTER COLUMN msisdn SET TAGS ('pii' = 'msisdn', 'classification' = 'confidential');

ALTER TABLE ${silver_schema}.silver_sessions SET TAGS ('domain' = 'customer_experience', 'contains_pii' = 'true', 'masked' = 'imsi,msisdn', 'row_filter' = 'region_code');
ALTER TABLE ${silver_schema}.silver_sessions ALTER COLUMN imsi SET TAGS ('pii' = 'imsi', 'classification' = 'confidential');
ALTER TABLE ${silver_schema}.silver_sessions ALTER COLUMN msisdn SET TAGS ('pii' = 'msisdn', 'classification' = 'confidential');
ALTER TABLE ${silver_schema}.silver_sessions ALTER COLUMN subscriber_key SET TAGS ('pii' = 'pseudonymous');
ALTER TABLE ${silver_schema}.silver_quarantine SET TAGS ('domain' = 'data_quality', 'access' = 'engineering_only');
ALTER TABLE ${silver_schema}.silver_kpis SET TAGS ('domain' = 'network_performance');
ALTER TABLE ${silver_schema}.silver_alarms SET TAGS ('domain' = 'fault_management');
ALTER TABLE ${silver_schema}.silver_topology_nodes SET TAGS ('domain' = 'network_inventory');

ALTER TABLE ${gold_schema}.gold_impact_detections SET TAGS ('domain' = 'service_assurance', 'sla' = '5min', 'row_filter' = 'region_code', 'consumer' = 'noc,lakebase,app');
ALTER TABLE ${gold_schema}.gold_cell_health_1m SET TAGS ('domain' = 'network_performance', 'grain' = 'cell_1m');
ALTER TABLE ${gold_schema}.gold_cell_health_5m SET TAGS ('domain' = 'network_performance', 'grain' = 'cell_5m');
ALTER TABLE ${gold_schema}.gold_cell_baseline SET TAGS ('domain' = 'network_performance', 'grain' = 'cell_hour_daytype');
ALTER TABLE ${gold_schema}.gold_element_impact_5m SET TAGS ('domain' = 'root_cause_analysis', 'consumer' = 'ml_rca_model', 'grain' = 'element_5m');
ALTER TABLE ${gold_schema}.gold_cell_sessions_5m SET TAGS ('domain' = 'customer_experience', 'grain' = 'cell_5m', 'contains_pii' = 'false');

ALTER TABLE ${eval_schema}.eval_gt_incidents SET TAGS ('ground_truth' = 'true', 'use' = 'evaluation_only');
ALTER TABLE ${eval_schema}.eval_incident_detection SET TAGS ('ground_truth' = 'true', 'use' = 'evaluation_only');
