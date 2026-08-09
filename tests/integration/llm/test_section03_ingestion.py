from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
from types import ModuleType
from typing import Any

import pytest

from vina_bim_shop.llm.section03_ingestion import (
    Section03ActivationError,
    Section03Loader,
    Section03ManifestReader,
)
from vina_bim_shop.llm.adapters.feast_postgres import FeastPostgresAdapter
from vina_bim_shop.llm.adapters.feast_postgres import Section03AdapterError


REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST = REPO_ROOT / "evidence" / "03_data_generator_improvement" / "section03_manifest.json"
MANIFEST_SHA256 = "af7189d00a187e539bb777d89111d2860a97822f34c2c911adc3eadf6166f8ad"


def _strict_verifier() -> ModuleType:
    path = REPO_ROOT / "scripts" / "generate" / "verify_section03_manifest.py"
    spec = importlib.util.spec_from_file_location("topic12_section03_verifier", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _loader_cli() -> ModuleType:
    path = REPO_ROOT / "scripts" / "feast" / "load_section03.py"
    spec = importlib.util.spec_from_file_location("topic12_load_section03", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copied_manifest(tmp_path: Path) -> Path:
    target = tmp_path / "section03_evidence"
    shutil.copytree(MANIFEST.parent, target)
    return target / MANIFEST.name


def _manifest_document(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_manifest(path: Path, document: dict[str, object]) -> None:
    path.write_text(json.dumps(document), encoding="utf-8")


class _SqlCursor:
    def __init__(self, connection: "_SqlConnection") -> None:
        self._connection = connection

    async def fetchall(self) -> list[dict[str, Any]]:
        return self._connection.rows.pop(0) if self._connection.rows else []


class _SqlTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_args: object) -> None:
        return None


class _SqlConnection:
    def __init__(self, rows: list[list[dict[str, Any]]] | None = None) -> None:
        self.rows = rows or []
        self.statements: list[tuple[str, Any]] = []

    def transaction(self) -> _SqlTransaction:
        return _SqlTransaction()

    async def execute(self, sql: str, parameters: Any = None) -> _SqlCursor:
        self.statements.append((sql, parameters))
        return _SqlCursor(self)

    async def close(self) -> None:
        return None


class FakeActivationAdapter:
    def __init__(
        self,
        *,
        active: str = "previous",
        feast: str = "previous",
        valkey: str = "previous",
        fail_feast: bool = False,
        fail_valkey: bool = False,
        fail_restore: bool = False,
        readback_mismatch: bool = False,
    ) -> None:
        self.active = active
        self.feast = feast
        self.valkey = valkey
        self.fail_feast = fail_feast
        self.fail_valkey = fail_valkey
        self.fail_restore = fail_restore
        self.readback_mismatch = readback_mismatch
        self.staged: str | None = None
        self.calls: list[str] = []

    async def fingerprint(self) -> tuple[str | None, str, str]:
        feast = "mismatch" if self.readback_mismatch and self.active != "previous" else self.feast
        return (self.active, "feast:" + feast, "valkey:" + self.valkey)

    async def stage(self, verified: object) -> None:
        self.staged = verified.manifest_sha256
        self.calls.append("stage")

    async def staged_section03_manifest_hash(self, manifest_sha256: str) -> str | None:
        self.calls.append("staged")
        return self.staged if manifest_sha256 == self.staged else None

    async def switch_active(self, manifest_sha256: str) -> str | None:
        self.calls.append("switch")
        previous, self.active = self.active, manifest_sha256
        return previous

    async def apply_feast(self, manifest_sha256: str | None) -> None:
        self.calls.append("feast:" + str(manifest_sha256))
        if self.fail_feast and manifest_sha256 != "previous":
            raise RuntimeError("feast failed")
        self.feast = str(manifest_sha256)

    async def materialize_valkey(self, manifest_sha256: str | None) -> None:
        self.calls.append("valkey:" + str(manifest_sha256))
        if self.fail_valkey and manifest_sha256 != "previous":
            raise RuntimeError("valkey failed")
        self.valkey = str(manifest_sha256)

    async def restore_active(self, manifest_sha256: str | None) -> None:
        self.calls.append("restore")
        if self.fail_restore:
            raise RuntimeError("restore failed")
        self.active = manifest_sha256


def test_verify_only_returns_hash_bound_bundle_without_activation() -> None:
    loader = Section03Loader(MANIFEST)
    verified = loader.verify_only()
    assert verified.manifest_sha256 == "af7189d00a187e539bb777d89111d2860a97822f34c2c911adc3eadf6166f8ad"
    assert verified.training_count == 11996
    assert verified.health_count == 22


def test_verify_only_rejects_wrong_ordered_label_columns(tmp_path: Path) -> None:
    manifest = tmp_path / "section03_manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        Section03Loader(manifest).verify_only()


def test_strict_verifier_accepts_the_real_canonical_manifest() -> None:
    manifest = _strict_verifier().verify_manifest(MANIFEST, strict=True)
    assert manifest["section"] == "03_data_generator_improvement"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda document: document["artifacts"]["labels"].__setitem__("sha256", "0" * 64),
            "hash.*labels",
        ),
        (
            lambda document: document["artifacts"]["labels"].__setitem__("row_count", 1),
            "metadata.*labels",
        ),
        (
            lambda document: document["artifacts"]["labels"].__setitem__("columns", ["label", "id"]),
            "metadata.*labels",
        ),
        (
            lambda document: document.__setitem__("section", "wrong-section"),
            "section",
        ),
    ],
)
def test_strict_verifier_names_the_tampered_artifact_or_expectation(
    tmp_path: Path, mutation: object, expected: str
) -> None:
    manifest_path = _copied_manifest(tmp_path)
    document = _manifest_document(manifest_path)
    mutation(document)
    _write_manifest(manifest_path, document)
    with pytest.raises(ValueError, match=expected):
        _strict_verifier().verify_manifest(manifest_path, strict=True)


