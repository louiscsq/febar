"""Ask Genie from the app: the Genie Conversation API on the NOC space, as the signed-in user.

The user's forwarded token carries the `dashboards.genie` scope, so Genie generates and runs the SQL with the user's
own Unity Catalog permissions (regional row filters apply; the scorecard table only answers for the national role).
The app's service principal holds CAN_RUN on the space (app resource) for completeness, but questions are never
asked as the app. Results pass through safety.scrub_table before they reach the browser.
"""

from __future__ import annotations

from typing import Protocol

from .safety import scrub, scrub_table


class Genie(Protocol):
    def ask(self, user_token: str | None, question: str, conversation_id: str | None = None) -> dict: ...


def _message_to_answer(w, space_id: str, msg) -> dict:
    out = {"conversation_id": msg.conversation_id, "message_id": msg.message_id or msg.id,
           "status": msg.status.value if msg.status else None, "text": [], "sql": None, "description": None,
           "columns": [], "rows": [], "row_count": 0, "error": msg.error.error if msg.error else None}
    for att in msg.attachments or []:
        if att.text and att.text.content:
            out["text"].append(att.text.content)
        if att.query:
            out["sql"] = att.query.query
            out["description"] = att.query.description
            res = w.genie.get_message_attachment_query_result(space_id, out["conversation_id"], out["message_id"],
                                                              att.attachment_id)
            sr = res.statement_response
            if sr and sr.manifest and sr.manifest.schema:
                cols = [c.name for c in sr.manifest.schema.columns]
                data = (sr.result.data_array if sr.result else None) or []
                out["columns"], out["rows"] = scrub_table(cols, data[:200])
                out["row_count"] = len(data)
    return scrub(out)


class GenieClient:
    def __init__(self, settings):
        self.s = settings

    def ask(self, user_token: str | None, question: str, conversation_id: str | None = None) -> dict:
        from datetime import timedelta

        from databricks.sdk import WorkspaceClient

        w = WorkspaceClient(host=self.s.host, token=user_token, auth_type="pat") if user_token else WorkspaceClient()
        if conversation_id:
            msg = w.genie.create_message_and_wait(self.s.genie_space_id, conversation_id, question,
                                                  timeout=timedelta(minutes=3))
        else:
            msg = w.genie.start_conversation_and_wait(self.s.genie_space_id, question, timeout=timedelta(minutes=3))
        return _message_to_answer(w, self.s.genie_space_id, msg)
