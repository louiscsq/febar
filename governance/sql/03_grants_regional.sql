-- Regional NOC role (noc_region_<code>): the region-filtered serving views and nothing else.
-- No access to the silver / gold tables themselves, bronze, the quarantine or eval, and no MODIFY.
-- ${principal} is the account group in production; on this workspace, the group's persona service
-- principals (UC rejects workspace-local groups as grantees; see docs/pipeline.md).

GRANT USE CATALOG ON CATALOG ${catalog} TO `${principal}`;
GRANT USE SCHEMA ON SCHEMA ${noc_schema} TO `${principal}`;
GRANT SELECT ON SCHEMA ${noc_schema} TO `${principal}`;
-- The views call the row-filter function.
GRANT USE SCHEMA ON SCHEMA ${gov_schema} TO `${principal}`;
GRANT EXECUTE ON FUNCTION ${gov}.region_filter TO `${principal}`;
