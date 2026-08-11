from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

import pytest
import yaml

from vina_bim_shop.kafka.bootstrap import bootstrap_topics


ROOT = Path(__file__).resolve().parents[3]
_CLI_SPEC = importlib.util.spec_from_file_location("topic19_bootstrap_cli", ROOT / "scripts/kafka/bootstrap_topics.py")
assert _CLI_SPEC is not None and _CLI_SPEC.loader is not None
_CLI_MODULE = importlib.util.module_from_spec(_CLI_SPEC)
_CLI_SPEC.loader.exec_module(_CLI_MODULE)
_gke_runner = _CLI_MODULE._gke_runner
WORKLOADS = ROOT / "infra" / "helm" / "edai2" / "workloads"
WORKLOAD_NAMES = {
    "retrieval.yaml",
    "drift.yaml",
    "coordinator.yaml",
    "rag-index.yaml",
    "feast-offline-writer.yaml",
    "feast-online-writer.yaml",
}


def _load(name: str) -> dict[str, object]:
    return yaml.safe_load((WORKLOADS / name).read_text(encoding="utf-8"))


def test_six_workload_values_exist_with_only_render_time_sentinel_tags() -> None:
    assert {path.name for path in WORKLOADS.glob("*.yaml")} == WORKLOAD_NAMES
    for name in WORKLOAD_NAMES:
        value = _load(name)
        assert value["image"]["tag"] == ""
        assert "testsha" not in (WORKLOADS / name).read_text(encoding="utf-8")


def test_api_workloads_have_bounded_prometheus_keda_and_health_probes() -> None:
    for name in ("retrieval.yaml", "drift.yaml", "coordinator.yaml"):
        value = _load(name)
        autoscaling = value["autoscaling"]
        assert autoscaling["enabled"] is True
        assert autoscaling["minReplicaCount"] == 1
        assert autoscaling["maxReplicaCount"] == 2
        assert autoscaling["pollingInterval"] == 15
        assert autoscaling["cooldownPeriod"] == 60
        assert autoscaling["triggers"][0]["type"] == "prometheus"
        assert autoscaling["triggers"][0]["metadata"]["threshold"] == "1"
        assert value["readinessProbe"]["httpGet"]["path"] == "/readyz"
        assert value["livenessProbe"]["httpGet"]["path"] == "/healthz"


def test_single_activation_owner_is_drift() -> None:
    matches = []
    for name in WORKLOAD_NAMES:
        text = (WORKLOADS / name).read_text(encoding="utf-8")
        if "scripts/feast/load_section03.py" in text:
            matches.append(name)
    assert matches == ["drift.yaml"]


def test_index_and_experiment_contracts_are_static_and_separate() -> None:
    rag_index = _load("rag-index.yaml")
    coordinator = _load("coordinator.yaml")
    assert rag_index["index"]["ciBootstrapTemplate"] == "ci-bootstrap-${GIT_COMMIT}"
    assert rag_index["index"]["canonicalOwner"] == "airflow-rag-pipeline"
    assert rag_index["index"]["canonicalPromotionForbidden"] is True

    factorial = coordinator["inferenceFactorial"]
    assert factorial["order"] == [
        "cache_off+load_aware",
        "cache_on+load_aware",
        "cache_off+prefix_aware",
        "cache_on+prefix_aware",
    ]
    assert factorial["constants"]["globalConcurrency"] == 1
    assert factorial["constants"]["contextTokens"] == 4096
    assert factorial["inactiveModelReplicas"] == 0
    assert coordinator["experiments"]["agent"]["salt"] == "agent_exp_v1"
    assert coordinator["experiments"]["model"]["salt"] == "model_exp_v1"
    assert coordinator["experiments"]["agent"]["sessionsPerArm"] == 60
    assert coordinator["experiments"]["model"]["sessionsPerArm"] == 60


