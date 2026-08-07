"""Stable, dependency-light domain and API contracts for EDAI2."""

from __future__ import annotations

from datetime import date, timedelta
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)


class ContractModel(BaseModel):
    """Base model that rejects undeclared contract fields."""

    model_config = ConfigDict(extra="forbid")


def require_utc(value: AwareDatetime) -> AwareDatetime:
    """Require an aware timestamp whose offset is exactly UTC."""

    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be timezone-aware UTC")
    return value


UtcDateTime = Annotated[AwareDatetime, AfterValidator(require_utc)]
Sha256 = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]


class ApiError(ContractModel):
    """Sanitized error envelope shared by every HTTP surface."""

    code: StrictStr
    message: StrictStr
    request_id: UUID


class KnowledgeCategory(StrEnum):
    """Allowlisted knowledge-document categories."""

    RETURNS = "returns"
    SHIPPING = "shipping"
    CANCELLATION = "cancellation"
    PAYMENTS = "payments"
    PROMOTIONS = "promotions"
    WARRANTIES = "warranties"
    PRIVACY = "privacy"
    MARKETPLACE_SUPPORT = "marketplace_support"


class SearchRequest(ContractModel):
    """Bounded retrieval request with an optional effective-time filter."""

    query: Annotated[StrictStr, Field(min_length=1, max_length=2000)]
    top_k: Annotated[StrictInt, Field(ge=1, le=8)] = 4
    category: KnowledgeCategory | None = None
    effective_at: UtcDateTime | None = None


class KnowledgeCitation(ContractModel):
    """Immutable knowledge-chunk citation."""

    kind: Literal["knowledge"] = "knowledge"
    chunk_id: StrictStr
    document_id: StrictStr
    category: KnowledgeCategory
    version: StrictStr
    effective_from: UtcDateTime
    effective_to: UtcDateTime | None
    content_sha256: Sha256


class DriftEvidenceCitation(ContractModel):
    """Hash-bound citation for a Section 03 drift result."""

    kind: Literal["drift"] = "drift"
    section03_manifest_sha256: Sha256
    feature_health_sha256: Sha256
    feature_name: Literal["f_customer_order_frequency_7d"]
    window_days: Literal[7]
    baseline_date: date
    monitoring_date: date
    result_sha256: Sha256


GroundingCitation = Annotated[
    KnowledgeCitation | DriftEvidenceCitation,
    Field(discriminator="kind"),
]


class SearchMatch(ContractModel):
    """One ordered retrieval result."""

    content: StrictStr
    score: StrictFloat
    citation: KnowledgeCitation


class SearchResponse(ContractModel):
    """Retrieval response with explicit abstention state."""

    request_id: UUID
    index_version: StrictStr
    embedding_model: Literal["BAAI/bge-small-en-v1.5"]
    matches: list[SearchMatch]
    retrieval_ms: StrictFloat
    abstained: StrictBool
    reason: StrictStr | None


class TimeWindow(ContractModel):
    """Exclusive-end UTC time window."""

    start: UtcDateTime
    end: UtcDateTime

    @model_validator(mode="after")
    def validate_order(self) -> "TimeWindow":
        """Require a non-empty forward window."""

        if self.start >= self.end:
            raise ValueError("window start must be before end")
        return self


class Section03FeatureRow(ContractModel):
    """Exact point-in-time feature/label row exposed by Section 03."""

    id: StrictStr
    event_timestamp: UtcDateTime
    label: Literal[0, 1]
    f_customer_total_orders_90d: StrictInt
    f_customer_paid_revenue_90d: StrictFloat
    f_customer_avg_order_value_90d: StrictFloat
    f_customer_distinct_categories_90d: StrictInt
    f_stream_views_60m: StrictInt
    f_stream_add_to_cart_60m: StrictInt
    f_stream_checkout_started_60m: StrictInt
    f_stream_order_placed_60m: StrictInt
    f_stream_cart_to_purchase_ratio_60m: StrictFloat
    created: UtcDateTime


class FeatureHealthPoint(ContractModel):
    """One published daily feature-health observation."""

    monitoring_date: date
    feature_name: Literal["f_customer_order_frequency_7d"]
    window_days: Literal[7]
    baseline_date: date
    customer_count: StrictInt
    mean_value: StrictFloat
    psi_vs_baseline: StrictFloat
    drift_status: Literal["stable", "warning", "alert"]


