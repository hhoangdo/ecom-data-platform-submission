from __future__ import annotations

import inspect
import json

import pytest

from vina_bim_shop.llm.api.drift import app as drift_app
from vina_bim_shop.llm.api.retrieval import app as retrieval_app
from vina_bim_shop.llm.mcp.drift import (
    DRIFT_TOOL_INPUT_SCHEMA,
    DRIFT_TOOL_NAME,
    DRIFT_TOOL_OUTPUT_SCHEMA,
    detect_customer_order_drift,
)
from vina_bim_shop.llm.mcp.retrieval import (
    RETRIEVAL_TOOL_INPUT_SCHEMA,
    RETRIEVAL_TOOL_NAME,
    RETRIEVAL_TOOL_OUTPUT_SCHEMA,
    search_ecommerce_knowledge,
)
from vina_bim_shop.llm.retrieval import FeastRetrievalService, IndexUnavailableError
from vina_bim_shop.llm.drift import DriftDetectionService, FeatureUnavailableError


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def test_only_the_two_named_mcp_tools_are_declared() -> None:
    assert RETRIEVAL_TOOL_NAME == "search_ecommerce_knowledge"
    assert DRIFT_TOOL_NAME == "detect_customer_order_drift"
    assert list(inspect.signature(search_ecommerce_knowledge).parameters) == [
        "query",
        "top_k",
        "category",
        "effective_at",
    ]
    assert list(inspect.signature(detect_customer_order_drift).parameters) == [
        "id",
        "baseline_window",
        "candidate_window",
        "feature_name",
    ]
    assert inspect.signature(search_ecommerce_knowledge).parameters["top_k"].default == 4
    assert (
        inspect.signature(detect_customer_order_drift)
        .parameters["feature_name"]
        .default
        == "f_customer_order_frequency_7d"
    )


def test_mcp_input_and_output_schemas_byte_match_openapi_components() -> None:
    retrieval_components = retrieval_app.openapi()["components"]["schemas"]
    drift_components = drift_app.openapi()["components"]["schemas"]
    assert _canonical(RETRIEVAL_TOOL_INPUT_SCHEMA) == _canonical(
        retrieval_components["SearchRequest"]
    )
    assert _canonical(RETRIEVAL_TOOL_OUTPUT_SCHEMA) == _canonical(
        retrieval_components["SearchResponse"]
    )
    assert _canonical(DRIFT_TOOL_INPUT_SCHEMA) == _canonical(
        drift_components["DriftDetectRequest"]
    )
    assert _canonical(DRIFT_TOOL_OUTPUT_SCHEMA) == _canonical(
        drift_components["DriftDetectResponse"]
    )


def test_retrieval_mcp_registers_only_its_named_tool() -> None:
    from vina_bim_shop.llm.mcp.retrieval import mcp

    assert set(mcp._tool_manager._tools) == {RETRIEVAL_TOOL_NAME}


@pytest.mark.asyncio
async def test_retrieval_mcp_uses_the_same_unavailable_service_boundary() -> None:
    original_service = retrieval_app.state.retrieval_service
    try:
        retrieval_app.state.retrieval_service = FeastRetrievalService()
        with pytest.raises(IndexUnavailableError, match="index_unavailable"):
            await search_ecommerce_knowledge(query="returns")
    finally:
        retrieval_app.state.retrieval_service = original_service


@pytest.mark.asyncio
async def test_drift_mcp_uses_the_same_unavailable_service_boundary() -> None:
    original_service = getattr(drift_app.state, "drift_service", None)
    try:
        drift_app.state.drift_service = DriftDetectionService()
        with pytest.raises(FeatureUnavailableError, match="feature_unavailable"):
            await detect_customer_order_drift(
                id=None,
                baseline_window={"start": "2026-04-04T00:00:00Z", "end": "2026-04-11T00:00:00Z"},
                candidate_window={"start": "2026-04-11T00:00:00Z", "end": "2026-04-12T00:00:00Z"},
            )
    finally:
        drift_app.state.drift_service = original_service
