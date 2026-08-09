"""Observed local inference with exact Qwen-template token budgeting."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal, Sequence

from .contracts import ObservedGeneration, WarmupResult
from .ports import InferencePort
from .telemetry import TelemetryRecorder


CONTEXT_TOKENS = 4096
INPUT_BUDGET_TOKENS = 3968
OUTPUT_BUDGET_TOKENS = 128
DEADLINE_SECONDS = 22


class ContextTooLargeError(ValueError):
    """Raised before a dependency call when immutable prompt content overflows."""


class IdempotentConnectionError(ConnectionError):
    """The only dependency failure eligible for a single retry."""


class DependencyTimeoutError(TimeoutError):
    """A typed dependency timeout used by the coordinator boundary."""


@dataclass(frozen=True)
class HistoryGroup:
    """One atomic retained conversation group."""

    group_id: str
    messages: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class RetrievalChunk:
    """One atomic retrieval record ordered by score then immutable ID."""

    chunk_id: str
    score: float
    messages: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class PreparedPrompt:
    """A deterministic, rendered-template-budgeted prompt without raw telemetry."""

    messages: tuple[dict[str, str], ...]
    input_tokens: int
    dropped_history_group_ids: tuple[str, ...]
    dropped_chunk_ids: tuple[str, ...]


class ObservedInferenceClient:
    """Generate only through an injected private adapter and record measurements."""

    deadline_seconds = DEADLINE_SECONDS

    def __init__(
        self,
        port: InferencePort,
        *,
        tokenizer: Any,
        telemetry: TelemetryRecorder | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = lambda: 0.05,
    ) -> None:
        self._port = port
        self._tokenizer = tokenizer
        self._telemetry = telemetry
        self._sleep = sleep
        self._jitter = jitter

    def _count_tokens(self, messages: Sequence[dict[str, str]]) -> int:
        rendered = self._tokenizer.apply_chat_template(
            list(messages), tokenize=True, add_generation_prompt=True
        )
        token_ids = rendered["input_ids"] if isinstance(rendered, Mapping) else rendered
        return len(token_ids)

    def prepare_prompt(
        self,
        *,
        system_messages: tuple[dict[str, str], ...],
        history_groups: tuple[HistoryGroup, ...],
        retrieval_chunks: tuple[RetrievalChunk, ...],
        current_user: dict[str, str],
    ) -> PreparedPrompt:
        """Drop only whole records in the locked deterministic order."""

        retained_history = list(history_groups)
        retained_chunks = list(retrieval_chunks)
        dropped_history: list[str] = []
        dropped_chunks: list[str] = []

        def render() -> tuple[dict[str, str], ...]:
            return tuple(
                [*system_messages]
                + [message for group in retained_history for message in group.messages]
                + [message for chunk in retained_chunks for message in chunk.messages]
                + [current_user]
            )

        fixed_messages = tuple([*system_messages, current_user])
        if self._count_tokens(fixed_messages) > INPUT_BUDGET_TOKENS:
            raise ContextTooLargeError("context_too_large")

        messages = render()
        while self._count_tokens(messages) > INPUT_BUDGET_TOKENS and retained_history:
            dropped_history.append(retained_history.pop(0).group_id)
            messages = render()
        for chunk in sorted(retrieval_chunks, key=lambda item: (item.score, item.chunk_id)):
            if self._count_tokens(messages) <= INPUT_BUDGET_TOKENS:
                break
            retained_chunks.remove(chunk)
            dropped_chunks.append(chunk.chunk_id)
            messages = render()

        input_tokens = self._count_tokens(messages)
        if input_tokens > INPUT_BUDGET_TOKENS:
            raise ContextTooLargeError("context_too_large")
        prepared = PreparedPrompt(
            messages=messages,
            input_tokens=input_tokens,
            dropped_history_group_ids=tuple(dropped_history),
            dropped_chunk_ids=tuple(dropped_chunks),
        )
        if self._telemetry is not None:
            self._telemetry.record_prompt_budget(
                input_tokens=prepared.input_tokens,
                dropped_history_group_ids=prepared.dropped_history_group_ids,
                dropped_chunk_ids=prepared.dropped_chunk_ids,
                messages=prepared.messages,
            )
        return prepared

    async def generate(
        self,
        *,
        messages: Sequence[dict[str, str]],
        model_variant: Literal["primary", "comparison"],
        max_context_tokens: int = CONTEXT_TOKENS,
    ) -> ObservedGeneration:
        """Generate with the locked deadline, retry rule, and output ceiling."""

        if max_context_tokens != CONTEXT_TOKENS:
            raise ValueError("max_context_tokens must equal 4096")
        input_tokens = self._count_tokens(messages)
        if input_tokens > INPUT_BUDGET_TOKENS:
            raise ContextTooLargeError("context_too_large")

        model = "primary" if model_variant == "primary" else "comparison"
        try:
            generation = await asyncio.wait_for(
                self._port.generate(list(messages), model), timeout=DEADLINE_SECONDS
            )
        except IdempotentConnectionError:
            await self._sleep(self._jitter())
            try:
                generation = await asyncio.wait_for(
                    self._port.generate(list(messages), model), timeout=DEADLINE_SECONDS
                )
            except asyncio.TimeoutError as exc:
                raise DependencyTimeoutError("dependency_timeout") from exc
        except asyncio.TimeoutError as exc:
            raise DependencyTimeoutError("dependency_timeout") from exc

        output_ids = self._tokenizer.encode(generation.text, add_special_tokens=False)
        if len(output_ids) > OUTPUT_BUDGET_TOKENS:
            generation = generation.model_copy(
                update={
                    "text": self._tokenizer.decode(output_ids[:OUTPUT_BUDGET_TOKENS]),
                    "output_tokens": OUTPUT_BUDGET_TOKENS,
                    "finish_reason": "length",
                }
            )
        generation = generation.model_copy(
            update={
                "input_tokens": input_tokens,
                "total_tokens": input_tokens + generation.output_tokens,
            }
        )
        if self._telemetry is not None:
            self._telemetry.record_generation(
                model_variant=model_variant,
                generation=generation,
                messages=messages,
            )
        return generation

    async def warmup(self, model_variant: Literal["primary", "comparison"]) -> WarmupResult:
        """Run one observed warm-up prompt and retain only port-measured fields."""

        generation = await self.generate(
            messages=[{"role": "user", "content": "Warm up."}],
            model_variant=model_variant,
        )
        return WarmupResult(
            model_version=generation.model_version,
            prompt_count=1,
            elapsed_ms=generation.ttft_ms + generation.generation_ms,
            ready=generation.finish_reason in {"stop", "length"},
        )


__all__ = [
    "CONTEXT_TOKENS",
    "DEADLINE_SECONDS",
    "DependencyTimeoutError",
    "ContextTooLargeError",
    "HistoryGroup",
    "IdempotentConnectionError",
    "INPUT_BUDGET_TOKENS",
    "ObservedInferenceClient",
    "OUTPUT_BUDGET_TOKENS",
    "PreparedPrompt",
    "RetrievalChunk",
]
