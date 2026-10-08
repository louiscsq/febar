-- Least-privilege grants, run once per NOC persona with ${principal} substituted.
-- NOC users read gold and the masked / row-filtered silver feeds. They get no access to bronze (raw IMSI
-- and MSISDN), the quarantine (raw rejected payloads) or the eval schema (ground truth), and no MODIFY
-- anywhere: the pipeline owner is the only writer.
--
-- In production ${principal} is the account group itself (noc_national, noc_region_<code>, pii_privileged).
-- UC rejects workspace-local groups as grantees, so on this workspace the notebook grants to each
-- group's member service principals instead (docs/pipeline.md, "Governance").

GRANT USE CATALOG ON CATALOG ${catalog} TO `${principal}`;

GRANT USE SCHEMA ON SCHEMA ${gold_schema} TO `${principal}`;
GRANT SELECT ON SCHEMA ${gold_schema} TO `${principal}`;

GRANT USE SCHEMA ON SCHEMA ${silver_schema} TO `${principal}`;
GRANT SELECT ON TABLE ${silver_schema}.silver_sessions TO `${principal}`;
GRANT SELECT ON TABLE ${silver_schema}.silver_kpis TO `${principal}`;
GRANT SELECT ON TABLE ${silver_schema}.silver_alarms TO `${principal}`;
GRANT SELECT ON TABLE ${silver_schema}.silver_topology_nodes TO `${principal}`;
GRANT SELECT ON TABLE ${silver_schema}.silver_topology_edges TO `${principal}`;
GRANT SELECT ON TABLE ${silver_schema}.silver_maintenance_windows TO `${principal}`;

-- Readers of a masked / filtered table need no EXECUTE on the policy functions; USE SCHEMA lets them
-- inspect the policy definitions.
GRANT USE SCHEMA ON SCHEMA ${gov_schema} TO `${principal}`;
