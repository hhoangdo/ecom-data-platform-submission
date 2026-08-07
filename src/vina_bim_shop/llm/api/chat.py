"""Coordinator chat FastAPI contract surface."""

from __future__ import annotations

from uuid import uuid4

from fastapi import status

from ..contracts import ApiError, ChatRequest, ChatResponse
from .common import create_contract_app


app = create_contract_app("edai2-coordinator")


@app.post(
    "/v1/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    responses={422: {"model": ApiError}},
    tags=["chat"],
)
async def chat(request: ChatRequest) -> ChatResponse:
    """Return a grounded abstention until a verified coordinator is supplied."""

    del request
    return ChatResponse(
        request_id=uuid4(),
        route="abstain",
        answer="I cannot answer without a verified evidence service.",
        claims=[],
        agent_name="commerce-coordinator",
        agent_version="contract-only",
        model_version="unavailable",
        index_version=None,
        tool_calls=[],
        safety_action="abstain",
    )


__all__ = ["app", "chat"]
