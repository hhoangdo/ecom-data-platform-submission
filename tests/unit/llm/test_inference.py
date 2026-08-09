from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml
from transformers import AutoTokenizer

from vina_bim_shop.llm.contracts import ObservedGeneration
from vina_bim_shop.llm.inference import (
    ContextTooLargeError,
    HistoryGroup,
    IdempotentConnectionError,
    ObservedInferenceClient,
    RetrievalChunk,
)
from vina_bim_shop.llm.telemetry import InMemoryTelemetrySink, TelemetryRecorder


ROOT = Path(__file__).resolve().parents[3]
TOKENIZER_ID = "Qwen/Qwen2.5-1.5B-Instruct"
TOKENIZER_REVISION = "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"


class FakeInferencePort:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    async def generate(
        self, messages: list[dict[str, str]], model: str
    ) -> ObservedGeneration:
        del messages, model
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome  # type: ignore[return-value]


@pytest.fixture(scope="module")
def tokenizer() -> object:
    return AutoTokenizer.from_pretrained(
        TOKENIZER_ID,
        revision=TOKENIZER_REVISION,
        local_files_only=True,
    )


def _generation(text: str = "Answer.", output_tokens: int = 2) -> ObservedGeneration:
    return ObservedGeneration(
        text=text,
        model_version="qwen-primary@sha256:test",
        input_tokens=1,
        output_tokens=output_tokens,
        total_tokens=output_tokens + 1,
        ttft_ms=3.0,
        generation_ms=5.0,
        finish_reason="stop",
    )


def test_model_config_pins_qwen_budget_and_single_concurrency() -> None:
    config = yaml.safe_load((ROOT / "configs/llm/models.yaml").read_text(encoding="utf-8"))
    primary = config["models"]["primary"]

    assert primary["tokenizer_model"] == TOKENIZER_ID
    assert primary["tokenizer_revision"] == TOKENIZER_REVISION
    assert primary["context_tokens"] == 4096
    assert primary["input_budget_tokens"] == 3968
    assert primary["max_new_tokens"] == 128
    assert primary["concurrency"] == 1
    comparison = config["models"]["comparison"]
    assert comparison["input_budget_tokens"] == 3968
    assert comparison["max_new_tokens"] == 128
    assert comparison["concurrency"] == 1


def test_prepare_prompt_drops_complete_history_before_ranked_chunks(tokenizer: object) -> None:
    client = ObservedInferenceClient(FakeInferencePort([_generation()]), tokenizer=tokenizer)
    prepared = client.prepare_prompt(
        system_messages=({"role": "system", "content": "Use evidence."},),
        history_groups=(
            HistoryGroup("old", ({"role": "assistant", "content": " old" * 100},)),
        ),
        retrieval_chunks=(
            RetrievalChunk("z", 0.9, ({"role": "tool", "content": " z" * 2000},)),
            RetrievalChunk("a", 0.1, ({"role": "tool", "content": " a" * 2000},)),
        ),
        current_user={"role": "user", "content": "What is the return policy?"},
    )

    assert prepared.input_tokens <= 3968
    assert prepared.dropped_history_group_ids == ("old",)
    assert prepared.dropped_chunk_ids == ("a",)
    assert all(" old" * 10 not in message["content"] for message in prepared.messages)


def test_prepare_prompt_rejects_oversized_fixed_content(tokenizer: object) -> None:
    client = ObservedInferenceClient(FakeInferencePort([_generation()]), tokenizer=tokenizer)

    with pytest.raises(ContextTooLargeError, match="context_too_large"):
        client.prepare_prompt(
            system_messages=({"role": "system", "content": " fixed" * 4000},),
            history_groups=(),
            retrieval_chunks=(),
            current_user={"role": "user", "content": "hello"},
        )


def test_prepare_prompt_accepts_3968_and_rejects_3969_rendered_tokens(tokenizer: object) -> None:
    client = ObservedInferenceClient(FakeInferencePort([_generation()]), tokenizer=tokenizer)

    def content_for(target: int) -> str:
        lower, upper = 0, 5000
        while lower <= upper:
            middle = (lower + upper) // 2
            content = " x" * middle
            count = client._count_tokens(  # type: ignore[attr-defined]
                ({"role": "system", "content": "Use evidence."}, {"role": "user", "content": content})
            )
            if count == target:
                return content
            if count < target:
                lower = middle + 1
            else:
                upper = middle - 1
        raise AssertionError(f"cannot construct rendered template with {target} tokens")

    accepted = client.prepare_prompt(
        system_messages=({"role": "system", "content": "Use evidence."},),
        history_groups=(),
        retrieval_chunks=(),
        current_user={"role": "user", "content": content_for(3968)},
    )
    assert accepted.input_tokens == 3968

    with pytest.raises(ContextTooLargeError, match="context_too_large"):
        client.prepare_prompt(
            system_messages=({"role": "system", "content": "Use evidence."},),
            history_groups=(),
            retrieval_chunks=(),
            current_user={"role": "user", "content": content_for(3969)},
        )


