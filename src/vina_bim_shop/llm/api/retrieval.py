"""FastAPI retrieval surface with route-local readiness and error mapping."""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from ..contracts import ApiError, SearchRequest, SearchResponse
from ..retrieval import DependencyTimeoutError, FeastRetrievalService, IndexUnavailableError
from ..safety import CitationIntegrityError


SERVICE_NAME = "edai2-retrieval-agent"
ROUTE_NAME = "/v1/retrieval/search"
_REQUESTS = Counter(
    "edai2_retrieval_requests",
    "Retrieval HTTP requests by stable outcome.",
    ("service", "route", "status"),
)
_DURATION = Histogram(
    "edai2_retrieval_request_duration_seconds",
    "Retrieval HTTP request duration by stable outcome.",
    ("service", "route", "status"),
)

app = FastAPI(title=SERVICE_NAME, version="0.1.0")
app.state.retrieval_service = FeastRetrievalService()


def get_retrieval_service() -> FeastRetrievalService:
    """Return the app-owned retrieval dependency for HTTP and MCP adapters."""

    return app.state.retrieval_service


def _error_body(code: str, message: str) -> dict[str, object]:
    return ApiError(code=code, message=message, request_id=uuid4()).model_dump(mode="json")


def _observe(status_code: int, started: float) -> None:
    labels = {"service": SERVICE_NAME, "route": ROUTE_NAME, "status": str(status_code)}
    _REQUESTS.labels(**labels).inc()
    _DURATION.labels(**labels).observe(perf_counter() - started)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return a sanitized, typed envelope for invalid retrieval input."""

    del request, exc
    started = perf_counter()
    _observe(status.HTTP_422_UNPROCESSABLE_CONTENT, started)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=_error_body("validation_error", "request validation failed"),
    )


@app.post(
    ROUTE_NAME,
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    responses={
        409: {"model": ApiError},
        422: {"model": ApiError},
        503: {"model": ApiError},
    },
    tags=["retrieval"],
)
async def search(request: SearchRequest) -> SearchResponse | JSONResponse:
    """Run one validated retrieval request without fabricating data."""

    started = perf_counter()
    try:
        response = await get_retrieval_service().search(request)
    except (IndexUnavailableError, CitationIntegrityError):
        _observe(status.HTTP_409_CONFLICT, started)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error_body("index_unavailable", "verified active index is unavailable"),
        )
    except DependencyTimeoutError:
        _observe(status.HTTP_503_SERVICE_UNAVAILABLE, started)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_error_body("dependency_timeout", "retrieval dependency timed out"),
        )
    _observe(status.HTTP_200_OK, started)
    return response


@app.get("/healthz", tags=["probes"])
async def healthz() -> dict[str, str]:
    """Report process liveness without checking external dependencies."""

    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/readyz", tags=["probes"])
async def readyz() -> JSONResponse:
    """Report whether the retrieval dependency has a verified active index."""

    if await get_retrieval_service().is_ready():
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready", "service": SERVICE_NAME})
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready", "service": SERVICE_NAME},
    )


@app.get("/metrics", tags=["probes"])
async def metrics() -> Response:
    """Return Prometheus metrics with no request-content labels."""

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


__all__ = ["app", "get_retrieval_service", "search"]
