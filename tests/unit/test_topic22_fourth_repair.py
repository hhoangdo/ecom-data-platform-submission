from __future__ import annotations

import copy
from datetime import UTC, datetime
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]


def _load(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _typed_readbacks() -> dict[str, object]:
    workload_identity = [
        {"workload": "retrieval", "ksa": "edai2-retrieval-agent", "ksa_member_sha256": "7" * 64, "gsa_sha256": "8" * 64, "prefixes": ["model-cache/"]},
        {"workload": "drift", "ksa": "edai2-drift-agent", "ksa_member_sha256": "9" * 64, "gsa_sha256": "a" * 64, "prefixes": ["langfuse-events/"]},
        {"workload": "coordinator", "ksa": "edai2-coordinator", "ksa_member_sha256": "b" * 64, "gsa_sha256": "c" * 64, "prefixes": ["agent-substrate/", "backups/"]},
        {"workload": "workers", "ksa": "edai2-worker", "ksa_member_sha256": "d" * 64, "gsa_sha256": "e" * 64, "prefixes": ["airflow-logs/"]},
    ]
    return {
        "project_alias_sha256": "1" * 64,
        "project_number_sha256": "2" * 64,
        "cluster": {"name": "edai2", "zone": "us-central1-a", "workload_pool_sha256": "3" * 64},
        "node_pools": [
            {"name": "platform", "machine_type": "e2-highmem-4", "spot": False, "min": 0, "max": 1, "current": 0},
            {"name": "spot", "machine_type": "e2-standard-8", "spot": True, "min": 0, "max": 2, "current": 0},
        ],
        "registries": [
            {"name": name, "format": "DOCKER", "location": "us-central1"}
            for name in (
                "edai2-rag-index", "edai2-retrieval-agent", "edai2-drift-agent",
                "edai2-coordinator", "edai2-feast-offline-writer", "edai2-feast-online-writer",
            )
        ],
        "bucket": {
            "name_sha256": "4" * 64,
            "location": "US-CENTRAL1",
            "cmek_sha256": "5" * 64,
            "lifecycle": {"7": ["agent-substrate/", "langfuse-events/"], "90": ["airflow-logs/", "backups/", "model-cache/"]},
            "uniform_access": True,
        },
        "kms": {"key_sha256": "5" * 64, "rotation_seconds": 7_776_000, "gcs_service_agent_sha256": "6" * 64, "gcs_role": "roles/cloudkms.cryptoKeyEncrypterDecrypter"},
        "workload_identity": workload_identity,
        "prefix_iam": [
            {"prefix": prefix, "gsa_sha256": fingerprint, "role": "roles/storage.objectUser"}
            for prefix, fingerprint in (
                ("model-cache/", "8" * 64), ("langfuse-events/", "a" * 64),
                ("agent-substrate/", "c" * 64), ("backups/", "c" * 64), ("airflow-logs/", "e" * 64),
            )
        ],
        "budget": {"currency": "VND", "amount_vnd": 6_000_000, "trial_credit_vnd": 7_500_000, "normalized_usd": 240, "thresholds": [0.5, 0.75, 0.9, 1.0], "project_number_sha256": "2" * 64, "project_number_filter_matches": True, "notification_channel_sha256": "f" * 64, "notification_channel_matches": True},
        "backend": {"bucket_sha256": "4" * 64, "prefix_sha256": "f" * 64, "remote_state_present": True},
        "forwarding_rules": [],
    }


def test_billing_writer_loads_by_file_path_without_repository_package_importability(tmp_path: Path) -> None:
    """Catches a production entrypoint importing `scripts.*` when only its own file is importable."""
    capture_path = ROOT / "scripts" / "qa" / "capture_edai2_evidence.py"
    program = f"""
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('standalone_capture', {str(capture_path)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module._billing_page_writer(
    'https://console.cloud.google.com/billing/overview', Path('private-state.json'),
    project_alias_sha256='a' * 64, observed_at='2026-08-12T00:00:00Z',
    required_markers=[\"[aria-label*='Billing']\", \"[data-testid='current-spend']\"],
    pii_selectors=[\"[data-field='billing-account-id']\", \"[aria-label*='email']\"],
    page_factory=lambda _state: None,
)
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", program], cwd=tmp_path,
        capture_output=True, text=True, encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr


def test_default_inventory_dependencies_construct_under_isolated_file_execution(tmp_path: Path) -> None:
    """Catches default operator-loader/REST imports depending on the checkout root being importable."""
    capture_path = ROOT / "scripts" / "qa" / "capture_edai2_evidence.py"
    program = f"""
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('standalone_capture_inventory', {str(capture_path)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
adapter = module.GcloudRestTopic22InventoryAdapter(workspace=Path.cwd())
assert callable(adapter._operator_loader)
assert callable(adapter._requester)
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", program], cwd=tmp_path,
        capture_output=True, text=True, encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr


def test_billing_cli_branch_runs_isolated_with_injected_safe_dependencies(tmp_path: Path) -> None:
    """Catches the billing parser branch importing a repository-only operator loader at runtime."""
    capture_path = ROOT / "scripts" / "qa" / "capture_edai2_evidence.py"
    program = f"""
import importlib.util
import json
from pathlib import Path
spec = importlib.util.spec_from_file_location('standalone_capture_billing', {str(capture_path)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
root = Path.cwd() / 'screenshots'
root.mkdir()
machine = Path.cwd() / 'forecast.json'
machine.write_text('{{\"ok\":true}}\\n', encoding='utf-8')
state = Path.cwd() / 'state.json'
state.write_text('{{}}\\n', encoding='utf-8')
operator = {{
  'project_id': 'private-project',
  'billing_console_url': 'https://console.cloud.google.com/billing/private',
  'spend_observed_at': '2026-08-12T00:00:00Z',
  'billing_required_markers': [\"[aria-label*='Billing']\"],
  'billing_pii_selectors': [\"[aria-label*='email']\"],
  'resolved_paths': {{'browser_storage_state': state}},
}}
def writer_factory(_operator):
    def writer(destination):
        module.Image.effect_noise((1600, 1000), 100).save(destination, 'PNG')
    return writer
result = module.run_topic22_cli([
  '--capture', 'billing', '--operator-inputs', 'private-bundle.json',
  '--viewport', '1600x1000', '--output', str(root / 'gcp_billing_spend.png'),
  '--manifest', str(root / 'ui_manifest.json'), '--machine-evidence', str(machine), '--strict',
], revision='d' * 40, operator_loader=lambda _path, _workspace: operator, billing_writer_factory=writer_factory)
assert result == 0
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", program], cwd=tmp_path,
        capture_output=True, text=True, encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    ("markers", "pii", "accepted"),
    [
        (["[aria-label*='Billing']", "[data-testid='current-spend']"], ["[data-field='billing-account-id']", "[aria-label*='email']"], True),
        ([], ["[aria-label*='email']"], False),
        (["body"], ["[aria-label*='email']"], False),
        (["[data-testid='https://private']"], ["[aria-label*='email']"], False),
        (["[aria-label*='Billing']"], ["*"], False),
    ],
)
def test_budget_and_capture_selector_validators_share_acceptance_vectors(markers, pii, accepted: bool) -> None:
    """Catches behavior drift between the two independently executable CLIs."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_budget_selector_vectors")
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_capture_selector_vectors")
    if accepted:
        assert budget.validate_billing_selectors(markers, pii) == (markers, pii)
        assert capture.validate_billing_selectors(markers, pii) == (markers, pii)
    else:
        with pytest.raises(ValueError, match="selector"):
            budget.validate_billing_selectors(markers, pii)
        with pytest.raises(ValueError, match="selector"):
            capture.validate_billing_selectors(markers, pii)


def test_typed_reducer_rejects_count_only_entries_and_accepts_exact_adapter_schema() -> None:
    """Catches a reducer that treats nonempty placeholder dictionaries as verified cloud facts."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_reducer")
    count_only = {"registry": [{}, {}, {}, {}, {}, {}], "gcs": [{}], "kms_cmek": [{}], "workload_identity_iam": [{}, {}, {}, {}], "budget": [{}], "forwarding_rules": []}
    with pytest.raises(ValueError):
        capture.reduce_topic22_readbacks(count_only, revision="d" * 40)
    reduced = capture.reduce_topic22_readbacks(_typed_readbacks(), revision="d" * 40)
    assert reduced["result"] == "successful"
    assert reduced["bucket"]["location"] == "US-CENTRAL1"
    assert reduced["forwarding_rule_count"] == 0


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["registries"][0].update(location="europe-west1"),
        lambda value: value["bucket"].update(location="US"),
        lambda value: value["prefix_iam"][0].update(role="roles/storage.admin"),
        lambda value: value["kms"].update(gcs_role="roles/owner"),
        lambda value: value["workload_identity"][0].update(ksa_member_sha256=""),
        lambda value: value["budget"].update(amount_vnd=1),
        lambda value: value["backend"].update(remote_state_present=False),
        lambda value: value["cluster"].update(name="other"),
        lambda value: value["node_pools"][0].update(min=1),
        lambda value: value["forwarding_rules"].append({"name": "forbidden"}),
    ],
)
def test_typed_reducer_rejects_each_wrong_foundation_fact(mutation) -> None:
    """Catches any category reverting from exact typed validation to presence/count checks."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_reducer_mutation")
    payload = _typed_readbacks()
    mutation(payload)
    with pytest.raises(ValueError):
        capture.reduce_topic22_readbacks(payload, revision="d" * 40)


def test_plan_sanitizer_publishes_fully_bound_artifact_once_and_replay_is_immutable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Catches publishing an incomplete authorization record and reopening it to add hashes later."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_sanitizer")
    third = _load("tests/unit/test_topic22_third_repair.py", "topic22_fourth_plan_fixture")
    plan = tmp_path / "topic22.tfplan"
    forecast = tmp_path / "forecast.json"
    output = tmp_path / "authorization.json"
    plan.write_bytes(b"approved-binary-plan")
    forecast.write_text('{"normalized_budget_usd":240}\n', encoding="utf-8")
    revision = "c" * 40
    replacements: list[dict[str, object]] = []
    real_replace = capture.os.replace

    def replace(source, destination):
        if Path(destination) == output:
            replacements.append(json.loads(Path(source).read_text(encoding="utf-8")))
        return real_replace(source, destination)

    monkeypatch.setattr(capture.os, "replace", replace)
    capture.sanitize_terraform_plan(plan, output, forecast_path=forecast, revision=revision,
        required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget"}, runner=lambda _command: json.dumps(third._realistic_plan()))
    assert len(replacements) == 1
    assert replacements[0]["plan_sha256"] == capture.hash_file(plan)
    assert replacements[0]["forecast_sha256"] == capture.hash_file(forecast)
    assert replacements[0]["revision"] == revision
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        capture.sanitize_terraform_plan(plan, output, forecast_path=forecast, revision=revision,
            required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget"}, runner=lambda _command: json.dumps(third._realistic_plan()))
    assert output.read_bytes() == before


def test_inventory_render_verify_cli_uses_one_canonical_sanitized_schema(tmp_path: Path) -> None:
    """Catches the renderer feeding sanitized apply evidence back through the raw readback validator."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_e2e")
    third = _load("tests/unit/test_topic22_third_repair.py", "topic22_fourth_e2e_plan")
    revision = "d" * 40
    authorization = capture.sanitize_terraform_payload(
        third._realistic_plan(), required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget"},
        plan_sha256="a" * 64, forecast_sha256="b" * 64, revision=revision,
    )
    authorization_path = tmp_path / "authorization.json"
    authorization_path.write_text(json.dumps(authorization) + "\n", encoding="utf-8")
    bundle = tmp_path / "operator.json"
    bundle.write_text("{}\n", encoding="utf-8")
    inventory = tmp_path / "terraform_apply.json"

    class Adapter:
        def read(self, _operator_inputs):
            return _typed_readbacks()

    assert capture.run_topic22_cli([
        "--terraform-inventory", "--operator-inputs", str(bundle),
        "--authorization-evidence", str(authorization_path), "--output", str(inventory), "--strict",
    ], inventory_adapter_factory=lambda: Adapter(), operator_loader=lambda *_args: None, revision=revision) == 0
    canonical = json.loads(inventory.read_text(encoding="utf-8"))
    capture.validate_sanitized_apply_evidence(canonical)
    assert canonical["plan_sha256"] == "a" * 64
    screenshot_root = tmp_path / "screenshots"
    screenshot_root.mkdir()
    screenshot = screenshot_root / "terraform_apply.png"
    manifest = screenshot_root / "ui_manifest.json"
    assert capture.run_topic22_cli([
        "--render-sanitized-terraform", str(inventory), "--capture", "terraform-apply",
        "--viewport", "1600x1000", "--output", str(screenshot), "--manifest", str(manifest),
        "--machine-evidence", str(inventory), "--strict",
        ], revision=revision, workspace=tmp_path) == 0
    assert capture.run_topic22_cli([
        "--verify-screenshots", "terraform_apply.png", "--manifest", str(manifest), "--strict",
    ], revision=revision, workspace=tmp_path) == 0


def test_billing_selectors_are_bundle_configured_and_malicious_or_empty_values_fail(tmp_path: Path) -> None:
    """Catches hard-coded browser selectors or operator-controlled JavaScript/XPath reaching Playwright."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_selectors")
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_selector_writer")
    markers = ["[aria-label*='Billing']", "[data-testid='current-spend']"]
    pii = ["[data-field='billing-account-id']", "[aria-label*='email']"]
    assert budget.validate_billing_selectors(markers, pii) == (markers, pii)
    for bad_markers, bad_pii in (([], pii), (["body"], pii), (["//div"], pii), (["[data-testid='https://private']"], pii), (markers, ["*"])):
        with pytest.raises(ValueError, match="selector"):
            budget.validate_billing_selectors(bad_markers, bad_pii)

    calls: list[tuple[str, str]] = []
    state = tmp_path / "state.json"
    state.write_text("{}\n", encoding="utf-8")

    class Locator:
        def count(self): return 1
        def inner_text(self, timeout=0): return "Billing overview ready"
        def evaluate_all(self, _script): calls.append(("masked", "configured"))
    class Page:
        url = "https://console.cloud.google.com/billing/overview"
        def goto(self, _url, **_kwargs): pass
        def wait_for_selector(self, selector, **_kwargs): calls.append(("marker", selector))
        def locator(self, _selector): return Locator()
        def evaluate(self, _script, _annotation): pass
        def screenshot(self, **kwargs): Path(kwargs["path"]).write_bytes(b"png")

    operator = {"billing_console_url": Page.url, "billing_required_markers": markers, "billing_pii_selectors": pii, "project_id": "private", "spend_observed_at": "2026-08-12T00:00:00Z", "resolved_paths": {"browser_storage_state": state}}
    writer = capture.billing_writer_from_operator(operator, page_factory=lambda _state: Page())
    writer(tmp_path / "billing.png")
    assert [("marker", value) for value in markers] == [item for item in calls if item[0] == "marker"]


def test_private_account_and_kube_helpers_never_put_identifiers_in_argv_or_output(tmp_path: Path) -> None:
    """Catches reintroducing direct identifier-bearing gcloud commands into the Topic 22 workflow."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_private_helpers")
    private = tmp_path / "tmp" / "edai2-gcp"
    private.mkdir(parents=True)
    bundle = private / "operator-inputs.json"
    raw_project, raw_billing = "private-project", "PRIVATE-BILLING"
    operator = {
        "project_id": raw_project, "billing_account_id": raw_billing,
        "resolved_paths": {"gcloud_config_dir": private, "application_default_credentials": private / "adc.json"},
    }
    bundle.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "summary.json"

    class Adapter:
        def project(self): return {"active": True, "project_sha256": "1" * 64, "project_number_sha256": "2" * 64}
        def billing(self): return {"linked": True, "billing_link_hash_matches": True, "billing_account_name_matches": True, "billing_account_open": True, "billing_currency_vnd": True, "billing_account_sha256": "3" * 64}

    loader = lambda _path, _workspace, _validator=None: operator
    account_environment: dict[str, str] = {}
    def adapter_factory(_project, _billing, environment):
        account_environment.update(environment)
        return Adapter()
    assert budget.write_redacted_account_summary(bundle, output, tmp_path, operator_loader=loader, adapter_factory=adapter_factory) == 0
    assert account_environment["CLOUDSDK_CONFIG"] == str(private)
    assert account_environment["GOOGLE_APPLICATION_CREDENTIALS"] == str(private / "adc.json")
    persisted = output.read_text(encoding="utf-8")
    assert raw_project not in persisted and raw_billing not in persisted
    assert all(json.loads(persisted)[key] is True for key in ("billing_account_name_matches", "billing_account_open", "billing_currency_vnd"))

    commands: list[list[str]] = []
    def runner(command: list[str], environment: dict[str, str]) -> None:
        commands.append(command)
        generated = f"gke_{raw_project}_us-central1-a_edai2"
        Path(environment["KUBECONFIG"]).write_text(json.dumps({
            "apiVersion": "v1", "kind": "Config", "current-context": generated,
            "contexts": [{"name": generated, "context": {"cluster": generated, "user": generated}}],
            "clusters": [{"name": generated, "cluster": {"server": "https://gke.private.invalid"}}],
            "users": [{"name": generated, "user": {"auth-provider": {"name": "gcp"}}}],
        }), encoding="utf-8")
    target = budget.prepare_private_kube_target(bundle, tmp_path, operator_loader=loader, runner=runner, path_validator=lambda path, _kind: path.resolve())
    assert commands == [["gcloud", "container", "clusters", "get-credentials", "edai2", "--zone", "us-central1-a"]]
    assert all(raw_project not in part and raw_billing not in part for part in commands[0])
    assert target == {"schema_version": 1, "kubeconfig": "tmp/edai2-gcp/kubeconfig", "context": "edai2-gke", "zone": "us-central1-a"}
    helper = (private / "kube-target.json").read_text(encoding="utf-8")
    assert raw_project not in helper and raw_billing not in helper


def test_private_kube_target_rejects_context_bound_to_other_project_or_cluster(tmp_path: Path) -> None:
    """Catches rewriting a context that gcloud returned for a different project or cluster."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_kube_binding")
    private = tmp_path / "tmp" / "edai2-gcp"
    private.mkdir(parents=True)
    bundle = private / "operator-inputs.json"
    bundle.write_text("{}\n", encoding="utf-8")
    operator = {"project_id": "private-project", "resolved_paths": {"gcloud_config_dir": private, "application_default_credentials": private / "adc.json"}}
    def runner(_command, environment):
        wrong = "gke_other-project_us-central1-a_other"
        Path(environment["KUBECONFIG"]).write_text(yaml.safe_dump({
            "current-context": wrong,
            "contexts": [{"name": wrong, "context": {"cluster": wrong, "user": wrong}}],
            "clusters": [{"name": wrong, "cluster": {"server": "https://gke.private.invalid"}}],
            "users": [{"name": wrong, "user": {}}],
        }), encoding="utf-8")
    with pytest.raises(ValueError, match="kubeconfig"):
        budget.prepare_private_kube_target(bundle, tmp_path, operator_loader=lambda *_args: operator, runner=runner, path_validator=lambda path, _kind: path.resolve())
    assert not (private / "kube-target.json").exists()