def test_prepare_prompt_records_redacted_dropped_content_counters(tokenizer: object) -> None:
    sink = InMemoryTelemetrySink()
    client = ObservedInferenceClient(
        FakeInferencePort([_generation()]), tokenizer=tokenizer, telemetry=TelemetryRecorder(sink)
    )
    client.prepare_prompt(
        system_messages=({"role": "system", "content": "Use evidence."},),
        history_groups=(
            HistoryGroup("old", ({"role": "assistant", "content": " old" * 4000},)),
        ),
        retrieval_chunks=(),
        current_user={"role": "user", "content": "alice@example.com"},
    )

    event = sink.events[-1]
    assert event.name == "llm.prompt_budget"
    assert event.attributes["llm.dropped_history_groups"] == "1"
    assert len(event.attributes["llm.dropped_history_group_ids_sha256"]) == 64
    assert len(event.attributes["llm.dropped_retrieval_chunk_ids_sha256"]) == 64
    assert "old" not in str(event.attributes)
    assert "alice@example.com" not in str(event.attributes)


@pytest.mark.asyncio
async def test_generation_retries_once_only_for_idempotent_connection_failure(
    tokenizer: object,
) -> None:
    port = FakeInferencePort([IdempotentConnectionError("offline"), _generation()])
    client = ObservedInferenceClient(
        port,
        tokenizer=tokenizer,
        sleep=lambda _: asyncio.sleep(0),
        jitter=lambda: 0,
    )

    result = await client.generate(
        messages=[{"role": "user", "content": "hello"}], model_variant="primary"
    )

    assert result.output_tokens <= 128
    assert port.calls == 2


@pytest.mark.asyncio
async def test_generation_caps_output_and_records_only_redacted_telemetry(
    tokenizer: object,
) -> None:
    sink = InMemoryTelemetrySink()
    client = ObservedInferenceClient(
        FakeInferencePort([_generation(" token" * 200, 200)]),
        tokenizer=tokenizer,
        telemetry=TelemetryRecorder(sink),
    )

    result = await client.generate(
        messages=[{"role": "user", "content": "alice@example.com"}],
        model_variant="primary",
    )

    assert result.output_tokens <= 128
    assert result.total_tokens == result.input_tokens + result.output_tokens
    assert sink.events
    attributes = sink.events[-1].attributes
    assert "alice@example.com" not in str(attributes)
    assert attributes["llm.output_tokens"] == str(result.output_tokens)


@pytest.mark.asyncio
async def test_generation_classifies_timeout_at_exact_deadline(tokenizer: object) -> None:
    client = ObservedInferenceClient(FakeInferencePort([asyncio.TimeoutError()]), tokenizer=tokenizer)

    with pytest.raises(TimeoutError):
        await client.generate(
            messages=[{"role": "user", "content": "hello"}], model_variant="primary"
        )
    assert client.deadline_seconds == 22


@pytest.mark.asyncio
async def test_generation_stops_after_second_connection_failure(tokenizer: object) -> None:
    port = FakeInferencePort([IdempotentConnectionError("one"), IdempotentConnectionError("two")])
    client = ObservedInferenceClient(
        port, tokenizer=tokenizer, sleep=lambda _: asyncio.sleep(0), jitter=lambda: 0
    )

    with pytest.raises(IdempotentConnectionError):
        await client.generate(messages=[{"role": "user", "content": "hello"}], model_variant="primary")
    assert port.calls == 2


@pytest.mark.asyncio
async def test_warmup_returns_port_measured_model_and_elapsed_time(tokenizer: object) -> None:
    client = ObservedInferenceClient(
        FakeInferencePort([_generation()]), tokenizer=tokenizer
    )

    result = await client.warmup("primary")

    assert result.ready is True
    assert result.prompt_count == 1
    assert result.model_version == "qwen-primary@sha256:test"
    assert result.elapsed_ms == 8.0


@pytest.mark.asyncio
@pytest.mark.parametrize("finish_reason", ["error", "rejected"])
async def test_warmup_reports_not_ready_for_failed_observed_generation(
    tokenizer: object, finish_reason: str
) -> None:
    client = ObservedInferenceClient(
        FakeInferencePort([_generation().model_copy(update={"finish_reason": finish_reason})]),
        tokenizer=tokenizer,
    )

    result = await client.warmup("primary")

    assert result.ready is False
    assert result.model_version == "qwen-primary@sha256:test"
    assert result.prompt_count == 1
    assert result.elapsed_ms == 8.0
