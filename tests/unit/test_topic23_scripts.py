from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml


def _load(name: str, relative: str):
    path = Path(__file__).resolve().parents[2] / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"missing module file: {relative}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_configure_vault_has_no_sink_or_custodian_concept() -> None:
    module = _load("configure_vault", "scripts/gke/configure_vault.py")
    assert not hasattr(module, "sink_ok")
    assert module.recovery_secret_ref("vault") == {"namespace": "vault", "name": "vault-recovery"}


def test_configure_vault_parses_kms_key_id_segments() -> None:
    module = _load("configure_vault", "scripts/gke/configure_vault.py")
    segments = module.parse_kms_key("projects/p/locations/r/keyRings/k/cryptoKeys/c")
    assert segments == {"project": "p", "region": "r", "key_ring": "k", "crypto_key": "c"}
    with pytest.raises(ValueError):
        module.parse_kms_key("not-a-key-id")


def test_configure_vault_redacted_evidence_carries_no_secret_or_custodian() -> None:
    module = _load("configure_vault", "scripts/gke/configure_vault.py")
    evidence = module.build_redacted_evidence(
        kms_key_id="projects/p/locations/us-central1/keyRings/r/cryptoKeys/k",
        seal_type="gcpckms",
        key_names=["model-api-key"],
        policy_results={"retrieval-allow": True, "facade-cross-deny": True},
        recovery_threshold=1,
        recovery_shares=1,
        root_revoked=True,
    )
    text = json.dumps(evidence).lower()
    assert "custodian" not in text
    assert "attestation" not in text
    assert "token" not in text
    assert evidence["recovery_threshold"] == 1
    assert evidence["recovery_material"] == "in-cluster-only"
    assert evidence["disaster_safe"] is False
    assert evidence["root_revoked"] is True


def test_model_cache_uri_format() -> None:
    module = _load("check_budget", "scripts/gke/check_budget.py")
    assert module.model_cache_uri("my-bucket") == "gs://my-bucket/model-cache/"
    with pytest.raises(ValueError):
        module.model_cache_uri("INVALID BUCKET")


def test_print_model_cache_uri_resolves_bucket_without_raw_leak() -> None:
    module = _load("check_budget", "scripts/gke/check_budget.py")
    operator = {"resolved_paths": {
        "tf_data_dir": Path("x"), "gcloud_config_dir": Path("y"),
        "application_default_credentials": Path("z"),
    }}
    uri = module.print_private_model_cache_uri(
        "bundle",
        Path.cwd(),
        operator_loader=lambda *args, **kwargs: operator,
        runner=lambda argv, env: '"data-bucket-1"',
    )
    assert uri == "gs://data-bucket-1/model-cache/"


def test_resolve_authorized_principal_prefers_gcloud_account() -> None:
    module = _load("check_budget", "scripts/gke/check_budget.py")
    seen: list[str] = []

    def fake_userinfo(url: str) -> dict:
        seen.append(url)
        return {"email": "other@example.com"}

    assert module.resolve_authorized_principal(lambda argv, env: "operator@example.com", {}, fake_userinfo) == "operator@example.com"
    assert seen == []


def test_resolve_authorized_principal_falls_back_to_userinfo() -> None:
    module = _load("check_budget", "scripts/gke/check_budget.py")

    def fake_userinfo(url: str) -> dict:
        assert url == "https://openidconnect.googleapis.com/v1/userinfo"
        return {"email": "operator@example.com", "sub": "123"}

    assert module.resolve_authorized_principal(lambda argv, env: "", {}, fake_userinfo) == "operator@example.com"


def test_resolve_authorized_principal_rejects_empty_identities() -> None:
    module = _load("check_budget", "scripts/gke/check_budget.py")
    with pytest.raises(ValueError):
        module.resolve_authorized_principal(lambda argv, env: "", {}, lambda url: {})
    with pytest.raises(ValueError):
        module.resolve_authorized_principal(lambda argv, env: "two lines\nnope", {}, lambda url: {})


