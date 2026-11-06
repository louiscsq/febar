"""Entry point of the Databricks App (app.yaml: uvicorn main:app)."""

import logging

from noc_app.api import create_app
from noc_app.config import Settings
from noc_app.genie import GenieClient
from noc_app.lakebase import LakebaseStore
from noc_app.service import NocService
from noc_app.warehouse import SqlWarehouse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _service() -> NocService:
    s = Settings()
    return NocService(s, LakebaseStore(s), SqlWarehouse(s), GenieClient(s))


app = create_app(_service)
