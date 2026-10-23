from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "evidence" / "04_2_llm_design"
MANIFEST = EVIDENCE / "run_manifest.json"


class BundleEntry(TypedDict):
    path: str
    sha256: str
    size_bytes: int


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bundle_digest(files: list[BundleEntry]) -> str:
    canonical = "".join(
        f"{entry['path']}\0{entry['sha256']}\0{entry['size_bytes']}\n"
        for entry in sorted(files, key=lambda item: item["path"])
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest_rel = MANIFEST.relative_to(ROOT).as_posix()
    files: list[BundleEntry] = []
    for path in sorted(EVIDENCE.rglob("*")):
        if not path.is_file() or path.resolve() == MANIFEST.resolve():
            continue
        files.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    manifest["bundle"] = {
        "root": EVIDENCE.relative_to(ROOT).as_posix(),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "file_count": len(files),
        "total_size_bytes": sum(entry["size_bytes"] for entry in files),
        "excludes": [manifest_rel],
        "files": files,
        "bundle_sha256": bundle_digest(files),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": manifest_rel, "file_count": len(files), "bundle_sha256": manifest["bundle"]["bundle_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
