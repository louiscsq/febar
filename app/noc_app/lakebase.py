"""Lakebase (Postgres) access: the app's hot path and its only write path.

Reads: the step-3 / step-4 synced tables `netmon_rca.lb_open_incidents`, `netmon_rca.lb_element_status` and
`netmon_genai.lb_incident_ai_latest` (Delta -> Postgres, refreshed by the scoring and assistant jobs).
Write: `netmon_app.sms_draft_reviews`, an append-only audit of approve / reject decisions on SMS drafts, created by
the app's own Postgres role. The table makes sending impossible by construction (`sent_at IS NULL`,
`send_channel = 'none'` CHECK constraints): approval records a human decision, nothing is ever sent.

Identity: the app's service principal (the `database` app resource gives its Postgres role CONNECT + CREATE;
`notebooks/13_app_lakebase_grants.py` grants SELECT on the synced tables). The password is a one-hour OAuth token
from `generate_database_credential`, minted per new pooled connection; no secret is stored anywhere.
Lakebase has no Unity Catalog row filters, so every read is scoped in SQL to the regions UC says the signed-in user
may see (`region_code = ANY(%(regions)s)`; see service.py).
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Protocol

SCHEMA_DDL = [
    "CREATE SCHEMA IF NOT EXISTS netmon_app",
    """CREATE TABLE IF NOT EXISTS netmon_app.sms_draft_reviews (
        review_id     uuid PRIMARY KEY,
        incident_id   text NOT NULL,
        summary_id    text NOT NULL,
        region_code   text NOT NULL,
        draft_sha256  text NOT NULL,
        draft_text    text NOT NULL,
        decision      text NOT NULL CHECK (decision IN ('approved', 'rejected')),
        note          text,
        reviewed_by   text NOT NULL,
        reviewed_at   timestamptz NOT NULL DEFAULT now(),
        app_identity  text NOT NULL,
        sent_at       timestamptz CHECK (sent_at IS NULL),
        send_channel  text NOT NULL DEFAULT 'none' CHECK (send_channel = 'none')
    )""",
    "CREATE INDEX IF NOT EXISTS sms_draft_reviews_incident ON netmon_app.sms_draft_reviews (incident_id, reviewed_at DESC)",
]

INCIDENT_COLUMNS = """
    i.incident_id, i.region_code, i.detected_ts, i.last_scored_ts, i.status,
    i.suspect_1_id, i.suspect_1_type, i.suspect_1_score, i.suspect_2_id, i.suspect_2_type, i.suspect_2_score,
    i.suspect_3_id, i.suspect_3_type, i.suspect_3_score, i.n_impacted_cells, i.n_candidates, i.model_version,
    a.summary_id, a.generated_at AS ai_generated_at, a.likely_root_cause, a.fault_hypothesis, a.confidence,
    a.summary AS ai_summary, a.next_steps_json, a.est_affected_subscribers, a.impacted_cells AS ai_impacted_cells,
    a.impacted_sites AS ai_impacted_sites, a.impact_description, a.sms_draft_text, a.sms_draft_status,
    a.generated_by AS ai_generated_by, a.noc_prompt_version,
    r.decision AS sms_decision, r.reviewed_by AS sms_reviewed_by, r.reviewed_at AS sms_reviewed_at"""

INCIDENTS_SQL = f"""
SELECT {INCIDENT_COLUMNS}
FROM netmon_rca.lb_open_incidents i
LEFT JOIN netmon_genai.lb_incident_ai_latest a ON a.incident_id = i.incident_id
LEFT JOIN LATERAL (
    SELECT decision, reviewed_by, reviewed_at FROM netmon_app.sms_draft_reviews v
    WHERE v.incident_id = i.incident_id AND v.summary_id = a.summary_id
    ORDER BY reviewed_at DESC LIMIT 1) r ON true
WHERE i.region_code = ANY(%(regions)s)
ORDER BY i.detected_ts DESC, i.incident_id"""

INCIDENT_SQL = INCIDENTS_SQL.replace("WHERE i.region_code = ANY(%(regions)s)",
                                     "WHERE i.region_code = ANY(%(regions)s) AND i.incident_id = %(incident_id)s")

ELEMENT_STATUS_SQL = """
SELECT element_id, element_type, parent_id, region_code, state, rca_score, n_impacted_cells, n_desc_cells,
       impacted_fraction, silent_fraction, n_alarms, n_service_down_alarms, open_incident_id, suspect_rank,
       last_updated_ts