def test_print_kms_key_id_returns_identifier_only() -> None:
    module = _load("check_budget", "scripts/gke/check_budget.py")
    operator = {"resolved_paths": {
        "tf_data_dir": Path("x"), "gcloud_config_dir": Path("y"),
        "application_default_credentials": Path("z"),
    }}
    key_id = module.print_private_kms_key_id(
        "bundle",
        Path.cwd(),
        operator_loader=lambda *args, **kwargs: operator,
        runner=lambda argv, env: '"projects/p/locations/r/keyRings/k/cryptoKeys/c"',
    )
    assert key_id == "projects/p/locations/r/keyRings/k/cryptoKeys/c"


def _proof_file(directory: Path, phase: str, *, revision: str, observed_at_utc: str, ok: bool = True) -> None:
    (directory / f"topic22-backend-{phase}-proof.json").write_text(json.dumps({
        "ok": ok, "phase": phase, "backend_bucket_proof_sha256": "a" * 64,
        "observed_proof_sha256": "b" * 64, "bucket_sha256": "c" * 64,
        "prefix_sha256": "d" * 64, "project_number_sha256": "e" * 64,
        "state_object_present": phase == "initialized",
        "observed_at_utc": observed_at_utc, "revision": revision,
    }), encoding="utf-8")


def _gate_operator() -> dict:
    return {"backend_bucket_preexists": True, "backend_bucket_proof_sha256": "b" * 64}


def test_require_current_backend_proof_prefers_fresh_initialized() -> None:
    module = _load("check_budget", "scripts/gke/check_budget.py")
    import tempfile
    from datetime import UTC, datetime
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        _proof_file(directory, "initialized", revision="0" * 40, observed_at_utc=now)
        proof = module.require_current_backend_proof(directory, _gate_operator(), directory)
        assert proof["phase"] == "initialized"


def test_require_current_backend_proof_falls_back_to_bootstrap() -> None:
    module = _load("check_budget", "scripts/gke/check_budget.py")
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        (directory / "topic22-bootstrap-proof.json").write_text(json.dumps({
            "ok": True, "phase": "bootstrap", "backend_bucket_proof_sha256": "b" * 64,
            "backend_bucket_sha256": "c" * 64, "backend_prefix_sha256": "d" * 64,
            "backend_project_number_sha256": "e" * 64, "revision": "0" * 40,
        }), encoding="utf-8")
        from datetime import UTC, datetime
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        _proof_file(directory, "bootstrap", revision="0" * 40, observed_at_utc=now)
        proof = module.require_current_backend_proof(directory, _gate_operator(), directory)
        assert proof["phase"] == "bootstrap"


def test_validate_initialized_backend_record_accepts_same_identity_new_revision() -> None:
    module = _load("check_budget", "scripts/gke/check_budget.py")
    import tempfile
    from datetime import UTC, datetime
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        (directory / "topic22-backend-bootstrap-proof.json").write_text(json.dumps({
            "ok": True, "phase": "bootstrap", "backend_bucket_proof_sha256": "a" * 64,
            "observed_proof_sha256": "a" * 64, "bucket_sha256": "c" * 64,
            "prefix_sha256": "d" * 64, "project_number_sha256": "e" * 64,
            "observed_at_utc": "2020-01-01T00:00:00Z", "revision": "0" * 40,
        }), encoding="utf-8")
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        record = {"phase": "initialized", "bucket_sha256": "c" * 64, "prefix_sha256": "d" * 64,
                  "project_number_sha256": "e" * 64, "revision": "1" * 40, "observed_at_utc": now}
        assert module.validate_initialized_backend_record(directory, record) is record
        tampered = dict(record, bucket_sha256="f" * 64)
        with pytest.raises(ValueError):
            module.validate_initialized_backend_record(directory, tampered)


