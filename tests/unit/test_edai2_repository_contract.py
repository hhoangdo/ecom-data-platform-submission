from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


TOPIC16_JOBS = (
    "edai2-rag-index",
    "edai2-retrieval-agent",
    "edai2-drift-agent",
    "edai2-coordinator",
    "edai2-feast-offline-writer",
    "edai2-feast-online-writer",
)

TOPIC16_RELEASE_METADATA = {
    "edai2-rag-index": ("rag_index", "worker", "infra/helm/edai2/worker/values.yaml", "rag-index", None),
    "edai2-retrieval-agent": ("retrieval_agent", "service-agent", "infra/helm/edai2/values/retrieval-agent.yaml", "retrieval-agent", None),
    "edai2-drift-agent": ("drift_agent", "service-agent", "infra/helm/edai2/values/drift-agent.yaml", "drift-agent", None),
    "edai2-coordinator": ("coordinator", "service-agent", "infra/helm/edai2/values/coordinator-agent.yaml", "coordinator", None),
    "edai2-feast-offline-writer": ("feast_offline_writer", "worker", "infra/helm/edai2/worker/values.yaml", "feast-offline-writer", None),
    "edai2-feast-online-writer": ("feast_online_writer", "worker", "infra/helm/edai2/worker/values.yaml", "feast-online-writer", None),
}


def _topic16_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_topic16(path: str) -> str:
    return (_topic16_root() / path).read_text(encoding="utf-8")


def _select_topic16_jobs(*changes: str, force_all: bool = False) -> list[str]:
    command = [
        sys.executable,
        "ci/jenkins/scripts/select_jobs.py",
        *(item for change in changes for item in ("--change", change)),
    ]
    if force_all:
        command.append("--force-all")
    completed = subprocess.run(
        command,
        cwd=_topic16_root(),
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


REQUIRED_FILES = [
    "src/vina_bim_shop/llm/__init__.py",
    "src/vina_bim_shop/llm/contracts.py",
    "src/vina_bim_shop/llm/ports.py",
    "src/vina_bim_shop/llm/indexing.py",
    "src/vina_bim_shop/llm/retrieval.py",
    "src/vina_bim_shop/llm/drift.py",
    "src/vina_bim_shop/llm/section03_ingestion.py",
    "src/vina_bim_shop/llm/inference.py",
    "src/vina_bim_shop/llm/routing.py",
    "src/vina_bim_shop/llm/coordinator.py",
    "src/vina_bim_shop/llm/safety.py",
    "src/vina_bim_shop/llm/evaluation.py",
    "src/vina_bim_shop/llm/telemetry.py",
    "src/vina_bim_shop/llm/adapters/__init__.py",
    "src/vina_bim_shop/llm/adapters/feast_postgres.py",
    "src/vina_bim_shop/llm/adapters/llmd.py",
    "src/vina_bim_shop/llm/adapters/kagent.py",
    "src/vina_bim_shop/llm/adapters/datahub.py",
    "src/vina_bim_shop/llm/api/__init__.py",
    "src/vina_bim_shop/llm/api/common.py",
    "src/vina_bim_shop/llm/api/retrieval.py",
    "src/vina_bim_shop/llm/api/drift.py",
    "src/vina_bim_shop/llm/api/chat.py",
    "src/vina_bim_shop/llm/mcp/__init__.py",
    "src/vina_bim_shop/llm/mcp/retrieval.py",
    "src/vina_bim_shop/llm/mcp/drift.py",
    "src/vina_bim_shop/llm/streaming/__init__.py",
    "src/vina_bim_shop/llm/streaming/offline_writer.py",
    "src/vina_bim_shop/llm/streaming/online_writer.py",
    "configs/llm/models.yaml",
    "configs/llm/routing.yaml",
    "configs/llm/evaluation.yaml",
    "configs/llm/warmup_prompts.json",
    "configs/llm/benchmark_requests.json",
    "configs/llm/test_scope.yaml",
    "configs/llm/coverage.ini",
    "configs/gke/profiles.yaml",
    "configs/gke/cost_envelope.yaml",
]


def test_topic08_file_map_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    assert all((root / path).is_file() for path in REQUIRED_FILES)


def test_core_points_inward_and_focus_symbols_are_explicit() -> None:
    root = Path(__file__).resolve().parents[2]
    core = root / "src" / "vina_bim_shop" / "llm"
    core_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in core.glob("*.py")
        if path.name != "__init__.py"
    )
    assert "vina_bim_shop.llm.adapters" not in core_text
    assert "from .adapters" not in core_text
    assert "class RouteStrategy" in (core / "routing.py").read_text(encoding="utf-8")
    for class_name in [
        "RagIndexPipeline",
        "FeastRetrievalService",
        "DriftDetectionService",
        "ObservedInferenceClient",
        "CommerceAgentCoordinator",
    ]:
        assert re.search(rf"^class {class_name}\b", core_text, re.MULTILINE)


