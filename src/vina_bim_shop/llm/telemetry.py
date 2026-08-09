"""Redacted telemetry contracts shared by local OTel/Langfuse integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Mapping, Sequence

from .contracts import ObservedGeneration


@dataclass(frozen=True)
class TelemetryEvent:
    """Sanitized event metadata suitable for OTel or Langfuse export."""

    name: str
    attributes: Mapping[str, str] = field(default_factory=dict)


class InMemoryTelemetrySink:
    """Deterministic test sink that stores only sanitized event metadata."""

    def __init__(self) -> None:
        self.events: list[TelemetryEvent] = []

    def record(self, event: TelemetryEvent) -> None:
        self.events.append(event)


class TelemetryRecorder:
    """Create correlated content-free attributes for observed inference events."""

    def __init__(self, sink: InMemoryTelemetrySink) -> None:
        self._sink = sink

    def record_generation(
        self,
        *,
        model_variant: str,
        generation: ObservedGeneration,
        messages: Sequence[dict[str, str]],
    ) -> None:
        digest = hashlib.sha256(
            "\n".join(message.get("content", "") for message in messages).encode("utf-8")
        ).hexdigest()
        self._sink.record(
            TelemetryEvent(
                name="llm.generation",
                attributes={
                    "llm.model_variant": model_variant,
                    "llm.model_version": generation.model_version,
                    "llm.input_tokens": str(generation.input_tokens),
                    "llm.output_tokens": str(generation.output_tokens),
                    "llm.total_tokens": str(generation.total_tokens),
                    "llm.ttft_ms": str(generation.ttft_ms),
                    "llm.generation_ms": str(generation.generation_ms),
                    "llm.prompt_sha256": digest,
                },
            )
        )

    def record_prompt_budget(
        self,
        *,
        input_tokens: int,
        dropped_history_group_ids: Sequence[str],
        dropped_chunk_ids: Sequence[str],
        messages: Sequence[dict[str, str]],
    ) -> None:
        """Record token/drop counts and a one-way prompt hash, never content."""

        digest = hashlib.sha256(
            "\n".join(message.get("content", "") for message in messages).encode("utf-8")
        ).hexdigest()
        self._sink.record(
            TelemetryEvent(
                name="llm.prompt_budget",
                attributes={
                    "llm.input_tokens": str(input_tokens),
                    "llm.dropped_history_groups": str(len(dropped_history_group_ids)),
                    "llm.dropped_retrieval_chunks": str(len(dropped_chunk_ids)),
                    "llm.dropped_history_group_ids_sha256": hashlib.sha256(
                        "\n".join(dropped_history_group_ids).encode("utf-8")
                    ).hexdigest(),
                    "llm.dropped_retrieval_chunk_ids_sha256": hashlib.sha256(
                        "\n".join(dropped_chunk_ids).encode("utf-8")
                    ).hexdigest(),
                    "llm.prompt_sha256": digest,
                },
            )
        )

    def record_coordinator(
        self,
        *,
        session_id: str,
        route: str,
        runtime_variant: str,
        destination: str,
        experiment: str,
        response: object,
    ) -> None:
        """Record only correlated routing, outcome, and tool metadata."""

        from .contracts import ChatResponse

        assert isinstance(response, ChatResponse)
        correlation = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        request_correlation = hashlib.sha256(str(response.request_id).encode("utf-8")).hexdigest()
        common = {
            "coordinator.session_sha256": correlation,
            "coordinator.request_sha256": request_correlation,
            "coordinator.route": route,
            "coordinator.runtime_variant": runtime_variant,
            "coordinator.destination": destination,
            "coordinator.experiment": experiment,
            "coordinator.safety_action": response.safety_action,
            "coordinator.agent_name": response.agent_name,
            "coordinator.agent_version": response.agent_version,
            "coordinator.model_version": response.model_version,
            "coordinator.index_version": response.index_version or "",
        }
        self._sink.record(TelemetryEvent(name="coordinator.agent", attributes=common))
        for call in response.tool_calls:
            self._sink.record(
                TelemetryEvent(
                    name="coordinator.tool",
                    attributes={
                        **common,
                        "coordinator.tool": call.tool,
                        "coordinator.tool_status": call.status,
                        "coordinator.tool_duration_ms": str(call.duration_ms),
                        "coordinator.tool_error_code": call.error_code or "",
                    },
                )
            )


__all__ = ["InMemoryTelemetrySink", "TelemetryEvent", "TelemetryRecorder"]
