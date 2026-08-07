"""Build a local, immutable EDAI2 candidate index report without storage writes."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Sequence

from huggingface_hub import snapshot_download

from vina_bim_shop.llm.indexing import (
    BGE_MODEL,
    BGE_REVISION,
    EXPECTED_SOURCE_FILES,
    RagIndexPipeline,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the deliberately narrow candidate-only command surface."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("candidate",), required=True)
    parser.add_argument("--index-version", required=True)
    parser.add_argument(
        "--index-purpose",
        choices=("local-bootstrap-sentinel",),
        default="local-bootstrap-sentinel",
    )
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.dry_run:
        parser.error("--dry-run is required; candidate storage is not available")
    return args


async def build_report(args: argparse.Namespace) -> dict[str, object]:
    """Use the cached immutable model revision and print a local report."""

    snapshot_path = Path(
        snapshot_download(
            repo_id=BGE_MODEL,
            revision=BGE_REVISION,
            local_files_only=True,
        )
    )
    pipeline = RagIndexPipeline()
    report = await pipeline.build_candidate(
        [str(args.source_root / filename) for filename in EXPECTED_SOURCE_FILES],
        args.index_version,
    )
    payload = report.model_dump(mode="json")
    payload.update(
        {
            "dry_run": True,
            "evidence_label": args.index_purpose,
            "model_file_sha256": _file_hashes(snapshot_path),
            "promotion": False,
            "storage_written": False,
        }
    )
    payload["report_sha256"] = canonical_report_sha256(payload)
    return payload


def _file_hashes(root: Path) -> dict[str, str]:
    """Return sorted SHA-256 hashes for the exact downloaded model snapshot."""

    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def canonical_report_sha256(payload: dict[str, object]) -> str:
    """Hash canonical report JSON before its self-referential digest is added."""

    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the candidate-only command and emit canonical JSON to stdout."""

    payload = asyncio.run(build_report(parse_args(argv)))
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