def test_six_release_identities_are_declared_with_digest_pins() -> None:
    models = (Path(__file__).resolve().parents[2] / "configs" / "llm" / "models.yaml").read_text(
        encoding="utf-8"
    )
    names = {
        "edai2-rag-index",
        "edai2-retrieval-agent",
        "edai2-drift-agent",
        "edai2-coordinator",
        "edai2-feast-offline-writer",
        "edai2-feast-online-writer",
    }
    assert names <= set(re.findall(r"edai2-[a-z-]+", models))
    assert models.count("@sha256:") >= 6


def test_authoritative_model_benchmark_evaluation_and_cost_contracts() -> None:
    root = Path(__file__).resolve().parents[2]
    models = yaml.safe_load((root / "configs/llm/models.yaml").read_text(encoding="utf-8"))
    assert models["models"]["primary"]["hub_revision"] == (
        "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
    )
    assert models["models"]["comparison"]["hub_revision"] == (
        "7ae557604adf67be50417f59c2c2f167def9a775"
    )
    assert models["models"]["embedding"]["hub_revision"] == (
        "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
    )
    assert models["models"]["primary"]["context_tokens"] == 4096
    assert models["models"]["primary"]["max_new_tokens"] == 128
    assert models["models"]["primary"]["temperature"] == 0
    assert models["models"]["primary"]["top_p"] == 1
    assert models["models"]["comparison"]["context_tokens"] == 4096
    assert models["models"]["comparison"]["max_new_tokens"] == 128
    assert models["models"]["comparison"]["temperature"] == 0
    assert models["models"]["comparison"]["top_p"] == 1

    warmup = json.loads((root / "configs/llm/warmup_prompts.json").read_text(encoding="utf-8"))
    assert len(warmup) == 3
    assert len({prompt.split(":", 1)[0] for prompt in warmup}) == 1

    benchmark = json.loads(
        (root / "configs/llm/benchmark_requests.json").read_text(encoding="utf-8")
    )
    assert benchmark["request_count"] == 40
    assert benchmark["global_concurrency"] == 1
    assert benchmark["max_new_tokens"] == 128
    assert benchmark["temperature"] == 0
    assert benchmark["top_p"] == 1
    assert benchmark["seed"] == 20260715
    assert len(benchmark["requests"]) == 40
    assert benchmark["order"] == [request["id"] for request in benchmark["requests"]]
    assert len({request["prefix"] for request in benchmark["requests"]}) >= 4

    evaluation = yaml.safe_load(
        (root / "configs/llm/evaluation.yaml").read_text(encoding="utf-8")
    )
    assert evaluation["case_count"] == 60
    assert evaluation["case_breakdown"] == {
        "grounded": 36,
        "abstention": 12,
        "injection": 6,
        "pii": 6,
    }
    assert evaluation["gates"]["recall_at_4_minimum"] == 0.85
    assert evaluation["gates"]["citation_precision_minimum"] == 0.90
    assert evaluation["gates"]["safety_pass_rate_minimum"] == 0.95
    assert evaluation["gates"]["retrieval_p95_ms_maximum"] == 750
    assert evaluation["gates"]["cpu_generation_p95_seconds_maximum"] == 20
    assert evaluation["concurrency"] == 1

    costs = yaml.safe_load(
        (root / "configs/gke/cost_envelope.yaml").read_text(encoding="utf-8")
    )
    assert costs["trial_credit_usd"] == 300
    assert costs["terraform_budget_usd"] == 240
    assert costs["pre_deployment_forecast_ceiling_usd"] == 180
    assert costs["ceilings"] == {
        "regular_platform_node_hours": 96,
        "aggregate_spot_node_hours": 72,
        "second_spot_node_hours": 16,
        "public_ingress_hours": 24,
        "evidence_session_ttl_hours": 6,
        "balanced_disk_gib": 80,
        "combined_gcs_artifact_registry_gib": 15,
    }


