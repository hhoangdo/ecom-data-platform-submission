"""Strict, read-only Section 03 bundle verification for local loading."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol


@dataclass(frozen=True)
class VerifiedSection03:
    """Validated immutable bundle details consumed by the activation adapter."""

    manifest: dict[str, Any]
    manifest_sha256: str
    training_count: int
    health_count: int
    training_path: Path
    health_path: Path


@dataclass(frozen=True)
class Section03ActivationReport:
    """Fingerprint-backed result of one idempotent Section 03 activation."""

    status: str
    manifest_sha256: str
    previous_manifest_sha256: str | None
    active_manifest_sha256: str | None
    feast_fingerprint: str
    valkey_fingerprint: str
    training_count: int
    health_count: int
    rollback_status: str


class Section03ActivationAdapter(Protocol):
    """The explicit, fakeable activation boundary for verified Section 03 data."""

    async def fingerprint(self) -> tuple[str | None, str, str]: ...

    async def stage(self, verified: "VerifiedSection03") -> None: ...

    async def staged_section03_manifest_hash(self, manifest_sha256: str) -> str | None: ...

    async def switch_active(self, manifest_sha256: str) -> str | None: ...

    async def restore_active(self, manifest_sha256: str | None) -> None: ...

    async def apply_feast(self, manifest_sha256: str | None) -> None: ...

    async def materialize_valkey(self, manifest_sha256: str | None) -> None: ...


class Section03ActivationError(RuntimeError):
    """Activation failure retaining the original and compensation failures."""

    def __init__(
        self,
        original: Exception,
        rollback: Exception | None = None,
        rollback_fingerprints: tuple[str | None, str, str] | None = None,
        *,
        before_manifest_sha256: str | None = None,
        after_manifest_sha256: str | None = None,
        training_count: int = 0,
        health_count: int = 0,
        feast_fingerprint: str | None = None,
        valkey_fingerprint: str | None = None,
        rollback_status: str = "not_attempted",
    ) -> None:
        self.original = original
        self.rollback = rollback
        self.rollback_fingerprints = rollback_fingerprints
        self.before_manifest_sha256 = before_manifest_sha256
        self.after_manifest_sha256 = after_manifest_sha256
        self.training_count = training_count
        self.health_count = health_count
        self.feast_fingerprint = feast_fingerprint
        self.valkey_fingerprint = valkey_fingerprint
        self.rollback_status = rollback_status
        super().__init__(f"activation failed: {original}; rollback={rollback or 'succeeded'}")


class Section03ManifestReader:
    """Load the canonical Section 03 manifest through its strict verifier."""

    def __init__(self, manifest_path: str | Path) -> None:
        self.manifest_path = Path(manifest_path)

    def _verifier(self, repo_root: Path) -> ModuleType:
        verifier_path = repo_root / "scripts" / "generate" / "verify_section03_manifest.py"
        spec = importlib.util.spec_from_file_location("edai2_section03_verifier", verifier_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("strict Section 03 verifier is unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def read_verified(self) -> dict[str, Any]:
        """Return a strict manifest without rewriting any Section 03 artifact."""

        repo_root = self.manifest_path.resolve().parents[2]
        verifier = self._verifier(repo_root)
        return verifier.verify_manifest(self.manifest_path, strict=True)


class Section03Loader:
    """Verify all loader-facing Section 03 invariants before activation."""

    def __init__(self, manifest_path: str | Path) -> None:
        self.manifest_path = Path(manifest_path)

    def verify_only(self) -> VerifiedSection03:
        """Strictly validate the canonical manifest and CSV contracts without I/O writes."""

        try:
            manifest = Section03ManifestReader(self.manifest_path).read_verified()
            if manifest.get("section") != "03_data_generator_improvement":
                raise ValueError("manifest section must be 03_data_generator_improvement")
            if manifest.get("schema_version") != 1:
                raise ValueError("manifest schema_version must be 1")
            consumer = manifest["consumer_contract"]
            artifacts = manifest["artifacts"]
            label = consumer["label"]
            training = consumer["training_join"]
            health = consumer["feature_health"]
            root = self.manifest_path.parent
            label_path = root / label["path"]
            training_path = root / training["path"]
            health_path = root / health["path"]
            label_rows = _read_csv(label_path, ["id", "label"])
            training_rows = _read_csv(training_path, artifacts["training_join"]["columns"])
            health_rows = _read_csv(health_path, artifacts["feature_health_daily"]["columns"])
            _validate_rows(label_rows, training_rows, health_rows, consumer)
            if len(label_rows) != artifacts["labels"]["row_count"]:
                raise ValueError("label row count does not match manifest")
            if len(training_rows) != artifacts["training_join"]["row_count"]:
                raise ValueError("training row count does not match manifest")
            if len(health_rows) != artifacts["feature_health_daily"]["row_count"]:
                raise ValueError("health row count does not match manifest")
        except (KeyError, OSError, RuntimeError, ValueError) as error:
            raise ValueError(f"invalid verified Section 03 bundle: {error}") from error
        return VerifiedSection03(
            manifest=manifest,
            manifest_sha256=_sha256(self.manifest_path),
            training_count=len(training_rows),
            health_count=len(health_rows),
            training_path=training_path,
            health_path=health_path,
        )

    async def activate(self, adapter: Section03ActivationAdapter) -> Section03ActivationReport:
        """Stage, switch, apply, and compensate through one explicit async adapter."""

        verified = self.verify_only()
        active, feast_fingerprint, valkey_fingerprint = await adapter.fingerprint()
        expected = _expected_fingerprints(verified.manifest_sha256)
        if (active, feast_fingerprint, valkey_fingerprint) == expected:
            return Section03ActivationReport(
                "noop", verified.manifest_sha256, active, active, feast_fingerprint,
                valkey_fingerprint, verified.training_count, verified.health_count,
                "not_required",
            )
        await adapter.stage(verified)
        if await adapter.staged_section03_manifest_hash(verified.manifest_sha256) != verified.manifest_sha256:
            raise Section03ActivationError(
                RuntimeError("staging fingerprint read-back mismatch"),
                before_manifest_sha256=active,
                after_manifest_sha256=active,
                training_count=verified.training_count,
                health_count=verified.health_count,
                feast_fingerprint=feast_fingerprint,
                valkey_fingerprint=valkey_fingerprint,
            )
        previous = await adapter.switch_active(verified.manifest_sha256)
        try:
            await adapter.apply_feast(verified.manifest_sha256)
            await adapter.materialize_valkey(verified.manifest_sha256)
            active, feast_fingerprint, valkey_fingerprint = await adapter.fingerprint()
            if (active, feast_fingerprint, valkey_fingerprint) != expected:
                raise RuntimeError("activation fingerprint read-back mismatch")
        except Exception as original:
            try:
                await adapter.restore_active(previous)
                await adapter.apply_feast(previous)
                await adapter.materialize_valkey(previous)
                rollback_fingerprints = await adapter.fingerprint()
                if rollback_fingerprints != _expected_fingerprints(previous):
                    raise RuntimeError("rollback fingerprint read-back mismatch")
            except Exception as rollback:
                raise Section03ActivationError(
                    original,
                    rollback,
                    before_manifest_sha256=previous,
                    after_manifest_sha256=verified.manifest_sha256,
                    training_count=verified.training_count,
                    health_count=verified.health_count,
                    rollback_status="failed",
                ) from original
            raise Section03ActivationError(
                original,
                rollback_fingerprints=rollback_fingerprints,
                before_manifest_sha256=previous,
                after_manifest_sha256=rollback_fingerprints[0],
                training_count=verified.training_count,
                health_count=verified.health_count,
                feast_fingerprint=rollback_fingerprints[1],
                valkey_fingerprint=rollback_fingerprints[2],
                rollback_status="restored",
            ) from original
        return Section03ActivationReport(
            "activated", verified.manifest_sha256, previous, active, feast_fingerprint,
            valkey_fingerprint, verified.training_count, verified.health_count,
            "not_required",
        )


def _read_csv(path: Path, columns: list[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != columns:
            raise ValueError("CSV columns differ from strict manifest order")
        return list(reader)


def _validate_rows(
    labels: list[dict[str, str]],
    training: list[dict[str, str]],
    health: list[dict[str, str]],
    consumer: dict[str, Any],
) -> None:
    label_ids = [row["id"] for row in labels]
    if not label_ids or any(not value for value in label_ids) or len(set(label_ids)) != len(label_ids):
        raise ValueError("labels must have unique non-empty IDs")
    if any(row["label"] not in {"0", "1"} for row in labels):
        raise ValueError("labels must be binary integers")
    training_ids = [row["id"] for row in training]
    if set(training_ids) != set(label_ids) or len(training_ids) != len(set(training_ids)):
        raise ValueError("training and label cohorts differ")
    labels_by_id = {row["id"]: row["label"] for row in labels}
    if any(row["label"] != labels_by_id[row["id"]] for row in training):
        raise ValueError("training labels differ from exact label artifact")
    cutoff = consumer["training_join"]["feature_cutoff_ts"]
    if any(row["event_timestamp"] != cutoff or row["created"] != cutoff for row in training):
        raise ValueError("training cutoff differs from manifest")
    health_contract = consumer["feature_health"]
    if not health or any(row["feature_name"] != health_contract["feature_name"] for row in health):
        raise ValueError("health feature differs from manifest")
    if any(row["window_days"] != str(health_contract["window_days"]) for row in health):
        raise ValueError("health horizon differs from manifest")
    if any(row["baseline_date"] != health_contract["baseline_date"] for row in health):
        raise ValueError("health baseline differs from manifest")
    dates = [row["monitoring_date"] for row in health]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise ValueError("health monitoring dates must be unique and ordered")
    if dates[0] != health_contract["monitoring_start"] or dates[-1] != health_contract["monitoring_end"]:
        raise ValueError("health monitoring range differs from manifest")
    if any(int(row["customer_count"]) != health_contract["cohort_size"] for row in health):
        raise ValueError("health cohort differs from manifest")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_fingerprints(manifest_sha256: str | None) -> tuple[str | None, str, str]:
    return (manifest_sha256, f"feast:{manifest_sha256}", f"valkey:{manifest_sha256}")


__all__ = ["Section03ActivationAdapter", "Section03ActivationError", "Section03ActivationReport", "Section03Loader", "Section03ManifestReader", "VerifiedSection03"]
