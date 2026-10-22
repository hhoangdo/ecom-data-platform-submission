from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SINK = "gs://operator-vault-recovery/edai2/"


def _load_script():
    path = ROOT / "scripts/gke/configure_vault.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bootstrap() -> dict:
    return {
        "initialized": True, "seal_type": "gcpckms",
        "kms_key_id": "projects/p/locations/r/keyRings/k/cryptoKeys/c",
        "key_names": ["auth", "authorization", "password"],
        "key_name_fingerprints": ["a" * 64, "b" * 64, "c" * 64],
        "policy_results": {
            "agentgateway-allow-gateway-entry": True, "coordinator-allow-gateway-keys": True,
            "retrieval-deny-gateway-keys": True, "retrieval-deny-gateway-entry": True,
            "cross-path-deny": True,
        },
        "recovery_threshold": 1, "recovery_shares": 1, "root_revoked": True,
    }


def _attestation(sink: str = SINK) -> dict:
    return {
        "sink_uri_sha256": hashlib.sha256(sink.encode("utf-8")).hexdigest(),
        "encrypted": True, "custodians": ["custodian-one", "custodian-two"],
        "attested_at": "2026-10-18T00:00:00+00:00",
    }


def _exec_factory(status_sealed: bool = False, keys: list[str] | None = None, probes: dict | None = None):
    keys = keys if keys is not None else ["auth", "authorization", "password"]
    probes = probes if probes is not None else {}
    calls: list[tuple] = []
    listed = {"n": 0}

    def exec_fn(*vault_args: str, token: str | None = None):
        calls.append((vault_args, token is not None))
        if vault_args[:2] == ("status", "-format=json"):
            return json.dumps({"initialized": True, "sealed": status_sealed, "type": "gcpckms"})
        if vault_args[:2] == ("kv", "list"):
            listed["n"] += 1
            return json.dumps(keys if listed["n"] == 1 else [])
        if vault_args[0] == "token" and vault_args[1] == "create":
            policy = next(part.split("=", 1)[1] for part in vault_args if part.startswith("-policy="))
            return json.dumps({"auth": {"client_token": f"role-token-{policy}"}})
        if vault_args[:2] == ("kv", "get"):
            if token is None:
                data = (
                    {key: "" for key in keys}
                    if vault_args[-1] == "kv/edai2/kagent/gateway-keys"
                    else {}
                )
                return json.dumps({"data": {"data": data}})
            if token == "role-token":
                return json.dumps({"data": {"data": {}}})
            if isinstance(token, str) and token.startswith("role-token-"):
                role = token.removeprefix("role-token-")
                path = vault_args[-1]
                allowed_paths = {
                    "agentgateway": ["kv/edai2/facade/gateway-entry"],
                    "coordinator": ["kv/edai2/kagent/gateway-keys"],
                }
                if path in allowed_paths.get(role, []):
                    return json.dumps({"data": {"data": {}}})
            raise RuntimeError("permission denied")
        if vault_args[:2] == ("token", "revoke"):
            return ""
        raise AssertionError(vault_args)

    exec_fn.calls = calls  # type: ignore[attr-defined]
    return exec_fn


def test_verify_recovery_proves_auto_unseal_and_policy_canary() -> None:
    """KMS auto-unseal, identical canary metadata, and scoped reads/denials."""
    vault = _load_script()
    result = vault.verify_recovery(
        exec_fn=_exec_factory(), expected_bootstrap=_bootstrap(),
        recovery_sink=SINK, attestation=_attestation(),
    )
    assert result["auto_unseal"] is True
    assert result["key_names_match"] is True
    assert result["policy_results"]["cross-path-deny"] is True
    text = json.dumps(result, sort_keys=True)
    assert "role-token" not in text and SINK not in text


def test_verify_recovery_rejects_manual_unseal_or_key_drift() -> None:
    vault = _load_script()
    with pytest.raises(ValueError, match="unseal"):
        vault.verify_recovery(
            exec_fn=_exec_factory(status_sealed=True), expected_bootstrap=_bootstrap(),
            recovery_sink=SINK, attestation=_attestation(),
        )
    with pytest.raises(ValueError, match="key"):
        vault.verify_recovery(
            exec_fn=_exec_factory(keys=["auth"]), expected_bootstrap=_bootstrap(),
            recovery_sink=SINK, attestation=_attestation(),
        )


def test_verify_recovery_rejects_bad_sink_attestation() -> None:
    vault = _load_script()
    bad = _attestation()
    bad["custodians"] = ["only-one"]
    with pytest.raises(ValueError, match="attestation"):
        vault.verify_recovery(
            exec_fn=_exec_factory(), expected_bootstrap=_bootstrap(),
            recovery_sink=SINK, attestation=bad,
        )
    bad = _attestation(sink="gs://elsewhere/x/")
    with pytest.raises(ValueError, match="attestation"):
        vault.verify_recovery(
            exec_fn=_exec_factory(), expected_bootstrap=_bootstrap(),
            recovery_sink=SINK, attestation=bad,
        )


def test_verify_recovery_study_only_without_sink() -> None:
    """Study-only: KMS auto-unseal + canary without sink/attestation inputs."""
    vault = _load_script()
    result = vault.verify_recovery(
        exec_fn=_exec_factory(), expected_bootstrap=_bootstrap(),
    )
    assert result["auto_unseal"] is True
    assert result["key_names_match"] is True
    assert result["policy_results"]["cross-path-deny"] is True
    text = json.dumps(result, sort_keys=True)
    assert "role-token" not in text and SINK not in text
    assert "recovery_sink_sha256" not in result

def test_record_existing_bootstrap_repairs_empty_seal_type_from_live_status() -> None:
    """The empty bootstrap seal_type is corrected by the live status, not hand-edited."""
    vault = _load_script()
    old = _bootstrap()
    old["seal_type"] = ""
    new = vault.record_existing_bootstrap(
        exec_fn=_exec_factory(), bootstrap=old, recorded_at="2026-10-19T00:00:00Z"
    )
    assert new["seal_type"] == "gcpckms"
    assert new["record_source"] == "live-vault-status"
    assert new["recorded_at_utc"] == "2026-10-19T00:00:00Z"
    assert new["key_names"] == old["key_names"]
    assert "role-token" not in json.dumps(new)