def test_topic16_jenkins_image_buildkit_stage_chart_contracts() -> None:
    root = _topic16_root()
    dockerfile = root / "containers/edai2/Dockerfile"
    catalog_path = root / "containers/edai2/images.yaml"
    jobs_path = root / "ci/jenkins/jobs.yaml"
    pod_path = root / "ci/jenkins/buildkit-pod.yaml"
    pipeline_path = root / "ci/jenkins/pipeline.groovy"
    release_path = root / "ci/jenkins/scripts/release.sh"
    required_paths = [
        dockerfile,
        catalog_path,
        jobs_path,
        pod_path,
        pipeline_path,
        release_path,
        root / "containers/edai2/.dockerignore",
        root / "containers/edai2/Dockerfile.dockerignore",
        root / "ci/jenkins/change-map.yaml",
        root / "infra/helm/edai2/service-agent/Chart.yaml",
        root / "infra/helm/edai2/worker/Chart.yaml",
    ]
    assert all(path.is_file() for path in required_paths)

    docker = dockerfile.read_text(encoding="utf-8")
    assert "python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c" in docker
    for target in (
        "rag_index",
        "retrieval_agent",
        "drift_agent",
        "coordinator",
        "feast_offline_writer",
        "feast_online_writer",
    ):
        assert re.search(rf"^FROM .+ AS {target}$", docker, re.MULTILINE)
    assert "USER edai2" in docker

    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    images = catalog["images"]
    assert len(images) == 6
    assert {image["job"] for image in images} == set(TOPIC16_JOBS)
    assert {image["target"] for image in images} == {
        "rag_index",
        "retrieval_agent",
        "drift_agent",
        "coordinator",
        "feast_offline_writer",
        "feast_online_writer",
    }
    assert all(image["context"] == "." for image in images)
    assert all(image["artifact_registry_repository"].startswith("edai2-") for image in images)
    assert all(image["helm_release"] == image["job"] for image in images)

    jobs = yaml.safe_load(jobs_path.read_text(encoding="utf-8"))
    assert jobs["controller"]["num_executors"] == 0
    assert jobs["buildkit_lock"] == {"name": "edai2-buildkit-slot", "capacity": 1}
    assert {item["name"] for item in jobs["jobs"]} == set(TOPIC16_JOBS)
    for item in jobs["jobs"]:
        assert (root / item["jenkinsfile"]).is_file()
        target, chart, values, workload_name, workload_values = TOPIC16_RELEASE_METADATA[item["name"]]
        jenkinsfile = _read_topic16(item["jenkinsfile"])
        arguments = (
            f"'{item['name']}', '{target}', '{chart}', "
            f"'{values}', '{workload_name}', '{item['name']}'"
        )
        if workload_values:
            arguments += f", '{workload_values}'"
        assert (
            f"ci.pipelineFor({arguments})"
        ) in jenkinsfile

    pod = pod_path.read_text(encoding="utf-8")
    assert "moby/buildkit:v0.20.2-rootless@sha256:cb5bb371545222c430528556acfdf424144b69897f5deaad391bd227187e90df" in pod
    assert "runAsNonRoot: true" in pod
    assert "edai2-buildkit-slot" in pod

    pipeline = pipeline_path.read_text(encoding="utf-8")
    stage_positions = [pipeline.index(name) for name in ("test", "build", "scan", "push_sha", "helm_atomic", "smoke_eval", "rollback_proof")]
    assert stage_positions == sorted(stage_positions)
    assert "lock(resource: 'edai2-buildkit-slot'" in pipeline
    assert "EDAI2_FORCE_ALL" in pipeline
    assert "--opt target=" in pipeline
    assert "--output type=docker,dest=artifacts/" in pipeline
    assert "pipelineFor(String jobName, String target, String chartKind, String valuesFile, String workloadName, String repository, String workloadValuesFile = '')" in pipeline
    assert 'release.sh helm_atomic ${jobName} ${chartKind} ${valuesFile} ${workloadName} ${repository}${workloadValuesArgument}' in pipeline

    release = release_path.read_text(encoding="utf-8")
    for value in ("trivy_0.70.0", "crane_0.21.7", "8b4376d5d6befe5c24d503f10ff136d9e0c49f9127a4279fd110b727929a5aa9", "1a57bc98207fa1c0d04bf760699099e26f8383499bfd55b99c1b919a928a7230"):
        assert value in release
    assert "install_tools" in release
    assert "verify_download \"$trivy_archive\" \"$TRIVY_SHA256\"" in release
    assert "verify_download \"$crane_archive\" \"$CRANE_SHA256\"" in release
    assert release.index("scan_archive") < release.index("push_archive")
    assert "archive_sha256" in release
    assert "archive_manifest_digest" in release
    assert "remote_manifest_digest" in release
    assert 'test -s "reports/${job}-remote-manifest-digest.txt"' in release
    assert "SUBSTRATE_BUCKET_NAME" in release
    assert "unknown chart or release metadata" in release
    assert 'image.repository=${AR_LOCATION}-docker.pkg.dev/${GCP_PROJECT_ID}/${repository}' in release
    assert 'image.tag=${GIT_COMMIT}' in release
    assert 'workload.name=${workload_name}' in release
    assert '"$EDAI2_KUBECONFIG"' in release
    assert '"$EDAI2_KUBE_CONTEXT"' in release
    assert "Workload Identity" in release
    assert "--severity CRITICAL" in release
    assert "cyclonedx" in release
    assert "--scanners vuln,secret,license" in release
    assert "rtk" not in release.lower()
    assert "cloud build" not in release.lower()
    assert "password=" not in release.lower()
    assert "service-account-key" not in release.lower()

    for chart, templates in {
        "service-agent": ("deployment", "service", "scaledobject", "networkpolicy", "serviceaccount", "sandboxagent", "remotemcpserver", "agentgateway-policy"),
        "worker": ("deployment", "scaledobject", "networkpolicy", "serviceaccount"),
    }.items():
        chart_root = root / "infra/helm/edai2" / chart
        assert (chart_root / "values.yaml").is_file()
        for template in templates:
            assert (chart_root / "templates" / f"{template}.yaml").is_file()


