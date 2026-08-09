"""FastAPI drift surface with local dependency-aware probes."""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from ..contracts import ApiError, DriftDetectRequest, DriftDetectResponse
from ..drift import DependencyTimeoutError, DriftDetectionService, FeatureUnavailableError


SERVICE_NAME = "edai2-drift-agent"
ROUTE_NAME = "/v1/drift/detect"
_REQUESTS = Counter("edai2_drift_requests", "Drift HTTP requests by stable outcome.", ("service", "route", "status"))
_DURATION = Histogram("edai2_drift_request_duration_seconds", "Drift HTTP request duration by stable outcome.", ("service", "route", "status"))

app = FastAPI(title=SERVICE_NAME, version="0.1.0")
app.state.drift_service = DriftDetectionService()


def get_drift_service() -> DriftDetectionService:
    """Return the shared service used by HTTP and streamable MCP adapters."""

    return app.state.drift_service


def _error_body(code: str, message: str) -> dict[str, object]:
    return ApiError(code=code, message=message, request_id=uuid4()).model_dump(mode="json")


def _observe(status_code: int, started: float) -> None:
    labels = {"service": SERVICE_NAME, "route": ROUTE_NAME, "status": str(status_code)}
    _REQUESTS.labels(**labels).inc()
    _DURATION.labels(**labels).observe(perf_counter() - started)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Map malformed request models to the shared typed validation envelope."""

    del request, exc
    _observe(422, perf_counter())
    return JSONResponse(status_code=422, content=_error_body("validation_error", "request validation failed"))


@app.post(ROUTE_NAME, response_model=DriftDetectResponse, responses={409: {"model": ApiError}, 422: {"model": ApiError}, 503: {"model": ApiError}}, tags=["drift"])
async def detect(request: DriftDetectRequest) -> DriftDetectResponse | JSONResponse:
    """Return one validated population-drift observation without fabricating data."""

    started = perf_counter()
    try:
        response = await get_drift_service().detect(request)
    except FeatureUnavailableError:
        _observe(409, started)
        return JSONResponse(status_code=409, content=_error_body("feature_unavailable", "verified Section 03 feature health is unavailable"))
    except DependencyTimeoutError:
        _observe(503, started)
        return JSONResponse(status_code=503, content=_error_body("dependency_timeout", "drift dependency timed out"))
    except ValueError:
        _observe(422, started)
        return JSONResponse(status_code=422, content=_error_body("validation_error", "request validation failed"))
    _observe(200, started)
    return response


@app.get("/healthz", tags=["probes"])
async def healthz() -> dict[str, str]:
    """Report process liveness without an external dependency call."""

    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/readyz", tags=["probes"])
async def readyz() -> JSONResponse:
    """Report ready only after the strict prerequisite hash is active."""

    try:
        ready = await get_drift_service().is_ready()
    except Exception:
        ready = False
    if ready:
        return JSONResponse(status_code=200, content={"status": "ready", "service": SERVICE_NAME})
    return JSONResponse(status_code=503, content={"status": "not_ready", "service": SERVICE_NAME})


@app.get("/metrics", tags=["probes"])
async def metrics() -> Response:
    """Return Prometheus text with no customer or request-content labels."""

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


__all__ = ["app", "detect", "get_drift_service"]