def test_streaming_schema_and_fixtures_are_closed_and_fixed() -> None:
    schema = json.loads(
        (ROOT / "infra/kafka/schemas/customer_feature_updates-value.schema.json").read_text(encoding="utf-8")
    )
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert schema["required"] == [
        "event_id", "manifest_sha256", "id", "event_timestamp", "feature_name", "feature_value", "source_version"
    ]

    warmups = json.loads((ROOT / "configs/llm/warmup_prompts.json").read_text(encoding="utf-8"))
    benchmark = json.loads((ROOT / "configs/llm/benchmark_requests.json").read_text(encoding="utf-8"))
    assert len(warmups) == 3
    assert len({prompt.split(":", 1)[0] for prompt in warmups}) == 1
    assert benchmark["request_count"] == 40
    assert benchmark["order"] == [request["id"] for request in benchmark["requests"]]


def test_streaming_topics_migration_and_bootstrap_modes_are_declared() -> None:
    topics = yaml.safe_load((ROOT / "infra/kafka/topics.yaml").read_text(encoding="utf-8"))
    assert topics["feature_update_topics"] == {
        "customer_feature_updates.v1": {
            "partitions": 1,
            "replication_factor": 1,
            "cleanup_policy": "delete",
            "retention_ms": 604800000,
        },
        "customer_feature_updates.v1.dlq": {
            "partitions": 1,
            "replication_factor": 1,
            "cleanup_policy": "delete",
            "retention_ms": 604800000,
        },
    }
    migration = (ROOT / "infra/postgres/edai2/004_streaming_features.sql").read_text(encoding="utf-8")
    assert all(name in migration for name in ("edai2_feature_outbox", "edai2_feature_dedup", "edai2_consumer_checkpoints"))
    assert "PRIMARY KEY (consumer_group, event_id)" in migration
    bootstrap = (ROOT / "scripts/kafka/bootstrap_topics.py").read_text(encoding="utf-8")
    assert "gke-rpk" in bootstrap
    assert "--kubeconfig" in bootstrap
    assert "--context" in bootstrap


def test_ci_layering_and_static_cli_contracts_are_present() -> None:
    expected_calls = {
        "Jenkinsfile.rag-index": "infra/helm/edai2/workloads/rag-index.yaml",
        "Jenkinsfile.retrieval-agent": "infra/helm/edai2/workloads/retrieval.yaml",
        "Jenkinsfile.drift-agent": "infra/helm/edai2/workloads/drift.yaml",
        "Jenkinsfile.coordinator": "infra/helm/edai2/workloads/coordinator.yaml",
        "Jenkinsfile.feast-offline-writer": "infra/helm/edai2/workloads/feast-offline-writer.yaml",
        "Jenkinsfile.feast-online-writer": "infra/helm/edai2/workloads/feast-online-writer.yaml",
    }
    for name, workload_values in expected_calls.items():
        assert workload_values in (ROOT / "ci/jenkins" / name).read_text(encoding="utf-8")

    benchmark = ROOT / "scripts/llm/benchmark_inference.py"
    smoke = ROOT / "scripts/llm/smoke_release.py"
    assert benchmark.is_file()
    assert smoke.is_file()
    assert "--dry-run" in benchmark.read_text(encoding="utf-8")
    assert "--dry-run" in smoke.read_text(encoding="utf-8")


class FakeGkeRunner:
    def __init__(self, states: dict[str, list[dict[str, object]]]) -> None:
        self.states = states
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str]) -> dict[str, object] | None:
        self.commands.append(command)
        topic = command[-3] if command[-2:] == ["-o", "json"] else command[-1]
        if "describe" in command:
            return self.states[topic].pop(0)
        if "create" in command:
            return None
        raise AssertionError(command)


def _topic_state(*, exists: bool, retention_ms: int = 604800000) -> dict[str, object]:
    return {
        "exists": exists,
        "partitions": 1,
        "replication_factor": 1,
        "configs": {"cleanup.policy": "delete", "retention.ms": str(retention_ms)},
    }


