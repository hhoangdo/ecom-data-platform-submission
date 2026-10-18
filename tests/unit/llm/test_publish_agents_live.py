"""Live-binding contracts for Topic 26 registry publication (Task 2)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
PUBLISHER = ROOT / "scripts/llm/publish_agents.py"
TEMPLATES = ROOT / "infra/agentregistry/edai2"
COMMIT = "a" * 40
ACTOR_IMAGE = "ghcr.io/kagent-dev/substrate/ateom-gvisor@sha256:" + "a" * 64


def _publisher():
    assert PUBLISHER.is_file(), "missing registry publisher"
    spec = importlib.util.spec_from_file_location("topic26_publish_agents_live", PUBLISHER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_template(directory: Path, agent: str, tokens: list[str]) -> None:
    body = {"agentName": agent, "edai2": {"hashes": {f"h{i}": token for i, token in enumerate(tokens)}}}
    (directory / f"{agent}-agent.yaml").write_text(yaml.safe_dump(body), encoding="utf-8")


def _jobs_payload(*, digest_match: bool = True, tamper: str | None = None) -> dict:
    jobs = []
    for agent in ("retrieval", "drift", "coordinator"):
        remote = "f" * 64
        pod = "f" * 64 if tamper != agent else "e" * 64
        jobs.append(
            {
                "job": f"edai2-{agent}-agent" if agent != "coordinator" else "edai2-coordinator",
                "workload": f"{agent}-agent" if agent != "coordinator" else "coordinator",
                "image": f"example/{agent}:abc1234",
                "remote_digest": f"sha256:{remote}",
                "pod_image_digest": f"sha256:{pod}",
                "expected_digest": f"sha256:{remote}",
                "digest_match": digest_match,
                "commit_sha": COMMIT,
            }
        )
    return {"commit_sha": COMMIT, "jobs": jobs}


def _inventory_payload() -> dict:
    return {
        "live_resources": {
            "resources": {
                "deployments": [
                    {
                        "metadata": {"name": "edai2-agents-deployment"},
                        "spec": {
                            "template": {
                                "spec": {
                                    "containers": [{"image": ACTOR_IMAGE}],
                                }
                            }
                        },
                    }
                ]
            }
        }
    }


def _isolate_prompt_source(monkeypatch: pytest.MonkeyPatch, module) -> None:
    for agent in ("retrieval", "drift", "coordinator"):
        monkeypatch.setitem(
            module.AGENT_HASH_SOURCES,
            (agent, "__LATE_BOUND_HASH_PROMPT__"),
            [__file__],
        )


def test_resolve_bindings_pins_images_at_digest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _publisher()
    templates = tmp_path / "templates"
    templates.mkdir()
    _write_template(templates, "retrieval", ["__LATE_BOUND_HASH_PROMPT__"])
    jobs_path = tmp_path / "jobs.json"
    jobs_path.write_text(json.dumps(_jobs_payload(tamper="retrieval")), encoding="utf-8")
    inventory_path = tmp_path / "platform.json"
    inventory_path.write_text(json.dumps(_inventory_payload()), encoding="utf-8")
    _isolate_prompt_source(monkeypatch, module)

    with pytest.raises(ValueError, match="digest"):
        module.resolve_bindings(templates, jobs_path, inventory_path, COMMIT)


def test_resolve_bindings_composes_pinned_images_and_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _publisher()
    templates = tmp_path / "templates"
    templates.mkdir()
    _write_template(templates, "retrieval", ["__LATE_BOUND_HASH_PROMPT__"])
    _write_template(templates, "drift", ["__LATE_BOUND_HASH_PROMPT__"])
    _write_template(templates, "coordinator", ["__LATE_BOUND_HASH_PROMPT__"])
    jobs_path = tmp_path / "jobs.json"
    jobs_path.write_text(json.dumps(_jobs_payload()), encoding="utf-8")
    inventory_path = tmp_path / "platform.json"
    inventory_path.write_text(json.dumps(_inventory_payload()), encoding="utf-8")
    _isolate_prompt_source(monkeypatch, module)

    bindings = module.resolve_bindings(templates, jobs_path, inventory_path, COMMIT)

    assert set(bindings) == {"retrieval", "drift", "coordinator"}
    assert bindings["retrieval"]["python_service_image"] == f"example/retrieval:abc1234@sha256:{'f' * 64}"
    assert bindings["retrieval"]["actor_image"] == ACTOR_IMAGE
    assert bindings["retrieval"]["commit_sha"] == COMMIT
    assert bindings["retrieval"]["hashes"] == bindings["drift"]["hashes"]


def test_strict_rejects_unmatched_digest_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = _publisher()
    templates = tmp_path / "templates"
    templates.mkdir()
    _write_template(templates, "retrieval", ["__LATE_BOUND_HASH_PROMPT__"])
    _write_template(templates, "drift", ["__LATE_BOUND_HASH_PROMPT__"])
    _write_template(templates, "coordinator", ["__LATE_BOUND_HASH_PROMPT__"])
    jobs_path = tmp_path / "jobs.json"
    jobs_path.write_text(json.dumps(_jobs_payload(digest_match=False)), encoding="utf-8")
    inventory_path = tmp_path / "platform.json"
    inventory_path.write_text(json.dumps(_inventory_payload()), encoding="utf-8")
    _isolate_prompt_source(monkeypatch, module)

    with pytest.raises(ValueError, match="digest_match"):
        module.resolve_bindings(templates, jobs_path, inventory_path, COMMIT, strict=True)


def test_template_token_coverage_over_real_templates() -> None:
    module = _publisher()

    assert module.unmapped_template_tokens(TEMPLATES) == []


def test_real_mapping_keeps_variant_prompt_relations() -> None:
    module = _publisher()

    def digest(token: str) -> str:
        return module.hash_inventory(token, ROOT)

    assert (
        digest("__LATE_BOUND_HASH_PROMPT_V1_PRIMARY__")
        == digest("__LATE_BOUND_HASH_PROMPT_V1_COMPARISON__")
    )
    assert digest("__LATE_BOUND_HASH_PROMPT_V1_PRIMARY__") != digest(
        "__LATE_BOUND_HASH_PROMPT_V2_PRIMARY__"
    )


def test_resolve_actor_image_requires_exactly_one_match(tmp_path: Path) -> None:
    module = _publisher()
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"live_resources": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match="actor image"):
        module.resolve_actor_image(empty)

    inventory = tmp_path / "platform.json"
    inventory.write_text(json.dumps(_inventory_payload()), encoding="utf-8")

    assert module.resolve_actor_image(inventory) == ACTOR_IMAGE


def test_main_accepts_topic_flags_and_requires_runner_mode(tmp_path: Path) -> None:
    module = _publisher()

    args = module.parse_args(
        [
            "--templates",
            str(TEMPLATES),
            "--commit-sha",
            COMMIT,
            "--publish",
            "--kubeconfig",
            str(tmp_path / "kubeconfig"),
            "--context",
            "edai2-gke",
            "--strict",
            "--output",
            str(tmp_path / "registry.json"),
        ]
    )

    assert args.publish is True
    assert args.strict is True

    with pytest.raises(SystemExit):
        module.parse_args(["--templates", str(TEMPLATES), "--commit-sha", COMMIT])


def test_main_wires_resolved_bindings_to_publish_and_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _publisher()
    templates = tmp_path / "templates"
    templates.mkdir()
    _write_template(templates, "retrieval", ["__LATE_BOUND_HASH_PROMPT__"])
    _write_template(templates, "drift", ["__LATE_BOUND_HASH_PROMPT__"])
    _write_template(templates, "coordinator", ["__LATE_BOUND_HASH_PROMPT__"])
    jobs_path = tmp_path / "jobs.json"
    jobs_path.write_text(json.dumps(_jobs_payload()), encoding="utf-8")
    inventory_path = tmp_path / "platform.json"
    inventory_path.write_text(json.dumps(_inventory_payload()), encoding="utf-8")
    _isolate_prompt_source(monkeypatch, module)
    calls: dict = {}

    def fake_publish_and_readback(templates_dir, bindings, *, runner, evidence_path):
        calls["bindings"] = bindings
        calls["runner"] = runner
        calls["evidence_path"] = evidence_path
        calls["templates"] = templates_dir
        return dict(bindings)

    monkeypatch.setattr(module, "publish_and_readback", fake_publish_and_readback)
    monkeypatch.setattr(module, "build_runner", lambda args: "fake-runner")
    monkeypatch.setattr(
        module,
        "resolve_bindings",
        lambda templates_dir, jobs_file, inventory_file, commit, strict=False: {
            "retrieval": {}, "drift": {}, "coordinator": {}
        },
    )

    assert (
        module.main(
            [
                "--templates",
                str(templates),
                "--commit-sha",
                COMMIT,
                "--jobs-evidence",
                str(jobs_path),
                "--platform-inventory",
                str(inventory_path),
                "--publish",
                "--read-back",
                "--output",
                str(tmp_path / "registry.json"),
            ]
        )
        == 0
    )
    assert set(calls["bindings"]) == {"retrieval", "drift", "coordinator"}
    assert calls["runner"] == "fake-runner"
    assert calls["evidence_path"] == tmp_path / "registry.json"
