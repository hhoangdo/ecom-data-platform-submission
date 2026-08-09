"""Coordinator chat FastAPI facade with typed errors and content-free metrics."""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from ..adapters.kagent import KagentCoordinatorAdapter
from ..contracts import ApiError, ChatRequest, ChatResponse
from ..coordinator import CommerceAgentCoordinator
from ..inference import ContextTooLargeError


SERVICE_NAME = "edai2-coordinator"
ROUTE_NAME = "/v1/chat"
_REQUESTS = Counter("edai2_chat_requests", "Chat requests by stable outcome.", ("service", "route", "status"))
_DURATION = Histogram("edai2_chat_request_duration_seconds", "Chat duration by stable outcome.", ("service", "route", "status"))

app = FastAPI(title=SERVICE_NAME, version="0.1.0")
app.state.coordinator = CommerceAgentCoordinator(agent=KagentCoordinatorAdapter())


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
async def chat(request: ChatRequest) -> ChatResponse:
    started = perf_counter()
    response = await get_coordinator().chat(request)
    _observe(200, started)
    return response


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


__all__ = ["app", "chat", "get_coordinator"]
