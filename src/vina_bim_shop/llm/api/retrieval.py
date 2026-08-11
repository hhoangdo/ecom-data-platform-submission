"""FastAPI retrieval surface with route-local readiness and error mapping."""

from __future__ import annotations

import os
from collections.abc import Mapping
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


class _KindPreflightFakeRetrieval:
    """Expose a verified-empty retrieval dependency for the dedicated Kind smoke."""

    async def active_version(self) -> str:
        """Return the fixed local-only index identity."""

        return "kind-preflight-empty"

    async def candidate_complete(self, index_version: str) -> bool:
        """Accept only the fixed local-only index identity."""

        return index_version == "kind-preflight-empty"

    async def is_validated(self, index_version: str) -> bool:
        """Accept only the fixed local-only index identity."""

        return index_version == "kind-preflight-empty"

    async def search_documents(
        self,
        vector: list[float],
        *,
        top_k: int,
        category: str | None,
        effective_at: object,
    ) -> list[object]:
        """Return no documents so the API emits a typed abstention."""

        del vector, top_k, category, effective_at
        return []

    async def get_verified_chunk(
        self,
        *,
        chunk_id: str,
        content_sha256: str,
    ) -> None:
        """Return no chunk because the fake dependency never returns matches."""

        del chunk_id, content_sha256
        return None


class _KindPreflightFakeEmbedder:
    """Provide the required query adapter without generating retrieval content."""

    async def embed_query(self, query: str) -> list[float]:
        """Return a fixed-dimensional zero vector for the empty local slice."""

        del query
        return [0.0] * 384


_KIND_PREFLIGHT_ENVIRONMENT = {
    "EDAI2_ENVIRONMENT": "local",
    "EDAI2_RUNTIME_MODE": "kind-preflight",
    "EDAI2_ALLOW_FAKE_RETRIEVAL": "1",
}


def create_retrieval_service_from_environment(
    environ: Mapping[str, str] | None = None,
) -> FeastRetrievalService:
    """Build the default unavailable service or the exact local Kind fake dependency."""

    settings = os.environ if environ is None else environ
    if not any(name in settings for name in _KIND_PREFLIGHT_ENVIRONMENT):
        return FeastRetrievalService()
    if {name: settings.get(name) for name in _KIND_PREFLIGHT_ENVIRONMENT} != _KIND_PREFLIGHT_ENVIRONMENT:
        raise RuntimeError("kind-preflight retrieval requires the exact local environment gate")
    return FeastRetrievalService(
        feast=_KindPreflightFakeRetrieval(),
        embedder=_KindPreflightFakeEmbedder(),
    )


app.state.retrieval_service = create_retrieval_service_from_environment()


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


__all__ = [
    "app",
    "create_retrieval_service_from_environment",
    "get_retrieval_service",
    "search",
]