def test_topic16_change_map_handles_required_fan_out_cases() -> None:
    assert _select_topic16_jobs("M:src/vina_bim_shop/llm/api/retrieval.py") == [
        "edai2-retrieval-agent"
    ]
    assert _select_topic16_jobs("D:infra/helm/edai2/workloads/feast-offline-writer.yaml") == [
        "edai2-feast-offline-writer"
    ]
    assert _select_topic16_jobs(
        "R100:src/vina_bim_shop/llm/api/retrieval.py:src/vina_bim_shop/llm/api/drift.py"
    ) == ["edai2-drift-agent", "edai2-retrieval-agent"]
    assert _select_topic16_jobs("M:configs/llm/routing.yaml") == list(TOPIC16_JOBS)
    assert _select_topic16_jobs("M:src/vina_bim_shop/llm/new_runtime.py") == list(TOPIC16_JOBS)
    assert _select_topic16_jobs("M:src/vina_bim_shop/llm/api/retrieval.py", force_all=True) == list(TOPIC16_JOBS)


def test_topic16_release_script_has_valid_bash_syntax_and_dispatch_metadata() -> None:
    root = _topic16_root()
    release = root / "ci/jenkins/scripts/release.sh"
    subprocess.run(
        ["bash", "-n", "ci/jenkins/scripts/release.sh"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    commit = "a" * 40
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
        workspace = Path(temporary)
        release_source = release.read_bytes().replace(b"\r\n", b"\n")

        def write_release_script(name: str, *, substrate_bucket: bool) -> None:
            fixture_environment = (
                f'export PATH="bin:$PATH" FAKE_HELM_ARGS=helm-args.txt GIT_COMMIT="{commit}" '
                "AR_LOCATION=us-central1 GCP_PROJECT_ID=project "
                "EDAI2_KUBECONFIG=fixture-kubeconfig EDAI2_KUBE_CONTEXT=fixture-context\n"
            )
            if substrate_bucket:
                fixture_environment += "export SUBSTRATE_BUCKET_NAME=sentinel-bucket\n"
            (workspace / name).write_bytes(
                release_source.replace(b"\n", b"\n" + fixture_environment.encode("utf-8"), 1)
            )

        write_release_script("release.sh", substrate_bucket=True)
        write_release_script("release-no-bucket.sh", substrate_bucket=False)
        values = workspace / "infra/helm/edai2/values/retrieval-agent.yaml"
        values.parent.mkdir(parents=True)
        values.write_text("namespace: edai2\n", encoding="utf-8")
        reports = workspace / "reports"
        reports.mkdir()
        (reports / "edai2-retrieval-agent-remote-manifest-digest.txt").write_text(
            "sha256:example\n", encoding="utf-8"
        )
        bin_dir = workspace / "bin"
        bin_dir.mkdir()
        args_path = workspace / "helm-args.txt"
        fake_helm = bin_dir / "helm"
        fake_helm.write_bytes(b'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$FAKE_HELM_ARGS"\n')
        fake_helm.chmod(0o755)
        def run_release(*arguments: str, script: str = "release.sh") -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["bash", script, *arguments],
                cwd=workspace,
                capture_output=True,
                text=True,
            )

        completed = run_release(
            "helm_atomic",
            "edai2-retrieval-agent",
            "service-agent",
            "infra/helm/edai2/values/retrieval-agent.yaml",
            "retrieval-agent",
            "edai2-retrieval-agent",
        )
        assert completed.returncode == 0, completed.stderr
        assert args_path.read_text(encoding="utf-8").splitlines() == [
            "upgrade",
            "--install",
            "edai2-retrieval-agent",
            "infra/helm/edai2/service-agent",
            "--atomic",
            "--wait",
            "--kubeconfig",
            "fixture-kubeconfig",
            "--kube-context",
            "fixture-context",
            "-f",
            "infra/helm/edai2/values/retrieval-agent.yaml",
            "--set-string",
            "image.repository=us-central1-docker.pkg.dev/project/edai2-retrieval-agent",
            "--set-string",
            f"image.tag={commit}",
            "--set-string",
            "workload.name=retrieval-agent",
            "--set-string",
            "substrate.bucketName=sentinel-bucket",
        ]
        args_path.unlink()
        unknown = run_release("helm_atomic", "unknown", "worker", "missing.yaml", "worker", "unknown")
        assert unknown.returncode != 0
        assert not args_path.exists()
        missing_bucket = run_release(
            "helm_atomic",
            "edai2-retrieval-agent",
            "service-agent",
            "infra/helm/edai2/values/retrieval-agent.yaml",
            "retrieval-agent",
            "edai2-retrieval-agent",
            script="release-no-bucket.sh",
        )
        assert missing_bucket.returncode != 0
        assert not args_path.exists()


def test_reusable_charts_render_topic19_keda_and_deployment_interfaces(tmp_path: Path) -> None:
    """Omitting a reusable KEDA or deployment field would block workload values from rendering it."""
    root = _topic16_root()
    overrides = tmp_path / "topic19-interface.yaml"
    overrides.write_text(
        yaml.safe_dump(
            {
                "image": {"tag": "testsha"},
                "workload": {"name": "interface-test"},
                "autoscaling": {
                    "enabled": True,
                    "minReplicaCount": 1,
                    "maxReplicaCount": 2,
                    "pollingInterval": 15,
                    "cooldownPeriod": 60,
                    "triggers": [
                        {
                            "type": "prometheus",
                            "metadata": {
                                "serverAddress": "http://prometheus.edai2.svc.cluster.local",
                                "metricName": "edai2_pending_work",
                                "threshold": "1",
                                "query": "sum(edai2_pending_work)",
                            },
                        }
                    ],
                },
                "readinessProbe": {"httpGet": {"path": "/ready", "port": "http"}},
                "livenessProbe": {"httpGet": {"path": "/live", "port": "http"}},
                "resources": {
                    "requests": {"cpu": "100m", "memory": "128Mi"},
                    "limits": {"cpu": "500m", "memory": "512Mi"},
                },
                "deploymentStrategy": {
                    "type": "RollingUpdate",
                    "rollingUpdate": {"maxUnavailable": 0, "maxSurge": 1},
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    expected_trigger = {
        "type": "prometheus",
        "metadata": {
            "serverAddress": "http://prometheus.edai2.svc.cluster.local",
            "metricName": "edai2_pending_work",
            "threshold": "1",
            "query": "sum(edai2_pending_work)",
        },
    }
    expected_strategy = {
        "type": "RollingUpdate",
        "rollingUpdate": {"maxUnavailable": 0, "maxSurge": 1},
    }
    expected_resources = {
        "requests": {"cpu": "100m", "memory": "128Mi"},
        "limits": {"cpu": "500m", "memory": "512Mi"},
    }
    for chart in ("service-agent", "worker"):
        rendered = subprocess.run(
            [
                "helm",
                "template",
                "interface-test",
                f"infra/helm/edai2/{chart}",
                "-f",
                str(overrides),
            ],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        documents = [item for item in yaml.safe_load_all(rendered.stdout) if item]
        deployment = next(item for item in documents if item["kind"] == "Deployment")
        scaled_object = next(item for item in documents if item["kind"] == "ScaledObject")
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        assert deployment["spec"]["strategy"] == expected_strategy
        assert container["readinessProbe"] == {"httpGet": {"path": "/ready", "port": "http"}}
        assert container["livenessProbe"] == {"httpGet": {"path": "/live", "port": "http"}}
        assert container["resources"] == expected_resources
        assert scaled_object["spec"]["pollingInterval"] == 15
        assert scaled_object["spec"]["cooldownPeriod"] == 60
        assert scaled_object["spec"]["triggers"] == [expected_trigger]


def test_existing_topic16_chart_values_still_render_without_topic19_overrides() -> None:
    """Requiring Topic 19-only values would break the already-owned Topic 16 render interface."""
    root = _topic16_root()
    service = subprocess.run(
        [
            "helm",
            "template",
            "retrieval",
            "infra/helm/edai2/service-agent",
            "-f",
            "infra/helm/edai2/values/retrieval-agent.yaml",
            "--set",
            "image.tag=testsha",
            "--set-string",
            "substrate.bucketName=edai2-sentinel-bucket",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    worker = subprocess.run(
        ["helm", "template", "writer", "infra/helm/edai2/worker", "--set", "image.tag=testsha"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert any(item and item["kind"] == "Deployment" for item in yaml.safe_load_all(service.stdout))
    assert any(item and item["kind"] == "Deployment" for item in yaml.safe_load_all(worker.stdout))


def test_topic19_release_values_are_ordered_and_fail_closed_in_helm_atomic(tmp_path: Path) -> None:
    """Dropping either values layer, substrate, or release mapping must stop before Helm runs."""
    root = _topic16_root()
    release = root / "ci/jenkins/scripts/release.sh"
    commit = "a" * 40
    release_source = release.read_bytes().replace(b"\r\n", b"\n")
    environment = (
        f'export PATH="bin:$PATH" FAKE_HELM_ARGS=helm-args.txt GIT_COMMIT="{commit}" '
        "AR_LOCATION=us-central1 GCP_PROJECT_ID=project "
        "EDAI2_KUBECONFIG=fixture-kubeconfig EDAI2_KUBE_CONTEXT=fixture-context "
        "SUBSTRATE_BUCKET_NAME=sentinel-bucket\n"
    )
    (tmp_path / "release.sh").write_bytes(
        release_source.replace(b"\n", b"\n" + environment.encode("utf-8"), 1)
    )
    (tmp_path / "release-no-bucket.sh").write_bytes(
        release_source.replace(
            b"\n",
            b"\n" + environment.replace("SUBSTRATE_BUCKET_NAME=sentinel-bucket", "unset SUBSTRATE_BUCKET_NAME").encode("utf-8"),
            1,
        )
    )
    for path in (
        "infra/helm/edai2/values/retrieval-agent.yaml",
        "infra/helm/edai2/worker/values.yaml",
        "infra/helm/edai2/workloads/retrieval.yaml",
        "infra/helm/edai2/workloads/feast-offline-writer.yaml",
        "infra/helm/edai2/workloads/unexpected.yaml",
    ):
        value = tmp_path / path
        value.parent.mkdir(parents=True, exist_ok=True)
        value.write_text("namespace: edai2\n", encoding="utf-8")
    reports = tmp_path / "reports"
    reports.mkdir()
    for job in ("edai2-retrieval-agent", "edai2-feast-offline-writer", "unknown"):
        (reports / f"{job}-remote-manifest-digest.txt").write_text("sha256:example\n", encoding="utf-8")
    fake_helm = tmp_path / "bin/helm"
    fake_helm.parent.mkdir()
    fake_helm.write_bytes(b'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$FAKE_HELM_ARGS"\n')
    fake_helm.chmod(0o755)

    def run_release(*arguments: str, script: str = "release.sh") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", script, *arguments],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

    retrieval = run_release(
        "helm_atomic",
        "edai2-retrieval-agent",
        "service-agent",
        "infra/helm/edai2/values/retrieval-agent.yaml",
        "retrieval-agent",
        "edai2-retrieval-agent",
        "infra/helm/edai2/workloads/retrieval.yaml",
    )
    assert retrieval.returncode == 0, retrieval.stderr
    assert (tmp_path / "helm-args.txt").read_text(encoding="utf-8").splitlines() == [
        "upgrade", "--install", "edai2-retrieval-agent", "infra/helm/edai2/service-agent", "--atomic", "--wait",
        "--kubeconfig", "fixture-kubeconfig", "--kube-context", "fixture-context",
        "-f", "infra/helm/edai2/values/retrieval-agent.yaml", "-f", "infra/helm/edai2/workloads/retrieval.yaml",
        "--set-string", "image.repository=us-central1-docker.pkg.dev/project/edai2-retrieval-agent",
        "--set-string", f"image.tag={commit}", "--set-string", "workload.name=retrieval-agent",
        "--set-string", "substrate.bucketName=sentinel-bucket",
    ]
    (tmp_path / "helm-args.txt").unlink()
    worker = run_release(
        "helm_atomic", "edai2-feast-offline-writer", "worker",
        "infra/helm/edai2/workloads/feast-offline-writer.yaml", "feast-offline-writer", "edai2-feast-offline-writer",
    )
    assert worker.returncode == 0, worker.stderr
    assert (tmp_path / "helm-args.txt").read_text(encoding="utf-8").splitlines().count("-f") == 1
    (tmp_path / "helm-args.txt").unlink()
    worker_legacy_extra = run_release(
        "helm_atomic", "edai2-feast-offline-writer", "worker",
        "infra/helm/edai2/worker/values.yaml", "feast-offline-writer", "edai2-feast-offline-writer",
        "infra/helm/edai2/workloads/unexpected.yaml",
    )
    assert worker_legacy_extra.returncode != 0
    assert not (tmp_path / "helm-args.txt").exists()
    worker_multiple_values = run_release(
        "helm_atomic", "edai2-feast-offline-writer", "worker",
        "infra/helm/edai2/workloads/feast-offline-writer.yaml", "feast-offline-writer", "edai2-feast-offline-writer",
        "infra/helm/edai2/workloads/unexpected.yaml",
    )
    assert worker_multiple_values.returncode != 0
    assert not (tmp_path / "helm-args.txt").exists()
    unknown = run_release(
        "helm_atomic", "unknown", "worker", "infra/helm/edai2/workloads/feast-offline-writer.yaml", "worker", "unknown",
    )
    assert unknown.returncode != 0
    assert "unknown chart or release metadata" in unknown.stderr
    assert not (tmp_path / "helm-args.txt").exists()
    missing_substrate = run_release(
        "helm_atomic", "edai2-retrieval-agent", "service-agent",
        "infra/helm/edai2/values/retrieval-agent.yaml", "retrieval-agent", "edai2-retrieval-agent",
        "infra/helm/edai2/workloads/retrieval.yaml", script="release-no-bucket.sh",
    )
    assert missing_substrate.returncode != 0
    assert "SUBSTRATE_BUCKET_NAME is required" in missing_substrate.stderr
    assert not (tmp_path / "helm-args.txt").exists()


def test_topic17_root_composes_only_approved_modules_and_nonsecret_outputs() -> None:
    root = _topic16_root()
    terraform_root = root / "infra" / "terraform" / "edai2"
    main = (terraform_root / "main.tf").read_text(encoding="utf-8")
    outputs = (terraform_root / "outputs.tf").read_text(encoding="utf-8").lower()
    assert all(f'module "{name}"' in main for name in ("gke", "artifact_registry", "gcs", "kms", "iam", "budget"))
    assert "backend" not in main.lower()
    assert not any(value in outputs for value in ("secret", "token", "password", "credential", "private_key"))
