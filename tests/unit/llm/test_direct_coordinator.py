from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone

import pytest

from vina_bim_shop.llm.adapters.direct import DirectCoordinatorAdapter
from vina_bim_shop.llm.contracts import ChatRequest


NOW = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> dict:
        return self._payload


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict, dict]] = []
        self.content = "Returns are accepted within thirty days."
        self.answer = "Returns are accepted within thirty days."

    async def post(self, url: str, *, json: dict, headers: dict) -> FakeResponse:
        self.calls.append((url, json, headers))
        if url.endswith("/v1/retrieval/search"):
            content = self.content
            return FakeResponse(
                {
                    "request_id": "00000000-0000-4000-8000-000000000001",
                    "index_version": "t27-smoke-test",
                    "embedding_model": "BAAI/bge-small-en-v1.5",
                    "matches": [
                        {
                            "content": content,
                            "score": 0.8,
                            "citation": {
                                "chunk_id": "a" * 64,
                                "document_id": "returns-policy",
                                "category": "returns",
                                "version": "1.0.0",
                                "effective_from": NOW.isoformat(),
                                "effective_to": None,
                                "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                            },
                        }
                    ],
                    "retrieval_ms": 1.0,
                    "abstained": False,
                    "reason": None,
                }
            )
        return FakeResponse(
            {
                "choices": [{"message": {"content": self.answer}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19},
            }
        )


def test_direct_adapter_returns_a_grounded_claim_with_the_retrieved_citation() -> None:
    client = FakeClient()
    adapter = DirectCoordinatorAdapter(
        retrieval_url="http://retrieval.edai2.svc.cluster.local:8080",
        llm_url="http://llmd-router.edai2.svc.cluster.local:8000",
        llm_api_key="test-key",
        model="Qwen/Qwen2.5-1.5B-Instruct",
        client=client,
    )

    response = asyncio.run(
        adapter.chat(
            request=ChatRequest(session_id="00000000-0000-4000-8000-000000000002", message="What is the return window?", route="support"),
            runtime_variant="v1-primary",
            route_hint="support",
        )
    )

    assert response.route == "support"
    assert response.answer == "Returns are accepted within thirty days."
    assert response.index_version == "t27-smoke-test"
    assert response.claims[0].text == response.answer
    assert response.claims[0].citations[0].chunk_id == "a" * 64
    assert response.tool_calls[0].tool == "search_ecommerce_knowledge"
    assert response.tool_calls[0].status == "succeeded"
    assert client.calls[0][0].endswith("/v1/retrieval/search")
    assert client.calls[1][0].endswith("/v1/chat/completions")


def test_direct_adapter_fails_closed_when_retrieval_has_no_match() -> None:
    client = FakeClient()
    client.content = ""
    adapter = DirectCoordinatorAdapter(
        retrieval_url="http://retrieval.edai2.svc.cluster.local:8080",
        llm_url="http://llmd-router.edai2.svc.cluster.local:8000",
        llm_api_key="test-key",
        model="Qwen/Qwen2.5-1.5B-Instruct",
        client=client,
    )
    client.post = lambda *args, **kwargs: _empty_matches()  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="no_matches"):
        asyncio.run(
            adapter.chat(
                request=ChatRequest(session_id="00000000-0000-4000-8000-000000000003", message="What is the return window?", route="support"),
                runtime_variant="v1-primary",
                route_hint="support",
            )
        )


async def _empty_matches() -> FakeResponse:
    return FakeResponse({"matches": [], "index_version": "empty", "abstained": True, "reason": "no_matching_policy_row"})
