from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

from vina_bim_shop.kafka.bootstrap import bootstrap_topics


def _validate_schema(path: Path) -> None:
    schema = json.loads(path.read_text(encoding="utf-8"))
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema" or not schema.get("additionalProperties") is False:
        raise ValueError("schema must be a closed Draft 2020-12 object")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create exact Kafka topics and validate their static schema.")
    parser.add_argument("--bootstrap-server", default="kafka:29092")
    parser.add_argument("--topics-file", default=None)
    parser.add_argument("--execution", choices=("local-docker", "gke-rpk"), default="local-docker")
    parser.add_argument("--namespace")
    parser.add_argument("--statefulset")
    parser.add_argument("--kubeconfig")
    parser.add_argument("--context")
    parser.add_argument("--schema-file", default="infra/kafka/schemas/customer_feature_updates-value.schema.json")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--evidence")
    return parser.parse_args()


def _gke_runner(command: list[str]) -> object:
    """Return the strict describe contract while preserving checked create failures."""

    is_describe = "describe" in command
    completed = subprocess.run(command, check=not is_describe, text=True, capture_output=is_describe)
    if not is_describe:
        return completed
    if completed.returncode != 0:
        diagnostic = f"{completed.stdout or ''}\n{completed.stderr or ''}"
        if re.search(r"(?:TOPIC_NOT_FOUND|topic[-_ ]not[-_ ]found)", diagnostic, re.IGNORECASE):
            return {"exists": False}
        raise ValueError(f"rpk topic describe failed with return code {completed.returncode}")
    if not isinstance(completed.stdout, str) or not completed.stdout.strip():
        raise ValueError("rpk describe must return valid JSON")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("rpk describe must return valid JSON") from error
    if isinstance(payload, list):
        if len(payload) != 1:
            raise ValueError("rpk describe must return exactly one topic")
        record = payload[0]
    else:
        record = payload
    if not isinstance(record, Mapping):
        raise ValueError("rpk describe did not return a JSON object")

    partitions_value = record.get("partitions")
    if isinstance(partitions_value, list):
        if not partitions_value or not all(isinstance(partition, Mapping) for partition in partitions_value):
            raise ValueError("rpk describe partitions must be a non-empty uniform list")
        replica_counts: list[int] = []
        for partition in partitions_value:
            replicas = partition.get("replicas")
            if not isinstance(replicas, list) or not replicas or not all(isinstance(replica, int) and not isinstance(replica, bool) for replica in replicas):
                raise ValueError("rpk describe partitions have invalid replicas")
            replica_counts.append(len(replicas))
        if len(set(replica_counts)) != 1:
            raise ValueError("rpk describe partitions have inconsistent replicas")
        partitions = len(partitions_value)
        replication_factor = replica_counts[0]
        declared_factor = record.get("replication_factor", record.get("replicas"))
        if declared_factor is not None and (
            not isinstance(declared_factor, int)
            or isinstance(declared_factor, bool)
            or declared_factor != replication_factor
        ):
            raise ValueError("rpk describe replication factor is inconsistent")
    elif isinstance(partitions_value, int) and not isinstance(partitions_value, bool) and partitions_value > 0:
        partitions = partitions_value
        replication_factor = record.get("replication_factor", record.get("replicas"))
        if not isinstance(replication_factor, int) or isinstance(replication_factor, bool) or replication_factor <= 0:
            raise ValueError("rpk describe replication factor is invalid")
    else:
        raise ValueError("rpk describe partitions are invalid")

    raw_configs = record.get("configs", record.get("config"))
    if isinstance(raw_configs, Mapping):
        configs = {}
        for key, value in raw_configs.items():
            if not isinstance(key, str) or not key or value is None or isinstance(value, (bool, Mapping, list)):
                raise ValueError("rpk describe configs are invalid")
            configs[key] = str(value)
    elif isinstance(raw_configs, list):
        configs = {}
        for item in raw_configs:
            if not isinstance(item, Mapping):
                raise ValueError("rpk describe configs are invalid")
            key = item.get("key", item.get("name"))
            value = item.get("value")
            if not isinstance(key, str) or not key or value is None or isinstance(value, (bool, Mapping, list)) or key in configs:
                raise ValueError("rpk describe configs are invalid")
            configs[key] = str(value)
    else:
        raise ValueError("rpk describe configs are invalid")
    return {
        "exists": True,
        "partitions": partitions,
        "replication_factor": replication_factor,
        "configs": configs,
    }


def main() -> None:
    args = parse_args()
    if args.execution == "gke-rpk" and (not args.strict or not args.namespace or not args.statefulset or not args.kubeconfig or not args.context):
        raise SystemExit("gke-rpk requires --strict --namespace --statefulset --kubeconfig and --context")
    schema_path = Path(args.schema_file)
    if args.strict:
        _validate_schema(schema_path)
    bootstrap_topics(
        runner=_gke_runner if args.execution == "gke-rpk" else lambda command: subprocess.run(command, check=True),
        bootstrap_server=args.bootstrap_server,
        topics_file=args.topics_file,
        execution=args.execution,
        namespace=args.namespace,
        statefulset=args.statefulset,
        kubeconfig=args.kubeconfig,
        context=args.context,
    )
    if args.evidence:
        Path(args.evidence).write_text(json.dumps({"schema": str(schema_path), "execution": args.execution}, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