def test_private_kube_target_rejects_extra_context_cluster_or_user(tmp_path: Path) -> None:
    """Catches a selected valid context being accepted beside an unbound kubeconfig entry."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_kube_exact_one")
    expected = "gke_private-project_us-central1-a_edai2"
    document = {"current-context": expected, "contexts": [{"name": expected, "context": {"cluster": expected, "user": expected}}, {"name": "other", "context": {"cluster": "other", "user": "other"}}], "clusters": [{"name": expected, "cluster": {"server": "https://gke.private.invalid"}}, {"name": "other", "cluster": {"server": "https://other.invalid"}}], "users": [{"name": expected, "user": {}}, {"name": "other", "user": {}}]}
    with pytest.raises(ValueError, match="kubeconfig"):
        budget._bind_private_kube_document(document, "private-project")


def test_private_helper_cli_dispatches_account_and_kube_modes_without_legacy_budget_path(tmp_path: Path) -> None:
    """Catches parsed helper flags falling through to the unrelated legacy budget evaluator."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_helper_dispatch")
    bundle = tmp_path / "operator.json"
    bundle.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "summary.json"
    calls: list[str] = []
    account_args = budget.parse_args(["--operator-inputs", str(bundle), "--redacted-account-summary", "--output", str(output)])
    assert budget.dispatch_private_helper(
        account_args, tmp_path,
        account_writer=lambda *_args, **_kwargs: calls.append("account") or 0,
        kube_preparer=lambda *_args, **_kwargs: pytest.fail("wrong helper branch"),
    ) == 0
    kube_args = budget.parse_args(["--operator-inputs", str(bundle), "--prepare-kube-target"])
    assert budget.dispatch_private_helper(
        kube_args, tmp_path,
        account_writer=lambda *_args, **_kwargs: pytest.fail("wrong helper branch"),
        kube_preparer=lambda *_args, **_kwargs: calls.append("kube") or {"context": "edai2-gke"},
    ) == 0
    assert calls == ["account", "kube"]


