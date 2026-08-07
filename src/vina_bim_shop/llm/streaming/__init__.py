"""Typed Feast writer boundaries for later streaming topics."""

from .offline_writer import OfflineWriterContract
from .online_writer import OnlineWriterContract

__all__ = ["OfflineWriterContract", "OnlineWriterContract"]
