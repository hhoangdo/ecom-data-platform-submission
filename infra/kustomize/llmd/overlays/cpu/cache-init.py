#!/usr/bin/env python3
"""Fetch and safely unpack the immutable primary model archive into /models."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath


MODEL_CACHE_FILE_SHA256 = "67609f908cf96cfb28d0910411a55dc8cb0670766dd17feb2405cb951ebf2dba"
MANIFEST_SHA256 = "9876ddc56b98e1df20888e29986ea7eabbbc3a81764421283b461883f8a77d57"
PRIMARY_REVISION = "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
MAX_CACHE_BYTES = 5 * 1024**3
MAX_EXPANDED_MODEL_BYTES = 5 * 1024**3
MANIFEST_PATH = Path("/etc/edai2-model-cache/model_cache.json")
MODEL_ROOT = Path("/models")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def validate_archive_members(archive: Path) -> str:
    """Reject unsafe entries and oversized expanded content before extraction."""
    root = None
    expanded_size = 0
    found = False
    with tarfile.open(archive, mode="r|zst", stream=True) as tar:
        for member in tar:
            found = True
            path = PurePosixPath(member.name)
            parts = path.parts
            if path.is_absolute() or not parts or ".." in parts:
                raise ValueError(f"unsafe archive path: {member.name}")
            if root is None:
                root = parts[0]
            if parts[0] != root:
                raise ValueError("model archive has more than one top-level directory")
            if not member.isfile() and not member.isdir():
                raise ValueError(f"unsupported archive entry type: {member.name}")
            if member.isfile():
                expanded_size += member.size
                if expanded_size > MAX_EXPANDED_MODEL_BYTES:
                    raise ValueError("expanded model archive exceeds the 5 GiB cache cap")
    if not found:
        raise ValueError("empty or malformed model archive")
    return str(root)


def extract_validated_archive(archive: Path, destination: Path, expected_root: str) -> None:
    """Stream the validated archive again and extract only data-filtered entries."""
    root = None
    expanded_size = 0
    found = False
    with tarfile.open(archive, mode="r|zst", stream=True) as tar:
        for member in tar:
            found = True
            path = PurePosixPath(member.name)
            parts = path.parts
            if path.is_absolute() or not parts or ".." in parts:
                raise ValueError(f"unsafe archive path: {member.name}")
            if root is None:
                root = parts[0]
            if parts[0] != root or root != expected_root:
                raise ValueError("model archive root changed after validation")
            if not member.isfile() and not member.isdir():
                raise ValueError(f"unsupported archive entry type: {member.name}")
            if member.isfile():
                expanded_size += member.size
                if expanded_size > MAX_EXPANDED_MODEL_BYTES:
                    raise ValueError("expanded model archive exceeds the 5 GiB cache cap")
            tar.extract(member, path=destination, filter="data")
    if not found:
        raise ValueError("empty or malformed model archive")


def model_staging_directory() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix="edai2-model-cache-", dir=MODEL_ROOT)


def promote_model_directory(extracted: Path, destination: Path) -> None:
    """Atomically promote an extracted model staged on the model volume."""
    if destination.exists():
        shutil.rmtree(destination)
    os.replace(extracted, destination)


def write_cache_provenance(manifest_bytes: bytes, entry: dict) -> None:
    """Record only immutable, non-secret source hashes for the verified cache."""
    payload = {
        "schema_version": 1,
        "manifest_file_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "init_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "objects": [{key: entry[key] for key in ("name", "generation", "bytes", "sha256", "revision")}],
    }
    target = MODEL_ROOT / ".edai2-cache-provenance.json"
    temporary = MODEL_ROOT / ".edai2-cache-provenance.json.tmp"
    temporary.write_bytes(canonical(payload) + b"\n")
    os.replace(temporary, target)


def metadata_token() -> str:
    request = urllib.request.Request(
        "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
        headers={"Metadata-Flavor": "Google"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        token = json.load(response).get("access_token")
    if not token:
        raise RuntimeError("metadata server returned no access token")
    return token


def download_archive(bucket: str, prefix: str, entry: dict, destination: Path, token: str) -> None:
    object_name = f"{prefix}{entry['name']}.tar.zst"
    query = urllib.parse.urlencode({"alt": "media", "generation": entry["generation"]})
    url = (
        "https://storage.googleapis.com/download/storage/v1/b/"
        + urllib.parse.quote(bucket, safe="")
        + "/o/"
        + urllib.parse.quote(object_name, safe="")
        + "?"
        + query
    )
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as target:
        generation = response.headers.get("x-goog-generation")
        if generation and generation != entry["generation"]:
            raise RuntimeError("GCS returned a different model-cache generation")
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > int(entry["bytes"]):
                raise RuntimeError("downloaded model archive exceeds its pinned size")
            digest.update(chunk)
            target.write(chunk)
    if size != int(entry["bytes"]) or digest.hexdigest() != entry["sha256"]:
        raise RuntimeError("model-cache archive size or SHA-256 does not match its pin")


def verify_manifest(manifest: dict) -> tuple[str, str, dict]:
    if not isinstance(manifest.get("objects"), list):
        raise ValueError("model-cache manifest has no object list")
    if hashlib.sha256(canonical({"objects": manifest["objects"]})).hexdigest() != MANIFEST_SHA256:
        raise ValueError("model-cache manifest SHA-256 does not match its pin")
    if int(manifest.get("total_bytes", MAX_CACHE_BYTES + 1)) > MAX_CACHE_BYTES:
        raise ValueError("model-cache manifest exceeds the 5 GiB cap")
    pins = {item.get("name"): item for item in manifest.get("pins", [])}
    pin = pins.get("primary", {})
    if pin.get("model") != "Qwen/Qwen2.5-1.5B-Instruct" or pin.get("revision") != PRIMARY_REVISION:
        raise ValueError("model-cache manifest does not pin the primary model revision")
    if pin.get("fallback") != "forbidden":
        raise ValueError("Hub fallback must remain forbidden")
    entry = next((item for item in manifest["objects"] if item.get("name") == "primary"), None)
    if entry is None or entry.get("revision") != PRIMARY_REVISION:
        raise ValueError("model-cache manifest has no matching primary archive")
    return manifest["gcs_uri"], PRIMARY_REVISION, entry


def run() -> None:
    manifest_bytes = MANIFEST_PATH.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != MODEL_CACHE_FILE_SHA256:
        raise ValueError("model-cache evidence file SHA-256 does not match its pin")
    manifest = json.loads(manifest_bytes)
    gcs_uri, _, entry = verify_manifest(manifest)
    parsed = urllib.parse.urlparse(gcs_uri)
    if parsed.scheme != "gs" or not parsed.netloc:
        raise ValueError("model-cache URI must be a GCS bucket URI")
    bucket, prefix = parsed.netloc, parsed.path.lstrip("/").rstrip("/") + "/"
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    model_dir = MODEL_ROOT / "primary"
    if model_dir.exists():
        shutil.rmtree(model_dir)
    with model_staging_directory() as temp:
        archive = Path(temp) / "primary.tar.zst"
        download_archive(bucket, prefix, entry, archive, metadata_token())
        root = validate_archive_members(archive)
        extract_root = Path(temp) / "extract"
        extract_root.mkdir()
        extract_validated_archive(archive, extract_root, root)
        extracted = extract_root / root
        if not extracted.is_dir() or any(path.is_symlink() for path in extracted.rglob("*")):
            raise RuntimeError("model archive did not produce one safe model directory")
        promote_model_directory(extracted, model_dir)
    write_cache_provenance(manifest_bytes, entry)


if __name__ == "__main__":
    run()