def test_strict_verifier_names_a_missing_referenced_artifact(tmp_path: Path) -> None:
    manifest_path = _copied_manifest(tmp_path)
    document = _manifest_document(manifest_path)
    label_path = manifest_path.parent / document["artifacts"]["labels"]["path"]
    label_path.unlink()
    with pytest.raises((FileNotFoundError, ValueError), match="labels|artifact|No such file"):
        _strict_verifier().verify_manifest(manifest_path, strict=True)


@pytest.mark.asyncio
async def test_postgres_adapter_stages_all_health_columns_and_reads_injected_fingerprints() -> None:
    verified = Section03Loader(MANIFEST).verify_only()
    consumer = verified.manifest["consumer_contract"]
    metadata = {
        "manifest_sha256": MANIFEST_SHA256,
        "label_sha256": consumer["label"]["sha256"],
        "training_sha256": consumer["training_join"]["sha256"],
        "health_sha256": consumer["feature_health"]["sha256"],
        "feature_cutoff": consumer["training_join"]["feature_cutoff_ts"],
        "baseline_date": consumer["feature_health"]["baseline_date"],
        "training_count": verified.training_count,
        "health_count": verified.health_count,
    }
    connection = _SqlConnection(rows=[[metadata], [{"row_count": verified.training_count}], [{"row_count": verified.health_count}], [{"manifest_sha256": MANIFEST_SHA256}], [{"manifest_sha256": "previous"}]])
    adapter = FeastPostgresAdapter(
        connection_factory=lambda: connection,
        feast_fingerprint=lambda: "feast:external",
        valkey_fingerprint=lambda: "valkey:external",
    )
    await adapter.stage(verified)
    assert await adapter.staged_section03_manifest_hash(verified.manifest_sha256) == MANIFEST_SHA256
    assert await adapter.fingerprint() == ("previous", "feast:external", "valkey:external")
    statements = "\n".join(sql for sql, _ in connection.statements).lower()
    assert "pg_advisory_xact_lock" in statements
    assert "label_sha256" in statements
    assert "stddev_value" in statements
    assert "warning_flag" in statements
    assert "alert_flag" in statements


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["training", "health", "metadata"])
async def test_postgres_adapter_rejects_incomplete_or_mismatched_immutable_staging(fault: str) -> None:
    verified = Section03Loader(MANIFEST).verify_only()
    consumer = verified.manifest["consumer_contract"]
    metadata = {
        "manifest_sha256": verified.manifest_sha256,
        "label_sha256": consumer["label"]["sha256"],
        "training_sha256": consumer["training_join"]["sha256"],
        "health_sha256": consumer["feature_health"]["sha256"],
        "feature_cutoff": consumer["training_join"]["feature_cutoff_ts"],
        "baseline_date": consumer["feature_health"]["baseline_date"],
        "training_count": verified.training_count,
        "health_count": verified.health_count,
    }
    if fault == "metadata":
        metadata["feature_cutoff"] = "2026-01-01T00:00:00Z"
    training_count = verified.training_count - 1 if fault == "training" else verified.training_count
    health_count = verified.health_count - 1 if fault == "health" else verified.health_count
    adapter = FeastPostgresAdapter(
        connection_factory=lambda: _SqlConnection(rows=[[metadata], [{"row_count": training_count}], [{"row_count": health_count}]]),
        feast_fingerprint=lambda: "feast:test",
        valkey_fingerprint=lambda: "valkey:test",
    )
    with pytest.raises(Section03AdapterError, match=fault):
        await adapter.stage(verified)


