"""Pure retrieval-integrity and later chat-safety boundaries."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from .contracts import (
    ChatResponse,
    DriftEvidenceCitation,
    KnowledgeCitation,
    SearchMatch,
)


class CitationIntegrityError(ValueError):
    """Raised when a retrieved citation cannot bind immutable content."""


@dataclass(frozen=True)
class SafetyDecision:
    """Sanitized decision that carries no raw secret or PII."""

    action: str
    reason_code: str


def verify_knowledge_match(match: SearchMatch) -> SearchMatch:
    """Require a knowledge citation whose hash binds the returned content."""

    citation = match.citation
    if not isinstance(citation, KnowledgeCitation) or citation.kind != "knowledge":
        raise CitationIntegrityError("citation_kind_mismatch")
    digest = hashlib.sha256(match.content.encode("utf-8")).hexdigest()
    if digest != citation.content_sha256:
        raise CitationIntegrityError("content_sha256_mismatch")
    return match


def verify_reloaded_match(
    match: SearchMatch,
    reloaded: SearchMatch | None,
) -> SearchMatch:
    """Bind a ranked result to the active persisted chunk it cites."""

    verify_knowledge_match(match)
    if reloaded is None:
        raise CitationIntegrityError("citation_not_found")
    verify_knowledge_match(reloaded)
    if match.content != reloaded.content or match.citation != reloaded.citation:
        raise CitationIntegrityError("citation_reload_mismatch")
    return match


def inspect_message(message: str) -> SafetyDecision:
    """Reject injection and require email redaction without external calls."""

    if re.search(r"ignore\s+(all|previous)\s+instructions", message, re.IGNORECASE):
        return SafetyDecision(action="reject", reason_code="prompt_injection")
    if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", message, re.IGNORECASE):
        return SafetyDecision(action="redact", reason_code="pii_email")
    return SafetyDecision(action="allow", reason_code="none")


def redact_sensitive_text(message: str) -> str:
    """Replace detected email addresses before forwarding or telemetry."""

    return re.sub(
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
        "[REDACTED_EMAIL]",
        message,
        flags=re.IGNORECASE,
    )


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def verify_grounded_chat_response(
    response: ChatResponse, *, expected_route: str
) -> ChatResponse:
    """Reject unsupported claims and route/citation discriminator mismatches."""

    if response.route != expected_route or expected_route not in {"support", "drift"}:
        raise CitationIntegrityError("route_mismatch")
    if not response.claims:
        raise CitationIntegrityError("missing_claims")
    claim_texts = {claim.text.strip() for claim in response.claims if claim.text.strip()}
    if not claim_texts or any(text not in response.answer for text in claim_texts):
        raise CitationIntegrityError("claim_not_in_answer")
    if any(sentence not in claim_texts for sentence in _sentences(response.answer)):
        raise CitationIntegrityError("unsupported_answer_sentence")
    expected_type = KnowledgeCitation if expected_route == "support" else DriftEvidenceCitation
    for claim in response.claims:
        if not claim.citations:
            raise CitationIntegrityError("missing_citations")
        if any(not isinstance(citation, expected_type) for citation in claim.citations):
            raise CitationIntegrityError("citation_kind_mismatch")
    return response


__all__ = [
    "CitationIntegrityError",
    "SafetyDecision",
    "inspect_message",
    "redact_sensitive_text",
    "verify_grounded_chat_response",
    "verify_knowledge_match",
    "verify_reloaded_match",
]
