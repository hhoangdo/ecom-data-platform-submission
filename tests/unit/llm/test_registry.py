"""Static late-binding and rollback contracts for Topic 14 registry metadata."""

from __future__ import annotations

import importlib.util
import copy
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "infra/agentregistry/edai2"
PUBLISHER = ROOT / "scripts/llm/publish_agents.py"
ACTOR_IMAGE = "ghcr.io/kagent-dev/substrate/ateom-gvisor@sha256:" + "a" * 64
PYTHON_IMAGE = "registry.example/edai2-retrieval-agent@sha256:" + "b" * 64
RETRIEVAL_HASHES = {
    "__LATE_BOUND_HASH_PROMPT__": "1" * 64,
    "__LATE_BOUND_HASH_RESOURCE__": "2" * 64,
}
DRIFT_HASHES = {
    "__LATE_BOUND_HASH_PROMPT__": "3" * 64,
    "__LATE_BOUND_HASH_RESOURCE__": "4" * 64,
}
COORDINATOR_HASHES = {
    "__LATE_BOUND_HASH_PROMPT_V1_PRIMARY__": "5" * 64,
    "__LATE_BOUND_HASH_PROMPT_V2_PRIMARY__": "6" * 64,
    "__LATE_BOUND_HASH_PROMPT_V1_COMPARISON__": "5" * 64,
    "__LATE_BOUND_HASH_RESOURCE_V1_PRIMARY__": "7" * 64,
    "__LATE_BOUND_HASH_RESOURCE_V2_PRIMARY__": "8" * 64,
    "__LATE_BOUND_HASH_RESOURCE_V1_COMPARISON__": "9" * 64,
    "__LATE_BOUND_HASH_MODEL_PRIMARY__": "d" * 64,
    "__LATE_BOUND_HASH_MODEL_COMPARISON__": "e" * 64,
    "__LATE_BOUND_HASH_TOOL__": "a" * 64,
    "__LATE_BOUND_HASH_SPECIALISTS__": "b" * 64,
    "__LATE_BOUND_HASH_INDEX__": "c" * 64,
    "__LATE_BOUND_HASH_SAFETY__": "f" * 64,
    "__LATE_BOUND_HASH_TIMEOUTS__": "0" * 64,
}


