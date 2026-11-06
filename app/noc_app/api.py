"""FastAPI routes of the NOC topology app. Every JSON response passes through safety.scrub."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .safety import scrub
from .service import AppError, NocService, User

log = logging.getLogger("noc_app")
STATIC = Path(__file__).resolve().parents[1] / "static"


class SmsReview(BaseModel):
    decision: str = Field(description="approve or reject")
    summary_id: str | None = Field(default=None, description="summary_id of the draft the operator saw")
    note: str | None = None


class GenieQuestion(BaseModel):
    question: str
    conversation_id: str | None = None


def user_from(request: Request) -> User:
    """Identity forwarded by the Databricks Apps proxy (trusted: the app is only reachable through it)."""
    h = request.headers
    return User(email=h.get("x-forwarded-email") or h.get("x-forwarded-preferred-username"),
                token=h.get("x-forwarded-access-token"), name=h.get("x-forwarded-preferred-username"))


def ok(payload) -> JSONResponse:
    return JSONResponse(scrub(jsonable_encoder(payload)))


def create_app(service_factory) -> FastAPI:
    """service_factory: () -> NocService (lazy, so the app starts even if Lakebase is still waking up)."""
    app = FastAPI(title="Banksia NOC topology", version="1.0")
    state: dict = {}

    def svc() -> NocService:
        if "svc" not in state:
            state["svc"] = service_factory()
        return state["svc"]

    @app.exception_handler(AppError)
    async def app_error(_: Request, e: AppError):
        return JSONResponse({"error": str(e)}, status_code=e.status)

    @app.middleware("http")
    async def timing(request: Request, call_next):
        t0 = time.perf_counter()
        resp = await call_next(request)
        log.info("%s %s -> %s in %.0f ms user=%s", request.method, request.url.path, resp.status_code,
                 1000 * (time.perf_counter() - t0), request.headers.get("x-forwarded-email", "-"))
        return resp

    @app.get("/api/health")
    def health():
        t0 = time.perf_counter()
        ping = svc().store.ping()
        return ok({"status": "ok", "lakebase": ping, "lakebase_ms": round(1000 * (time.perf_counter() - t0), 1)})

    @app.get("/api/me")
    def me(request: Request):
        return ok(svc().me(user_from(request)))

    @app.get("/api/incidents")
    def incidents(request: Request, region: str | None = None):
        return ok({"incidents": svc().incidents(user_from(request), region)})

    @app.get("/api/incidents/{incident_id}")
    def incident(request: Request, incident_id: str):
        return ok(svc().incident(user_from(request), incident_id))

    @app.get("/api/regions/{region}/topology")
    def region_topology(request: Request, region: str, incident_id: str | None = None):
        return ok(svc().topology(user_from(request), region, incident_id))

    @app.post("/api/incidents/{incident_id}/sms-review")
    def sms_review(request: Request, incident_id: str, body: SmsReview):
        return ok(svc().review_sms(user_from(request), incident_id, body.decision, body.summary_id, body.note))

    @app.get("/api/incidents/{incident_id}/sms-reviews")
    def sms_reviews(request: Request, incident_id: str):
        return ok({"reviews": svc().reviews(user_from(request), incident_id)})

    @app.get("/api/kpis")
    def kpis(request: Request):
        return ok(svc().kpis(user_from(request)))

    @app.post("/api/genie/ask")
    def genie_ask(request: Request, body: GenieQuestion):
        return ok(svc().ask_genie(user_from(request), body.question, body.conversation_id))

    if STATIC.exists():
        app.mount("/static", StaticFiles(directory=STATIC), name="static")

        @app.get("/")
        def index():
            return FileResponse(STATIC / "index.html")

    return app