class DriftDetectRequest(ContractModel):
    """Population drift request using two complete UTC windows."""

    id: Annotated[StrictStr, Field(min_length=1, max_length=128)] | None = None
    baseline_window: TimeWindow
    candidate_window: TimeWindow
    feature_name: Literal["f_customer_order_frequency_7d"] = (
        "f_customer_order_frequency_7d"
    )


class DriftDetectResponse(ContractModel):
    """Drift response with optional cutoff-safe customer context."""

    request_id: UUID
    scope: Literal["population"]
    feature_name: Literal["f_customer_order_frequency_7d"]
    window_days: Literal[7]
    baseline_window: TimeWindow
    candidate_window: TimeWindow
    population_size: StrictInt
    candidate_day_count: StrictInt
    baseline_mean: StrictFloat
    candidate_mean: StrictFloat
    psi: StrictFloat
    status: Literal["stable", "warning", "alert"]
    drift_detected: StrictBool
    feature_service_version: StrictStr
    customer_context: Section03FeatureRow | None
    observed_at: UtcDateTime


class ChatRequest(ContractModel):
    """Coordinator chat request."""

    session_id: UUID
    message: Annotated[StrictStr, Field(min_length=1, max_length=4000)]
    route: Literal["auto", "support", "drift"] = "auto"


class GroundedClaim(ContractModel):
    """One answer claim and its evidence citations."""

    text: StrictStr
    citations: list[GroundingCitation]


class ToolCallRecord(ContractModel):
    """Sanitized record of each attempted specialist tool call."""

    tool: Literal["search_ecommerce_knowledge", "detect_customer_order_drift"]
    status: Literal["succeeded", "failed", "timed_out", "rejected"]
    duration_ms: StrictFloat
    error_code: StrictStr | None


class ChatResponse(ContractModel):
    """Coordinator response with grounded-claim and safety boundaries."""

    request_id: UUID
    route: Literal["support", "drift", "abstain"]
    answer: StrictStr
    claims: list[GroundedClaim]
    agent_name: StrictStr
    agent_version: StrictStr
    model_version: StrictStr
    index_version: StrictStr | None
    tool_calls: list[ToolCallRecord]
    safety_action: Literal["allow", "redact", "reject", "abstain"]


class IndexBuildReport(ContractModel):
    """Candidate index inventory report."""

    index_version: StrictStr
    document_count: Literal[8]
    document_version_count: Literal[9]
    chunk_count: StrictInt
    embedding_dimension: Literal[384]
    source_sha256: dict[StrictStr, Sha256]


class IndexValidationReport(ContractModel):
    """Candidate index quality-gate report."""

    index_version: StrictStr
    recall_at_4: StrictFloat
    citation_precision: StrictFloat
    safety_pass_rate: StrictFloat
    passed: StrictBool
    failures: list[StrictStr]


class ObservedGeneration(ContractModel):
    """Sanitized generation measurement returned by an inference adapter."""

    text: StrictStr
    model_version: StrictStr
    input_tokens: StrictInt
    output_tokens: StrictInt
    total_tokens: StrictInt
    ttft_ms: StrictFloat
    generation_ms: StrictFloat
    finish_reason: Literal["stop", "length", "rejected", "error"]


class WarmupResult(ContractModel):
    """Measured model warm-up result."""

    model_version: StrictStr
    prompt_count: StrictInt
    elapsed_ms: StrictFloat
    ready: StrictBool


__all__ = [
    "ApiError",
    "ChatRequest",
    "ChatResponse",
    "ContractModel",
    "DriftDetectRequest",
    "DriftDetectResponse",
    "DriftEvidenceCitation",
    "FeatureHealthPoint",
    "GroundedClaim",
    "GroundingCitation",
    "IndexBuildReport",
    "IndexValidationReport",
    "KnowledgeCategory",
    "KnowledgeCitation",
    "ObservedGeneration",
    "SearchMatch",
    "SearchRequest",
    "SearchResponse",
    "Section03FeatureRow",
    "Sha256",
    "TimeWindow",
    "ToolCallRecord",
    "UtcDateTime",
    "WarmupResult",
    "require_utc",
]