FROM netmon_rca.lb_element_status
WHERE region_code = %(region)s"""

INSERT_REVIEW_SQL = """
INSERT INTO netmon_app.sms_draft_reviews
    (review_id, incident_id, summary_id, region_code, draft_sha256, draft_text, decision, note, reviewed_by,
     app_identity)
VALUES (%(review_id)s, %(incident_id)s, %(summary_id)s, %(region_code)s, %(draft_sha256)s, %(draft_text)s,
        %(decision)s, %(note)s, %(reviewed_by)s, %(app_identity)s)
RETURNING review_id, incident_id, summary_id, region_code, draft_sha256, decision, note, reviewed_by, reviewed_at,
          app_identity, sent_at, send_channel"""

REVIEWS_SQL = """
SELECT review_id, incident_id, summary_id, region_code, draft_sha256, decision, note, reviewed_by, reviewed_at,
       app_identity, sent_at, send_channel
FROM netmon_app.sms_draft_reviews
WHERE incident_id = %(incident_id)s AND region_code = ANY(%(regions)s)
ORDER BY reviewed_at DESC"""


class Store(Protocol):
    def incidents(self, regions: list[str]) -> list[dict]: ...
    def incident(self, incident_id: str, regions: list[str]) -> dict | None: ...
    def element_status(self, region: str) -> list[dict]: ...
    def insert_review(self, row: dict) -> dict: ...
    def reviews(self, incident_id: str, regions: list[str]) -> list[dict]: ...
    def ping(self) -> dict: ...


def draft_sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def new_review_id() -> str:
    return str(uuid.uuid4())


class LakebaseStore:
    """psycopg 3 connection pool against the Lakebase instance, as the app's service principal."""

    def __init__(self, settings, workspace_client=None, min_size: int = 1, max_size: int = 4):
        import psycopg
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        if workspace_client is None:
            from databricks.sdk import WorkspaceClient
            workspace_client = WorkspaceClient()
        self.s, self.w = settings, workspace_client
        instance = settings.lakebase_instance
        w = workspace_client

        class OAuthConnection(psycopg.Connection):
            @classmethod
            def connect(cls, conninfo: str = "", **kwargs: Any):
                cred = w.database.generate_database_credential(request_id=str(uuid.uuid4()), instance_names=[instance])
                kwargs["password"] = cred.token
                return super().connect(conninfo, **kwargs)

        host = settings.pg_host or w.database.get_database_instance(instance).read_write_dns
        user = settings.pg_user or w.current_user.me().user_name
        self.pool = ConnectionPool(
            conninfo="", connection_class=OAuthConnection, min_size=min_size, max_size=max_size,
            max_lifetime=45 * 60,  # recycle before the 1-hour token expires
            kwargs={"host": host, "port": settings.pg_port, "dbname": settings.pg_database, "user": user,
                    "sslmode": settings.pg_sslmode, "row_factory": dict_row, "application_name": "banksia-noc-app"},
            open=True)
        self.ensure_schema()

    def _all(self, sql: str, params: dict) -> list[dict]:
        with self.pool.connection() as c:
            return list(c.execute(sql, params).fetchall())

    def ensure_schema(self) -> None:
        with self.pool.connection() as c:
            for ddl in SCHEMA_DDL:
                c.execute(ddl)

    def incidents(self, regions: list[str]) -> list[dict]:
        return self._all(INCIDENTS_SQL, {"regions": regions})

    def incident(self, incident_id: str, regions: list[str]) -> dict | None:
        rows = self._all(INCIDENT_SQL, {"regions": regions, "incident_id": incident_id})
        return rows[0] if rows else None

    def element_status(self, region: str) -> list[dict]:
        return self._all(ELEMENT_STATUS_SQL, {"region": region})

    def insert_review(self, row: dict) -> dict:
        with self.pool.connection() as c:
            return c.execute(INSERT_REVIEW_SQL, row).fetchone()

    def reviews(self, incident_id: str, regions: list[str]) -> list[dict]:
        return self._all(REVIEWS_SQL, {"incident_id": incident_id, "regions": regions})

    def ping(self) -> dict:
        """Connection status only: the Postgres role and server time (no data, so nothing to region-scope)."""
        return self._all("SELECT current_user AS pg_user, now() AS server_time", {})[0]
