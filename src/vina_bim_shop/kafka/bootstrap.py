from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Literal

import yaml

from vina_bim_shop.kafka.topics import load_topic_config


CommandRunner = Callable[[list[str]], object]
ExecutionMode = Literal["local-docker", "gke-rpk"]


def _all_topics(config: dict[str, object]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for group in ("source_topics", "derived_placeholder_topics", "feature_update_topics"):
        result.update(config[group])  # type: ignore[arg-type]
    return result


def _configs(topic_config: dict[str, object]) -> list[str]:
    values = [f"cleanup.policy={topic_config['cleanup_policy']}"]
    if "retention_ms" in topic_config:
        values.append(f"retention.ms={topic_config['retention_ms']}")
    return values


def _local_create(topic: str, topic_config: dict[str, object], bootstrap_server: str) -> list[str]:
    command = [
        "docker", "compose", "exec", "-T", "kafka", "kafka-topics", "--bootstrap-server", bootstrap_server,
        "--create", "--if-not-exists", "--topic", topic, "--partitions", str(topic_config["partitions"]),
        "--replication-factor", str(topic_config["replication_factor"]),
    ]
    for value in _configs(topic_config):
        command.extend(("--config", value))
    return command


def _gke_prefix(*, namespace: str, statefulset: str, kubeconfig: Path, context: str) -> list[str]:
    return [
        "kubectl", "--kubeconfig", str(kubeconfig), "--context", context, "--namespace", namespace,
        "exec", f"statefulset/{statefulset}", "--", "rpk", "topic",
    ]


def _gke_rpk(topic: str, topic_config: dict[str, object], *, namespace: str, statefulset: str, kubeconfig: Path, context: str) -> list[str]:
    command = _gke_prefix(namespace=namespace, statefulset=statefulset, kubeconfig=kubeconfig, context=context)
    command.extend(("create", topic, "--partitions", str(topic_config["partitions"]), "--replicas", str(topic_config["replication_factor"])))
    for value in _configs(topic_config):
        command.extend(("--topic-config", value))
    return command


def _gke_describe(topic: str, *, namespace: str, statefulset: str, kubeconfig: Path, context: str) -> list[str]:
    return [
        *_gke_prefix(namespace=namespace, statefulset=statefulset, kubeconfig=kubeconfig, context=context),
        "describe", topic, "-o", "json",
    ]


def _verify_kubeconfig(kubeconfig: Path, context: str) -> None:
    if not kubeconfig.is_absolute() or not kubeconfig.is_file():
        raise ValueError("gke-rpk kubeconfig must be absolute and readable")
    try:
        config = yaml.safe_load(kubeconfig.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError("gke-rpk kubeconfig must be absolute and readable") from error
    contexts = config.get("contexts", []) if isinstance(config, dict) else []
    if not any(isinstance(item, dict) and item.get("name") == context for item in contexts):
        raise ValueError("gke-rpk context is absent from kubeconfig")


def _is_exact_topic(result: object, topic_config: dict[str, object]) -> bool | None:
    """Return None for absent, True for exact, or raise for unsafe read-back."""

    if not isinstance(result, Mapping) or not isinstance(result.get("exists"), bool):
        raise ValueError("gke-rpk describe must return the machine-readable topic read-back contract")
    if not result["exists"]:
        return None
    configs = result.get("configs")
    if (
        result.get("partitions") != topic_config["partitions"]
        or result.get("replication_factor") != topic_config["replication_factor"]
        or not isinstance(configs, Mapping)
        or configs.get("cleanup.policy") != topic_config["cleanup_policy"]
        or str(configs.get("retention.ms")) != str(topic_config["retention_ms"])
    ):
        raise ValueError("gke-rpk topic read-back mismatch")
    return True


def bootstrap_topics(
    *,
    runner: CommandRunner = subprocess.run,
    bootstrap_server: str = "kafka:29092",
    topics_file: str | Path | None = None,
    execution: ExecutionMode = "local-docker",
    namespace: str | None = None,
    statefulset: str | None = None,
    kubeconfig: str | Path | None = None,
    context: str | None = None,
) -> None:
    """Create only absent GKE topics and require exact read-back before continuing."""

    config = load_topic_config(topics_file) if topics_file is not None else load_topic_config()
    resolved_kubeconfig = Path(kubeconfig) if kubeconfig is not None else None
    if execution == "gke-rpk":
        if not namespace or not statefulset or not context or resolved_kubeconfig is None:
            raise ValueError("gke-rpk requires namespace, statefulset, kubeconfig, and context")
        _verify_kubeconfig(resolved_kubeconfig, context)

    for topic, topic_config in _all_topics(config).items():
        if execution == "local-docker":
            runner(_local_create(topic, topic_config, bootstrap_server))
            continue

        assert resolved_kubeconfig is not None
        describe = _gke_describe(
            topic, namespace=namespace or "", statefulset=statefulset or "",
            kubeconfig=resolved_kubeconfig, context=context or "",
        )
        if _is_exact_topic(runner(describe), topic_config) is True:
            continue
        runner(_gke_rpk(
            topic, topic_config, namespace=namespace or "", statefulset=statefulset or "",
            kubeconfig=resolved_kubeconfig, context=context or "",
        ))
        if _is_exact_topic(runner(describe), topic_config) is not True:
            raise ValueError("gke-rpk topic read-back mismatch")
