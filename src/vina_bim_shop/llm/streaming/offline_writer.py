"""Offline Feast writer contract without Kafka/PostgreSQL side effects."""

from __future__ import annotations

from typing import Mapping


class OfflineWriterContract:
    """Validate and persist one offline event in a later runtime topic."""

    async def write(self, event: Mapping[str, object]) -> None:
        """Reject live writes in the contract-only phase."""

        del event
        raise NotImplementedError("offline writer behavior belongs to successor topics")


__all__ = ["OfflineWriterContract"]
