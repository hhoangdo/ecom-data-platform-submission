"""Retrieval FastAPI contract surface."""

from __future__ import annotations

from uuid import uuid4

from fastapi import status

from ..contracts import ApiError, SearchRequest, SearchResponse
from .common import DependencyUnavailable, create_contract_app


app = create_contract_app("edai2-retrieval-agent")


@app.post(
    "/v1/retrieval/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    responses={422: {"model": ApiError}, 409: {"model": ApiError}},
    tags=["retrieval"],
)
async def search(request: SearchRequest) -> SearchResponse:
    """Expose retrieval validation; later topics supply the active index."""

    del request
    raise DependencyUnavailable("index_unavailable", "verified active index is unavailable")


__all__ = ["app", "search"]