def test_private_helper_dispatches_backend_gate_and_apply_without_public_plan_or_approval_argv(tmp_path: Path) -> None:
    """Catches the executable gate being bypassed or an apply approval/plan path entering public CLI arguments."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_runtime_dispatch")
    bundle = tmp_path / "operator.json"; bundle.write_text("{}\n", encoding="utf-8")
    data = tmp_path / "tmp" / "edai2-gcp" / "terraform-data"; data.mkdir(parents=True)
    operator = {"backend_bucket_preexists": True, "backend_bucket_proof_sha256": "a" * 64, "resolved_paths": {"tf_data_dir": data}}
    backend = budget.parse_args(["--operator-inputs", str(bundle), "--verify-private-backend", "bootstrap"])
    assert budget.dispatch_private_helper(backend, tmp_path, operator_loader=lambda *_args: operator, backend_verifier=lambda _operator, phase: {"phase": phase, "state_object_present": False, "proof_sha256": "a" * 64, "bucket_sha256": "b" * 64, "prefix_sha256": "c" * 64, "project_number_sha256": "d" * 64}, account_writer=lambda *_args: pytest.fail("wrong branch"), kube_preparer=lambda *_args: pytest.fail("wrong branch")) == 0
    action = budget.parse_args(["--operator-inputs", str(bundle), "--private-terraform-action", "apply"])
    calls: list[tuple[Path, str]] = []
    assert budget.dispatch_private_helper(action, tmp_path, operator_loader=lambda *_args: operator, terraform_executor=lambda contract, _operator, name, **_kwargs: calls.append((contract, name)) or {"ok": True}, backend_verifier=lambda _operator, phase: {"phase": phase, "state_object_present": phase == "initialized", "proof_sha256": "a" * 64, "bucket_sha256": "b" * 64, "prefix_sha256": "c" * 64, "project_number_sha256": "d" * 64}, account_writer=lambda *_args: pytest.fail("wrong branch"), kube_preparer=lambda *_args: pytest.fail("wrong branch")) == 0
    assert calls == [(data / "topic22-terraform-runtime.json", "apply")]


def test_manifest_verifier_revalidates_linked_canonical_apply_schema(tmp_path: Path) -> None:
    """Catches a hash-updated but factually invalid apply record remaining valid evidence."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_manifest_schema")
    revision = "d" * 40
    canonical = capture.sanitize_apply_inventory(_typed_readbacks(), revision=revision)
    canonical.update({"plan_sha256": "a" * 64, "forecast_sha256": "b" * 64, "approval_record_sha256": "c" * 64})
    machine = tmp_path / "terraform_apply.json"
    machine.write_text(json.dumps(canonical) + "\n", encoding="utf-8")
    root = tmp_path / "screenshots"
    root.mkdir()
    screenshot, manifest = root / "terraform_apply.png", root / "ui_manifest.json"
    capture.record_capture(
        final_path=screenshot, root=root,
        writer=lambda destination: capture.render_topic22_png(canonical, destination, machine_path=machine),
        source="https://evidence.local/terraform-apply", revision=revision,
        visible_selectors=capture.REQUIRED_VIEWS["terraform_apply.png"], machine_evidence=[str(machine)],
        proves="Sanitized apply inventory is successful.", does_not_prove="It does not prove workload readiness.", manifest_path=manifest, workspace=tmp_path,
    )
    changed = json.loads(machine.read_text(encoding="utf-8"))
    changed["bucket"]["location"] = "US"
    machine.write_text(json.dumps(changed) + "\n", encoding="utf-8")
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    entries[0]["linked_machine_evidence"][0]["sha256"] = capture.hash_file(machine)
    manifest.write_text(json.dumps(entries) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="inventory|evidence|bucket"):
        capture.verify_topic22_screenshots(manifest, root, ["terraform_apply.png"], revision=revision)


def test_backend_proof_requires_the_exact_state_object_and_public_access_is_rejected() -> None:
    """Catches accepting a boolean/hash or arbitrary object as a Terraform backend proof."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_backend_proof")

    def requester(_method, url, _headers, _body):
        if url.endswith("/b/private-bucket"):
            return {"location": "US-CENTRAL1", "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}}, "versioning": {"enabled": True}}
        if url.endswith("/b/private-bucket/iam"):
            return {"bindings": [{"role": "roles/storage.objectViewer", "members": ["serviceAccount:private@example.invalid"]}]}
        if "/o?" in url:
            return {"items": [{"name": "edai2/topic22/default.tfstate"}]}
        raise AssertionError(url)

    proof = budget.verify_backend_bucket_proof("private-bucket", "edai2/topic22", "initialized", requester=requester)
    assert proof["state_object_present"] is True
    assert len(proof["proof_sha256"]) == 64

    def public_requester(method, url, headers, body):
        response = requester(method, url, headers, body)
        if url.endswith("/iam"):
            response["bindings"][0]["members"] = ["allUsers"]
        return response

    with pytest.raises(ValueError, match="backend"):
        budget.verify_backend_bucket_proof("private-bucket", "edai2/topic22", "initialized", requester=public_requester)


def test_runtime_contract_is_written_only_to_private_json(tmp_path: Path) -> None:
    """Catches plan/apply commands escaping a private atomically written runtime contract."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_runtime_contract")
    private = tmp_path / "tmp" / "edai2-gcp"
    private.mkdir(parents=True)
    for name, text in (("backend.hcl", 'bucket = "private-bucket"\nprefix = "edai2/topic22"\n'), ("vars.tfvars", "project_id = \"private\"\n")):
        (private / name).write_text(text, encoding="utf-8")
    data = private / "terraform-data"
    data.mkdir()
    contract = budget.write_terraform_runtime_contract(
        backend_config=private / "backend.hcl", tfvars=private / "vars.tfvars", tf_data_dir=data,
        workspace=tmp_path, backend_bucket_proof_sha256="a" * 64,
        path_validator=lambda path, _kind: path.resolve(),
    )
    persisted = json.loads(contract.read_text(encoding="utf-8"))
    assert contract.parent == data
    assert persisted["plan"][-1].endswith("topic22.tfplan")
    assert persisted["backend_bucket_proof_sha256"] == "a" * 64


def test_private_bundle_backend_helper_uses_private_gcloud_environment(tmp_path: Path) -> None:
    """Catches a backend proof helper reading ambient gcloud state or exposing its raw bucket."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_private_backend")
    private = tmp_path / "tmp" / "edai2-gcp"
    private.mkdir(parents=True)
    operator = {"project_id": "private-project", "resolved_paths": {"gcloud_config_dir": private, "application_default_credentials": private / "adc.json", "terraform_backend_config": private / "backend.hcl"}}
    (private / "adc.json").write_text("{}", encoding="utf-8")
    (private / "backend.hcl").write_text('bucket = "private-bucket"\nprefix = "edai2/topic22"\n', encoding="utf-8")
    environments: list[dict[str, str]] = []
    def token(command, environment):
        assert command == ["gcloud", "auth", "print-access-token"]
        environments.append(environment)
        return "memory-token"
    def requester(_method, url, _headers, _body):
        if "cloudresourcemanager" in url: return {"name": "projects/123", "projectId": "private-project"}
        if url.endswith("/b/private-bucket"): return {"projectNumber": "123", "location": "US-CENTRAL1", "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}}, "versioning": {"enabled": True}}
        if url.endswith("/iam"): return {"bindings": []}
        return {"items": [{"name": "edai2/topic22/default.tfstate"}]}
    proof = budget.verify_private_backend_bundle(operator, token_runner=token, requester=requester)
    assert proof["state_object_present"] is True
    assert environments[0]["CLOUDSDK_CONFIG"] == str(private)


def test_aggregated_forwarding_rules_follow_page_tokens_and_reject_cycles() -> None:
    """Catches a forbidden forwarding rule hidden after the first aggregated Compute page."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_forwarding_pagination")
    calls: list[str] = []
    def rest(_method, url, _body):
        calls.append(url)
        return {"items": {"zones/us-central1-a": {"forwardingRules": []}}, "nextPageToken": "second"} if "pageToken" not in url else {"items": {"zones/us-central1-b": {"forwardingRules": [{"name": "forbidden"}]}}}
    assert capture.paged_aggregated_forwarding_rules(rest, "https://compute.example/forwardingRules") == [{"name": "forbidden"}]
    def cycle(_method, _url, _body): return {"items": {}, "nextPageToken": "again"}
    with pytest.raises(ValueError, match="paged"):
        capture.paged_aggregated_forwarding_rules(cycle, "https://compute.example/forwardingRules")


def test_plan_sanitizer_rejects_unallowlisted_top_level_fields_and_nested_secret_values() -> None:
    """Catches a Terraform show carrying unreviewed top-level data or a hidden secret-bearing field."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_top_level_schema")
    third = _load("tests/unit/test_topic22_third_repair.py", "topic22_fourth_top_level_fixture")
    plan = third._realistic_plan() | {"unexpected": {"note": "unreviewed"}}
    with pytest.raises(ValueError, match="schema"):
        capture.sanitize_terraform_payload(plan, required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget"})
    plan = third._realistic_plan() | {"planned_values": {"root_module": {"values": {"api_token": "private-token"}}}}
    with pytest.raises(ValueError, match="secret"):
        capture.sanitize_terraform_payload(plan, required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget"})


def test_windows_acl_parser_requires_current_owner_without_inherited_broad_grants() -> None:
    """Catches accepting a private path owned by somebody else or inheriting a broad effective grant."""
    private = _load("src/vina_bim_shop/topic22_private.py", "topic22_fourth_acl")
    good = "C:\\private OWNER\\user:(OI)(CI)(F)\n            OWNER\\user:(I)(OI)(CI)(F)\nSuccessfully processed 1 files"
    assert private.windows_private_acl_ok(good, "OWNER\\user") is True
    assert private.windows_private_acl_ok(good.replace("OWNER\\user:(I)(OI)(CI)(F)", "BUILTIN\\Users:(I)(RX)"), "OWNER\\user") is False
    assert private.windows_private_acl_ok(good, "OTHER\\user") is False


@pytest.mark.skipif(os.name != "nt", reason="Windows owner invocation is a Windows host contract")
def test_windows_owner_subprocess_uses_environment_path_without_command_argument_parser_error(tmp_path: Path) -> None:
    """Catches passing a private path after `--` to PowerShell -Command, which it parses as a command."""
    private = _load("src/vina_bim_shop/topic22_private.py", "topic22_fourth_windows_owner_smoke")
    assert private.windows_owner_for_path(tmp_path).casefold() == subprocess.run(
        ["whoami"], capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.strip().casefold()


def test_windows_owner_helper_is_injectable_and_does_not_put_path_in_argv(tmp_path: Path) -> None:
    """Catches future reintroduction of a private path as a PowerShell command-line argument."""
    private = _load("src/vina_bim_shop/topic22_private.py", "topic22_fourth_windows_owner_injected")
    calls: list[tuple[list[str], dict[str, str]]] = []
    def runner(command, **kwargs):
        calls.append((command, kwargs["env"]))
        return subprocess.CompletedProcess(command, 0, "OWNER\\user\n", "")
    assert private.windows_owner_for_path(tmp_path, runner=runner) == "OWNER\\user"
    assert str(tmp_path) not in calls[0][0]
    assert calls[0][1]["TOPIC22_OWNER_PATH"] == str(tmp_path)


def test_private_unix_tree_modes_require_0700_directories_and_0600_file(tmp_path: Path) -> None:
    """Catches validating only the bundle leaf while a private parent is traversable."""
    private = _load("src/vina_bim_shop/topic22_private.py", "topic22_fourth_unix_modes")
    root = tmp_path / "edai2-gcp"
    nested = root / "operator"
    nested.mkdir(parents=True)
    bundle = nested / "inputs.json"
    bundle.write_text("{}\n", encoding="utf-8")
    modes = {root.resolve(): 0o700, nested.resolve(): 0o700, bundle.resolve(): 0o600}
    assert private.private_unix_tree_modes_ok(bundle, root, mode_reader=lambda path: modes[path.resolve()]) is True
    modes[nested.resolve()] = 0o750
    assert private.private_unix_tree_modes_ok(bundle, root, mode_reader=lambda path: modes[path.resolve()]) is False


def test_private_root_directory_is_a_valid_private_directory_not_a_file_or_escape(tmp_path: Path) -> None:
    """Catches rejecting the exact tmp/edai2-gcp helper destination despite it being the authorized private root."""
    private = _load("src/vina_bim_shop/topic22_private.py", "topic22_fourth_private_root")
    root = tmp_path / "tmp" / "edai2-gcp"; root.mkdir(parents=True)
    assert private._private_topic22_path(root, tmp_path, directory=True) == root.resolve()
    with pytest.raises(ValueError):
        private._private_topic22_path(root, tmp_path, directory=False)


def test_budget_cli_reports_fixed_error_without_echoing_private_argv(capsys: pytest.CaptureFixture[str]) -> None:
    """Catches argparse reflecting an operator's secret path back to stderr."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_redacted_cli")
    with pytest.raises(SystemExit):
        budget.parse_args(["--unknown-private=/secret/token"])
    captured = capsys.readouterr()
    assert "TOPIC22_INPUT_ERROR" in captured.err
    assert "/secret/token" not in captured.err


