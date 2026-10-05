"""Windows binary resolution for the Topic 22 inventory adapter.

Regression: GcloudRestTopic22InventoryAdapter._run shelled bare binary names
(``gcloud``) under an explicit environment. On Windows an extensionless
``.CMD`` name is unresolvable that way (FileNotFoundError) even with a
correct PATH, so --terraform-inventory could never run here. Resolution must
mirror check_budget._run_gcloud_private via shutil.which.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "capture_edai2_evidence", ROOT / "scripts" / "qa" / "capture_edai2_evidence.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_executable_returns_absolute_path() -> None:
    """A known binary resolves to an absolute existing path (RED first)."""
    module = _load()
    resolved = module._resolve_executable("python", dict(os.environ))
    assert resolved != "python"
    assert Path(resolved).is_file()


def test_resolve_executable_falls_back_to_bare_name() -> None:
    """Without PATH help the bare name is preserved (old behavior, no crash)."""
    module = _load()
    assert module._resolve_executable("gcloud", {"PATH": ""}) == "gcloud"


def test_run_uses_resolved_binary() -> None:
    """_run executes the resolved binary for a real command."""
    module = _load()
    out = module.GcloudRestTopic22InventoryAdapter._run(
        ["python", "--version"], dict(os.environ)
    )
    assert "Python" in out


def test_which_mirror_matches_check_budget_behavior() -> None:
    """Resolution matches check_budget._run_gcloud_private semantics."""
    module = _load()
    environment = dict(os.environ)
    expected = shutil.which("python", path=environment.get("PATH")) or "python"
    assert module._resolve_executable("python", environment) == expected


def _load_check_budget():
    spec = importlib.util.spec_from_file_location(
        "check_budget_winres", ROOT / "scripts" / "gke" / "check_budget.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runners_use_resolved_absolute_binary() -> None:
    """Both inventory and kube runners must exec a resolved path, never a bare name.

    Regression: on Windows a bare ``gcloud`` under an explicit environment raises
    FileNotFoundError even with a correct PATH, so every private runner must
    resolve through shutil.which first (mirroring _run_gcloud_private).
    """
    import subprocess

    capture_module = _load()
    budget_module = _load_check_budget()
    seen: list[list[str]] = []
    real_run = subprocess.run

    def fake_run(argv: list[str], **kwargs):
        seen.append(list(argv))
        raise RuntimeError("captured")

    subprocess.run = fake_run  # type: ignore[assignment]
    try:
        for runner in (
            capture_module.GcloudRestTopic22InventoryAdapter._run,
            budget_module._run_get_credentials_redacted,
        ):
            try:
                runner(["gcloud", "version"], dict(os.environ))
            except RuntimeError:
                pass
    finally:
        subprocess.run = real_run  # type: ignore[assignment]
    assert len(seen) == 2
    expected = shutil.which("gcloud", path=dict(os.environ).get("PATH")) or "gcloud"
    for argv in seen:
        assert argv[0] == expected, "runner must exec the shutil.which-resolved binary"
        assert argv[1:] == ["version"]


def _fake_operator(tmp_path: Path) -> dict[str, object]:
    backend = tmp_path / "backend.hcl"
    backend.write_text('bucket = "topic22-test-bucket"\nprefix = "topic22/state"\n', encoding="utf-8")
    return {
        "project_id": "topic22-test-project",
        "billing_account_id": "TEST-BILLING",
        "budget_notification_target": "projects/topic22-test-project/notificationChannels/1",
        "trial_credit_vnd": 7500000,
        "resolved_paths": {
            "tf_data_dir": tmp_path,
            "gcloud_config_dir": tmp_path,
            "application_default_credentials": tmp_path / "adc.json",
            "terraform_backend_config": backend,
        },
    }


def _fake_runner_factory(calls: list[tuple[str, str]]):
    def runner(command: list[str], environment: dict[str, str]) -> str:
        import json

        argv = " ".join(command)
        if command[0].endswith("terraform") or command[0] == "terraform":
            calls.append(("terraform", argv))
            return json.dumps({
                "bucket_name": {"value": "topic22-test-bucket"},
                "kms_key_id": {"value": "projects/topic22-test-project/locations/us-central1/keyRings/edai2/cryptoKeys/edai2"},
                "workload_identity_bindings": {"value": {
                    workload: {
                        "ksa": f"member-{workload}",
                        "gsa": f"edai2-{workload}@topic22-test-project.iam.gserviceaccount.com",
                        "prefixes": ["model-cache/"],
                    }
                    for workload in ("retrieval", "drift", "coordinator", "workers")
                }},
            })
        calls.append(("gcloud", argv))
        return "fake-token"
    return runner


def test_kms_policy_uses_get_with_policy_version(tmp_path: Path) -> None:
    """KMS getIamPolicy must be GET with requestedPolicyVersion (POST 404s).

    Regression: the adapter POSTed an empty body to the KMS custom method and
    Google answered 404, while gcloud issues GET with
    ``?alt=json&options.requestedPolicyVersion=3`` and succeeds.
    """
    import json

    module = _load()
    calls: list[tuple[str, str]] = []

    def requester(method: str, url: str, headers: dict[str, str], payload: dict[str, object] | None):
        calls.append((method, url))
        if "cryptoKeys" in url and url.rsplit(":", 1)[-1].split("?")[0] == "getIamPolicy":
            return {"bindings": [{"role": "roles/cloudkms.cryptoKeyEncrypterDecrypter", "members": ["serviceAccount:gcs-agent@example.iam.gserviceaccount.com"]}]}
        if "serviceAccounts" in url and ":getIamPolicy" in url:
            gsa = url.split("serviceAccounts/", 1)[1].split(":")[0]
            workload = gsa.split("@")[0].removeprefix("edai2-")
            return {"bindings": [{"role": "roles/iam.workloadIdentityUser", "members": ["member-" + workload]}]}
        if url.endswith("/serviceAccount"):
            return {"emailAddress": "gcs-agent@example.iam.gserviceaccount.com"}
        if "/budgets" in url:
            return {"budgets": [{
                "amount": {"specifiedAmount": {"currencyCode": "VND", "units": "6000000"}},
                "budgetFilter": {"projects": ["projects/123"]},
                "allUpdatesRule": {"monitoringNotificationChannels": ["projects/topic22-test-project/notificationChannels/1"]},
                "thresholdRules": [{"thresholdPercent": 0.5}, {"thresholdPercent": 0.75}, {"thresholdPercent": 0.9}, {"thresholdPercent": 1.0}],
            }]}
        if "/o?" in url:
            return {"items": [{"name": "topic22/state/default.tfstate"}]}
        if "forwardingRules" in url:
            return {"items": {}}
        if "instanceGroupManagers" in url:
            return {"items": {"zones/us-central1-a": {"instanceGroupManagers": [
                {"selfLink": "https://example/platform", "targetSize": 0},
                {"selfLink": "https://example/spot", "targetSize": 0},
            ]}}}
        if url.endswith("/iam"):
            bindings = []
            for prefix in ("model-cache/", "agent-substrate/", "langfuse-events/", "airflow-logs/", "backups/"):
                bindings.append({
                    "role": "roles/storage.objectUser",
                    "condition": {"expression": "resource.name.startsWith('projects/_/buckets/x/objects/" + prefix + "')"},
                    "members": ["serviceAccount:gsa@example.iam.gserviceaccount.com"],
                })
            return {"bindings": bindings}
        if "/repositories" in url:
            repos = []
            for name in ("a", "b", "c", "d", "e", "f"):
                repos.append({"name": "projects/x/locations/us-central1/repositories/" + name, "format": "DOCKER"})
            return {"repositories": repos}
        if url.endswith("/nodePools"):
            pools = []
            for name, machine, spot, maximum in (("platform", "e2-highmem-4", False, 1), ("spot", "e2-standard-8", True, 2)):
                pools.append({
                    "name": "projects/x/zones/us-central1-a/clusters/edai2/nodePools/" + name,
                    "autoscaling": {"minNodeCount": 0, "maxNodeCount": maximum},
                    "config": {"machineType": machine, "spot": spot},
                    "instanceGroupUrls": ["https://example/" + name],
                })
            return {"nodePools": pools}
        if url.endswith("/clusters/edai2"):
            return {"name": "edai2", "location": "us-central1-a",
                    "workloadIdentityConfig": {"workloadPool": "x.svc.id.goog"}}
        if "/buckets/" in url:
            return {"location": "US-CENTRAL1", "encryption": {"defaultKmsKeyName": "k"},
                    "lifecycle": {"rule": [
                        {"action": {"type": "Delete"}, "condition": {"age": 7, "matchesPrefix": ["agent-substrate/", "langfuse-events/"]}},
                        {"action": {"type": "Delete"}, "condition": {"age": 90, "matchesPrefix": ["airflow-logs/", "backups/", "model-cache/"]}},
                    ]},
                    "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}}}
        if "/projects/" in url:
            return {"name": "projects/123", "projectId": "topic22-test-project", "lifecycleState": "ACTIVE"}
        return {}

    adapter = module.GcloudRestTopic22InventoryAdapter(
        operator_loader=lambda inputs, workspace: _fake_operator(tmp_path),
        runner=_fake_runner_factory([]),
        token_supplier=lambda: "fake-token",
        requester=requester,
    )
    raw = adapter.read(tmp_path / "operator-inputs.json")
    assert isinstance(raw, dict)
    kms_calls = [(method, url) for method, url in calls if "cryptoKeys" in url and url.rsplit(":", 1)[-1].split("?")[0] == "getIamPolicy"]
    assert kms_calls, "expected a KMS getIamPolicy call"
    method, url = kms_calls[0]
    assert method == "GET", f"KMS getIamPolicy must be GET, got {method}"
    assert "requestedPolicyVersion" in url, "KMS getIamPolicy must request a policy version"
