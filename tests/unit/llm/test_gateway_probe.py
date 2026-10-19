from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
CHAT_URL = "https://chat.203.0.113.7.sslip.io/v1/chat"
AUTH = {"Authorization": "Basic GUARDED"}


def _load_script():
    path = ROOT / "scripts/llm/smoke_release.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _responder(statuses: list[int]):
    calls: list[tuple[str, dict | None]] = []
    iterator = iter(statuses)

    def http_get(url: str, headers: dict | None = None) -> dict:
        calls.append((url, headers))
        return {"status": next(iterator)}

    http_get.calls = calls  # type: ignore[attr-defined]
    return http_get


def test_gateway_auth_rate_limit_proves_401_accepted_burst_and_429() -> None:
    """Exact EP/BVA behavior with no 503 is the HTTPS gate."""
    smoke = _load_script()
    http_get = _responder([401, 200, 200, 200, 200, 200, 429])
    evidence = smoke.prove_gateway_auth_rate_limit(
        http_get=http_get, chat_url=CHAT_URL, auth_headers=AUTH,
        expected_unauthenticated=401, accepted_rps=1, burst=5, expected_over_limit=429,
    )
    assert evidence["unauthenticated_status"] == 401
    assert evidence["accepted"] == 5 and evidence["over_limit_status"] == 429
    assert evidence["saw_503"] is False
    assert http_get.calls[0] == (CHAT_URL, None)  # type: ignore[attr-defined]
    assert all(call[1] == AUTH for call in http_get.calls[1:])  # type: ignore[attr-defined]


def test_gateway_probe_rejects_wrong_unauthenticated_status() -> None:
    smoke = _load_script()
    with pytest.raises(ValueError, match="unauthenticated"):
        smoke.prove_gateway_auth_rate_limit(
            http_get=_responder([200, 200, 200, 200, 200, 200, 429]), chat_url=CHAT_URL,
            auth_headers=AUTH, expected_unauthenticated=401, accepted_rps=1, burst=5,
            expected_over_limit=429,
        )


def test_gateway_probe_rejects_503_instead_of_429() -> None:
    """A 503 means controller misconfiguration, never a pass."""
    smoke = _load_script()
    with pytest.raises(ValueError, match="503"):
        smoke.prove_gateway_auth_rate_limit(
            http_get=_responder([401, 200, 200, 200, 200, 200, 503]), chat_url=CHAT_URL,
            auth_headers=AUTH, expected_unauthenticated=401, accepted_rps=1, burst=5,
            expected_over_limit=429,
        )


def test_gateway_probe_rejects_missing_over_limit() -> None:
    smoke = _load_script()
    with pytest.raises(ValueError, match="over-limit"):
        smoke.prove_gateway_auth_rate_limit(
            http_get=_responder([401, 200, 200, 200, 200, 200, 200]), chat_url=CHAT_URL,
            auth_headers=AUTH, expected_unauthenticated=401, accepted_rps=1, burst=5,
            expected_over_limit=429,
        )