@pytest.mark.asyncio
async def test_postgres_adapter_activation_fingerprint_requires_explicit_readback_hooks() -> None:
    adapter = FeastPostgresAdapter(connection_factory=lambda: _SqlConnection(rows=[[{"manifest_sha256": "previous"}]]))
    with pytest.raises(Section03AdapterError, match="readback hooks"):
        await adapter.fingerprint()


@pytest.mark.asyncio
async def test_unchanged_injected_registry_and_online_readbacks_fail_activation_post_check() -> None:
    class FrozenReadbackAdapter(FeastPostgresAdapter):
        def __init__(self) -> None:
            super().__init__(
                connection_factory=lambda: _SqlConnection(),
                feast_apply=lambda _hash: None,
                valkey_materialize=lambda _hash: None,
                feast_fingerprint=lambda: "feast:previous",
                valkey_fingerprint=lambda: "valkey:previous",
            )
            self.active = "previous"

        async def active_section03_manifest_hash(self) -> str | None:
            return self.active

        async def stage(self, verified: object) -> None:
            self.staged = verified.manifest_sha256

        async def staged_section03_manifest_hash(self, manifest_sha256: str) -> str | None:
            return self.staged if manifest_sha256 == self.staged else None

        async def switch_active(self, manifest_sha256: str) -> str | None:
            previous, self.active = self.active, manifest_sha256
            return previous

        async def restore_active(self, manifest_sha256: str | None) -> None:
            self.active = manifest_sha256

    with pytest.raises(Section03ActivationError, match="read-back mismatch") as error:
        await Section03Loader(MANIFEST).activate(FrozenReadbackAdapter())
    assert error.value.rollback_status == "restored"
    assert error.value.before_manifest_sha256 == "previous"
    assert error.value.after_manifest_sha256 == "previous"
    assert error.value.training_count == 11996
    assert error.value.health_count == 22


def test_loader_cli_emits_structured_verify_and_fake_activation_evidence(capsys: pytest.CaptureFixture[str]) -> None:
    cli = _loader_cli()
    assert cli.main(["--manifest", str(MANIFEST), "--strict", "--verify-only"]) == 0
    verify_output = json.loads(capsys.readouterr().out)
    assert verify_output["status"] == "verified"
    assert verify_output["before_manifest_sha256"] is None
    assert verify_output["training_count"] == 11996

    assert cli.main(
        ["--manifest", str(MANIFEST), "--strict", "--activate", "--adapter-factory", "tests.fake:adapter"],
        adapter_factory_resolver=lambda _reference: FakeActivationAdapter,
    ) == 0
    activation_output = json.loads(capsys.readouterr().out)
    assert activation_output["status"] == "activated"
    assert activation_output["before_manifest_sha256"] == "previous"
    assert activation_output["after_manifest_sha256"] == MANIFEST_SHA256
    assert activation_output["rollback_status"] == "not_required"


def test_loader_cli_fails_closed_for_missing_or_invalid_activation_factory(capsys: pytest.CaptureFixture[str]) -> None:
    cli = _loader_cli()
    assert cli.main(
        ["--manifest", str(MANIFEST), "--strict", "--activate"],
    ) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "--adapter-factory is required for --activate"
    assert cli.main(
        ["--manifest", str(MANIFEST), "--strict", "--activate", "--adapter-factory", "missing:factory"],
        adapter_factory_resolver=lambda _reference: (_ for _ in ()).throw(ValueError("invalid factory")),
    ) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_section03_migration_preserves_exact_columns_constraints_and_btree_indexes() -> None:
    migration = (REPO_ROOT / "infra" / "postgres" / "edai2" / "003_section03_features.sql").read_text(encoding="utf-8").lower()
    for column in ("label_sha256", "stddev_value", "warning_flag", "alert_flag"):
        assert column in migration
    assert "check (label in (0, 1))" in migration
    assert "check (psi_vs_baseline >= 0)" in migration
    assert migration.count("btree") >= 2


@pytest.mark.parametrize(("field", "value", "expected"), [("section", "wrong-section", "section"), ("schema_version", 999, "schema")])
def test_loader_rejects_wrong_manifest_identity_with_a_named_expectation(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object, expected: str
) -> None:
    manifest = _strict_verifier().verify_manifest(MANIFEST, strict=True)
    manifest[field] = value
    monkeypatch.setattr(Section03ManifestReader, "read_verified", lambda _: manifest)
    with pytest.raises(ValueError, match=expected):
        Section03Loader(MANIFEST).verify_only()


