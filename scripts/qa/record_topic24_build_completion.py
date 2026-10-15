"""Write a sanitized, source-bound read-back for the Topic 24 builder Job."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

from capture_edai2_evidence import verify_registry_platform_provenance


ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT / "tmp/edai2-gcp/topic24-finalize"
OUTPUT = SCRATCH / "remote-build-output"


def _time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("builder completion timestamp is missing")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("builder completion timestamp has no timezone")
    return parsed


def sanitized_completion(raw: object, *, root: Path = ROOT) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise ValueError("builder Job read-back is malformed")
    metadata, status = raw.get("metadata"), raw.get("status")
    if not isinstance(metadata, dict) or not isinstance(status, dict):
        raise ValueError("builder Job completion status is missing")
    conditions = status.get("conditions")
    complete = [item for item in conditions if isinstance(item, dict) and item.get("type") == "Complete" and item.get("status") == "True"] if isinstance(conditions, list) else []
    if metadata.get("name") != "topic24-substrate-api-build" or not isinstance(metadata.get("uid"), str) or len(complete) != 1 or status.get("succeeded") != 1:
        raise ValueError("builder Job is not uniquely Complete")
    started, completed = _time(status.get("startTime")), _time(status.get("completionTime"))
    transitioned = _time(complete[0].get("lastTransitionTime"))
    if completed <= started or transitioned < started or transitioned > completed:
        raise ValueError("builder Job completion timestamps are inconsistent")

    scratch = root / "tmp/edai2-gcp/topic24-finalize"
    output = scratch / "remote-build-output"
    build = json.loads((scratch / "remote-build-provenance.json").read_text(encoding="utf-8"))
    job_manifest_path = scratch / "topic24-builder-job.yaml"
    expected_job_manifest = yaml.safe_load(job_manifest_path.read_text(encoding="utf-8"))
    expected_builder = expected_job_manifest["spec"]["template"]["spec"]["containers"][0]
    actual_builder_spec = raw.get("spec", {}).get("template", {}).get("spec", {})
    actual_containers = actual_builder_spec.get("containers", [])
    if len(actual_containers) != 1 or not isinstance(actual_containers[0], dict):
        raise ValueError("builder container read-back is ambiguous")
    actual_builder = actual_containers[0]
    expected_command = expected_builder.get("command", []) + expected_builder.get("args", [])
    actual_command = actual_builder.get("command", []) + actual_builder.get("args", [])
    expected_env = {item["name"]: item["value"] for item in expected_builder.get("env", []) if item.get("name") in {"BUILD_TAG", "SOURCE_BUNDLE_SHA256", "KO_DOCKER_REPO"}}
    actual_env = {item["name"]: item.get("value") for item in actual_builder.get("env", []) if item.get("name") in {"BUILD_TAG", "SOURCE_BUNDLE_SHA256", "KO_DOCKER_REPO"}}
    command_hash = hashlib.sha256(json.dumps(actual_command, separators=(",", ":")).encode()).hexdigest()
    expected_command_hash = hashlib.sha256(json.dumps(expected_command, separators=(",", ":")).encode()).hexdigest()
    if (actual_builder.get("image") != expected_builder.get("image") or actual_command != expected_command
            or actual_env != expected_env or actual_builder_spec.get("serviceAccountName") != "topic24-builder"):
        raise ValueError("live builder Job differs from the pinned local manifest")
    source_manifest_path = scratch / "substrate-source-topic24-finalize.manifest.json"
    bundle_path = scratch / "substrate-source-topic24-finalize.tar.gz"
    source_manifest_hash = hashlib.sha256(source_manifest_path.read_bytes()).hexdigest()
    bundle_hash = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    if (build.get("source_manifest_sha256") != source_manifest_hash or build.get("source_bundle_sha256") != bundle_hash
            or source_manifest_path.is_file() is False):
        raise ValueError("prepared builder source provenance is stale")
    image_lines = [line.strip() for line in (output / "image-refs.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
    platform_image_digest = verify_registry_platform_provenance(output / "image-platform-provenance.json", image_lines[0]) if len(image_lines) == 1 else ""
    inputs_path = output / "verified-inputs.sha256"
    inputs = inputs_path.read_text(encoding="utf-8")
    target = build.get("target", {})
    image_repo = f"{target.get('region')}-docker.pkg.dev/{target.get('project_id')}/{target.get('artifact_registry_repository')}/{target.get('image_name')}"
    expected_prefix = f"{image_repo}:{target.get('tag')}@sha256:"
    if (len(image_lines) != 1 or not image_lines[0].startswith(expected_prefix)
            or not re.search(rf"(?m)^{re.escape(bundle_hash)}\s+.*substrate-source-topic24-finalize\.tar\.gz$", inputs)
            or command_hash != expected_command_hash):
        raise ValueError("builder outputs do not match the prepared source bundle")
    if hashlib.sha256(inputs_path.read_bytes()).hexdigest() == "":
        raise ValueError("verified build inputs are unavailable")
    return {
        "schema_version": 1,
        "job": {"name": metadata["name"], "uid": metadata["uid"], "succeeded": 1,
                "start_time": status["startTime"], "completion_time": status["completionTime"]},
        "complete_condition": {"type": "Complete", "status": "True", "last_transition_time": complete[0]["lastTransitionTime"]},
        "builder": {"image": actual_builder["image"], "command_sha256": command_hash,
                    "source_bundle_sha256": actual_env["SOURCE_BUNDLE_SHA256"], "build_tag": actual_env["BUILD_TAG"],
                    "ko_docker_repo": actual_env["KO_DOCKER_REPO"],
                    "job_manifest_sha256": hashlib.sha256(job_manifest_path.read_bytes()).hexdigest()},
        "source_bundle_sha256": bundle_hash,
        "source_manifest_sha256": source_manifest_hash,
        "image_ref": image_lines[0],
        "platform_image_digest": platform_image_digest,
        "verified_archive": {"sha256": bundle_hash, "source_manifest_sha256": source_manifest_hash, "command_exit_code": 0},
        "verified_inputs_sha256": hashlib.sha256(inputs_path.read_bytes()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(OUTPUT / "job-completion.json"))
    args = parser.parse_args()
    try:
        raw = json.load(sys.stdin)
        proof = sanitized_completion(raw)
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        parser.error("builder Job completion read-back could not be verified")
    print(json.dumps({"recorded": target.name}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
