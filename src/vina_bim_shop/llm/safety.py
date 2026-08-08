"""Pure retrieval-integrity and later chat-safety boundaries."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from .contracts import KnowledgeCitation, SearchMatch


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
    """Reject obvious prompt-injection markers without external calls."""

    if re.search(r"ignore\s+(all|previous)\s+instructions", message, re.IGNORECASE):
        return SafetyDecision(action="reject", reason_code="prompt_injection")
    return SafetyDecision(action="allow", reason_code="none")


__all__ = [
    "CitationIntegrityError",
    "SafetyDecision",
    "inspect_message",
    "verify_knowledge_match",
    "verify_reloaded_match",
]
