from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


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
