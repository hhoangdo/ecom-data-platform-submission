"""Online Feast writer contract without Redpanda/Valkey side effects."""

from __future__ import annotations

from typing import Mapping


class OnlineWriterContract:
    """Validate and publish one online event in a later runtime topic."""

    async def write(self, event: Mapping[str, object]) -> None:
        """Reject live writes in the contract-only phase."""

        del event
        raise NotImplementedError("online writer behavior belongs to successor topics")


__all__ = ["OnlineWriterContract"]