def _publisher():
    assert PUBLISHER.is_file(), "missing Topic 14 registry publisher"
    spec = importlib.util.spec_from_file_location("topic14_publish_agents", PUBLISHER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registry_templates_and_publisher_exist() -> None:
    assert {path.name for path in TEMPLATES.glob("*.yaml")} == {
        "retrieval-agent.yaml",
        "drift-agent.yaml",
        "coordinator-agent.yaml",
    }
    assert PUBLISHER.is_file()


def test_materialization_binds_only_a_digest_pinned_go_actor_image() -> None:
    module = _publisher()
    template = TEMPLATES / "retrieval-agent.yaml"

    materialized = module.materialize_template(
        template,
        actor_image=ACTOR_IMAGE,
        python_service_image=PYTHON_IMAGE,
        commit_sha="a" * 40,
        hashes=RETRIEVAL_HASHES,
    )

    assert materialized["image"] == ACTOR_IMAGE
    assert materialized["language"] == "go"
    assert materialized["framework"] == "kagent"
    assert materialized["modelProvider"] == "llmd"
    assert materialized["version"] == "0.1.0+aaaaaaa"
    assert materialized["edai2"]["pythonServiceImage"] == PYTHON_IMAGE
    assert materialized["edai2"]["hashes"] == {
        "prompt": "1" * 64,
        "resource": "2" * 64,
    }

    with pytest.raises(ValueError, match="registry image must be the generated Go ActorTemplate image"):
        module.materialize_template(
            template,
            actor_image=PYTHON_IMAGE,
            python_service_image=PYTHON_IMAGE,
            commit_sha="a" * 40,
            hashes=RETRIEVAL_HASHES,
        )
    with pytest.raises(ValueError, match="hash bindings are incomplete"):
        module.materialize_template(
            template,
            actor_image=ACTOR_IMAGE,
            python_service_image=PYTHON_IMAGE,
            commit_sha="a" * 40,
            hashes={"__LATE_BOUND_HASH_PROMPT__": "1" * 64},
        )
    with pytest.raises(ValueError, match="hash bindings contain unknown"):
        module.materialize_template(
            template,
            actor_image=ACTOR_IMAGE,
            python_service_image=PYTHON_IMAGE,
            commit_sha="a" * 40,
            hashes={**RETRIEVAL_HASHES, "__LATE_BOUND_HASH_UNKNOWN__": "d" * 64},
        )
    with pytest.raises(ValueError, match="hash binding must be lowercase 64-hex"):
        module.materialize_template(
            template,
            actor_image=ACTOR_IMAGE,
            python_service_image=PYTHON_IMAGE,
            commit_sha="a" * 40,
            hashes={**RETRIEVAL_HASHES, "__LATE_BOUND_HASH_PROMPT__": "not-a-hash"},
        )


def test_coordinator_variants_materialize_all_runtime_metadata_and_hold_constants() -> None:
    module = _publisher()
    materialized = module.materialize_template(
        TEMPLATES / "coordinator-agent.yaml",
        actor_image=ACTOR_IMAGE,
        python_service_image=PYTHON_IMAGE,
        commit_sha="a" * 40,
        hashes=COORDINATOR_HASHES,
    )
    variants = materialized["edai2"]["runtimeVariants"]
    assert set(variants) == {"v1-primary", "v2-primary", "v1-comparison"}
    for variant in variants.values():
        assert set(variant) == {
            "route",
            "modelConfig",
            "snapshot",
            "promptHash",
            "resourceHash",
            "modelHash",
            "toolHash",
            "heldConstantHashes",
            "pythonServiceImage",
            "commitSha",
        }
        assert variant["pythonServiceImage"] == PYTHON_IMAGE
        assert variant["commitSha"] == "a" * 40
        assert set(variant["heldConstantHashes"]) == {
            "specialists",
            "tools",
            "index",
            "safety",
            "timeouts",
        }

    v1 = variants["v1-primary"]
    v2 = variants["v2-primary"]
    comparison = variants["v1-comparison"]
    assert v1["modelConfig"] == v2["modelConfig"] == "default-model-config"
    assert v1["modelHash"] == v2["modelHash"]
    assert v1["promptHash"] != v2["promptHash"]
    assert v1["toolHash"] == v1["heldConstantHashes"]["tools"]
    assert v1["heldConstantHashes"] == v2["heldConstantHashes"]
    assert v1["promptHash"] == comparison["promptHash"]
    assert v1["heldConstantHashes"] == comparison["heldConstantHashes"]
    assert v1["modelConfig"] != comparison["modelConfig"]
    assert v1["modelHash"] != comparison["modelHash"]


@pytest.mark.parametrize(
    "token",
    ("__LATE_BOUND_HASH_MODEL_PRIMARY__", "__LATE_BOUND_HASH_SAFETY__"),
)
def test_coordinator_materialization_rejects_malformed_provenance_hash(token: str) -> None:
    module = _publisher()

    with pytest.raises(ValueError, match="hash binding must be lowercase 64-hex"):
        module.materialize_template(
            TEMPLATES / "coordinator-agent.yaml",
            actor_image=ACTOR_IMAGE,
            python_service_image=PYTHON_IMAGE,
            commit_sha="a" * 40,
            hashes={**COORDINATOR_HASHES, token: "not-a-hash"},
        )


def test_coordinator_materialization_rejects_primary_model_provenance_drift(tmp_path: Path) -> None:
    module = _publisher()
    template = tmp_path / "coordinator-agent.yaml"
    template.write_text(
        (TEMPLATES / "coordinator-agent.yaml").read_text(encoding="utf-8").replace(
            "__LATE_BOUND_HASH_MODEL_PRIMARY__",
            "__LATE_BOUND_HASH_MODEL_V2_PRIMARY__",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="coordinator primary comparison changed model hash"):
        module.materialize_template(
            template,
            actor_image=ACTOR_IMAGE,
            python_service_image=PYTHON_IMAGE,
            commit_sha="a" * 40,
            hashes={
                **COORDINATOR_HASHES,
                "__LATE_BOUND_HASH_MODEL_V2_PRIMARY__": "1" * 64,
            },
        )


def test_coordinator_materialization_rejects_held_constant_provenance_drift(tmp_path: Path) -> None:
    module = _publisher()
    template = tmp_path / "coordinator-agent.yaml"
    template.write_text(
        (TEMPLATES / "coordinator-agent.yaml").read_text(encoding="utf-8").replace(
            "__LATE_BOUND_HASH_SAFETY__",
            "__LATE_BOUND_HASH_SAFETY_V2_PRIMARY__",
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="coordinator A/B held constants differ"):
        module.materialize_template(
            template,
            actor_image=ACTOR_IMAGE,
            python_service_image=PYTHON_IMAGE,
            commit_sha="a" * 40,
            hashes={
                **COORDINATOR_HASHES,
                "__LATE_BOUND_HASH_SAFETY_V2_PRIMARY__": "1" * 64,
            },
        )


def test_readback_rejects_model_and_held_constant_provenance_drift() -> None:
    module = _publisher()
    expected = module.materialize_template(
        TEMPLATES / "coordinator-agent.yaml",
        actor_image=ACTOR_IMAGE,
        python_service_image=PYTHON_IMAGE,
        commit_sha="a" * 40,
        hashes=COORDINATOR_HASHES,
    )
    model_drift = copy.deepcopy(expected)
    model_drift["edai2"]["runtimeVariants"]["v1-comparison"]["modelHash"] = "1" * 64
    held_constant_drift = copy.deepcopy(expected)
    held_constant_drift["edai2"]["runtimeVariants"]["v2-primary"]["heldConstantHashes"][
        "safety"
    ] = "1" * 64

    with pytest.raises(ValueError, match="read-back mismatch"):
        module.verify_readback(expected, model_drift)
    with pytest.raises(ValueError, match="read-back mismatch"):
        module.verify_readback(expected, held_constant_drift)


def test_readback_and_rollback_fail_closed_on_any_drift_or_cas_mismatch() -> None:
    module = _publisher()
    expected = {
        "agentName": "retrieval",
        "version": "0.1.0+aaaaaaa",
        "route": "retrieval-mcp",
        "snapshot": "agent-substrate/retrieval/v1-primary/",
        "hashes": {"prompt": "1" * 64, "resource": "2" * 64},
    }

    module.verify_readback(expected, expected.copy())
    with pytest.raises(ValueError, match="read-back mismatch"):
        module.verify_readback(expected, {**expected, "route": "wrong-route"})

    registry = {
        "runtimes": {"v1-primary": {"version": "0.1.0+aaaaaaa"}, "bad": {}},
        "facadeAlias": "bad",
    }
    updated = module.rollback_bad_runtime(
        registry,
        bad_runtime="bad",
        expected_alias="bad",
        prior_runtime="v1-primary",
    )
    assert updated == {
        "runtimes": {"v1-primary": {"version": "0.1.0+aaaaaaa"}},
        "facadeAlias": "v1-primary",
    }
    with pytest.raises(ValueError, match="rollback CAS mismatch"):
        module.rollback_bad_runtime(
            registry,
            bad_runtime="bad",
            expected_alias="v1-primary",
            prior_runtime="v1-primary",
        )
    assert registry == {
        "runtimes": {"v1-primary": {"version": "0.1.0+aaaaaaa"}, "bad": {}},
        "facadeAlias": "bad",
    }


def test_cli_builds_only_supported_publish_and_readback_commands() -> None:
    module = _publisher()
    assert module.publish_command(Path("C:/tmp/materialized/retrieval")) == [
        "arctl",
        "agent",
        "publish",
        "C:/tmp/materialized/retrieval",
    ]
    assert module.show_command("retrieval") == [
        "arctl",
        "agent",
        "show",
        "retrieval",
        "--output",
        "json",
    ]


def test_orchestration_uses_injected_runner_for_exact_publish_show_order_and_cleanup(
    tmp_path: Path,
) -> None:
    module = _publisher()
    bindings = {
        "retrieval": {
            "actor_image": ACTOR_IMAGE,
            "python_service_image": PYTHON_IMAGE,
            "commit_sha": "a" * 40,
            "hashes": RETRIEVAL_HASHES,
        },
        "drift": {
            "actor_image": ACTOR_IMAGE,
            "python_service_image": PYTHON_IMAGE,
            "commit_sha": "a" * 40,
            "hashes": DRIFT_HASHES,
        },
        "coordinator": {
            "actor_image": ACTOR_IMAGE,
            "python_service_image": PYTHON_IMAGE,
            "commit_sha": "a" * 40,
            "hashes": COORDINATOR_HASHES,
        },
    }
    expected = {
        name: module.materialize_template(TEMPLATES / f"{name}-agent.yaml", **binding)
        for name, binding in bindings.items()
    }
    commands: list[list[str]] = []
    temporary_roots: set[Path] = set()

    def runner(command: list[str], cwd: Path) -> str:
        commands.append(command)
        temporary_roots.add(cwd)
        if command[2] == "publish":
            return "{}"
        return json.dumps(expected[command[3]])

    evidence_path = tmp_path / "registry-evidence.json"
    evidence = module.publish_and_readback(
        TEMPLATES,
        bindings,
        runner=runner,
        evidence_path=evidence_path,
    )

    assert list(evidence) == ["retrieval", "drift", "coordinator"]
    assert [[*command[:3]] for command in commands[:3]] == [
        ["arctl", "agent", "publish"],
        ["arctl", "agent", "publish"],
        ["arctl", "agent", "publish"],
    ]
    assert [command[3] for command in commands[3:]] == ["retrieval", "drift", "coordinator"]
    assert all(not root.exists() for root in temporary_roots)
    assert json.loads(evidence_path.read_text(encoding="utf-8")) == evidence
    assert "subprocess" not in PUBLISHER.read_text(encoding="utf-8")


def test_orchestration_rejects_mismatched_readback_and_still_cleans_temp_directory(
    tmp_path: Path,
) -> None:
    module = _publisher()
    bindings = {
        "retrieval": {
            "actor_image": ACTOR_IMAGE,
            "python_service_image": PYTHON_IMAGE,
            "commit_sha": "a" * 40,
            "hashes": RETRIEVAL_HASHES,
        },
        "drift": {
            "actor_image": ACTOR_IMAGE,
            "python_service_image": PYTHON_IMAGE,
            "commit_sha": "a" * 40,
            "hashes": DRIFT_HASHES,
        },
        "coordinator": {
            "actor_image": ACTOR_IMAGE,
            "python_service_image": PYTHON_IMAGE,
            "commit_sha": "a" * 40,
            "hashes": COORDINATOR_HASHES,
        },
    }
    roots: set[Path] = set()

    def runner(command: list[str], cwd: Path) -> str:
        roots.add(cwd)
        if command[2] == "publish":
            return "{}"
        return json.dumps({"agentName": command[3], "route": "wrong"})

    with pytest.raises(ValueError, match="read-back mismatch"):
        module.publish_and_readback(TEMPLATES, bindings, runner=runner, evidence_path=tmp_path / "bad.json")
    assert all(not root.exists() for root in roots)