def test_private_wi_values_writer_emits_all_four_exact_bindings(tmp_path: Path) -> None:
    """Catches a private Helm bridge omitting a chart or mapping a GSA to the wrong KSA."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_wi_writer")
    bindings = {
        workload: {"ksa": f"serviceAccount:project.svc.id.goog[edai2:{ksa}]", "gsa": f"{workload}@project.iam.gserviceaccount.com"}
        for workload, ksa in {"retrieval": "edai2-retrieval-agent", "drift": "edai2-drift-agent", "coordinator": "edai2-coordinator", "workers": "edai2-worker"}.items()
    }
    private = tmp_path / "tmp" / "edai2-gcp"
    private.mkdir(parents=True)
    output = budget.write_private_workload_identity_helm_values(
        bindings, private / "topic22-workload-identity-values.yaml", tmp_path,
        path_validator=lambda path, _kind: path.resolve(), ignore_checker=lambda _path: True,
    )
    values = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert set(values) == {"retrieval", "drift", "coordinator", "workers"}
    assert values["workers"]["serviceAccount"]["name"] == "edai2-worker"


def test_wi_values_writer_rejects_noncanonical_or_unvalidated_destination(tmp_path: Path) -> None:
    """Catches raw GSA values being written outside the one private, ACL-checked bridge path."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_wi_destination")
    private = tmp_path / "tmp" / "edai2-gcp"
    private.mkdir(parents=True)
    bindings = {workload: {"ksa": f"serviceAccount:project.svc.id.goog[edai2:{ksa}]", "gsa": f"{workload}@project.iam.gserviceaccount.com"} for workload, ksa in {"retrieval": "edai2-retrieval-agent", "drift": "edai2-drift-agent", "coordinator": "edai2-coordinator", "workers": "edai2-worker"}.items()}
    with pytest.raises(ValueError, match="private workload"):
        budget.write_private_workload_identity_helm_values(bindings, tmp_path / "outside.yaml", tmp_path, path_validator=lambda path, _kind: path.resolve(), ignore_checker=lambda _path: True)


