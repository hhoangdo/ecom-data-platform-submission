"""Drift MCP tool contract and OpenAPI schema binding."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ..api.drift import app as drift_app
from ..contracts import DriftDetectResponse, TimeWindow, UtcDateTime


DRIFT_TOOL_NAME = "detect_customer_order_drift"
mcp = FastMCP("edai2-drift-mcp")


@mcp.tool(name=DRIFT_TOOL_NAME)
async def detect_customer_order_drift(
    id: Annotated[str, Field(min_length=1, max_length=128)] | None,
    baseline_window: TimeWindow,
    candidate_window: TimeWindow,
    feature_name: str = "f_customer_order_frequency_7d",
) -> DriftDetectResponse:
    """Expose the typed drift boundary without fabricating a measurement."""

    del id, baseline_window, candidate_window, feature_name
    raise RuntimeError("feature_unavailable")


DRIFT_TOOL_INPUT_SCHEMA = drift_app.openapi()["components"]["schemas"]["DriftDetectRequest"]
DRIFT_TOOL_OUTPUT_SCHEMA = drift_app.openapi()["components"]["schemas"]["DriftDetectResponse"]
_registered_tool = mcp._tool_manager._tools[DRIFT_TOOL_NAME]
_registered_tool.parameters = DRIFT_TOOL_INPUT_SCHEMA
_registered_tool.fn_metadata.output_schema = DRIFT_TOOL_OUTPUT_SCHEMA
streamable_http_app = mcp.streamable_http_app()


__all__ = [
    "DRIFT_TOOL_INPUT_SCHEMA",
    "DRIFT_TOOL_NAME",
    "DRIFT_TOOL_OUTPUT_SCHEMA",
    "detect_customer_order_drift",
    "mcp",
    "streamable_http_app",
]
