"""Direct coordinator transport for the compact T27 runtime.

The full kagent/agentgateway/MCP specialist chain is not deployed in this
cluster.  This adapter performs the same work with real calls: it retrieves
grounded chunks from the retrieval API and generates an answer with the
pinned local model.  It is deliberately not presented as the full agent
runtime; Topic 28 keeps that architecture as an approved exception.
"""

from __future__ import annotations

import re
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4

import httpx
from opentelemetry import trace
from opentelemetry.propagate import inject

from ..contracts import (
    ChatRequest,
    ChatResponse,
    GroundedClaim,
    KnowledgeCitation,
    SearchMatch,
    ToolCallRecord,
)


_TRACER = trace.get_tracer(__name__)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


class DirectCoordinatorAdapter:
    """Retrieve grounded context, call the local model, and return a cited claim."""

    deadline_seconds = 45

    def __init__(
        self,
        *,
        retrieval_url: str,
        llm_url: str,
        llm_api_key: str,
        model: str,
        client: Any | None = None,
        langfuse: Any | None = None,
    ) -> None:
        if not retrieval_url.startswith(("http://", "https://")):
            raise ValueError("retrieval_url must be an explicit HTTP URL")
        if not llm_url.startswith(("http://", "https://")):
            raise ValueError("llm_url must be an explicit HTTP URL")
        if not llm_api_key or not model:
            raise ValueError("llm_api_key and model are required")
        self._retrieval_url = retrieval_url.rstrip("/")
        self._llm_url = llm_url.rstrip("/")
        self._llm_api_key = llm_api_key
        self._model = model
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(self.deadline_seconds))
        self._langfuse = langfuse

    async def is_ready(self) -> bool:
        """Report ready only when the pinned local model answers its health probe."""

        get = getattr(self._client, "get", None)
        if get is None:
            return True
        try:
            response = await get(f"{self._llm_url}/health", timeout=5.0)
            return int(getattr(response, "status_code", 500)) == 200
        except Exception:
            return False

    async def chat(
        self,
        *,
        request: ChatRequest,
        runtime_variant: Literal["v1-primary", "v2-primary", "v1-comparison"],
        route_hint: Literal["support", "drift", "abstain"],
    ) -> ChatResponse:
        del runtime_variant
        if route_hint != "support":
            raise ValueError("direct coordinator supports the support route only")

        started = perf_counter()
        with _TRACER.start_as_current_span("coordinator") as coordinator:
            coordinator.set_attribute("chat.route", route_hint)
            with _TRACER.start_as_current_span("specialist") as specialist:
                specialist.set_attribute("tool", "search_ecommerce_knowledge")
                search_started = perf_counter()
                headers: dict[str, str] = {"Content-Type": "application/json"}
                inject(headers)
                search_response = await self._client.post(
                    f"{self._retrieval_url}/v1/retrieval/search",
                    json={"query": request.message, "top_k": 4},
                    headers=headers,
                )
                search_response.raise_for_status()
                search_payload = search_response.json()
                matches = [
                    SearchMatch.model_validate(item)
                    for item in search_payload.get("matches", [])
                ]
                specialist.set_attribute("retrieval.match_count", len(matches))
                specialist.set_attribute(
                    "retrieval.duration_ms",
                    round((perf_counter() - search_started) * 1000, 3),
                )
            if not matches:
                raise RuntimeError("no_matches")

            citation = _citation(matches[0])
            prompt = _prompt(request.message, matches)
            llm_started = perf_counter()
            with _TRACER.start_as_current_span("llm-d") as llm_span:
                llm_span.set_attribute("llm.model", self._model)
                if self._langfuse is not None:
                    with self._langfuse.start_as_current_observation(
                        as_type="generation",
                        name="llm-d",
                        model=self._model,
                        input=prompt,
                    ) as generation:
                        answer, usage = await self._complete(prompt)
                        generation.update(
                            output=answer,
                            usage_details={
                                "input": int(usage.get("prompt_tokens", 0)),
                                "output": int(usage.get("completion_tokens", 0)),
                                "total": int(usage.get("total_tokens", 0)),
                            },
                        )
                else:
                    answer, usage = await self._complete(prompt)
                llm_span.set_attribute("llm.total_tokens", int(usage.get("total_tokens", 0)))
            if not answer.strip():
                raise RuntimeError("empty_answer")

            claims = [
                GroundedClaim(text=sentence, citations=[citation])
                for sentence in _sentences(answer)
            ]
            return ChatResponse(
                request_id=uuid4(),
                route="support",
                answer=answer,
                claims=claims,
                agent_name="commerce-coordinator",
                agent_version="direct-t27-v1",
                model_version=self._model,
                index_version=search_payload.get("index_version"),
                tool_calls=[
                    ToolCallRecord(
                        tool="search_ecommerce_knowledge",
                        status="succeeded",
                        duration_ms=round((perf_counter() - llm_started) * 1000, 3),
                        error_code=None,
                    )
                ],
                safety_action="allow",
            )

    async def _complete(self, prompt: list[dict[str, str]]) -> tuple[str, dict[str, int]]:
        response = await self._client.post(
            f"{self._llm_url}/v1/chat/completions",
            json={
                "model": self._model,
                "messages": prompt,
                "max_tokens": 96,
                "temperature": 0,
            },
            headers={
                "Authorization": f"Bearer {self._llm_api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()
        try:
            answer = str(payload["choices"][0]["message"]["content"]).strip()
            usage = payload.get("usage") or {}
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("invalid_llm_response") from error
        return answer, {key: int(value) for key, value in usage.items() if isinstance(value, int)}


def _citation(match: SearchMatch) -> KnowledgeCitation:
    citation = match.citation
    if not isinstance(citation, KnowledgeCitation):
        raise RuntimeError("citation_kind_mismatch")
    return citation


def _sentences(answer: str) -> list[str]:
    sentences = [item.strip() for item in _SENTENCE.split(answer.strip()) if item.strip()]
    return sentences or [answer.strip()]


def _prompt(question: str, matches: list[SearchMatch]) -> list[dict[str, str]]:
    context = "\n\n".join(match.content for match in matches[:4])
    return [
        {
            "role": "system",
            "content": (
                "Answer the customer question in one short sentence using only "
                "the supplied context. If the context does not answer it, say "
                "that the policy is unavailable. Do not add facts."
            ),
        },
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
    ]


__all__ = ["DirectCoordinatorAdapter"]
