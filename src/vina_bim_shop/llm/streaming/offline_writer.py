"""Deterministic offline feature-update writer contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


UPDATE_TOPIC = "customer_feature_updates.v1"
OFFLINE_CONSUMER_GROUP = "edai2-feast-offline-writer-v1"
ONLINE_CONSUMER_GROUP = "edai2-feast-online-writer-v1"
_REQUIRED_EVENT_FIELDS = (
    "event_id",
    "manifest_sha256",
    "id",
    "event_timestamp",
    "feature_name",
    "feature_value",
    "source_version",
)


class WriterStore(Protocol):
    """Side-effect boundary implemented by future PostgreSQL/Feast adapters."""

    async def persist_outbox(self, consumer_group: str, event_id: str, event: dict[str, object]) -> bool: ...

    async def acknowledge_destination(self, destination: str, event: dict[str, object]) -> None: ...

    async def advance_checkpoint(self, consumer_group: str, topic: str, partition: int, offset: int) -> None: ...

    async def publish_dlq(self, envelope: dict[str, object]) -> None: ...


@dataclass(frozen=True)
class WriterResult:
    """Outcome safe to record without retaining a feature payload."""

    status: str
    event_id: str | None


def _canonical_payload(payload: Mapping[str, object]) -> str:
    return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), default=str)


def _valid_event(payload: Mapping[str, object]) -> bool:
    if tuple(payload) != _REQUIRED_EVENT_FIELDS:
        return False
    if not all(isinstance(payload[field], str) and payload[field] for field in _REQUIRED_EVENT_FIELDS if field != "feature_value"):
        return False
    return isinstance(payload["feature_value"], (int, float)) and not isinstance(payload["feature_value"], bool)


class _FeatureWriter:
    def __init__(self, store: WriterStore, *, consumer_group: str, destination: str) -> None:
        self._store = store
        self.consumer_group = consumer_group
        self.destination = destination

    async def write(
        self,
        event: Mapping[str, object],
        *,
        source_topic: str = UPDATE_TOPIC,
        source_partition: int = 0,
        source_offset: int = 0,
        observed_at: str | None = None,
    ) -> WriterResult:
        payload = dict(event)
        if not _valid_event(payload):
            await self._publish_invalid(
                payload,
                source_topic=source_topic,
                source_partition=source_partition,
                source_offset=source_offset,
                observed_at=observed_at,
            )
            await self._store.advance_checkpoint(self.consumer_group, source_topic, source_partition, source_offset)
            return WriterResult("dlq", None)

        event_id = str(payload["event_id"])
        if not await self._store.persist_outbox(self.consumer_group, event_id, payload):
            await self._store.advance_checkpoint(self.consumer_group, source_topic, source_partition, source_offset)
            return WriterResult("duplicate", event_id)
        await self._store.acknowledge_destination(self.destination, payload)
        await self._store.advance_checkpoint(self.consumer_group, source_topic, source_partition, source_offset)
        return WriterResult("applied", event_id)

    async def _publish_invalid(
        self,
        payload: Mapping[str, object],
        *,
        source_topic: str,
        source_partition: int,
        source_offset: int,
        observed_at: str | None,
    ) -> None:
        payload_sha256 = hashlib.sha256(_canonical_payload(payload).encode("utf-8")).hexdigest()
        error_code = "invalid_customer_feature_update"
        dlq_id = hashlib.sha256(
            f"{self.consumer_group}:{source_topic}:{source_partition}:{source_offset}:{payload_sha256}:{error_code}".encode("utf-8")
        ).hexdigest()
        await self._store.publish_dlq(
            {
                "dlq_id": dlq_id,
                "consumer_group": self.consumer_group,
                "source_topic": source_topic,
                "source_partition": source_partition,
                "source_offset": source_offset,
                "payload_sha256": payload_sha256,
                "error_code": error_code,
                "observed_at": observed_at or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
        )


class OfflineWriterContract(_FeatureWriter):
    """Persist one valid update to the offline destination before checkpointing."""

    def __init__(self, store: WriterStore) -> None:
        super().__init__(store, consumer_group=OFFLINE_CONSUMER_GROUP, destination="offline")


__all__ = [
    "OFFLINE_CONSUMER_GROUP",
    "ONLINE_CONSUMER_GROUP",
    "UPDATE_TOPIC",
    "OfflineWriterContract",
    "WriterResult",
    "WriterStore",
    "_FeatureWriter",
]
