"""Shared probes and sanitized validation errors for FastAPI contracts."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from ..contracts import ApiError


class DependencyUnavailable(Exception):
    """Typed local dependency-unavailable condition."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _error_body(code: str, message: str) -> dict[str, object]:
    return ApiError(code=code, message=message, request_id=uuid4()).model_dump(mode="json")


def create_contract_app(service_name: str) -> FastAPI:
    """Create a local FastAPI app with the required probes and error handler."""

    app = FastAPI(title=service_name, version="0.1.0")

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request, exc
        return JSONResponse(status_code=422, content=_error_body("validation_error", "request validation failed"))

    @app.exception_handler(DependencyUnavailable)
    async def dependency_error_handler(
        request: Request,
        exc: DependencyUnavailable,
    ) -> JSONResponse:
        del request
        return JSONResponse(status_code=409, content=_error_body(exc.code, exc.message))

    @app.get("/healthz", tags=["probes"])
    async def healthz() -> dict[str, str]:
        """Report process liveness without checking external dependencies."""

        return {"status": "ok", "service": service_name}

    @app.get("/readyz", tags=["probes"])
    async def readyz() -> dict[str, str]:
        """Report contract-process readiness without acquiring a runtime."""

        return {"status": "ok", "service": service_name}

    @app.get("/metrics", tags=["probes"])
    async def metrics() -> Response:
        """Return Prometheus text without request or customer labels."""

        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


__all__ = ["DependencyUnavailable", "create_contract_app"]