@pytest.mark.asyncio
async def test_activation_success_reports_all_post_action_fingerprints() -> None:
    adapter = FakeActivationAdapter()
    report = await Section03Loader(MANIFEST).activate(adapter)
    assert report.status == "activated"
    assert report.active_manifest_sha256 == report.manifest_sha256
    assert report.feast_fingerprint == f"feast:{report.manifest_sha256}"
    assert report.valkey_fingerprint == f"valkey:{report.manifest_sha256}"
    assert adapter.calls[:5] == ["stage", "staged", "switch", f"feast:{report.manifest_sha256}", f"valkey:{report.manifest_sha256}"]


@pytest.mark.asyncio
async def test_activation_full_fingerprint_match_is_a_noop() -> None:
    target = Section03Loader(MANIFEST).verify_only().manifest_sha256
    adapter = FakeActivationAdapter(active=target, feast=target, valkey=target)
    report = await Section03Loader(MANIFEST).activate(adapter)
    assert report.status == "noop"
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_activation_repairs_active_only_fingerprint_mismatch() -> None:
    target = Section03Loader(MANIFEST).verify_only().manifest_sha256
    adapter = FakeActivationAdapter(active="previous", feast=target, valkey=target)
    report = await Section03Loader(MANIFEST).activate(adapter)
    assert report.status == "activated"
    assert (await adapter.fingerprint()) == (target, f"feast:{target}", f"valkey:{target}")


@pytest.mark.asyncio
async def test_activation_repairs_feast_only_fingerprint_mismatch() -> None:
    target = Section03Loader(MANIFEST).verify_only().manifest_sha256
    adapter = FakeActivationAdapter(active=target, feast="previous", valkey=target)
    report = await Section03Loader(MANIFEST).activate(adapter)
    assert report.status == "activated"
    assert (await adapter.fingerprint()) == (target, f"feast:{target}", f"valkey:{target}")


@pytest.mark.asyncio
async def test_activation_repairs_valkey_only_fingerprint_mismatch() -> None:
    target = Section03Loader(MANIFEST).verify_only().manifest_sha256
    adapter = FakeActivationAdapter(active=target, feast=target, valkey="previous")
    report = await Section03Loader(MANIFEST).activate(adapter)
    assert report.status == "activated"
    assert (await adapter.fingerprint()) == (target, f"feast:{target}", f"valkey:{target}")


@pytest.mark.asyncio
async def test_activation_feast_failure_restores_all_prior_fingerprints() -> None:
    failing = FakeActivationAdapter(fail_feast=True)
    with pytest.raises(Section03ActivationError, match="feast failed") as error:
        await Section03Loader(MANIFEST).activate(failing)
    assert str(error.value.original) == "feast failed"
    assert error.value.rollback is None
    assert error.value.rollback_status == "restored"
    assert error.value.before_manifest_sha256 == "previous"
    assert error.value.after_manifest_sha256 == "previous"
    assert (await failing.fingerprint()) == ("previous", "feast:previous", "valkey:previous")
    assert failing.calls[-3:] == ["restore", "feast:previous", "valkey:previous"]


@pytest.mark.asyncio
async def test_activation_valkey_failure_restores_all_prior_fingerprints() -> None:
    valkey_failure = FakeActivationAdapter(fail_valkey=True)
    with pytest.raises(Section03ActivationError, match="valkey failed") as error:
        await Section03Loader(MANIFEST).activate(valkey_failure)
    assert str(error.value.original) == "valkey failed"
    assert error.value.rollback is None
    assert (await valkey_failure.fingerprint()) == ("previous", "feast:previous", "valkey:previous")


@pytest.mark.asyncio
async def test_activation_post_readback_mismatch_restores_all_prior_fingerprints() -> None:
    adapter = FakeActivationAdapter(readback_mismatch=True)
    with pytest.raises(Section03ActivationError, match="read-back mismatch") as error:
        await Section03Loader(MANIFEST).activate(adapter)
    assert str(error.value.original) == "activation fingerprint read-back mismatch"
    assert error.value.rollback is None
    assert adapter.active == "previous"
    assert adapter.feast == "previous"
    assert adapter.valkey == "previous"


@pytest.mark.asyncio
async def test_activation_rollback_failure_surfaces_original_and_compensation_errors() -> None:
    adapter = FakeActivationAdapter(fail_feast=True, fail_restore=True)
    with pytest.raises(Section03ActivationError, match="rollback=restore failed") as error:
        await Section03Loader(MANIFEST).activate(adapter)
    assert str(error.value.original) == "feast failed"
    assert str(error.value.rollback) == "restore failed"
