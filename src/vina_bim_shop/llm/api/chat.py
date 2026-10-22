"""Coordinator chat FastAPI facade with typed errors and content-free metrics."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from html import escape
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from opentelemetry import trace
from opentelemetry.propagate import extract
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from ..adapters.direct import DirectCoordinatorAdapter
from ..adapters.kagent import KagentCoordinatorAdapter
from ..contracts import ApiError, ChatRequest, ChatResponse
from ..coordinator import CommerceAgentCoordinator
from ..inference import ContextTooLargeError
from ..observability import configure_tracing


SERVICE_NAME = "edai2-coordinator"
ROUTE_NAME = "/v1/chat"
_TRACER = trace.get_tracer(__name__)
configure_tracing(SERVICE_NAME)
_REQUESTS = Counter("edai2_chat_requests", "Chat requests by stable outcome.", ("service", "route", "status"))
_DURATION = Histogram("edai2_chat_request_duration_seconds", "Chat duration by stable outcome.", ("service", "route", "status"))

app = FastAPI(title=SERVICE_NAME, version="0.1.0")


def _langfuse_from_environment(settings: Mapping[str, str]) -> object | None:
    public_key = settings.get("LANGFUSE_PUBLIC_KEY")
    secret_key = settings.get("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        return None
    from langfuse import Langfuse

    return Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=settings.get("LANGFUSE_HOST", "http://langfuse-web.edai2.svc.cluster.local:3000"),
    )


def create_coordinator_from_environment(
    environ: Mapping[str, str] | None = None,
) -> CommerceAgentCoordinator:
    """Build the direct T27 runtime or the fail-closed kagent facade."""

    settings = os.environ if environ is None else environ
    retrieval_url = settings.get("EDAI2_RETRIEVAL_URL")
    llm_url = settings.get("EDAI2_LLM_URL")
    api_key = settings.get("EDAI2_LLM_API_KEY")
    if retrieval_url or llm_url or api_key:
        if not all((retrieval_url, llm_url, api_key)):
            raise RuntimeError(
                "direct chat runtime requires EDAI2_RETRIEVAL_URL, EDAI2_LLM_URL, and EDAI2_LLM_API_KEY"
            )
        return CommerceAgentCoordinator(
            agent=DirectCoordinatorAdapter(
                retrieval_url=str(retrieval_url),
                llm_url=str(llm_url),
                llm_api_key=str(api_key),
                model=settings.get("EDAI2_LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct"),
                langfuse=_langfuse_from_environment(settings),
            )
        )
    return CommerceAgentCoordinator(agent=KagentCoordinatorAdapter())


app.state.coordinator = create_coordinator_from_environment()


def get_coordinator() -> CommerceAgentCoordinator:
    return app.state.coordinator


def _error_body(code: str, message: str) -> dict[str, object]:
    return ApiError(code=code, message=message, request_id=uuid4()).model_dump(mode="json")


def _observe(status_code: int, started: float) -> None:
    labels = {"service": SERVICE_NAME, "route": ROUTE_NAME, "status": str(status_code)}
    _REQUESTS.labels(**labels).inc()
    _DURATION.labels(**labels).observe(perf_counter() - started)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    del request, exc
    _observe(422, perf_counter())
    return JSONResponse(status_code=422, content=_error_body("validation_error", "request validation failed"))


@app.exception_handler(ContextTooLargeError)
async def context_too_large_handler(request: Request, exc: ContextTooLargeError) -> JSONResponse:
    del request, exc
    _observe(422, perf_counter())
    return JSONResponse(status_code=422, content=_error_body("context_too_large", "fixed chat context exceeds token budget"))


@app.post(
    ROUTE_NAME,
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    responses={422: {"model": ApiError}},
    tags=["chat"],
)
async def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    context = extract(http_request.headers)
    with _TRACER.start_as_current_span("facade", context=context) as span:
        started = perf_counter()
        response = await get_coordinator().chat(request)
        span.set_attribute("http.status_code", 200)
        _observe(200, started)
        return response


@app.get("/evidence/auth-rate-limit", response_class=HTMLResponse, include_in_schema=False)
async def auth_rate_limit_evidence() -> str:
    """Render the real 401/429 probe result for the T27 rate-limit capture."""

    path = Path(
        os.environ.get("EDAI2_RATE_LIMIT_EVIDENCE", "/evidence/https_rate_limit.json")
    )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=404, detail="rate limit evidence is unavailable") from error
    attempts = ", ".join(str(item) for item in payload.get("attempts", []))
    return (
        "<!doctype html><html><head><title>EDAI2 Chat 401/429</title></head>"
        "<body><main><h1>EDAI2 Chat authentication and rate limit</h1>"
        f"<p>Unauthenticated status: <strong>{escape(str(payload.get('unauthenticated_status')))}</strong></p>"
        f"<p>Authenticated burst accepted: <strong>{escape(str(payload.get('accepted')))}</strong></p>"
        f"<p>Over-limit status: <strong>{escape(str(payload.get('over_limit_status')))}</strong></p>"
        f"<p>Observed attempts: {escape(attempts)}</p>"
        f"<p>Observed at: {escape(str(payload.get('at')))}</p>"
        "</main></body></html>"
    )


@app.get("/healthz", tags=["probes"])
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/readyz", tags=["probes"])
async def readyz() -> dict[str, str]:
    if await get_coordinator().is_ready():
        return {"status": "ready", "service": SERVICE_NAME}
    return JSONResponse(status_code=503, content={"status": "not_ready", "service": SERVICE_NAME})


@app.get("/metrics", tags=["probes"])
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


__all__ = ["app", "chat", "create_coordinator_from_environment", "get_coordinator"]
