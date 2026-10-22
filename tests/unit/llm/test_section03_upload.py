from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType

import pytest
from google.api_core.exceptions import NotFound, PreconditionFailed

from vina_bim_shop.llm.section03_ingestion import Section03Loader


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "evidence" / "03_data_generator_improvement" / "section03_manifest.json"
PREFIX = "gs://edai2-data-test/section03/f6d07b09a12107b19a4bfe45a7bda6f87ab9356021a90e2ec6f02f63b5602640/"


def _load_script() -> ModuleType:
    path = ROOT / "scripts" / "feast" / "load_section03.py"
    spec = importlib.util.spec_from_file_location("section03_upload_cli", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeBlob:
    def __init__(self, bucket: "FakeBucket", name: str) -> None:
        self._bucket = bucket
        self.name = name
        self.generation: int | None = None
        self.size = 0

    def reload(self) -> None:
        entry = self._bucket.objects.get(self.name)
        if entry is None:
            raise NotFound(self.name)
        data, generation = entry
        self.generation = generation
        self.size = len(data)

    def upload_from_filename(self, filename: str, if_generation_match: int | None = None) -> None:
        if if_generation_match == 0 and self.name in self._bucket.objects:
            raise PreconditionFailed("object already exists")
        self._bucket.uploads.append(self.name)
        data = Path(filename).read_bytes()
        self._bucket.generations += 1
        self._bucket.objects[self.name] = (data, self._bucket.generations)

    def download_as_bytes(self) -> bytes:
        entry = self._bucket.objects.get(self.name)
        if entry is None:
            raise NotFound(self.name)
        return entry[0]


class FakeBucket:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, int]] = {}
        self.generations = 0
        self.uploads: list[str] = []

    def blob(self, name: str) -> FakeBlob:
        return FakeBlob(self, name)


class FakeClient:
    def __init__(self) -> None:
        self.buckets: dict[str, FakeBucket] = {}

    def bucket(self, name: str) -> FakeBucket:
        return self.buckets.setdefault(name, FakeBucket())


def _manifest_paths(manifest: dict) -> set[str]:
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


def test_upload_section03_uploads_every_manifest_path_and_verifies_read_back(tmp_path: Path) -> None:
    script = _load_script()
    verified = Section03Loader(MANIFEST).verify_only()
    output = tmp_path / "upload.json"
    client = FakeClient()

    evidence = script.upload_section03(
        verified, gcs_prefix=PREFIX, client=client, output=output, verify=True
    )

    assert evidence["uploaded"] is True
    assert evidence["verified"] is True
    assert evidence["bundle_id"] == verified.manifest["bundle_id"]
    assert evidence["manifest_sha256"] == verified.manifest_sha256
    assert evidence["reasons"] == []
    assert output.exists()
    stored = client.bucket("edai2-data-test")
    assert all(name.startswith("section03/") for name in stored.objects)
    expected = _manifest_paths(verified.manifest)
    uploaded = {item["path"] for item in evidence["objects"]}
    assert expected == uploaded
    for item in evidence["objects"]:
        assert item["generation"]
        assert item["sha256"]
        assert item["size"] > 0


def test_upload_section03_reuses_identical_objects_without_new_generation(tmp_path: Path) -> None:
    script = _load_script()
    verified = Section03Loader(MANIFEST).verify_only()
    client = FakeClient()
    first = script.upload_section03(
        verified, gcs_prefix=PREFIX, client=client, output=tmp_path / "one.json"
    )
    uploads_after_first = len(client.bucket("edai2-data-test").uploads)
    second = script.upload_section03(
        verified, gcs_prefix=PREFIX, client=client, output=tmp_path / "two.json"
    )
    assert first["objects"] == second["objects"]
    assert len(client.bucket("edai2-data-test").uploads) == uploads_after_first


def test_upload_section03_rejects_same_key_content_mismatch(tmp_path: Path) -> None:
    script = _load_script()
    verified = Section03Loader(MANIFEST).verify_only()
    client = FakeClient()
    script.upload_section03(verified, gcs_prefix=PREFIX, client=client, output=tmp_path / "one.json")
    bucket = client.bucket("edai2-data-test")
    key = next(name for name in bucket.objects if name.endswith("/ml_customer_label.csv"))
    bucket.objects[key] = (b"tampered", bucket.generations)

    with pytest.raises(ValueError, match="mismatch"):
        script.upload_section03(verified, gcs_prefix=PREFIX, client=client, output=tmp_path / "two.json")


def test_upload_section03_rejects_non_gcs_prefix(tmp_path: Path) -> None:
    script = _load_script()
    verified = Section03Loader(MANIFEST).verify_only()
    with pytest.raises(ValueError, match="gs://"):
        script.upload_section03(
            verified, gcs_prefix="section03/", client=FakeClient(), output=tmp_path / "x.json"
        )


def test_cli_upload_only_writes_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = _load_script()
    client = FakeClient()
    monkeypatch.setattr(script, "_storage_client", lambda: client)
    output = tmp_path / "upload.json"

    code = script.main(
        [
            "--manifest",
            str(MANIFEST),
            "--strict",
            "--upload-only",
            "--verify-upload",
            "--gcs-prefix",
            PREFIX,
            "--evidence",
            str(output),
        ]
    )

    assert code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "verified"
    assert payload["uploaded"] is True
    assert payload["object_count"] > 0
