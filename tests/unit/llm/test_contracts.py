from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from vina_bim_shop.llm.contracts import (
    ApiError,
    ChatRequest,
    ChatResponse,
    DriftDetectRequest,
    DriftDetectResponse,
    DriftEvidenceCitation,
    FeatureHealthPoint,
    GroundedClaim,
    IndexBuildReport,
    IndexValidationReport,
    KnowledgeCitation,
    SearchRequest,
    SearchResponse,
    Section03FeatureRow,
    TimeWindow,
    ToolCallRecord,
)
from vina_bim_shop.llm.drift import DriftDetectionService
from vina_bim_shop.llm.indexing import RagIndexPipeline
from vina_bim_shop.llm.inference import ObservedInferenceClient
from vina_bim_shop.llm.ports import (
    CoordinatorAgentPort,
    EmbeddingPort,
    FeastPort,
    InferencePort,
    McpClientPort,
)
from vina_bim_shop.llm.retrieval import FeastRetrievalService
from vina_bim_shop.llm.routing import RouteStrategy
from vina_bim_shop.llm.coordinator import CommerceAgentCoordinator


ALL_MODELS = [
    ApiError,
    SearchRequest,
    KnowledgeCitation,
    SearchResponse,
    TimeWindow,
    Section03FeatureRow,
    FeatureHealthPoint,
    DriftDetectRequest,
    DriftDetectResponse,
    ChatRequest,
    GroundedClaim,
    ToolCallRecord,
    ChatResponse,
    IndexBuildReport,
    IndexValidationReport,
    DriftEvidenceCitation,
]


def test_domain_models_forbid_unknown_fields() -> None:
    assert all(model.model_config["extra"] == "forbid" for model in ALL_MODELS)


def test_search_request_enforces_strict_bounds_and_utc() -> None:
    valid = SearchRequest(
        query="returns",
        top_k=4,
        effective_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
    )
    assert valid.top_k == 4

    with pytest.raises(ValidationError):
        SearchRequest(query="returns", top_k=0)
    with pytest.raises(ValidationError):
        SearchRequest(query="returns", top_k=9)
    with pytest.raises(ValidationError):
        SearchRequest(query="returns", top_k="4")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        SearchRequest(
            query="returns",
            effective_at=datetime(
                2026, 8, 7, tzinfo=timezone(timedelta(hours=7))
            ),
        )
    with pytest.raises(ValidationError):
        SearchRequest(query="returns", unexpected=True)  # type: ignore[call-arg]


def test_time_window_and_drift_request_are_ordered_and_typed() -> None:
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    end = datetime(2026, 4, 8, tzinfo=timezone.utc)
    request = DriftDetectRequest(
        baseline_window=TimeWindow(start=start, end=end),
        candidate_window=TimeWindow(
            start=datetime(2026, 4, 11, tzinfo=timezone.utc),
            end=datetime(2026, 4, 12, tzinfo=timezone.utc),
        ),
    )
    assert request.feature_name == "f_customer_order_frequency_7d"

    with pytest.raises(ValidationError):
        TimeWindow(start=end, end=start)


def test_response_contracts_keep_typed_citations_and_tool_calls() -> None:
    request_id = uuid4()
    citation = KnowledgeCitation(
        chunk_id="chunk-1",
        document_id="returns",
        category="returns",
        version="1.0.0",
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        effective_to=None,
        content_sha256="a" * 64,
    )
    response = SearchResponse(
        request_id=request_id,
        index_version="index-20260807",
        embedding_model="BAAI/bge-small-en-v1.5",
        matches=[],
        retrieval_ms=1.0,
        abstained=True,
        reason="index_unavailable",
    )
    assert response.request_id == request_id
    assert citation.model_dump()["kind"] == "knowledge"

    drift = DriftEvidenceCitation(
        section03_manifest_sha256="b" * 64,
        feature_health_sha256="c" * 64,
        feature_name="f_customer_order_frequency_7d",
        window_days=7,
        baseline_date="2026-04-10",
        monitoring_date="2026-04-11",
        result_sha256="d" * 64,
    )
    assert drift.kind == "drift"


def test_focus_class_method_signatures_are_stable() -> None:
    assert list(inspect.signature(RagIndexPipeline.build_candidate).parameters) == [
        "self",
        "source_paths",
        "index_version",
    ]
    assert list(inspect.signature(RagIndexPipeline.validate_candidate).parameters) == [
        "self",
        "index_version",
        "evaluation_path",
    ]
    assert list(inspect.signature(FeastRetrievalService.search).parameters) == [
        "self",
        "request",
    ]
    assert list(inspect.signature(DriftDetectionService.detect).parameters) == [
        "self",
        "request",
    ]
    assert list(inspect.signature(ObservedInferenceClient.generate).parameters) == [
        "self",
        "messages",
        "model_variant",
        "max_context_tokens",
    ]
    assert (
        inspect.signature(ObservedInferenceClient.generate)
        .parameters["max_context_tokens"]
        .default
        == 4096
    )
    assert list(inspect.signature(CommerceAgentCoordinator.chat).parameters) == [
        "self",
        "request",
    ]


def test_ports_and_route_strategy_are_runtime_protocols() -> None:
    protocols = [
        EmbeddingPort,
        FeastPort,
        InferencePort,
        McpClientPort,
        CoordinatorAgentPort,
        RouteStrategy,
    ]
    assert all(getattr(protocol, "_is_protocol", False) for protocol in protocols)