def test_private_process_environment_carries_quota_project() -> None:
    module = _load("check_budget", "scripts/gke/check_budget.py")
    from pathlib import Path as _Path
    env = module.private_process_environment(
        {"project_id": "private-project"}, _Path("d"), _Path("c"), _Path("a"))
    assert env["GOOGLE_CLOUD_QUOTA_PROJECT"] == "private-project"
    assert env["TF_DATA_DIR"] == "d"
    bare = module.private_process_environment({}, _Path("d"), _Path("c"), _Path("a"))
    assert "GOOGLE_CLOUD_QUOTA_PROJECT" not in bare


def test_configure_vault_token_reaches_pod_process() -> None:
    module = _load("configure_vault", "scripts/gke/configure_vault.py")
    import subprocess as _subprocess
    seen: dict = {}
    real_run = _subprocess.run

    def fake_run(argv, **kwargs):
        seen["argv"] = list(argv)
        class _Result:
            returncode = 0
            stdout = "{}"
            stderr = ""
        return _Result()

    module.subprocess.run = fake_run
    try:
        module._vault_exec("kubeconfig", "edai2-gke", "vault", "token", "revoke", "-self", token="s.secret")
    finally:
        module.subprocess.run = real_run
    joined = " ".join(seen["argv"])
    assert "VAULT_TOKEN=s.secret" in joined
    assert "vault" in joined


def test_configure_vault_probe_matrix_matches_checked_in_policies() -> None:
    module = _load("configure_vault", "scripts/gke/configure_vault.py")
    root = Path(__file__).resolve().parents[2]
    for role, path, _ in module.PROBE_MATRIX:
        assert (root / "infra" / "security" / "vault" / "policies" / f"{role}.hcl").is_file()
        assert path.split("kv/", 1)[1] in (
            "edai2/kagent/gateway-keys", "edai2/facade/gateway-entry")


def test_vault_kms_identity_exists_in_terraform() -> None:
    root = Path(__file__).resolve().parents[2]
    iam = (root / "infra" / "terraform" / "modules" / "iam" / "main.tf").read_text(encoding="utf-8")
    assert "edai2-vault" in iam
    assert "vault/vault" in iam
    assert "roles/cloudkms.cryptoKeyEncrypterDecrypter" in iam
    assert "roles/cloudkms.viewer" in iam


def test_extract_manifest_skips_noise_lines() -> None:
    module = _load("prefetch_models", "scripts/gke/prefetch_models.py")
    assert module.extract_manifest("pip noise\nnot json\n") is None
    assert module.extract_manifest('noise\n{"objects": [{"a": 1}]}\ntrailing') == {"objects": [{"a": 1}]}


def test_render_job_yaml_substitutes_everything() -> None:
    module = _load("prefetch_models", "scripts/gke/prefetch_models.py")
    rendered = module.render_job_yaml("edai2-retrieval-agent", "gs://b/model-cache/", "[]")
    assert "$worker" not in rendered and "$uri" not in rendered and "'$pins'" not in rendered
    assert "edai2-retrieval-agent" in rendered and "gs://b/model-cache/" in rendered
    import yaml as _yaml
    parsed = _yaml.safe_load(rendered)
    command = parsed["spec"]["template"]["spec"]["containers"][0]["command"]
    assert command[0:2] == ["/bin/sh", "-c"]
    assert "gs://b/model-cache/" in command[2]


def test_worker_argv_indices_match_python_dash_c_semantics() -> None:
    module = _load("prefetch_models", "scripts/gke/prefetch_models.py")
    source = module.worker_source()
    assert "sys.argv[2]" in source
    assert "sys.argv[3]" in source


def test_worker_adopts_only_byte_identical_objects() -> None:
    module = _load("prefetch_models", "scripts/gke/prefetch_models.py")
    source = module.worker_source()
    assert "PreconditionFailed" in source
    assert "bytes mismatch" in source
    assert "adopted" in source