def _fake_kubeconfig() -> TemporaryDirectory[str]:
    directory = TemporaryDirectory()
    Path(directory.name, "kubeconfig.yaml").write_text(
        "apiVersion: v1\ncontexts:\n  - name: gke_edai2\n    context: {}\n", encoding="utf-8"
    )
    return directory


def _feature_topics_file(directory: str) -> Path:
    path = Path(directory, "topics.yaml")
    path.write_text(
        "source_topics: {}\nderived_placeholder_topics: {}\nfeature_update_topics:\n"
        "  customer_feature_updates.v1: {partitions: 1, replication_factor: 1, cleanup_policy: delete, retention_ms: 604800000}\n"
        "  customer_feature_updates.v1.dlq: {partitions: 1, replication_factor: 1, cleanup_policy: delete, retention_ms: 604800000}\n",
        encoding="utf-8",
    )
    return path


def test_gke_bootstrap_creates_absent_topics_then_requires_exact_readback() -> None:
    with _fake_kubeconfig() as directory:
        kubeconfig = Path(directory, "kubeconfig.yaml")
        topics_file = _feature_topics_file(directory)
        runner = FakeGkeRunner({
            "customer_feature_updates.v1": [{"exists": False}, _topic_state(exists=True)],
            "customer_feature_updates.v1.dlq": [{"exists": False}, _topic_state(exists=True)],
        })
        bootstrap_topics(runner=runner, topics_file=topics_file, execution="gke-rpk", namespace="edai2", statefulset="edai2-redpanda", kubeconfig=kubeconfig, context="gke_edai2")
    creates = [command for command in runner.commands if "create" in command]
    assert len(creates) == 2
    assert all(command[:5] == ["kubectl", "--kubeconfig", str(kubeconfig), "--context", "gke_edai2"] for command in runner.commands)
    assert all(command[-2:] == ["-o", "json"] for command in runner.commands if "describe" in command)


def test_gke_bootstrap_skips_existing_exact_topics_and_rejects_mismatches_before_create() -> None:
    with _fake_kubeconfig() as directory:
        kubeconfig = Path(directory, "kubeconfig.yaml")
        topics_file = _feature_topics_file(directory)
        exact = FakeGkeRunner({
            "customer_feature_updates.v1": [_topic_state(exists=True)],
            "customer_feature_updates.v1.dlq": [_topic_state(exists=True)],
        })
        bootstrap_topics(runner=exact, topics_file=topics_file, execution="gke-rpk", namespace="edai2", statefulset="edai2-redpanda", kubeconfig=kubeconfig, context="gke_edai2")
        assert not any("create" in command for command in exact.commands)

        mismatch = FakeGkeRunner({"customer_feature_updates.v1": [_topic_state(exists=True, retention_ms=1)]})
        with pytest.raises(ValueError, match="mismatch"):
            bootstrap_topics(runner=mismatch, topics_file=topics_file, execution="gke-rpk", namespace="edai2", statefulset="edai2-redpanda", kubeconfig=kubeconfig, context="gke_edai2")
        assert not any("create" in command for command in mismatch.commands)


def test_gke_bootstrap_rejects_created_readback_mismatch_and_invalid_kubeconfig_before_runner() -> None:
    with _fake_kubeconfig() as directory:
        kubeconfig = Path(directory, "kubeconfig.yaml")
        topics_file = _feature_topics_file(directory)
        runner = FakeGkeRunner({"customer_feature_updates.v1": [{"exists": False}, _topic_state(exists=True, retention_ms=1)]})
        with pytest.raises(ValueError, match="mismatch"):
            bootstrap_topics(runner=runner, topics_file=topics_file, execution="gke-rpk", namespace="edai2", statefulset="edai2-redpanda", kubeconfig=kubeconfig, context="gke_edai2")
        assert sum("create" in command for command in runner.commands) == 1

    commands: list[list[str]] = []
    with pytest.raises(ValueError, match="absolute and readable"):
        bootstrap_topics(runner=commands.append, execution="gke-rpk", namespace="edai2", statefulset="edai2-redpanda", kubeconfig="relative.yaml", context="gke_edai2")
    assert commands == []

    with _fake_kubeconfig() as directory:
        with pytest.raises(ValueError, match="context is absent"):
            bootstrap_topics(
                runner=commands.append,
                execution="gke-rpk",
                namespace="edai2",
                statefulset="edai2-redpanda",
                kubeconfig=Path(directory, "kubeconfig.yaml"),
                context="wrong-context",
            )
    assert commands == []


