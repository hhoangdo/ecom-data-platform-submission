"""Read-only strict Section 03 manifest ingestion boundary."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


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


__all__ = ["Section03ManifestReader"]