def test_dir_manifest_compares_file_trees() -> None:
    module = _load("prefetch_models", "scripts/gke/prefetch_models.py")
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        first, second = Path(tmp) / "a", Path(tmp) / "b"
        for root in (first, second):
            (root / "sub").mkdir(parents=True)
            (root / "f.txt").write_text("same", encoding="utf-8")
            (root / "sub" / "g.bin").write_bytes(b"\x00\x01")
        assert module.dir_manifest(first) == module.dir_manifest(second)
        (second / "f.txt").write_text("different", encoding="utf-8")
        assert module.dir_manifest(first) != module.dir_manifest(second)


def test_worker_adopts_identical_trees_after_topdir_strip(tmp_path: Path) -> None:
    module = _load("prefetch_models", "scripts/gke/prefetch_models.py")
    work = tmp_path / "work"
    (work / "sub").mkdir(parents=True)
    (work / "f.txt").write_text("same", encoding="utf-8")
    (work / "sub" / "g.bin").write_bytes(b"\x00\x01")
    refit = tmp_path / "refit"
    nested = refit / "old456"
    (nested / "sub").mkdir(parents=True)
    (nested / "f.txt").write_text("same", encoding="utf-8")
    (nested / "sub" / "g.bin").write_bytes(b"\x00\x01")
    assert module._adoption_identical(refit, work) is True
    (nested / "f.txt").write_text("different", encoding="utf-8")
    assert module._adoption_identical(refit, work) is False
    source = module.worker_source()
    assert "_adoption_identical" in source
    assert "if not _adoption_identical(refit, work):" in source


def test_prefetch_config_requires_three_pinned_revisions_without_fallback() -> None:
    module = _load("prefetch_models", "scripts/gke/prefetch_models.py")
    config = yaml.safe_load(
        Path(__file__).resolve().parents[2].joinpath("configs/llm/models.yaml").read_text(encoding="utf-8")
    )
    pins = module.load_pins(config)
    assert len(pins) == 3
    assert all(len(pin["revision"]) == 40 for pin in pins)
    assert all(pin["fallback"] == "forbidden" for pin in pins)


def test_prefetch_config_rejects_mutable_revision() -> None:
    module = _load("prefetch_models", "scripts/gke/prefetch_models.py")
    with pytest.raises(ValueError):
        module.load_pins({"models": {"primary": {"model": "m", "hub_revision": "main", "fallback": "forbidden"}}})


def test_prefetch_manifest_entry_is_canonical_and_hashed() -> None:
    module = _load("prefetch_models", "scripts/gke/prefetch_models.py")
    first = module.manifest_entry("primary", "rev", "a" * 64, 42, "7")
    second = module.manifest_entry("primary", "rev", "a" * 64, 42, "7")
    assert first == second
    assert first["name"] == "primary"
    assert len(first["sha256"]) == 64
    with pytest.raises(ValueError):
        module.manifest_entry("primary", "rev", "not-a-hash", 42, "7")


def test_manage_profile_lease_is_sole_and_owner_checked(tmp_path: Path) -> None:
    module = _load("manage_profile", "scripts/gke/manage_profile.py")
    lease = tmp_path / "lease.json"
    module.acquire_lease(lease, owner="topic23-bootstrap", profile="core", ttl_hours=2, commit_sha="a" * 40)
    with pytest.raises(ValueError):
        module.acquire_lease(lease, owner="other", profile="core", ttl_hours=2, commit_sha="a" * 40)
    with pytest.raises(ValueError):
        module.release_lease(lease, owner="other")
    module.release_lease(lease, owner="topic23-bootstrap")
    assert not lease.exists()


def test_capture_verify_vault_bootstrap_accepts_minimal_redacted_payload() -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    module.verify_vault_bootstrap({
        "initialized": True, "seal_type": "gcpckms", "root_revoked": True,
        "key_names": ["model-api-key"], "policy_results": {"ok": True},
    })


