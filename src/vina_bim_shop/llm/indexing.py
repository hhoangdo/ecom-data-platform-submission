"""Typed candidate-index pipeline boundary; behavior belongs to later topics."""

from __future__ import annotations

from typing import Sequence

from .contracts import IndexBuildReport, IndexValidationReport


class RagIndexPipeline:
    """Own the four compare-and-swap candidate-index stages."""

    async def build_candidate(
        self,
        source_paths: Sequence[str],
        index_version: str,
    ) -> IndexBuildReport:
        """Build a candidate report without acquiring a runtime in Topic 08."""

        raise NotImplementedError("RAG indexing is implemented by a successor topic")

    async def validate_candidate(
        self,
        index_version: str,
        evaluation_path: str,
    ) -> IndexValidationReport:
        """Validate a candidate through the later retrieval quality gates."""

        raise NotImplementedError("RAG validation is implemented by a successor topic")

    async def promote(
        self,
        index_version: str,
        expected_active_version: str | None,
    ) -> str:
        """Return a promotion boundary for a later transactional adapter."""

        raise NotImplementedError("RAG promotion is implemented by a successor topic")

    async def rollback(self, previous_index_version: str) -> str:
        """Return a rollback boundary for a later transactional adapter."""

        raise NotImplementedError("RAG rollback is implemented by a successor topic")


__all__ = ["RagIndexPipeline"]
