"""App settings from the environment. app.yaml maps the bundle's app resources onto these variables; nothing here is a
secret (Lakebase passwords are one-hour OAuth tokens minted at connect time, the user's token comes per request)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _host() -> str:
    h = os.environ.get("DATABRICKS_HOST", "")
    return h if not h or h.startswith("http") else f"https://{h}"


@dataclass(frozen=True)
class Settings:
    catalog: str = field(default_factory=lambda: os.environ.get("NETMON_CATALOG", "telco_netmon_febar_catalog"))
    noc_schema: str = field(default_factory=lambda: os.environ.get("NETMON_NOC_SCHEMA", "netmon_noc"))
    warehouse_id: str = field(default_factory=lambda: os.environ.get("DATABRICKS_WAREHOUSE_ID", ""))
    genie_space_id: str = field(default_factory=lambda: os.environ.get("GENIE_SPACE_ID", ""))
    lakebase_instance: str = field(default_factory=lambda: os.environ.get("LAKEBASE_INSTANCE", ""))
    # injected by the Apps runtime for the `database` resource
    pg_host: str = field(default_factory=lambda: os.environ.get("PGHOST", ""))
    pg_database: str = field(default_factory=lambda: os.environ.get("PGDATABASE", "netmon_serving"))
    pg_user: str = field(default_factory=lambda: os.environ.get("PGUSER", ""))
    pg_port: int = field(default_factory=lambda: int(os.environ.get("PGPORT", "5432")))
    pg_sslmode: str = field(default_factory=lambda: os.environ.get("PGSSLMODE", "require"))
    host: str = field(default_factory=_host)
    app_identity: str = field(default_factory=lambda: os.environ.get("DATABRICKS_CLIENT_ID", "local"))
    # Local development only (never set in app.yaml): regions to assume when no user token is forwarded.
    dev_regions: tuple[str, ...] = field(default_factory=lambda: tuple(
        r for r in os.environ.get("NOC_DEV_REGIONS", "").split(",") if r))

    @property
    def noc(self) -> str:
        return f"{self.catalog}.{self.noc_schema}"
