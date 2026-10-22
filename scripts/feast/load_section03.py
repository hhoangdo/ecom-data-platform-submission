"""Strict Section 03 verification and explicitly owned activation CLI."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vina_bim_shop.llm.section03_ingestion import (
    Section03ActivationError,
    Section03ActivationReport,
    Section03Loader,
    VerifiedSection03,
)


def _load_adapter_factory(reference: str) -> Callable[[], Any]:
    """Resolve a caller-owned adapter factory without constructing a runtime by default."""

    module_name, separator, attribute = reference.partition(":")
    if not module_name or not separator or not attribute:
        raise ValueError("adapter factory must use module:callable syntax")
    factory = getattr(importlib.import_module(module_name), attribute, None)
    if not callable(factory):
        raise ValueError("adapter factory must resolve to a callable")
    return factory


def _payload(
    verified: VerifiedSection03,
    *,
    status: str,
    before_manifest_sha256: str | None,
    after_manifest_sha256: str | None,
    feast_fingerprint: str | None,
    valkey_fingerprint: str | None,
    rollback_status: str,
    error: str | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "before_manifest_sha256": before_manifest_sha256,
        "after_manifest_sha256": after_manifest_sha256,
        "manifest_sha256": verified.manifest_sha256,
        "training_count": verified.training_count,
        "health_count": verified.health_count,
        "feast_fingerprint": feast_fingerprint,
        "valkey_fingerprint": valkey_fingerprint,
        "rollback_status": rollback_status,
        "error": error,
    }


def _report_payload(verified: VerifiedSection03, report: Section03ActivationReport) -> dict[str, object]:
    return _payload(
        verified,
        status=report.status,
        before_manifest_sha256=report.previous_manifest_sha256,
        after_manifest_sha256=report.active_manifest_sha256,
        feast_fingerprint=report.feast_fingerprint,
        valkey_fingerprint=report.valkey_fingerprint,
        rollback_status=report.rollback_status,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_relative_paths(manifest: dict[str, Any]) -> set[str]:
    paths: set[str] = {"manifest.json"}

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "path" and isinstance(item, str):
                    paths.add(item)
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(manifest)
    snapshot = manifest.get("config_snapshot")
    if isinstance(snapshot, str):
        paths.add(snapshot)
    return paths


def _bundle_root(verified: VerifiedSection03) -> Path:
    # training_path is <root>/runs/<bundle_id>/ml_customer_purchase_training.csv
    return verified.training_path.parents[2].resolve()


def _upload_files(verified: VerifiedSection03) -> list[tuple[str, Path]]:
    root = _bundle_root(verified)
    manifest_path = root / "section03_manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"Section 03 manifest is missing: {manifest_path}")
    files: list[tuple[str, Path]] = [("manifest.json", manifest_path)]
    for relative in sorted(_manifest_relative_paths(verified.manifest)):
        if relative == "manifest.json":
            continue
        candidate = (root / relative).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError(f"Section 03 path escapes the bundle root: {relative}")
        if not candidate.is_file():
            raise ValueError(f"Section 03 artifact is missing: {relative}")
        files.append((relative.replace("\\", "/"), candidate))
    return files


def _parse_gcs_prefix(gcs_prefix: str) -> tuple[str, str]:
    if not isinstance(gcs_prefix, str) or not gcs_prefix.startswith("gs://"):
        raise ValueError("GCS prefix must start with gs://")
    remainder = gcs_prefix[5:]
    bucket, separator, prefix = remainder.partition("/")
    if not bucket or not separator:
        raise ValueError("GCS prefix must include a bucket and prefix")
    normalized = prefix.strip("/")
    if not normalized:
        raise ValueError("GCS prefix must not be the bucket root")
    return bucket, normalized + "/"


def _storage_client() -> Any:
    from google.cloud import storage

    return storage.Client()


def _write_json(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def upload_section03(
    verified: VerifiedSection03,
    *,
    gcs_prefix: str,
    client: Any,
    output: Path | None = None,
    verify: bool = True,
) -> dict[str, Any]:
    """Create-only upload the verified bundle and prove every object by SHA-256 read-back."""

    from google.api_core.exceptions import NotFound

    bucket_name, prefix = _parse_gcs_prefix(gcs_prefix)
    bucket = client.bucket(bucket_name)
    objects: list[dict[str, Any]] = []
    created = 0
    reused = 0
    for relative, local_path in _upload_files(verified):
        blob = bucket.blob(prefix + relative)
        local_sha256 = _sha256_file(local_path)
        try:
            blob.reload()
        except NotFound:
            blob.upload_from_filename(str(local_path), if_generation_match=0)
            blob.reload()
            created += 1
        else:
            reused += 1
        if verify:
            remote = blob.download_as_bytes()
            remote_sha256 = hashlib.sha256(remote).hexdigest()
            if remote_sha256 != local_sha256:
                raise ValueError(
                    f"GCS object content mismatch for {relative}: "
                    f"local={local_sha256} remote={remote_sha256}"
                )
        objects.append(
            {
                "path": relative,
                "gcs_uri": f"gs://{bucket_name}/{prefix}{relative}",
                "generation": str(blob.generation),
                "size": int(blob.size),
                "sha256": local_sha256,
            }
        )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": "verified",
        "uploaded": True,
        "verified": bool(verify),
        "bundle_id": verified.manifest["bundle_id"],
        "manifest_sha256": verified.manifest_sha256,
        "gcs_prefix": f"gs://{bucket_name}/{prefix}",
        "objects": sorted(objects, key=lambda item: item["path"]),
        "object_count": len(objects),
        "total_bytes": sum(int(item["size"]) for item in objects),
        "created_count": created,
        "reused_count": reused,
        "uploaded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "reasons": [],
        "defect_for_owning_topic": None,
    }
    _write_json(output, payload)
    return payload


def main(
    argv: Sequence[str] | None = None,
    *,
    adapter_factory_resolver: Callable[[str], Callable[[], Any]] = _load_adapter_factory,
) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--strict", action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify-only", action="store_true")
    mode.add_argument("--upload-only", action="store_true")
    mode.add_argument("--activate", action="store_true")
    parser.add_argument("--adapter-factory")
    parser.add_argument("--gcs-prefix", required=False, default=None)
    parser.add_argument("--verify-upload", action="store_true")
    parser.add_argument("--if-generation-match-zero", action="store_true")
    parser.add_argument("--defer-activation-to-release", default=None)
    parser.add_argument("--evidence", default=None)
    args = parser.parse_args(argv)
    if not args.strict:
        parser.error("--strict is required")
    if args.defer_activation_to_release not in (None, "drift"):
        parser.error("--defer-activation-to-release only accepts drift")

    verified = Section03Loader(args.manifest).verify_only()
    if args.upload_only:
        if not args.gcs_prefix:
            parser.error("--upload-only requires --gcs-prefix")
        output = Path(args.evidence) if args.evidence else None
        try:
            evidence = upload_section03(
                verified,
                gcs_prefix=args.gcs_prefix,
                client=_storage_client(),
                output=output,
                verify=args.verify_upload,
            )
        except Exception as error:
            failure = {
                **_payload(
                    verified,
                    status="failed",
                    before_manifest_sha256=None,
                    after_manifest_sha256=None,
                    feast_fingerprint=None,
                    valkey_fingerprint=None,
                    rollback_status="not_attempted",
                    error=str(error),
                ),
                "uploaded": False,
                "verified": False,
                "gcs_prefix": args.gcs_prefix,
                "reasons": [str(error)],
            }
            _write_json(output, failure)
            print(json.dumps(failure, sort_keys=True))
            return 2
        print(json.dumps(evidence, sort_keys=True))
        return 0
    if args.verify_only:
        print(json.dumps(_payload(
            verified,
            status="verified",
            before_manifest_sha256=None,
            after_manifest_sha256=verified.manifest_sha256,
            feast_fingerprint=None,
            valkey_fingerprint=None,
            rollback_status="not_applicable",
        ), sort_keys=True))
        return 0
    if not args.adapter_factory:
        print(json.dumps(_payload(
            verified,
            status="failed",
            before_manifest_sha256=None,
            after_manifest_sha256=None,
            feast_fingerprint=None,
            valkey_fingerprint=None,
            rollback_status="not_attempted",
            error="--adapter-factory is required for --activate",
        ), sort_keys=True))
        return 2
    try:
        adapter = adapter_factory_resolver(args.adapter_factory)()
        report = asyncio.run(Section03Loader(args.manifest).activate(adapter))
    except Section03ActivationError as error:
        print(json.dumps(_payload(
            verified,
            status="failed",
            before_manifest_sha256=error.before_manifest_sha256,
            after_manifest_sha256=error.after_manifest_sha256,
            feast_fingerprint=error.feast_fingerprint,
            valkey_fingerprint=error.valkey_fingerprint,
            rollback_status=error.rollback_status,
            error=str(error),
        ), sort_keys=True))
        return 1
    except Exception as error:
        print(json.dumps(_payload(
            verified,
            status="failed",
            before_manifest_sha256=None,
            after_manifest_sha256=None,
            feast_fingerprint=None,
            valkey_fingerprint=None,
            rollback_status="not_attempted",
            error=str(error),
        ), sort_keys=True))
        return 2
    print(json.dumps(_report_payload(verified, report), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
