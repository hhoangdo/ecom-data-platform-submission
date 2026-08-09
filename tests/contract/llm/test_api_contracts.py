from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from vina_bim_shop.llm.api.chat import app as chat_app
from vina_bim_shop.llm.coordinator import CommerceAgentCoordinator
from vina_bim_shop.llm.inference import ContextTooLargeError
from vina_bim_shop.llm.api.drift import app as drift_app
from vina_bim_shop.llm.drift import SECTION03_MANIFEST_SHA256
from vina_bim_shop.llm.api.retrieval import app as retrieval_app


APPS = [retrieval_app, drift_app, chat_app]
REQUIRED_PROBES = {"/healthz", "/readyz", "/metrics"}


def test_every_fastapi_service_exposes_the_stable_routes() -> None:
    for app in APPS:
        paths = set(app.openapi()["paths"])
        assert REQUIRED_PROBES <= paths
        assert "/v1/retrieval/search" in paths or "/v1/drift/detect" in paths or "/v1/chat" in paths
        assert "ApiError" in app.openapi()["components"]["schemas"]


def test_validation_errors_use_the_typed_api_error_envelope() -> None:
    for app, path in [
        (retrieval_app, "/v1/retrieval/search"),
        (drift_app, "/v1/drift/detect"),
        (chat_app, "/v1/chat"),
    ]:
        response = TestClient(app).post(path, json={})
        assert response.status_code == 422
        body = response.json()
        assert set(body) == {"code", "message", "request_id"}
        assert body["code"] == "validation_error"


def test_valid_contract_requests_return_typed_local_abstentions() -> None:
    search = TestClient(retrieval_app).post(
        "/v1/retrieval/search", json={"query": "return policy"}
    )
    assert search.status_code == 409
    assert search.json()["code"] == "index_unavailable"

    drift = TestClient(drift_app).post(
        "/v1/drift/detect",
        json={
            "baseline_window": {
                "start": "2026-04-01T00:00:00Z",
                "end": "2026-04-08T00:00:00Z",
            },
            "candidate_window": {
                "start": "2026-04-11T00:00:00Z",
                "end": "2026-04-12T00:00:00Z",
            },
        },
    )
    assert drift.status_code == 409
    assert drift.json()["code"] == "feature_unavailable"

    chat = TestClient(chat_app).post(
        "/v1/chat", json={"session_id": str(uuid4()), "message": "hello"}
    )
    assert chat.status_code == 200
    assert chat.json()["safety_action"] == "abstain"
    assert chat.json()["tool_calls"][0]["status"] == "failed"


def test_retrieval_openapi_declares_typed_success_and_error_contracts() -> None:
    operation = retrieval_app.openapi()["paths"]["/v1/retrieval/search"]["post"]
    responses = operation["responses"]

    assert responses["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SearchResponse"
    }
    for status_code in ("409", "422", "503"):
        assert responses[status_code]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ApiError"
        }


def test_health_readiness_and_metrics_are_local_and_machine_readable() -> None:
    chat_client = TestClient(chat_app)
    assert chat_client.get("/healthz").status_code == 200
    assert chat_client.get("/readyz").status_code == 503
    assert "text/plain" in chat_client.get("/metrics").headers["content-type"]

    drift_client = TestClient(drift_app)
    assert drift_client.get("/healthz").status_code == 200
    readiness = drift_client.get("/readyz")
    assert readiness.status_code == 503
    assert readiness.json()["status"] == "not_ready"
    assert "text/plain" in drift_client.get("/metrics").headers["content-type"]

    retrieval_client = TestClient(retrieval_app)
    assert retrieval_client.get("/healthz").status_code == 200
    readiness = retrieval_client.get("/readyz")
    assert readiness.status_code == 503
    assert readiness.json()["status"] == "not_ready"
    assert "text/plain" in retrieval_client.get("/metrics").headers["content-type"]


def test_chat_openapi_and_context_too_large_error_are_byte_faithful() -> None:
    operation = chat_app.openapi()["paths"]["/v1/chat"]["post"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ChatResponse"
    }
    assert operation["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ApiError"
    }
    request = {"session_id": str(uuid4()), "message": "hello", "route": "auto"}
    response = TestClient(chat_app).post("/v1/chat", json=request)
    assert response.status_code == 200
    assert set(response.json()) == {
        "request_id", "route", "answer", "claims", "agent_name", "agent_version",
        "model_version", "index_version", "tool_calls", "safety_action",
    }


def test_chat_maps_context_too_large_to_the_typed_422_envelope() -> None:
    class OverBudgetPort:
        async def chat(self, **_: object) -> object:
            raise ContextTooLargeError("context_too_large")

    original = chat_app.state.coordinator
    chat_app.state.coordinator = CommerceAgentCoordinator(agent=OverBudgetPort())
    try:
        response = TestClient(chat_app).post(
            "/v1/chat", json={"session_id": str(uuid4()), "message": "hello"}
        )
    finally:
        chat_app.state.coordinator = original
    assert response.status_code == 422
    assert response.json()["code"] == "context_too_large"
