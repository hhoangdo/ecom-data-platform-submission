"""Retrieval MCP tool contract and OpenAPI schema binding."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api.retrieval import app as retrieval_app
from ..contracts import (
    KnowledgeCategory,
    SearchResponse,
    UtcDateTime,
)


RETRIEVAL_TOOL_NAME = "search_ecommerce_knowledge"
mcp = FastMCP("edai2-retrieval-mcp")


@mcp.tool(name=RETRIEVAL_TOOL_NAME)
async def search_ecommerce_knowledge(
    query: Annotated[str, Field(min_length=1, max_length=2000)],
    top_k: Annotated[int, Field(ge=1, le=8)] = 4,
    category: KnowledgeCategory | None = None,
    effective_at: UtcDateTime | None = None,
) -> SearchResponse:
    """Return the typed local retrieval abstention until an index is promoted."""

    del query, top_k, category, effective_at
    return SearchResponse(
        request_id=uuid4(),
        index_version="unavailable",
        embedding_model="BAAI/bge-small-en-v1.5",
        matches=[],
        retrieval_ms=0.0,
        abstained=True,
        reason="index_unavailable",
    )


RETRIEVAL_TOOL_INPUT_SCHEMA = retrieval_app.openapi()["components"]["schemas"]["SearchRequest"]
RETRIEVAL_TOOL_OUTPUT_SCHEMA = retrieval_app.openapi()["components"]["schemas"]["SearchResponse"]
_registered_tool = mcp._tool_manager._tools[RETRIEVAL_TOOL_NAME]
_registered_tool.parameters = RETRIEVAL_TOOL_INPUT_SCHEMA
_registered_tool.fn_metadata.output_schema = RETRIEVAL_TOOL_OUTPUT_SCHEMA
streamable_http_app = mcp.streamable_http_app()


__all__ = [
    "RETRIEVAL_TOOL_INPUT_SCHEMA",
    "RETRIEVAL_TOOL_NAME",
    "RETRIEVAL_TOOL_OUTPUT_SCHEMA",
    "mcp",
    "search_ecommerce_knowledge",
    "streamable_http_app",
]
