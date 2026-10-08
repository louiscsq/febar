-- Unity Catalog policy functions used by the pipeline's column masks and row filters.
-- Applied by governance/apply_governance.py (stage `functions`) BEFORE the pipeline runs, because the
-- pipeline declares `MASK ${gov}.mask_imsi` / `ROW FILTER ${gov}.region_filter` on its tables.
--
-- Group checks use both is_account_group_member() (account groups, the production setup) and is_member()
-- (workspace-local groups, which is what this FEVM workspace allows; see docs/pipeline.md).

CREATE OR REPLACE FUNCTION ${gov}.is_pii_privileged()
RETURNS BOOLEAN
COMMENT 'True if the current user may see raw subscriber identifiers (member of pii_privileged).'
RETURN is_account_group_member('pii_privileged') OR is_member('pii_privileged');

-- IMSI = MCC (3) + MNC (2) + MSIN (10). Non-privileged readers keep the PLMN and the last two digits.
CREATE OR REPLACE FUNCTION ${gov}.mask_imsi(imsi STRING)
RETURNS STRING
COMMENT 'Column mask for IMSI: full value for pii_privileged, otherwise PLMN + ********** + last 2 digits.'
RETURN CASE
  WHEN imsi IS NULL THEN NULL
  WHEN ${gov}.is_pii_privileged() THEN imsi
  ELSE concat(substr(imsi, 1, 5), repeat('*', greatest(length(imsi) - 7, 0)), right(imsi, 2))
END;

-- MSISDN = +CC + subscriber number. Non-privileged readers keep the country code and the last 3 digits.
CREATE OR REPLACE FUNCTION ${gov}.mask_msisdn(msisdn STRING)
RETURNS STRING
COMMENT 'Column mask for MSISDN: full value for pii_privileged, otherwise +CC ****** + last 3 digits.'
RETURN CASE
  WHEN msisdn IS NULL THEN NULL
  WHEN ${gov}.is_pii_privileged() THEN msisdn
  ELSE concat(substr(msisdn, 1, 4), repeat('*', greatest(length(msisdn) - 7, 0)), right(msisdn, 3))
END;

-- Row filter: national NOC sees every region; a regional NOC group noc_region_<code> sees its own region.
CREATE OR REPLACE FUNCTION ${gov}.region_filter(region_code STRING)
RETURNS BOOLEAN
COMMENT 'Row filter on region_code: noc_national sees all rows, noc_region_<code> only its region.'
RETURN is_account_group_member('noc_national') OR is_member('noc_national')
  OR is_account_group_member(concat('noc_region_', lower(region_code)))
  OR is_member(concat('noc_region_', lower(region_code)));
