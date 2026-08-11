from __future__ import annotations

import hashlib

import pytest

from vina_bim_shop.llm.streaming.offline_writer import OfflineWriterContract
from vina_bim_shop.llm.streaming.online_writer import OnlineWriterContract


class FakeWriterStore:
    def __init__(self, *, fail_destination: bool = False, fail_dlq: bool = False) -> None:
        self.outbox: set[tuple[str, str]] = set()
        self.destinations: list[tuple[str, str]] = []
        self.checkpoints: list[tuple[str, str, int, int]] = []
        self.dlqs: list[dict[str, object]] = []
        self.calls: list[str] = []
        self.fail_destination = fail_destination
        self.fail_dlq = fail_dlq

    async def persist_outbox(self, consumer_group: str, event_id: str, event: dict[str, object]) -> bool:
        del event
        self.calls.append(f"outbox:{consumer_group}")
        key = (consumer_group, event_id)
        if key in self.outbox:
            return False
        self.outbox.add(key)
        return True

    async def acknowledge_destination(self, destination: str, event: dict[str, object]) -> None:
        self.calls.append(f"destination:{destination}")
        if self.fail_destination:
            raise RuntimeError("destination unavailable")
        self.destinations.append((destination, str(event["event_id"])))

    async def advance_checkpoint(self, consumer_group: str, topic: str, partition: int, offset: int) -> None:
        self.calls.append(f"checkpoint:{consumer_group}:{offset}")
        self.checkpoints.append((consumer_group, topic, partition, offset))

    async def publish_dlq(self, envelope: dict[str, object]) -> None:
        self.calls.append(f"dlq:{envelope['consumer_group']}")
        if self.fail_dlq:
            raise RuntimeError("dlq unavailable")
        self.dlqs.append(envelope)


def _event() -> dict[str, object]:
    return {
        "event_id": "e" * 64,
        "manifest_sha256": "a" * 64,
        "id": "customer-1",
        "event_timestamp": "2026-08-12T00:00:00Z",
        "feature_name": "customer_order_frequency",
        "feature_value": 1.25,
        "source_version": "section03-v1",
    }


@pytest.mark.asyncio
async def test_valid_event_is_acknowledged_before_each_independent_checkpoint() -> None:
    store = FakeWriterStore()
    event = _event()

    offline = OfflineWriterContract(store)
    online = OnlineWriterContract(store)
    assert (await offline.write(event, source_partition=0, source_offset=7)).status == "applied"
    assert (await online.write(event, source_partition=0, source_offset=7)).status == "applied"

    assert store.destinations == [("offline", "e" * 64), ("online", "e" * 64)]
    assert store.outbox == {
        ("edai2-feast-offline-writer-v1", "e" * 64),
        ("edai2-feast-online-writer-v1", "e" * 64),
    }
    assert store.checkpoints == [
        ("edai2-feast-offline-writer-v1", "customer_feature_updates.v1", 0, 7),
        ("edai2-feast-online-writer-v1", "customer_feature_updates.v1", 0, 7),
    ]


@pytest.mark.asyncio
async def test_duplicate_event_has_no_second_destination_effect() -> None:
    store = FakeWriterStore()
    writer = OfflineWriterContract(store)
    assert (await writer.write(_event(), source_offset=8)).status == "applied"
    assert (await writer.write(_event(), source_offset=9)).status == "duplicate"
    assert store.destinations == [("offline", "e" * 64)]
    assert store.checkpoints == [
        ("edai2-feast-offline-writer-v1", "customer_feature_updates.v1", 0, 8),
        ("edai2-feast-offline-writer-v1", "customer_feature_updates.v1", 0, 9),
    ]
    assert store.calls == [
        "outbox:edai2-feast-offline-writer-v1",
        "destination:offline",
        "checkpoint:edai2-feast-offline-writer-v1:8",
        "outbox:edai2-feast-offline-writer-v1",
        "checkpoint:edai2-feast-offline-writer-v1:9",
    ]


@pytest.mark.asyncio
async def test_invalid_event_creates_one_redacted_deterministic_dlq_per_group() -> None:
    store = FakeWriterStore()
    payload = {"id": "customer-1", "raw_secret": "do-not-copy"}
    await OfflineWriterContract(store).write(payload, source_partition=0, source_offset=11)
    await OnlineWriterContract(store).write(payload, source_partition=0, source_offset=11)

    assert len(store.dlqs) == 2
    assert {record["consumer_group"] for record in store.dlqs} == {
        "edai2-feast-offline-writer-v1", "edai2-feast-online-writer-v1"
    }
    for record in store.dlqs:
        assert set(record) == {
            "dlq_id", "consumer_group", "source_topic", "source_partition", "source_offset", "payload_sha256", "error_code", "observed_at"
        }
        assert record["payload_sha256"] == hashlib.sha256(
            b'{"id":"customer-1","raw_secret":"do-not-copy"}'
        ).hexdigest()
        assert "raw_secret" not in str(record)
    assert store.checkpoints == [
        ("edai2-feast-offline-writer-v1", "customer_feature_updates.v1", 0, 11),
        ("edai2-feast-online-writer-v1", "customer_feature_updates.v1", 0, 11),
    ]
    assert store.calls == [
        "dlq:edai2-feast-offline-writer-v1",
        "checkpoint:edai2-feast-offline-writer-v1:11",
        "dlq:edai2-feast-online-writer-v1",
        "checkpoint:edai2-feast-online-writer-v1:11",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("store", [FakeWriterStore(fail_destination=True), FakeWriterStore(fail_dlq=True)])
async def test_checkpoint_does_not_advance_when_destination_acknowledgement_fails(store: FakeWriterStore) -> None:
    writer = OfflineWriterContract(store)
    payload = _event() if store.fail_destination else {"id": "customer-1"}
    with pytest.raises(RuntimeError):
        await writer.write(payload, source_offset=12)
    assert store.checkpoints == []
