"""Section 03 drift FastAPI contract surface."""

from __future__ import annotations

from fastapi import status

from ..contracts import ApiError, DriftDetectRequest, DriftDetectResponse
from .common import DependencyUnavailable, create_contract_app


app = create_contract_app("edai2-drift-agent")


@app.post(
    "/v1/drift/detect",
    response_model=DriftDetectResponse,
    status_code=status.HTTP_200_OK,
    responses={422: {"model": ApiError}, 409: {"model": ApiError}},
    tags=["drift"],
)
async def detect(request: DriftDetectRequest) -> DriftDetectResponse:
    """Expose drift validation; later topics supply the verified feature view."""

    del request
    raise DependencyUnavailable("feature_unavailable", "verified Section 03 feature health is unavailable")


__all__ = ["app", "detect"]
