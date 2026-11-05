-- National NOC role (noc_national): every region. Gold and the operational silver tables directly, plus
-- the serving views. Still no bronze (raw IMSI / MSISDN), quarantine or eval, and no MODIFY. IMSI / MSISDN
-- stay masked unless the user is also in pii_privileged.
-- pii_privileged itself receives NO grants: it is only tested inside the mask functions, so it unmasks
-- values for someone who already holds a NOC role and gives access to nothing on its own.

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

GRANT USE SCHEMA ON SCHEMA ${noc_schema} TO `${principal}`;
GRANT SELECT ON SCHEMA ${noc_schema} TO `${principal}`;

GRANT USE SCHEMA ON SCHEMA ${gov_schema} TO `${principal}`;
GRANT EXECUTE ON FUNCTION ${gov}.region_filter TO `${principal}`;