def test_gke_cli_runner_normalizes_only_supported_machine_readback_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    command = ["kubectl", "--", "rpk", "topic", "describe", "customer_feature_updates.v1", "-o", "json"]
    completed = subprocess.CompletedProcess(
        command,
        0,
        stdout=json.dumps({
            "partitions": [{"id": 0, "replicas": [1]}],
            "configs": [
                {"key": "cleanup.policy", "value": "delete"},
                {"key": "retention.ms", "value": "604800000"},
            ],
        }),
        stderr="",
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed)
    assert _gke_runner(command) == {
        "exists": True,
        "partitions": 1,
        "replication_factor": 1,
        "configs": {"cleanup.policy": "delete", "retention.ms": "604800000"},
    }


@pytest.mark.parametrize(
    ("completed", "error"),
    [
        (subprocess.CompletedProcess(["describe"], 1, stdout="", stderr="TOPIC_NOT_FOUND"), "exists"),
        (subprocess.CompletedProcess(["describe"], 1, stdout="", stderr="permission denied"), "describe failed"),
        (subprocess.CompletedProcess(["describe"], 0, stdout="not-json", stderr=""), "valid JSON"),
    ],
)
def test_gke_cli_runner_fails_closed_except_recognized_topic_not_found(
    monkeypatch: pytest.MonkeyPatch, completed: subprocess.CompletedProcess[str], error: str
) -> None:
    command = ["kubectl", "--", "rpk", "topic", "describe", "customer_feature_updates.v1", "-o", "json"]
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed)
    if error == "exists":
        assert _gke_runner(command) == {"exists": False}
    else:
        with pytest.raises(ValueError, match=error):
            _gke_runner(command)


@pytest.mark.parametrize(
    "payload",
    [
        {"partitions": [{"replicas": [1]}, {"replicas": []}], "configs": {"cleanup.policy": "delete"}},
        {"partitions": [{"replicas": [1]}, {"replicas": [1, 2]}], "configs": {"cleanup.policy": "delete"}},
        {"partitions": [{"replicas": [1]}], "configs": {"cleanup.policy": None}},
    ],
)
def test_gke_cli_runner_rejects_malformed_partition_and_config_members(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]
) -> None:
    command = ["kubectl", "--", "rpk", "topic", "describe", "customer_feature_updates.v1", "-o", "json"]
    completed = subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed)
    with pytest.raises(ValueError):
        _gke_runner(command)


def test_permission_failure_in_cli_runner_prevents_bootstrap_create(monkeypatch: pytest.MonkeyPatch) -> None:
    with _fake_kubeconfig() as directory:
        kubeconfig = Path(directory, "kubeconfig.yaml")
        topics_file = _feature_topics_file(directory)
        invocations: list[list[str]] = []

        def denied(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            invocations.append(command)
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="permission denied")

        monkeypatch.setattr(subprocess, "run", denied)
        with pytest.raises(ValueError, match="describe failed"):
            bootstrap_topics(
                runner=_gke_runner,
                topics_file=topics_file,
                execution="gke-rpk",
                namespace="edai2",
                statefulset="edai2-redpanda",
                kubeconfig=kubeconfig,
                context="gke_edai2",
            )
    assert len(invocations) == 1
    assert "describe" in invocations[0]
    assert not any("create" in command for command in invocations)