def test_capture_verify_vault_bootstrap_accepts_threshold_counts_without_false_positive() -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    module.verify_vault_bootstrap({
        "initialized": True, "seal_type": "gcpckms", "root_revoked": True,
        "key_names": ["model-api-key"], "policy_results": {"ok": True},
        "recovery_threshold": 1, "recovery_shares": 1,
        "recovery_material": "in-cluster-only", "disaster_safe": False,
    })


def test_capture_verify_vault_bootstrap_rejects_secret_or_custodian_payload() -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    with pytest.raises(ValueError):
        module.verify_vault_bootstrap({"initialized": True, "root_token": "s.abc", "custodian": "x"})
    with pytest.raises(ValueError):
        module.verify_vault_bootstrap({"initialized": True})


def test_prefetch_run_resolves_binary_to_full_path() -> None:
    module = _load("prefetch_models", "scripts/gke/prefetch_models.py")
    import shutil as _shutil
    import subprocess as _subprocess
    real_which, real_run = _shutil.which, _subprocess.run
    seen: dict = {}
    _shutil.which = lambda name: "C:\\fake\\gcloud.cmd" if name == "gcloud" else real_which(name)  # type: ignore[method-assign]

    def fake_run(argv, **kwargs):
        seen["argv"] = list(argv)
        assert argv[0] == "C:\\fake\\gcloud.cmd", f"binary not resolved: {argv[0]}"
        class _Result:
            returncode = 0
            stdout = "{}"
            stderr = ""
        return _Result()

    module.subprocess.run = fake_run
    try:
        assert module._run("gcloud", "storage", "objects", "describe", "x") == "{}"
    finally:
        _shutil.which = real_which  # type: ignore[method-assign]
        module.subprocess.run = real_run
    assert seen["argv"][1:] == ["storage", "objects", "describe", "x"]


def test_prefetch_run_raises_clear_error_when_binary_missing() -> None:
    module = _load("prefetch_models", "scripts/gke/prefetch_models.py")
    import shutil as _shutil
    real_which = _shutil.which
    _shutil.which = lambda name: None  # type: ignore[method-assign]
    try:
        with pytest.raises(RuntimeError, match="not found on PATH"):
            module._run("gcloud", "storage", "objects", "describe", "x")
    finally:
        _shutil.which = real_which  # type: ignore[method-assign]


def test_capture_verify_model_cache_rejects_credential_or_mutable_payload() -> None:
    module = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    with pytest.raises(ValueError):
        module.verify_model_cache({"objects": [], "service_account_key": "x"})
    with pytest.raises(ValueError):
        module.verify_model_cache({"objects": []})
    module.verify_model_cache({
        "gcs_uri": "gs://b/model-cache/",
        "objects": [{"name": name, "generation": str(i + 1), "sha256": "a" * 64, "bytes": 10}
                    for i, name in enumerate(("primary", "comparison", "embedding"))],
        "manifest_sha256": "b" * 64,
    })


def test_build_cache_evidence_from_live_describes() -> None:
    prefetch = _load("prefetch_models", "scripts/gke/prefetch_models.py")
    pins = [
        {"name": "primary", "model": "org/primary", "revision": "a" * 40, "fallback": "forbidden"},
        {"name": "comparison", "model": "org/comparison", "revision": "b" * 40, "fallback": "forbidden"},
        {"name": "embedding", "model": "org/embedding", "revision": "c" * 40, "fallback": "forbidden"},
    ]
    describes = [
        {"generation": "1", "size": 10},
        {"generation": "2", "size": 20},
        {"generation": "3", "size": 30},
    ]
    hashes = ["d" * 64, "e" * 64, "f" * 64]
    result = prefetch.build_cache_evidence("gs://b/model-cache/", pins, describes, hashes)
    verifier = _load("capture_edai2_evidence", "scripts/qa/capture_edai2_evidence.py")
    verifier.verify_model_cache(result)
    assert result["total_bytes"] == 60
    import re as _re
    assert _re.fullmatch(r"[0-9a-f]{64}", result["manifest_sha256"])
