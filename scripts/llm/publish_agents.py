"""Materialize and validate late-bound Agent Registry metadata without local publication."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import yaml


COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ACTOR_IMAGE_RE = re.compile(
    r"^ghcr\.io/kagent-dev/substrate/ateom-gvisor@sha256:[0-9a-f]{64}$"
)
PYTHON_IMAGE_RE = re.compile(r"^[a-z0-9./_-]+@sha256:[0-9a-f]{64}$")
STATIC_TOKENS = {
    "__LATE_BOUND_ACTOR_TEMPLATE_IMAGE__",
    "__LATE_BOUND_PYTHON_SERVICE_IMAGE__",
    "__LATE_BOUND_COMMIT_SHA__",
    "__LATE_BOUND_VERSION__",
}
PUBLISH_ORDER = ("retrieval", "drift", "coordinator")
Runner = Callable[[list[str], Path], str]


def _replace_tokens(value: Any, replacements: Mapping[str, str]) -> Any:
    """Recursively replace exact late-binding tokens."""

    if isinstance(value, dict):
        return {key: _replace_tokens(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_tokens(item, replacements) for item in value]
    if isinstance(value, str):
        return replacements.get(value, value)
    return value


def _late_bound_tokens(value: Any) -> set[str]:
    """Return every late-binding token remaining in a parsed template."""

    if isinstance(value, dict):
        return set().union(*(_late_bound_tokens(item) for item in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(_late_bound_tokens(item) for item in value)) if value else set()
    if isinstance(value, str) and value.startswith("__LATE_BOUND_") and value.endswith("__"):
        return {value}
    return set()


def _hash_tokens(template: Any) -> set[str]:
    """Return hash late-binding tokens that require immutable caller values."""

    return {token for token in _late_bound_tokens(template) if token.startswith("__LATE_BOUND_HASH_")}


def _validate_actor_image(image: str) -> None:
    """Reject a Python service image or mutable/non-Go ActorTemplate image."""

    if not ACTOR_IMAGE_RE.fullmatch(image):
        raise ValueError("registry image must be the generated Go ActorTemplate image")


def _validate_python_image(image: str) -> None:
    """Require an immutable digest-pinned Python service image."""

    if not PYTHON_IMAGE_RE.fullmatch(image):
        raise ValueError("Python service image must be digest pinned")


def _validate_hash_bindings(template: Any, hashes: Mapping[str, str]) -> None:
    """Require an exact, valid mapping for every hash token in one template."""

    required = _hash_tokens(template)
    supplied = set(hashes)
    if required - supplied:
        raise ValueError("hash bindings are incomplete")
    if supplied - required:
        raise ValueError("hash bindings contain unknown tokens")
    if any(not isinstance(value, str) or not SHA256_RE.fullmatch(value) for value in hashes.values()):
        raise ValueError("hash binding must be lowercase 64-hex")


def _validate_coordinator_variants(materialized: dict[str, Any]) -> None:
    """Ensure each coordinator A/B runtime has complete, controlled provenance."""

    variants = materialized["edai2"]["runtimeVariants"]
    expected_names = {"v1-primary", "v2-primary", "v1-comparison"}
    expected_fields = {
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
    if set(variants) != expected_names or any(set(item) != expected_fields for item in variants.values()):
        raise ValueError("coordinator runtime inventory is incomplete")
    expected_held_constant_fields = {"specialists", "tools", "index", "safety", "timeouts"}
    if any(
        set(item["heldConstantHashes"]) != expected_held_constant_fields
        or item["toolHash"] != item["heldConstantHashes"]["tools"]
        for item in variants.values()
    ):
        raise ValueError("coordinator held constant inventory is incomplete")

    v1_primary = variants["v1-primary"]
    v2_primary = variants["v2-primary"]
    comparison = variants["v1-comparison"]
    if v1_primary["modelConfig"] != v2_primary["modelConfig"]:
        raise ValueError("coordinator primary comparison changed ModelConfig")
    if v1_primary["modelHash"] != v2_primary["modelHash"]:
        raise ValueError("coordinator primary comparison changed model hash")
    if v1_primary["promptHash"] == v2_primary["promptHash"]:
        raise ValueError("coordinator primary comparison did not change prompt")
    if v1_primary["promptHash"] != comparison["promptHash"]:
        raise ValueError("coordinator v1 comparison changed prompt")
    if v1_primary["modelConfig"] == comparison["modelConfig"]:
        raise ValueError("coordinator v1 comparison did not change ModelConfig")
    if v1_primary["modelHash"] == comparison["modelHash"]:
        raise ValueError("coordinator v1 comparison did not change model hash")
    for field in ("heldConstantHashes", "pythonServiceImage", "commitSha"):
        if not (v1_primary[field] == v2_primary[field] == comparison[field]):
            raise ValueError("coordinator A/B held constants differ")


def materialize_template(
    template_path: Path,
    *,
    actor_image: str,
    python_service_image: str,
    commit_sha: str,
    hashes: Mapping[str, str],
) -> dict[str, Any]:
    """Late-bind immutable images, commit, version, and complete hash provenance."""

    if not COMMIT_RE.fullmatch(commit_sha):
        raise ValueError("commit SHA must be a lowercase 40-hex value")
    _validate_actor_image(actor_image)
    _validate_python_image(python_service_image)
    template = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    _validate_hash_bindings(template, hashes)
    materialized = _replace_tokens(
        template,
        {
            "__LATE_BOUND_ACTOR_TEMPLATE_IMAGE__": actor_image,
            "__LATE_BOUND_PYTHON_SERVICE_IMAGE__": python_service_image,
            "__LATE_BOUND_COMMIT_SHA__": commit_sha,
            "__LATE_BOUND_VERSION__": f"0.1.0+{commit_sha[:7]}",
            **hashes,
        },
    )
    remaining = _late_bound_tokens(materialized)
    if remaining:
        raise ValueError(f"unbound registry tokens: {sorted(remaining)}")
    _validate_actor_image(materialized["image"])
    if materialized["agentName"] == "coordinator":
        _validate_coordinator_variants(materialized)
    return materialized


def verify_readback(expected: dict[str, Any], observed: dict[str, Any]) -> None:
    """Require registry read-back to preserve every semantic contract field."""

    if observed != expected:
        raise ValueError("read-back mismatch")


def publish_and_readback(
    templates: Path,
    bindings: Mapping[str, Mapping[str, Any]],
    *,
    runner: Runner,
    evidence_path: Path,
) -> dict[str, dict[str, Any]]:
    """Publish and exactly read back all agents through an injected runtime runner."""

    if set(bindings) != set(PUBLISH_ORDER):
        raise ValueError("publish bindings must name each required agent exactly once")
    evidence: dict[str, dict[str, Any]] = {}
    with TemporaryDirectory(prefix="edai2-agentregistry-") as temporary_root:
        root = Path(temporary_root)
        for agent_name in PUBLISH_ORDER:
            materialized = materialize_template(
                templates / f"{agent_name}-agent.yaml", **bindings[agent_name]
            )
            agent_directory = root / agent_name
            agent_directory.mkdir()
            (agent_directory / "agent.yaml").write_text(
                yaml.safe_dump(materialized, sort_keys=False), encoding="utf-8"
            )
            runner(publish_command(agent_directory), root)
            evidence[agent_name] = materialized
        for agent_name in PUBLISH_ORDER:
            raw_readback = runner(show_command(agent_name), root)
            try:
                observed = json.loads(raw_readback)
            except json.JSONDecodeError as error:
                raise ValueError("registry read-back is not JSON") from error
            if not isinstance(observed, dict):
                raise ValueError("registry read-back is not an object")
            verify_readback(evidence[agent_name], observed)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


def rollback_bad_runtime(
    registry: dict[str, Any],
    *,
    bad_runtime: str,
    expected_alias: str,
    prior_runtime: str,
) -> dict[str, Any]:
    """Delete only an injected bad runtime and atomically restore a known-good alias."""

    if registry.get("facadeAlias") != expected_alias:
        raise ValueError("rollback CAS mismatch")
    updated = copy.deepcopy(registry)
    runtimes = updated.get("runtimes", {})
    if bad_runtime not in runtimes or prior_runtime not in runtimes:
        raise ValueError("rollback runtime is not published")
    del runtimes[bad_runtime]
    updated["facadeAlias"] = prior_runtime
    return updated


def publish_command(directory: Path) -> list[str]:
    """Build the supported Agent Registry publication command without executing it."""

    return ["arctl", "agent", "publish", directory.as_posix()]


def show_command(agent_name: str) -> list[str]:
    """Build the supported JSON read-back command without executing it."""

    return ["arctl", "agent", "show", agent_name, "--output", "json"]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the Topic 26 registry publication request."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--templates", type=Path, required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument(
        "--jobs-evidence",
        type=Path,
        default=Path("evidence/04_2_llm_design/cicd/jobs.json"),
    )
    parser.add_argument(
        "--platform-inventory",
        type=Path,
        default=Path("evidence/04_2_llm_design/gke/platform_install.json"),
    )
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--submit-gke-job", action="store_true")
    parser.add_argument("--read-back", action="store_true")
    parser.add_argument("--kubeconfig", type=Path, default=None)
    parser.add_argument("--context", default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(argv)
    if bool(args.publish) == bool(args.submit_gke_job):
        parser.error("exactly one of --publish and --submit-gke-job is required")
    if args.output is None and args.evidence is None:
        parser.error("one of --output and --evidence is required")
    if bool(args.kubeconfig is None) != bool(args.context is None):
        parser.error("--kubeconfig and --context are required together")
    if args.submit_gke_job and (args.kubeconfig is None or args.context is None):
        parser.error("--submit-gke-job requires --kubeconfig and --context")
    return args


AGENT_JOBS = {
    "retrieval": "edai2-retrieval-agent",
    "drift": "edai2-drift-agent",
    "coordinator": "edai2-coordinator",
}

# Interim provenance: each hash token binds the nearest governing repo
# artifact until Topic 13 authors discrete prompt files. The mapping must
# keep v1 == v1-comparison prompt equality and v1 != v2 prompt inequality,
# which hash_inventory over file bytes guarantees by construction.
HASH_SOURCES: dict[str, list[str]] = {
    "__LATE_BOUND_HASH_MODEL_PRIMARY__": ["infra/kagent/edai2/model-configs.yaml"],
    "__LATE_BOUND_HASH_MODEL_COMPARISON__": [
        "infra/kagent/edai2/model-configs.yaml",
        "configs/llm/models.yaml",
    ],
    "__LATE_BOUND_HASH_PROMPT_V1_PRIMARY__": ["configs/llm/routing.yaml"],
    "__LATE_BOUND_HASH_PROMPT_V1_COMPARISON__": ["configs/llm/routing.yaml"],
    "__LATE_BOUND_HASH_PROMPT_V2_PRIMARY__": [
        "configs/llm/routing.yaml",
        "infra/helm/edai2/workloads/coordinator.yaml",
    ],
    "__LATE_BOUND_HASH_RESOURCE_V1_PRIMARY__": ["infra/helm/edai2/workloads/coordinator.yaml"],
    "__LATE_BOUND_HASH_RESOURCE_V2_PRIMARY__": ["infra/helm/edai2/workloads/coordinator.yaml"],
    "__LATE_BOUND_HASH_RESOURCE_V1_COMPARISON__": ["infra/helm/edai2/workloads/coordinator.yaml"],
    "__LATE_BOUND_HASH_TOOL__": [
        "src/vina_bim_shop/llm/mcp/retrieval.py",
        "src/vina_bim_shop/llm/mcp/drift.py",
    ],
    "__LATE_BOUND_HASH_SPECIALISTS__": ["configs/llm/routing.yaml"],
    "__LATE_BOUND_HASH_INDEX__": ["infra/helm/edai2/workloads/rag-index.yaml"],
    "__LATE_BOUND_HASH_SAFETY__": ["src/vina_bim_shop/llm/safety.py"],
    "__LATE_BOUND_HASH_TIMEOUTS__": ["infra/helm/edai2/workloads/coordinator.yaml"],
}

# Retrieval and drift templates reuse the generic prompt/resource token
# names, so their sources are keyed per agent to keep distinct hashes.
AGENT_HASH_SOURCES: dict[tuple[str, str], list[str]] = {
    ("retrieval", "__LATE_BOUND_HASH_PROMPT__"): ["src/vina_bim_shop/llm/retrieval.py"],
    ("retrieval", "__LATE_BOUND_HASH_RESOURCE__"): ["infra/helm/edai2/workloads/retrieval.yaml"],
    ("drift", "__LATE_BOUND_HASH_PROMPT__"): ["src/vina_bim_shop/llm/drift.py"],
    ("drift", "__LATE_BOUND_HASH_RESOURCE__"): ["infra/helm/edai2/workloads/drift.yaml"],
}


def hash_inventory(token: str, repo_root: str | Path, agent: str = "") -> str:
    """Hash the governing repo sources bound to one registry hash token."""
    key = (agent, token)
    if key in AGENT_HASH_SOURCES:
        sources = AGENT_HASH_SOURCES[key]
    elif token in HASH_SOURCES:
        sources = HASH_SOURCES[token]
    else:
        raise ValueError(f"no hash source for token: {token}")
    digest = hashlib.sha256()
    for relative in sorted(sources):
        path = Path(relative)
        full = path if path.is_absolute() else Path(repo_root) / relative
        if not full.is_file():
            raise ValueError(f"hash source missing: {relative}")
        digest.update(full.read_bytes())
    return digest.hexdigest()


def unmapped_template_tokens(templates: Path) -> list[str]:
    """List every hash token in the three templates that has no source binding."""
    missing: set[str] = set()
    for agent in PUBLISH_ORDER:
        template = yaml.safe_load(
            (templates / f"{agent}-agent.yaml").read_text(encoding="utf-8")
        )
        for token in _late_bound_tokens(template):
            if not token.startswith("__LATE_BOUND_HASH_"):
                continue
            if (agent, token) not in AGENT_HASH_SOURCES and token not in HASH_SOURCES:
                missing.add(f"{agent}:{token}")
    return sorted(missing)


def _unique_image_digest(text: str, repository: str, label: str) -> str:
    """Require exactly one digest-pinned image for one repository in JSON text."""
    matches = sorted(set(re.findall(re.escape(repository) + r"@sha256:[0-9a-f]{64}", text)))
    if len(matches) != 1:
        raise ValueError(f"{label} image is not uniquely pinned")
    return matches[0]


def resolve_actor_image(platform_inventory: Path) -> str:
    """Resolve the shared kagent Go runtime digest from platform provenance."""
    text = platform_inventory.read_text(encoding="utf-8")
    return _unique_image_digest(
        text, "ghcr.io/kagent-dev/substrate/ateom-gvisor", "actor"
    )


def resolve_job_image(platform_inventory: Path) -> str:
    """Resolve the in-cluster arctl image from platform provenance."""
    text = platform_inventory.read_text(encoding="utf-8")
    return _unique_image_digest(
        text, "ghcr.io/agentregistry-dev/agentregistry/server", "registry job"
    )


def resolve_bindings(
    templates: Path,
    jobs_path: Path,
    platform_inventory: Path,
    commit_sha: str,
    repo_root: str | Path | None = None,
    strict: bool = False,
) -> dict[str, dict[str, Any]]:
    """Bind immutable images, commit, and hash provenance for all three agents."""
    if not COMMIT_RE.fullmatch(commit_sha):
        raise ValueError("commit SHA must be a lowercase 40-hex value")
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    jobs = json.loads(jobs_path.read_text(encoding="utf-8"))
    by_job = {entry.get("job"): entry for entry in jobs.get("jobs", [])}
    actor_image = resolve_actor_image(platform_inventory)
    bindings: dict[str, dict[str, Any]] = {}
    for agent in PUBLISH_ORDER:
        entry = by_job.get(AGENT_JOBS[agent])
        if not isinstance(entry, dict):
            raise ValueError(f"job record missing for agent: {agent}")
        if entry.get("commit_sha") != commit_sha:
            raise ValueError(f"job commit mismatch for agent: {agent}")
        remote = entry.get("remote_digest", "")
        pod = entry.get("pod_image_digest", "")
        if not remote or remote != pod:
            raise ValueError(f"service digest mismatch for agent: {agent}")
        expected = entry.get("expected_digest", "")
        if expected and expected != remote:
            raise ValueError(f"service digest mismatch for agent: {agent}")
        if not entry.get("digest_match", True) and strict:
            raise ValueError(f"digest_match is false for agent: {agent}")
        template = yaml.safe_load(
            (templates / f"{agent}-agent.yaml").read_text(encoding="utf-8")
        )
        hashes = {
            token: hash_inventory(token, root, agent)
            for token in sorted(_late_bound_tokens(template))
            if token.startswith("__LATE_BOUND_HASH_")
        }
        bindings[agent] = {
            "actor_image": actor_image,
            "python_service_image": f"{entry['image']}@{remote}",
            "commit_sha": commit_sha,
            "hashes": hashes,
        }
    return bindings


_LIVE_RUNNER: Any = None


def _live_runner_module() -> Any:
    """Load the sibling process-execution helpers without importing them."""
    global _LIVE_RUNNER
    if _LIVE_RUNNER is None:
        path = Path(__file__).resolve().parent / "live_runner.py"
        spec = importlib.util.spec_from_file_location("topic26_live_runner", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LIVE_RUNNER = module
    return _LIVE_RUNNER


def build_runner(args: argparse.Namespace) -> Runner:
    """Select the local or GKE job runner for one publication run."""
    live = _live_runner_module()
    if args.publish:
        return live.local_arctl_runner()
    assert args.kubeconfig is not None and args.context is not None
    inventory = Path(args.platform_inventory)
    image = resolve_job_image(inventory)

    def run(command: list[str], cwd: Path) -> str:
        return live.gke_job_runner(
            args.kubeconfig, args.context, "edai2", image, list(command), 600
        )

    return run


def main(argv: Sequence[str] | None = None) -> int:
    """Resolve bindings, publish, read back, and write immutable evidence."""
    args = parse_args(argv)
    if not COMMIT_RE.fullmatch(args.commit_sha):
        raise SystemExit("--commit-sha must be a lowercase 40-hex value")
    output = args.output if args.output is not None else args.evidence
    assert output is not None
    bindings = resolve_bindings(
        args.templates,
        args.jobs_evidence,
        args.platform_inventory,
        args.commit_sha,
        strict=args.strict,
    )
    evidence = publish_and_readback(
        args.templates,
        bindings,
        runner=build_runner(args),
        evidence_path=output,
    )
    print(json.dumps({"commit_sha": args.commit_sha, "evidence": str(output), "agents": sorted(evidence)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
