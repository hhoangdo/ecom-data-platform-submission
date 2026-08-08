from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from vina_bim_shop.llm.contracts import (
    DriftEvidenceCitation,
    KnowledgeCitation,
    SearchMatch,
)
from vina_bim_shop.llm.safety import (
    CitationIntegrityError,
    verify_knowledge_match,
    verify_reloaded_match,
)


def _match(content: str = "Returns are accepted within thirty days.") -> SearchMatch:
    return SearchMatch(
        content=content,
        score=0.75,
        citation=KnowledgeCitation(
            chunk_id="a" * 64,
            document_id="returns-policy",
            category="returns",
            version="1.0.0",
            effective_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
            effective_to=None,
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        ),
    )


def test_verify_knowledge_match_accepts_hash_bound_content() -> None:
    match = _match()

    assert verify_knowledge_match(match) is match


def test_verify_knowledge_match_rejects_tampered_content() -> None:
    match = _match()
    tampered = match.model_copy(update={"content": "Altered policy text."})

    with pytest.raises(CitationIntegrityError, match="content_sha256_mismatch"):
        verify_knowledge_match(tampered)


def test_verify_knowledge_match_rejects_wrong_citation_discriminator() -> None:
    match = _match()
    wrong_kind = SearchMatch.model_construct(
        content=match.content,
        score=match.score,
        citation=DriftEvidenceCitation(
            section03_manifest_sha256="b" * 64,
            feature_health_sha256="c" * 64,
            feature_name="f_customer_order_frequency_7d",
            window_days=7,
            baseline_date="2026-04-10",
            monitoring_date="2026-04-11",
            result_sha256="d" * 64,
        ),
    )

    with pytest.raises(CitationIntegrityError, match="citation_kind_mismatch"):
        verify_knowledge_match(wrong_kind)


def test_verify_reloaded_match_rejects_missing_or_changed_persisted_chunk() -> None:
    match = _match()

    with pytest.raises(CitationIntegrityError, match="citation_not_found"):
        verify_reloaded_match(match, None)

    reloaded = _match("A different returns policy.")
    with pytest.raises(CitationIntegrityError, match="citation_reload_mismatch"):
        verify_reloaded_match(match, reloaded)