def test_notification_requires_exact_verified_status() -> None:
    """Catches accepted non-UNVERIFIED channel states that are not the official verified value."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_notification_verified")
    target = "projects/private-project/notificationChannels/private-channel"
    def requester(_method, _url, _headers, _body):
        return {"name": target, "enabled": True, "verificationStatus": "VERIFIED"}
    adapter = budget.GcloudRestExternalAdapter("private-project", "billingAccounts/private", token_supplier=lambda: "token", requester=requester)
    assert adapter.notification(target) is True
    for status in ("UNVERIFIED", "PENDING", None):
        def response(_method, _url, _headers, _body, status=status):
            return {"name": target, "enabled": True, "verificationStatus": status}
        assert budget.GcloudRestExternalAdapter("private-project", "billingAccounts/private", token_supplier=lambda: "token", requester=response).notification(target) is False


def test_backend_proof_pages_all_objects_and_rejects_cycle_or_second_page_extra_object() -> None:
    """Catches accepting the state object from page one while page two hides another backend object."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_backend_pages")
    def requester(_method, url, _headers, _body):
        if url.endswith("/b/private-bucket"):
            return {"location": "US-CENTRAL1", "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}}, "versioning": {"enabled": True}}
        if url.endswith("/iam"):
            return {"bindings": []}
        if "pageToken=second" in url:
            return {"items": [{"name": "edai2/topic22/unexpected"}]}
        return {"items": [{"name": "edai2/topic22/default.tfstate"}], "nextPageToken": "second"}
    with pytest.raises(ValueError, match="backend"):
        budget.verify_backend_bucket_proof("private-bucket", "edai2/topic22", "initialized", requester=requester)
    def cycle(_method, url, _headers, _body):
        if url.endswith("/b/private-bucket"):
            return {"location": "US-CENTRAL1", "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}}, "versioning": {"enabled": True}}
        if url.endswith("/iam"):
            return {"bindings": []}
        return {"items": [], "nextPageToken": "again"}
    with pytest.raises(ValueError, match="backend"):
        budget.verify_backend_bucket_proof("private-bucket", "edai2/topic22", "bootstrap", requester=cycle)


def test_sanitizer_allows_approved_iam_principals_only_in_memory_and_requires_supported_plan_flags() -> None:
    """Catches a global email ban or accepting official Terraform plan keys without a safe executable plan."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_sanitizer_principals")
    third = _load("tests/unit/test_topic22_third_repair.py", "topic22_fourth_sanitizer_principal_fixture")
    plan = third._realistic_plan() | {
        "applyable": True, "complete": True, "errored": False,
        "proposed_unknown": {}, "relevant_attributes": [], "checks": [],
        "planned_values": {"root_module": {"resources": [{"type": "google_service_account_iam_member", "values": {"member": "serviceAccount:approved@private-project.iam.gserviceaccount.com", "service_account_id": "projects/private-project/serviceAccounts/approved@private-project.iam.gserviceaccount.com"}}, {"type": "google_service_account", "values": {"email": "approved@private-project.iam.gserviceaccount.com"}}]}},
        "configuration": {"root_module": {"resources": [{"type": "google_storage_bucket_iam_member", "expressions": {"member": {"constant_value": "serviceAccount:approved@private-project.iam.gserviceaccount.com"}}}]}},
    }
    record = capture.sanitize_terraform_payload(plan, required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget"})
    assert "approved@private-project.iam.gserviceaccount.com" not in json.dumps(record)
    plan["planned_values"]["root_module"]["resources"][0]["values"]["adjacent_token"] = "secret-token"
    with pytest.raises(ValueError, match="secret"):
        capture.sanitize_terraform_payload(plan, required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget"})
    plan = third._realistic_plan() | {"applyable": False, "complete": True, "errored": False}
    with pytest.raises(ValueError, match="schema"):
        capture.sanitize_terraform_payload(plan, required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget"})


def test_sanitizer_allows_exact_provider_service_account_id_path_but_not_adjacent_email() -> None:
    """Catches rejecting the normal provider service_account_id shape or broadening an email exception beyond its exact leaf."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_provider_iam_id")
    third = _load("tests/unit/test_topic22_third_repair.py", "topic22_fourth_provider_iam_fixture")
    plan = third._realistic_plan()
    item = next(change for change in plan["resource_changes"] if change["type"] == "google_service_account_iam_member")
    item["change"]["after"]["service_account_id"] = "projects/secret-project/serviceAccounts/edai2-retrieval@secret-project.iam.gserviceaccount.com"
    record = capture.sanitize_terraform_payload(plan, required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget", "project-services"})
    assert "edai2-retrieval@secret-project.iam.gserviceaccount.com" not in json.dumps(record)
    item["change"]["after"]["unapproved_contact"] = "admin@example.com"
    with pytest.raises(ValueError, match="secret"):
        capture.sanitize_terraform_payload(plan, required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget", "project-services"})


def test_windows_acl_parser_accepts_path_first_ace_and_trusted_system_admin_only() -> None:
    """Catches icacls first-ACE parsing failures or trusting broad principals while accepting Windows system administration."""
    private = _load("src/vina_bim_shop/topic22_private.py", "topic22_fourth_acl_first_ace")
    acl = "C:\\private OWNER\\user:(OI)(CI)(F)\n             NT AUTHORITY\\SYSTEM:(I)(OI)(CI)(F)\n             BUILTIN\\Administrators:(I)(OI)(CI)(F)\nSuccessfully processed 1 files"
    assert private.windows_private_acl_ok(acl, "OWNER\\user") is True
    assert private.windows_private_acl_ok(acl + "\n             Everyone:(RX)", "OWNER\\user") is False


@pytest.mark.parametrize("branch", ["checks", "proposed_unknown", "relevant_attributes"])
def test_sanitizer_scans_every_supported_nonmetadata_top_level_branch(branch: str) -> None:
    """Catches a secret hidden in an accepted Terraform branch the recursive scanner skipped."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_all_branches")
    third = _load("tests/unit/test_topic22_third_repair.py", "topic22_fourth_all_branches_fixture")
    plan = third._realistic_plan() | {branch: {"api_token": "private-token"}}
    with pytest.raises(ValueError, match="secret"):
        capture.sanitize_terraform_payload(plan, required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget"})


def test_sanitizer_requires_exact_project_service_create_set_and_non_destructive_lifecycle() -> None:
    """Catches real Terraform service-enable resources being rejected or a broadened service/deletion plan passing."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_project_services")
    third = _load("tests/unit/test_topic22_third_repair.py", "topic22_fourth_project_services_fixture")
    plan = third._realistic_plan()
    record = capture.sanitize_terraform_payload(plan, required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget", "project-services"})
    assert len(record["invariants"]["project_services"]) == 11
    service = next(change for change in plan["resource_changes"] if change["type"] == "google_project_service")
    service["change"]["after"]["disable_on_destroy"] = True
    with pytest.raises(ValueError, match="project service"):
        capture.sanitize_terraform_payload(plan, required_resources={"gke", "node-pools", "artifact-registry", "gcs", "kms", "iam", "budget", "project-services"})


@pytest.mark.parametrize("field", ["project_number_filter_matches", "notification_channel_matches"])
def test_inventory_budget_requires_exact_project_filter_and_notification_binding(field: str) -> None:
    """Catches an otherwise valid VND amount with an unbound project filter or notification channel."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_budget_binding")
    payload = _typed_readbacks()
    payload["budget"][field] = False
    with pytest.raises(ValueError, match="budget"):
        capture.sanitize_apply_inventory(payload, revision="d" * 40)


def test_topic22_terraform_enables_required_apis_before_all_foundation_modules() -> None:
    """Catches a fresh/reused project reaching provider resources before its required services are enabled."""
    main = (ROOT / "infra" / "terraform" / "edai2" / "main.tf").read_text(encoding="utf-8")
    permissions = json.loads((ROOT / "configs" / "gke" / "required_permissions.json").read_text(encoding="utf-8"))
    expected = {
        "artifactregistry.googleapis.com", "billingbudgets.googleapis.com", "cloudbilling.googleapis.com", "cloudkms.googleapis.com", "cloudresourcemanager.googleapis.com",
        "compute.googleapis.com", "container.googleapis.com", "iam.googleapis.com", "monitoring.googleapis.com", "serviceusage.googleapis.com", "storage.googleapis.com",
    }
    assert 'resource "google_project_service" "topic22"' in main
    assert "disable_on_destroy = false" in main
    for service in expected:
        assert service in main
    assert main.count("google_project_service.topic22") == 6
    assert "serviceusage.services.enable" in permissions["project"]


def test_topic22_permission_manifest_and_terraform_dependencies_cover_real_operations() -> None:
    """Catches a preflight manifest or graph that passes before later Terraform operations race or lack permission."""
    permissions = json.loads((ROOT / "configs" / "gke" / "required_permissions.json").read_text(encoding="utf-8"))
    project = set(permissions["project"])
    billing = set(permissions["billing_account"])
    assert "resourcemanager.projects.setIamPolicy" not in project
    assert {"serviceusage.services.enable", "servicemanagement.services.bind", "container.clusters.create", "artifactregistry.repositories.create", "storage.buckets.create", "storage.buckets.setIamPolicy", "cloudkms.cryptoKeys.setIamPolicy", "iam.serviceAccounts.setIamPolicy", "monitoring.notificationChannels.get", "compute.instanceGroupManagers.list"} <= project
    assert {"billing.accounts.get", "billing.resourceAssociations.list", "billing.budgets.create", "billing.budgets.get", "billing.budgets.list", "billing.budgets.update"} <= billing
    main = (ROOT / "infra" / "terraform" / "edai2" / "main.tf").read_text(encoding="utf-8")
    assert "[google_project_service.topic22, module.kms]" in main
    assert "[google_project_service.topic22, module.gcs]" in main


def test_required_permissions_reconcile_every_topic22_operation_to_its_scope() -> None:
    """Catches adding a REST/Terraform operation without its least-privilege preflight permission."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_permission_reconciliation")
    manifest = json.loads((ROOT / "configs" / "gke" / "required_permissions.json").read_text(encoding="utf-8"))
    assert set(manifest) == {"project", "billing_account"}
    for operation, required in budget.TOPIC22_OPERATION_PERMISSIONS.items():
        scope = required["scope"]
        assert set(required["permissions"]) <= set(manifest[scope]), operation
    assert "resourcemanager.projects.getIamPolicy" in manifest["project"]


def test_private_runtime_executor_binds_credentials_and_approved_plan_without_public_paths(tmp_path: Path) -> None:
    """Catches a runtime action inheriting ambient credentials or accepting an unapproved private binary plan."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_runtime_executor")
    private = tmp_path / "tmp" / "edai2-gcp"
    private.mkdir(parents=True)
    data = private / "terraform-data"; data.mkdir()
    plan = data / "topic22.tfplan"; plan.write_bytes(b"approved")
    contract = data / "topic22-terraform-runtime.json"
    contract.write_text(json.dumps({"environment": {"TF_DATA_DIR": str(data)}, "init": ["terraform", "init"], "plan": ["terraform", "plan"], "apply": ["terraform", "apply"], "backend_bucket_proof_sha256": "a" * 64}) + "\n", encoding="utf-8")
    (data / "topic22-backend-bootstrap-proof.json").write_text(json.dumps({"ok": True, "phase": "bootstrap", "backend_bucket_proof_sha256": "a" * 64, "observed_proof_sha256": "a" * 64, "bucket_sha256": "b" * 64, "prefix_sha256": "c" * 64, "project_number_sha256": "d" * 64, "observed_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "revision": "0" * 40}) + "\n", encoding="utf-8")
    operator = {"backend_bucket_preexists": True, "backend_bucket_proof_sha256": "a" * 64, "resolved_paths": {"tf_data_dir": data, "gcloud_config_dir": private / "gcloud", "application_default_credentials": private / "adc.json"}}
    calls = []
    def runner(command, environment): calls.append((command, environment)); return "private-subprocess-output"
    approval = {"operator_approved": True, "plan_sha256": budget._hash("approved"), "forecast_sha256": "b" * 64, "revision": "c" * 40}
    (data / "topic22-runtime-binding.json").write_text(json.dumps({"forecast_sha256": "b" * 64, "revision": "c" * 40}) + "\n", encoding="utf-8")
    status = budget.execute_private_terraform_action(contract, operator, "apply", approval=approval, runner=runner)
    assert status == {"ok": True, "action": "apply", "plan_sha256": approval["plan_sha256"], "forecast_sha256": "b" * 64, "revision": "c" * 40}
    assert calls[0][1]["CLOUDSDK_CONFIG"] == str(private / "gcloud")
    assert calls[0][1]["GOOGLE_APPLICATION_CREDENTIALS"] == str(private / "adc.json")
    assert "private-subprocess-output" not in json.dumps(status)
    with pytest.raises(ValueError, match="approved"):
        budget.execute_private_terraform_action(contract, operator, "apply", approval={**approval, "plan_sha256": "d" * 64}, runner=runner)


def test_runtime_requires_durable_bootstrap_proof_and_dispatches_initialized_proof_after_apply(tmp_path: Path) -> None:
    """Catches Terraform init/plan accepting a bundle hash without a fresh proof or apply claiming success before initialized proof."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_runtime_backend_records")
    data = tmp_path / "tmp" / "edai2-gcp" / "terraform-data"; data.mkdir(parents=True)
    contract = data / "topic22-terraform-runtime.json"
    contract.write_text(json.dumps({"environment": {"TF_DATA_DIR": str(data)}, "init": ["terraform", "init"], "plan": ["terraform", "plan"], "apply": ["terraform", "apply"], "backend_bucket_proof_sha256": "a" * 64}) + "\n", encoding="utf-8")
    operator = {"backend_bucket_preexists": True, "backend_bucket_proof_sha256": "a" * 64, "resolved_paths": {"tf_data_dir": data, "gcloud_config_dir": data / "gcloud", "application_default_credentials": data / "adc.json"}}
    with pytest.raises(ValueError, match="backend"):
        budget.execute_private_terraform_action(contract, operator, "init", runner=lambda *_args: "")
    (data / "topic22-backend-bootstrap-proof.json").write_text(json.dumps({"ok": True, "phase": "bootstrap", "backend_bucket_proof_sha256": "a" * 64, "observed_proof_sha256": "a" * 64, "bucket_sha256": "b" * 64, "prefix_sha256": "c" * 64, "project_number_sha256": "d" * 64, "observed_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "revision": "0" * 40}) + "\n", encoding="utf-8")
    assert budget.execute_private_terraform_action(contract, operator, "plan", runner=lambda *_args: "")["ok"] is True
    bundle = tmp_path / "operator.json"; bundle.write_text("{}\n", encoding="utf-8")
    args = budget.parse_args(["--operator-inputs", str(bundle), "--private-terraform-action", "apply"])
    (data / "topic22.tfplan").write_bytes(b"approved")
    (data / "topic22-approval.json").write_text(json.dumps({"operator_approved": True, "plan_sha256": budget._hash("approved"), "forecast_sha256": "b" * 64, "revision": "c" * 40}) + "\n", encoding="utf-8")
    (data / "topic22-runtime-binding.json").write_text(json.dumps({"forecast_sha256": "b" * 64, "revision": "c" * 40}) + "\n", encoding="utf-8")
    calls: list[str] = []
    assert budget.dispatch_private_helper(args, tmp_path, operator_loader=lambda *_args: operator, terraform_executor=lambda *_args, **_kwargs: {"ok": True}, backend_verifier=lambda _operator, phase: calls.append(phase) or {"phase": phase, "state_object_present": phase == "initialized", "proof_sha256": "a" * 64, "bucket_sha256": "b" * 64, "prefix_sha256": "c" * 64, "project_number_sha256": "d" * 64}) == 0
    assert calls == ["initialized"]
    assert json.loads((data / "topic22-backend-initialized-proof.json").read_text(encoding="utf-8"))["phase"] == "initialized"


def test_initialized_backend_proof_must_bind_bootstrap_bucket_prefix_project_and_revision(tmp_path: Path) -> None:
    """Catches a valid initialized proof for another accessible backend being accepted after apply."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_cross_phase_backend")
    data = tmp_path / "tmp" / "edai2-gcp" / "terraform-data"; data.mkdir(parents=True)
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    bootstrap = {"ok": True, "phase": "bootstrap", "backend_bucket_proof_sha256": "a" * 64, "observed_proof_sha256": "a" * 64, "bucket_sha256": "b" * 64, "prefix_sha256": "c" * 64, "project_number_sha256": "d" * 64, "observed_at_utc": now, "revision": "e" * 40}
    (data / "topic22-backend-bootstrap-proof.json").write_text(json.dumps(bootstrap) + "\n", encoding="utf-8")
    initialized = {**bootstrap, "phase": "initialized", "observed_proof_sha256": "f" * 64, "observed_at_utc": now}
    assert budget.validate_initialized_backend_record(data, initialized)["phase"] == "initialized"
    with pytest.raises(ValueError, match="backend"):
        budget.validate_initialized_backend_record(data, {**initialized, "prefix_sha256": "0" * 64})


def test_backend_gate_dispatch_binds_bundle_proof_and_rejects_reuse_or_partial_state(tmp_path: Path) -> None:
    """Catches a bootstrap action treating an existing Topic 22 state prefix as safely reusable."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_backend_dispatch")
    operator = {"backend_bucket_preexists": True, "backend_bucket_proof_sha256": "a" * 64}
    proof = {"phase": "bootstrap", "state_object_present": False, "proof_sha256": "a" * 64}
    assert budget.validate_private_backend_gate(operator, proof, phase="bootstrap")["observed_proof_sha256"] == "a" * 64
    with pytest.raises(ValueError, match="backend"):
        budget.validate_private_backend_gate(operator, {**proof, "phase": "initialized", "state_object_present": True}, phase="bootstrap")


def test_private_bootstrap_contract_classifies_fresh_lro_and_reused_empty_project_only() -> None:
    """Catches applying normal project-scoped authorization to project creation/linking or a nonempty reused prefix."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_bootstrap")
    enabled = set(budget.TOPIC22_REQUIRED_SERVICES)
    fresh = {"mode": "fresh", "project_lro": {"done": True, "response": {"projectId": "private-project", "name": "projects/123"}}, "project": {"projectId": "private-project", "name": "projects/123", "state": "ACTIVE"}, "billing_linked": True, "enabled_services": enabled, "backend": {"phase": "bootstrap", "state_object_present": False, "proof_sha256": "a" * 64}}
    assert budget.validate_private_bootstrap_contract(fresh, "private-project", "a" * 64) == {"ok": True, "mode": "fresh", "project_number_sha256": budget._hash("123"), "extra_enabled_service_count": 0, "extra_enabled_services_sha256": budget._hash("")}
    with pytest.raises(ValueError, match="bootstrap"):
        budget.validate_private_bootstrap_contract({**fresh, "mode": "reused", "backend": {**fresh["backend"], "state_object_present": True}}, "private-project", "a" * 64)


def test_private_bootstrap_executor_uses_only_private_token_environment_and_redacts_lro_protocol(tmp_path: Path) -> None:
    """Catches a bootstrap implementation sending project/billing identity via CLI/public output rather than REST memory."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_bootstrap_executor")
    private = tmp_path / "tmp" / "edai2-gcp"; private.mkdir(parents=True)
    operator = {"project_id": "private-project", "billing_account_id": "private-billing", "backend_bucket_preexists": True, "backend_bucket_proof_sha256": "a" * 64, "resolved_paths": {"gcloud_config_dir": private / "config", "application_default_credentials": private / "adc.json", "tf_data_dir": private / "terraform-data"}, "current_spend_vnd": 0, "console_spend_vnd": 0, "forecast_vnd": 0, "trial_credit_vnd": 6_000_000, "trial_expires_at": "2099-01-01T00:00:00Z", "conversion_observed_at": "2026-08-12T00:00:00Z", "spend_observed_at": "2026-08-12T00:00:00Z", "requested_ttl_hours": 1, "bootstrap_authorization": {"operator_approved": True, "forecast_sha256": "b" * 64, "revision": "c" * 40, "current_spend_vnd": 0, "console_spend_vnd": 0, "forecast_vnd": 0, "trial_credit_vnd": 6_000_000, "trial_expires_at": "2099-01-01T00:00:00Z", "conversion_observed_at": "2026-08-12T00:00:00Z", "spend_observed_at": "2026-08-12T00:00:00Z", "requested_ttl_hours": 1, "project_parent": "folders/123"}}
    (private / "terraform-data").mkdir()
    backend = private / "backend.hcl"; backend.write_text('bucket = "private-backend"\nprefix = "edai2/topic22"\n', encoding="utf-8"); operator["resolved_paths"]["terraform_backend_config"] = backend
    authorization = private / "bootstrap-authorization.json"; authorization.write_text(json.dumps(operator["bootstrap_authorization"]) + "\n", encoding="utf-8"); operator["resolved_paths"]["bootstrap_authorization"] = authorization
    calls: list[tuple[str, str]] = []
    def request(method, url, _headers, _body):
        calls.append((method, url))
        if url.endswith(":testIamPermissions"): return {"permissions": _body["permissions"]}
        if "/billingAccounts/" in url: return {"name": "billingAccounts/private-billing", "open": True, "currencyCode": "VND"}
        if "cloudresourcemanager" in url and method == "GET": return {"name": "projects/123", "projectId": "private-project", "state": "ACTIVE"}
        if any(name in url for name in ("container.googleapis.com", "artifactregistry.googleapis.com", "storage.googleapis.com/storage", "cloudkms.googleapis.com", "iam.googleapis.com", "compute.googleapis.com")): return {}
        if "billingInfo" in url: return {"billingEnabled": True, "billingAccountName": "billingAccounts/private-billing"}
        if "batchEnable" in url: return {"done": True, "response": {"enabled": True}}
        if "serviceusage" in url: return {"services": [{"state": "ENABLED", "config": {"name": service}} for service in budget.TOPIC22_REQUIRED_SERVICES]}
        raise AssertionError(url)
    proof = budget.execute_private_bootstrap(operator, token_runner=lambda command, environment: "memory-token" if command == ["gcloud", "auth", "print-access-token"] and environment["CLOUDSDK_CONFIG"] == str(private / "config") else pytest.fail("bad token environment"), requester=request, backend_verifier=lambda _operator, phase: {"phase": phase, "state_object_present": False, "proof_sha256": "a" * 64})
    assert proof["ok"] is True and proof["mode"] == "reused" and proof["project_number_sha256"] == budget._hash("123")
    assert all("memory-token" not in url for _method, url in calls)


def test_private_bootstrap_only_creates_on_crm_404_polls_owned_apis_and_persists_redacted_proof(tmp_path: Path) -> None:
    """Catches bootstrap treating a parse/auth failure as absence, polling Service Usage through CRM, or discarding its proof."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_bootstrap_owned_lro")
    private = tmp_path / "tmp" / "edai2-gcp"; private.mkdir(parents=True)
    data = private / "terraform-data"; data.mkdir()
    operator = {
        "project_id": "private-project", "billing_account_id": "private-billing",
        "backend_bucket_preexists": False, "backend_bucket_proof_sha256": "",
        "resolved_paths": {"gcloud_config_dir": private / "config", "application_default_credentials": private / "adc.json", "tf_data_dir": data},
        "current_spend_vnd": 0, "console_spend_vnd": 0, "forecast_vnd": 0, "trial_credit_vnd": 6_000_000,
        "trial_expires_at": "2099-01-01T00:00:00Z", "conversion_observed_at": "2026-08-12T00:00:00Z", "spend_observed_at": "2026-08-12T00:00:00Z", "requested_ttl_hours": 1,
        "bootstrap_authorization": {"operator_approved": True, "forecast_sha256": "b" * 64, "revision": "c" * 40, "current_spend_vnd": 0, "console_spend_vnd": 0, "forecast_vnd": 0, "trial_credit_vnd": 6_000_000, "trial_expires_at": "2099-01-01T00:00:00Z", "conversion_observed_at": "2026-08-12T00:00:00Z", "spend_observed_at": "2026-08-12T00:00:00Z", "requested_ttl_hours": 1, "project_parent": "folders/123"},
    }
    backend = private / "backend.hcl"; backend.write_text('bucket = "private-backend"\nprefix = "edai2/topic22"\n', encoding="utf-8"); operator["resolved_paths"]["terraform_backend_config"] = backend
    authorization = private / "bootstrap-authorization.json"; authorization.write_text(json.dumps(operator["bootstrap_authorization"]) + "\n", encoding="utf-8"); operator["resolved_paths"]["bootstrap_authorization"] = authorization
    calls: list[tuple[str, str]] = []
    def request(method, url, _headers, _body):
        calls.append((method, url))
        if url.endswith(":testIamPermissions"):
            return {"permissions": _body["permissions"]}
        if "/billingAccounts/" in url and method == "GET":
            return {"name": "billingAccounts/private-billing", "open": True, "currencyCode": "VND"}
        if url.endswith("/projects/private-project") and method == "GET":
            if sum(item == (method, url) for item in calls) == 1:
                raise budget.urllib.error.HTTPError(url, 404, "missing", None, None)
            return {"name": "projects/123", "projectId": "private-project", "state": "ACTIVE"}
        if url.endswith("/v3/projects") and method == "POST":
            return {"name": "operations/new-project"}
        if url.endswith("/v3/operations/new-project"):
            return {"done": True, "response": {"name": "projects/123", "projectId": "private-project"}}
        if "billingInfo" in url:
            return {"billingEnabled": True, "billingAccountName": "billingAccounts/private-billing"}
        if "batchEnable" in url:
            return {"name": "operations/enable-services"}
        if url.endswith("/v1/operations/enable-services"):
            return {"done": True, "response": {}}
        if url == "https://storage.googleapis.com/storage/v1/b?project=123" and method == "POST":
            return {"name": "private-backend"}
        if url.endswith("/b/private-backend/iam"):
            return {"bindings": []}
        if "/b/private-backend/o?" in url:
            return {"items": []}
        if url.endswith("/b/private-backend"):
            return {"projectNumber": "123", "location": "US-CENTRAL1", "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}}, "versioning": {"enabled": True}}
        if any(name in url for name in ("container.googleapis.com", "artifactregistry.googleapis.com", "storage.googleapis.com/storage", "cloudkms.googleapis.com", "iam.googleapis.com", "compute.googleapis.com")):
            return {}
        if "/services?filter=state%3AENABLED" in url:
            return {"services": [{"state": "ENABLED", "config": {"name": item}} for item in budget.TOPIC22_REQUIRED_SERVICES]}
        raise AssertionError(url)
    proof = budget.execute_private_bootstrap(
        operator, token_runner=lambda *_args: "private-token", requester=request,
    )
    assert proof["ok"] is True and proof["mode"] == "fresh" and proof["project_number_sha256"] == budget._hash("123") and proof["extra_enabled_service_count"] == 0
    assert (data / "topic22-bootstrap-proof.json").is_file()
    assert all("private-project" not in (data / "topic22-bootstrap-proof.json").read_text(encoding="utf-8") for _ in [0])
    assert ("GET", "https://cloudresourcemanager.googleapis.com/v3/operations/new-project") in calls
    assert ("GET", "https://serviceusage.googleapis.com/v1/operations/enable-services") in calls
    with pytest.raises(ValueError, match="bootstrap"):
        budget.execute_private_bootstrap(
            operator, token_runner=lambda *_args: "private-token",
            requester=lambda *_args: (_ for _ in ()).throw(ValueError("malformed private response")),
        )


def test_private_bootstrap_allows_extra_enabled_services_and_requires_private_authorization(tmp_path: Path) -> None:
    """Catches impossible exact Service Usage equality or bootstrap mutation without a hash-bound operator approval."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_bootstrap_authorization")
    readback = {
        "mode": "reused", "project": {"projectId": "private-project", "name": "projects/123", "state": "ACTIVE"},
        "billing_linked": True, "enabled_services": set(budget.TOPIC22_REQUIRED_SERVICES) | {"logging.googleapis.com"},
        "backend": {"phase": "bootstrap", "state_object_present": False, "proof_sha256": "a" * 64},
    }
    assert budget.validate_private_bootstrap_contract(readback, "private-project", "a" * 64)["extra_enabled_service_count"] == 1
    with pytest.raises(ValueError, match="bootstrap"):
        budget.validate_private_bootstrap_authorization({}, {"billing_account_open": True, "billing_currency_vnd": True})


def test_authoritative_plan_exposes_only_fixed_private_plan_apply_interfaces() -> None:
    """Catches private binary paths, Python-function operator instructions, direct apply, or pre-record authorization wording."""
    plan = (ROOT / "tmp" / "edai2-plan" / "execution-v1" / "gcp" / "22-gcp-account-budget-terraform-apply.md").read_text(encoding="utf-8")
    completion = plan[plan.index("## Completion Record"):]
    public = plan[:plan.index("## Completion Record")]
    assert "<private-binary-plan>" not in public
    assert "--sanitize-terraform-show" not in public
    assert "tmp/edai2-gcp/terraform-show.json" not in public
    assert "execute_private_terraform_action()" not in public
    assert "exact `apply` command" not in public
    assert "--private-plan-sanitize" in public
    assert "--private-terraform-action apply" in public
    assert "Completion Record" not in public[public.index("### Task 5"):public.index("### Task 6")]
    assert completion.startswith("## Completion Record")
    assert not any(marker in plan for marker in ("â", "Ã", "�"))


def test_plan_inventory_consumes_the_exact_public_sanitized_authorization_artifact() -> None:
    """Catches a state-machine handoff that writes one authorization record but asks inventory to read another path."""
    plan = (ROOT / "tmp" / "edai2-plan" / "execution-v1" / "gcp" / "22-gcp-account-budget-terraform-apply.md").read_text(encoding="utf-8")
    public = plan[:plan.index("## Completion Record")]
    sanitizer = next(line for line in public.splitlines() if "--private-plan-sanitize" in line)
    inventory = next(line for line in public.splitlines() if "--terraform-inventory" in line)
    expected = "evidence/04_2_llm_design/gke/terraform-show.json"
    assert f"--output {expected}" in sanitizer
    assert f"--authorization-evidence {expected}" in inventory


def test_private_wi_helper_dispatches_fixed_private_terraform_output(tmp_path: Path) -> None:
    """Catches a CLI that asks an operator to copy private GSA identities into a readback file."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_wi_dispatch")
    bundle = tmp_path / "operator.json"; bundle.write_text("{}\n", encoding="utf-8")
    private = tmp_path / "tmp" / "edai2-gcp"; private.mkdir(parents=True)
    bindings = {workload: {"ksa": f"serviceAccount:p.svc.id.goog[edai2:{ksa}]", "gsa": f"edai2-{workload}@p.iam.gserviceaccount.com"} for workload, ksa in budget._WORKLOAD_KSAS.items()}
    data = private / "terraform-data"; data.mkdir()
    operator = {"resolved_paths": {"tf_data_dir": data, "gcloud_config_dir": private / "gcloud", "application_default_credentials": private / "adc.json"}}
    args = budget.parse_args(["--operator-inputs", str(bundle), "--write-private-wi-values"])
    seen: list[tuple[list[str], dict[str, str]]] = []
    def output_runner(argv, env):
        seen.append((argv, env))
        return json.dumps(bindings)
    def writer(actual, destination, workspace):
        assert actual == bindings and destination == private / "topic22-workload-identity-values.yaml" and workspace == tmp_path
        destination.write_text("{}\n", encoding="utf-8")
        return destination
    def helm(argv):
        workload = argv[2] if argv[1] == "template" else {"retrieval-agent.yaml": "retrieval", "drift-agent.yaml": "drift", "coordinator-agent.yaml": "coordinator"}.get(next((item for item in argv if item.endswith("-agent.yaml")), ""), "workers")
        return f"apiVersion: v1\nkind: ServiceAccount\nmetadata:\n  name: {budget._WORKLOAD_KSAS[workload]}\n  annotations:\n    iam.gke.io/gcp-service-account: {bindings[workload]['gsa']}\n"
    assert budget.dispatch_private_helper(args, tmp_path, operator_loader=lambda *_args: operator, terraform_output_runner=output_runner, wi_writer=writer, helm_runner=helm) == 0
    assert seen[0][0] == ["terraform", "-chdir=infra/terraform/edai2", "output", "-json", "workload_identity_bindings"]
    assert seen[0][1]["TF_DATA_DIR"] == str(data)


def test_authorization_bindings_require_fixed_private_approval_and_durable_plan_forecast(tmp_path: Path) -> None:
    """Catches inventory relabelling public authorization evidence as an approval record."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_approval_binding")
    revision = "d" * 40
    data = tmp_path / "tmp" / "edai2-gcp" / "terraform-data"; data.mkdir(parents=True)
    plan = data / "topic22.tfplan"; plan.write_bytes(b"approved-private-plan")
    forecast = tmp_path / "evidence" / "04_2_llm_design" / "gke" / "cost_forecast_topic22.json"; forecast.parent.mkdir(parents=True); forecast.write_text('{"forecast": 1}\n', encoding="utf-8")
    authorization = {
        "schema_version": 2, "result": "approved-for-operator-review", "managed_resource_count": 1,
        "data_read_count": 0, "resource_types": ["google_container_cluster"], "invariants": {},
        "principal_fingerprints": [], "plan_sha256": capture.hash_file(plan), "forecast_sha256": capture.hash_file(forecast), "revision": revision,
    }
    public = tmp_path / "authorization.json"; public.write_text(json.dumps(authorization) + "\n", encoding="utf-8")
    approval = {"operator_approved": True, "plan_sha256": authorization["plan_sha256"], "forecast_sha256": authorization["forecast_sha256"], "revision": revision}
    private = data / "topic22-approval.json"; private.write_text(json.dumps(approval) + "\n", encoding="utf-8")
    actual = capture._authorization_bindings(public, revision, operator={"resolved_paths": {"tf_data_dir": data}}, workspace=tmp_path)
    assert actual["approval_record_sha256"] == capture.hash_file(private)
    private.write_text(json.dumps({**approval, "plan_sha256": "0" * 64}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="private Terraform approval"):
        capture._authorization_bindings(public, revision, operator={"resolved_paths": {"tf_data_dir": data}}, workspace=tmp_path)


def test_reused_project_empty_gate_pages_every_category_and_fails_closed() -> None:
    """Catches bootstrap billing/API writes proceeding after an ambiguous or nonempty reused project."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_reuse_gate")
    def empty(_method, url, _payload=None):
        return {"nextPageToken": ""} if "pageToken" not in url else {}
    enabled = {"container.googleapis.com", "artifactregistry.googleapis.com", "storage.googleapis.com", "cloudkms.googleapis.com", "iam.googleapis.com", "billingbudgets.googleapis.com", "compute.googleapis.com"}
    proof = budget.verify_reused_project_empty(empty, "private-project", "123", billing_account="private-billing", enabled_services=enabled, backend_bucket="private-backend")
    assert proof["reused_project_empty"] is True and proof["reused_resource_category_count"] == 14
    calls = 0
    def page_two_resource(_method, url, _payload=None):
        nonlocal calls
        calls += 1
        if "clusters" in url and "pageToken" not in url:
            return {"clusters": [], "nextPageToken": "next"}
        if "clusters" in url:
            return {"clusters": [{"name": "private"}]}
        return {}
    with pytest.raises(ValueError, match="reused project is not empty"):
        budget.verify_reused_project_empty(page_two_resource, "private-project", "123", billing_account="private-billing", enabled_services=enabled, backend_bucket="private-backend")
    def repeated(_method, _url, _payload=None):
        return {"clusters": [], "nextPageToken": "same"}
    with pytest.raises(ValueError, match="bootstrap contract"):
        budget.verify_reused_project_empty(repeated, "private-project", "123", billing_account="private-billing", enabled_services=enabled, backend_bucket="private-backend")


def test_reused_project_empty_gate_covers_all_material_surfaces_and_never_treats_disabled_as_empty() -> None:
    """Catches a reuse gate that silently ignores inherited Compute/IAM/budget resources or disabled APIs."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_reuse_material")
    expected = {
        "gke_clusters", "artifact_repositories", "storage_buckets", "kms_key_rings", "iam_service_accounts", "billing_budgets",
        "compute_instances", "compute_migs", "compute_forwarding_rules", "compute_networks", "compute_subnetworks", "compute_firewalls", "compute_addresses", "project_iam",
    }
    assert set(budget._REUSE_EMPTY_CATEGORIES) == expected
    enabled = {"container.googleapis.com", "artifactregistry.googleapis.com", "storage.googleapis.com", "cloudkms.googleapis.com", "iam.googleapis.com", "billingbudgets.googleapis.com", "compute.googleapis.com"}
    with pytest.raises(ValueError, match="cannot prove reused project empty"):
        budget.verify_reused_project_empty(lambda *_args: {}, "private-project", "123", enabled_services=enabled - {"compute.googleapis.com"})

    def unsafe_iam(_method, url, _payload=None):
        if "serviceAccounts" in url:
            return {"accounts": [{"email": "private"}]}
        return {}
    with pytest.raises(ValueError, match="reused project is not empty"):
        budget.verify_reused_project_empty(unsafe_iam, "private-project", "123", billing_account="private-billing", enabled_services=enabled, backend_bucket="private-backend")


