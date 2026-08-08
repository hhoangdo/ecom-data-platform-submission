"""Streamable-HTTP MCP adapter for the shared retrieval service."""

from __future__ import annotations

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api.retrieval import app as retrieval_app
from ..api.retrieval import get_retrieval_service
from ..contracts import KnowledgeCategory, SearchRequest, SearchResponse, UtcDateTime


RETRIEVAL_TOOL_NAME = "search_ecommerce_knowledge"
mcp = FastMCP("edai2-retrieval-mcp")


@mcp.tool(name=RETRIEVAL_TOOL_NAME)
async def search_ecommerce_knowledge(
    query: Annotated[str, Field(min_length=1, max_length=2000)],
    top_k: Annotated[int, Field(ge=1, le=8)] = 4,
    category: KnowledgeCategory | None = None,
    effective_at: UtcDateTime | None = None,
) -> SearchResponse:
    """Adapt the exact search contract to the same async retrieval service."""

    return await get_retrieval_service().search(
        SearchRequest(
            query=query,
            top_k=top_k,
            category=category,
            effective_at=effective_at,
        )
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
