"""Deterministic online feature-update writer contract."""

from __future__ import annotations

from .offline_writer import ONLINE_CONSUMER_GROUP, WriterStore, _FeatureWriter


class OnlineWriterContract(_FeatureWriter):
    """Persist one valid update to the online destination before checkpointing."""

    def __init__(self, store: WriterStore) -> None:
        super().__init__(store, consumer_group=ONLINE_CONSUMER_GROUP, destination="online")


__all__ = ["OnlineWriterContract"]
