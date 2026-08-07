"""Redacted telemetry contracts without exporter or network side effects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class TelemetryEvent:
    """Sanitized event metadata suitable for a later OTel/Langfuse adapter."""

    name: str
    attributes: Mapping[str, str] = field(default_factory=dict)


class InMemoryTelemetrySink:
    """Deterministic test sink that stores only sanitized event metadata."""

    def __init__(self) -> None:
        self.events: list[TelemetryEvent] = []

    def record(self, event: TelemetryEvent) -> None:
        """Append a pre-sanitized event."""

        self.events.append(event)


__all__ = ["InMemoryTelemetrySink", "TelemetryEvent"]
