"""DataHub catalog adapter boundary without a live service call."""

from __future__ import annotations

from ..contracts import IndexValidationReport


class DatahubIndexCatalogAdapter:
    """Publish and read candidate lineage through a later DataHub adapter."""

    async def publish_index(self, report: IndexValidationReport) -> str:
        """Reject live catalog writes in the contract-only phase."""

        raise NotImplementedError("DataHub publication belongs to successor topics")

    async def read_index(self, index_version: str) -> IndexValidationReport:
        """Reject live catalog reads in the contract-only phase."""

        raise NotImplementedError("DataHub read-back belongs to successor topics")


__all__ = ["DatahubIndexCatalogAdapter"]