def test_bootstrap_authority_gates_are_scope_specific_and_fail_closed_for_each_mutation() -> None:
    """Catches a bootstrap write/LRO path that has no supported, exact permission gate."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_bootstrap_authorities")
    seen: list[str] = []
    def granted(_method, url, payload=None):
        seen.append(url)
        return {"permissions": payload["permissions"]}
    budget.validate_private_bootstrap_authorities(granted, project_id="private-project", project_number="123", billing_account="private-billing", project_parent="folders/123", mode="fresh")
    assert len(seen) == 3 + len(budget.TOPIC22_REQUIRED_SERVICES)
    assert not any("serviceusage.googleapis.com/v1/projects" in url for url in seen)
    assert sum("servicemanagement.googleapis.com/v1/services/" in url for url in seen) == len(budget.TOPIC22_REQUIRED_SERVICES)
    def missing(_method, _url, payload=None):
        return {"permissions": payload["permissions"][:-1]}
    with pytest.raises(ValueError, match="bootstrap authority"):
        budget.validate_private_bootstrap_authorities(missing, project_id="private-project", project_number="123", billing_account="private-billing", project_parent="folders/123", mode="reused")


def test_fresh_bootstrap_creates_only_private_backend_then_requires_full_readback(tmp_path: Path) -> None:
    """Catches a fresh selected project being unable to obtain its required out-of-state backend bucket."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_fresh_backend")
    data = tmp_path / "tmp" / "edai2-gcp" / "terraform-data"; data.mkdir(parents=True)
    created: list[tuple[str, str, dict[str, object] | None]] = []
    def call(method, url, payload=None):
        created.append((method, url, payload))
        if method == "POST": return {"name": "private-backend"}
        if url.endswith("/iam"): return {"bindings": []}
        if "/o?" in url: return {"items": []}
        return {"projectNumber": "123", "location": "US-CENTRAL1", "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}}, "versioning": {"enabled": True}}
    proof = budget.create_private_backend_bucket(call, bucket="private-backend", prefix="edai2/topic22", project_number="123", data_dir=data)
    assert proof["state_object_present"] is False and created[0] == ("POST", "https://storage.googleapis.com/storage/v1/b?project=123", {"name": "private-backend", "location": "US-CENTRAL1", "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}}, "versioning": {"enabled": True}})

    def bad_readback(method, url, payload=None):
        if method == "POST": return {"name": "private-backend"}
        return {"projectNumber": "999", "location": "US-CENTRAL1", "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}}, "versioning": {"enabled": True}, "bindings": []}
    with pytest.raises(ValueError, match="backend"):
        budget.create_private_backend_bucket(bad_readback, bucket="private-backend", prefix="edai2/topic22", project_number="123", data_dir=data)
    partial = json.loads((data / "topic22-bootstrap-partial.json").read_text(encoding="utf-8"))
    assert partial == {"ok": False, "phase": "fresh_backend_create", "project_create_requested": False, "project_created": False, "billing_linked": False, "apis_enabled": False, "backend_bucket_created": True, "rollback_required": True, "owned_rollback_actions": ["backend_bucket_created"], "do_not_delete_existing": True, "cost_estimate_usd_upper_bound": 0, "resume_condition": "operator_review_required", "bucket_sha256": budget._hash("private-backend")}


def test_reuse_gate_allows_only_the_exact_prevalidated_backend_bucket() -> None:
    """Catches the required backend bucket being rejected or a name-only exception allowing another bucket."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_reuse_backend")
    enabled = {"container.googleapis.com", "artifactregistry.googleapis.com", "storage.googleapis.com", "cloudkms.googleapis.com", "iam.googleapis.com", "billingbudgets.googleapis.com", "compute.googleapis.com"}
    def only_backend(_method, url, _payload=None):
        if "storage/v1/b?" in url: return {"items": [{"name": "private-backend"}]}
        return {}
    assert budget.verify_reused_project_empty(only_backend, "private-project", "123", billing_account="private-billing", enabled_services=enabled, backend_bucket="private-backend")["reused_project_empty"] is True
    def extra_bucket(_method, url, _payload=None):
        if "storage/v1/b?" in url: return {"items": [{"name": "private-backend"}, {"name": "other"}]}
        return {}
    with pytest.raises(ValueError, match="reused project is not empty"):
        budget.verify_reused_project_empty(extra_bucket, "private-project", "123", billing_account="private-billing", enabled_services=enabled, backend_bucket="private-backend")


def test_fresh_backend_runtime_binding_requires_durable_bootstrap_proof(tmp_path: Path) -> None:
    """Catches a fresh bucket proof being discarded before private init/plan contract construction."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_fresh_runtime_binding")
    data = tmp_path / "tmp" / "edai2-gcp" / "terraform-data"; data.mkdir(parents=True)
    with pytest.raises(ValueError, match="backend proof"):
        budget._bootstrap_backend_binding({"backend_bucket_preexists": False, "backend_bucket_proof_sha256": ""}, data)
    (data / "topic22-bootstrap-proof.json").write_text(json.dumps({"ok": True, "phase": "bootstrap", "backend_bucket_proof_sha256": "a" * 64}) + "\n", encoding="utf-8")
    assert budget._bootstrap_backend_binding({"backend_bucket_preexists": False, "backend_bucket_proof_sha256": ""}, data) == (True, "a" * 64)


def test_personal_trial_no_parent_mode_omits_v3_parent_and_never_tests_a_fake_scope() -> None:
    """Catches personal free-trial bootstrap fabricating an organization/folder permission check."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_no_parent")
    assert budget.private_project_create_payload("private-project", "none") == {"projectId": "private-project"}
    seen: list[str] = []
    budget.validate_private_bootstrap_authorities(lambda _method, url, payload=None: seen.append(url) or {"permissions": payload["permissions"]}, project_id="private-project", project_number="123", billing_account="private-billing", project_parent="none", mode="fresh")
    assert not any("folders/" in url or "organizations/" in url for url in seen)


def test_api_enable_partial_handoff_is_idempotent_and_redacted(tmp_path: Path) -> None:
    """Catches Service Usage LRO failure after fresh billing masking the root error with FileExistsError."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_api_enable_partial")
    data = tmp_path / "tmp" / "edai2-gcp" / "terraform-data"; data.mkdir(parents=True)
    completed = {"project_create_requested": True, "project_created": True, "billing_linked": True, "apis_enabled": False, "backend_bucket_created": False}
    budget.ensure_partial_handoff(data, phase="api_enable", completed=completed)
    budget.ensure_partial_handoff(data, phase="api_enable", completed=completed)
    handoff = json.loads((data / "topic22-bootstrap-partial.json").read_text(encoding="utf-8"))
    assert handoff["phase"] == "api_enable" and handoff["project_create_requested"] is True and handoff["billing_linked"] is True
    assert "private" not in json.dumps(handoff)


def test_private_wi_dispatch_renders_and_lints_all_four_mappings_without_persisting_temps(tmp_path: Path) -> None:
    """Catches a private WI values file with no real chart consumer or mismatched service account."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_wi_consumers")
    private = tmp_path / "tmp" / "edai2-gcp"; private.mkdir(parents=True)
    bindings = {workload: {"ksa": f"serviceAccount:p.svc.id.goog[edai2:{ksa}]", "gsa": f"edai2-{workload}@p.iam.gserviceaccount.com"} for workload, ksa in budget._WORKLOAD_KSAS.items()}
    combined = private / "topic22-workload-identity-values.yaml"; combined.write_text("{}\n", encoding="utf-8")
    calls: list[list[str]] = []
    def helm(argv):
        calls.append(argv)
        workload = argv[2] if argv[1] == "template" else {"retrieval-agent.yaml": "retrieval", "drift-agent.yaml": "drift", "coordinator-agent.yaml": "coordinator"}.get(next((item for item in argv if item.endswith("-agent.yaml")), ""), "workers")
        value = bindings[workload]
        return f"kind: ServiceAccount\nmetadata:\n  name: {budget._WORKLOAD_KSAS[workload]}\n  annotations:\n    iam.gke.io/gcp-service-account: {value['gsa']}\n"
    budget.validate_private_wi_helm_consumers(bindings, combined, tmp_path, runner=helm)
    assert len(calls) == 8 and {call[1] for call in calls} == {"lint", "template"}
    assert not list(private.glob("tmp*.yaml"))
    wrong = {**bindings, "workers": {**bindings["workers"], "gsa": "wrong@p.iam.gserviceaccount.com"}}
    with pytest.raises(ValueError, match="mapping"):
        budget.validate_private_wi_helm_consumers(wrong, combined, tmp_path, runner=helm)


def test_private_plan_sanitizer_uses_bundle_contract_without_private_plan_argv(tmp_path: Path) -> None:
    """Catches the fixed public evidence command accepting a private plan path or losing private credential binding."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_private_plan_sanitize")
    private = tmp_path / "tmp" / "edai2-gcp"; private.mkdir(parents=True)
    data = private / "terraform-data"; data.mkdir(); (data / "topic22.tfplan").write_bytes(b"private-plan")
    forecast = tmp_path / "evidence" / "04_2_llm_design" / "gke" / "cost_forecast_topic22.json"; forecast.parent.mkdir(parents=True); forecast.write_text("{}\n", encoding="utf-8")
    output = tmp_path / "evidence" / "04_2_llm_design" / "gke" / "terraform-show.json"
    operator = {"resolved_paths": {"tf_data_dir": data, "gcloud_config_dir": private / "gcloud", "application_default_credentials": private / "adc.json"}}
    seen: list[tuple[list[str], dict[str, str]]] = []
    third = _load("tests/unit/test_topic22_third_repair.py", "topic22_fourth_private_plan_fixture")
    result = capture.sanitize_private_terraform_plan(
        private / "operator-inputs.json", output, workspace=tmp_path,
        operator_loader=lambda *_args: operator,
        runner=lambda command, environment: seen.append((command, environment)) or json.dumps(third._realistic_plan()),
        revision="d" * 40,
    )
    assert result["result"] == "approved-for-operator-review"
    assert seen[0][0][:3] == ["terraform", "show", "-json"]
    assert str(data / "topic22.tfplan") not in json.dumps(result)
    assert seen[0][1]["CLOUDSDK_CONFIG"] == str(private / "gcloud")


def test_inventory_uses_live_compute_mig_target_not_nodepool_initial_count() -> None:
    """Catches passing an initial node count while live managed instance groups have capacity."""
    capture = _load("scripts/qa/capture_edai2_evidence.py", "topic22_fourth_live_mig")
    source = (ROOT / "scripts" / "qa" / "capture_edai2_evidence.py").read_text(encoding="utf-8")
    assert "paged_aggregated_instance_group_managers" in source
    assert '"current": target_size' in source
    calls = []
    def rest(_method, url, _body):
        calls.append(url)
        return {"items": {"zones/us-central1-a": {"instanceGroupManagers": [{"selfLink": "https://compute.example/pool", "targetSize": 1}]}}}
    managers = capture.paged_aggregated_instance_group_managers(rest, "https://compute.example/instanceGroupManagers")
    assert managers[0]["targetSize"] == 1


def test_recovery_attestation_requires_two_distinct_hash_bound_custodians_with_provenance() -> None:
    """Catches a mutable count claim standing in for two independent recovery approvals."""
    budget = _load("scripts/gke/check_budget.py", "topic22_fourth_recovery")
    sink = "gs://private-recovery"
    attestation = {"approved": True, "encrypted": True, "outside_workspace": True, "sink_uri_sha256": budget._hash(sink), "attestations": [{"custodian_sha256": "a" * 64, "approved_at_utc": "2026-08-12T00:00:00Z", "provenance_sha256": "b" * 64}, {"custodian_sha256": "c" * 64, "approved_at_utc": "2026-08-12T00:01:00Z", "provenance_sha256": "d" * 64}]}
    assert budget.recovery_attestation_ok(attestation, sink) is True
    assert budget.recovery_attestation_ok({**attestation, "attestations": [*attestation["attestations"], attestation["attestations"][0]]}, sink) is False
