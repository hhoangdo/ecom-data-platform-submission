"""Fake-backed DataHub lineage boundary for the local RAG index contract."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Sequence

from ..contracts import IndexBuildReport, KnowledgeChunk, KnowledgeDocumentVersion


class DataHubReadBackError(RuntimeError):
    """Raised when emitted active lineage cannot be read back exactly."""


EmitPort = Callable[[dict[str, object]], Awaitable[None]]
ReadPort = Callable[[str], Awaitable[dict[str, object]]]


class DatahubIndexCatalogAdapter:
    """Emit and verify lineage through injected local test doubles only."""

    def __init__(
        self,
        *,
        emit: EmitPort | None = None,
        read: ReadPort | None = None,
    ) -> None:
        self._emit = emit
        self._read = read
        self._active_payloads: dict[str, dict[str, object]] = {}

    async def emit_candidate(
        self,
        *,
        report: IndexBuildReport,
        versions: Sequence[KnowledgeDocumentVersion],
        chunks: Sequence[KnowledgeChunk],
    ) -> str:
        """Emit source-to-candidate lineage for a built immutable candidate."""

        version_nodes = [f"{item.document_id}@{item.version}" for item in versions]
        chunk_nodes = [item.chunk_id for item in chunks]
        payload: dict[str, object] = {
            "kind": "candidate",
            "index_version": report.index_version,
            "source_sha256": report.source_sha256,
            "version_nodes": version_nodes,
            "chunk_nodes": chunk_nodes,
            "embedding_sha256": report.embedding_sha256,
            "edges": [
                "source->document_version",
                "document_version->chunk",
                "chunk->embedding",
                "embedding->candidate",
            ],
        }
        await self._emit_payload(payload)
        return f"urn:li:dataProcessInstance:edai2-rag-candidate-{report.index_version}"

    async def emit_active(
        self,
        *,
        index_version: str,
        previous_index_version: str | None,
    ) -> str:
        """Emit active-alias, Feast, and API lineage after a successful CAS."""

        payload: dict[str, object] = {
            "kind": "active",
            "index_version": index_version,
            "previous_index_version": previous_index_version,
            "edges": [
                f"{index_version}->active",
                "active->feast",
                "feast->api",
            ],
        }
        payload["lineage_sha256"] = _payload_sha256(payload)
        await self._emit_payload(payload)
        self._active_payloads[index_version] = payload
        return f"urn:li:dataProcessInstance:edai2-rag-active-{index_version}"

    async def emit_rollback(
        self,
        *,
        failed_index_version: str,
        restored_index_version: str | None,
        reason: str,
    ) -> str:
        """Emit compensation lineage after post-CAS active lineage fails."""

        payload: dict[str, object] = {
            "kind": "rollback",
            "failed_index_version": failed_index_version,
            "restored_index_version": restored_index_version,
            "reason": reason,
            "edges": ["active->rollback"],
        }
        await self._emit_payload(payload)
        return f"urn:li:dataProcessInstance:edai2-rag-rollback-{failed_index_version}"

    async def read_back(self, *, index_version: str) -> bool:
        """Verify the emitted active record and its deterministic content hash."""

        expected = self._active_payloads.get(index_version)
        if expected is None:
            raise DataHubReadBackError(f"no emitted active lineage for {index_version}")
        if self._read is None:
            raise DataHubReadBackError("DataHub read-back is not configured for local testing")

        observed = await self._read(index_version)
        if observed.get("index_version") != index_version:
            raise DataHubReadBackError("DataHub read-back returned the wrong index version")
        if observed.get("edges") != expected["edges"]:
            raise DataHubReadBackError("DataHub read-back is missing an active lineage edge")
        observed_hash = observed.get("lineage_sha256")
        if not isinstance(observed_hash, str) or observed_hash != _payload_sha256(
            {key: value for key, value in observed.items() if key != "lineage_sha256"}
        ):
            raise DataHubReadBackError("DataHub read-back lineage hash does not match")
        return True

    async def _emit_payload(self, payload: dict[str, object]) -> None:
        if self._emit is None:
            raise RuntimeError("DataHub live emission is not configured for local testing")
        await self._emit(payload)


def _payload_sha256(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = ["DataHubReadBackError", "DatahubIndexCatalogAdapter"]
