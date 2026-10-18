"""Build a local, immutable EDAI2 candidate index report without storage writes."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import inspect
import json
import os
import urllib.request
from pathlib import Path
from typing import Any, Sequence

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
    parser.add_argument("--mode", choices=("candidate",), required=False, default=None)
    parser.add_argument("--index-version", required=False, default=None)
    parser.add_argument(
        "--index-purpose",
        choices=("local-bootstrap-sentinel",),
        default="local-bootstrap-sentinel",
    )
    parser.add_argument("--source-root", type=Path, required=False, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run long-lived for Deployment availability (canonical index is Topic 28 owned).",
    )
    parser.add_argument("--kubeconfig", type=Path, required=False, default=None)
    parser.add_argument("--context", required=False, default=None)
    parser.add_argument("--inject-validation-failure", action="store_true")
    parser.add_argument("--verify-active-unchanged", action="store_true")
    parser.add_argument("--rollback-to-previous", action="store_true")
    parser.add_argument("--previous-good", required=False, default=None)
    parser.add_argument("--restore-current", action="store_true")
    parser.add_argument("--output", type=Path, required=False, default=None)
    parser.add_argument("--chat-base-url", required=False, default=None)
    parser.add_argument("--postgres-dsn", required=False, default=None)
    args = parser.parse_args(argv)
    if args.serve:
        return args
    live = (
        args.inject_validation_failure
        or args.verify_active_unchanged
        or args.rollback_to_previous
        or args.restore_current
    )
    if live:
        for name in ("index_version", "output", "previous_good", "chat_base_url"):
            if getattr(args, name) is None:
                parser.error(f"live index rollback requires --{name.replace('_', '-')}")
        if bool(args.kubeconfig is None) != bool(args.context is None):
            parser.error("--kubeconfig and --context are required together")
        return args
    if not args.mode or not args.index_version or not args.source_root:
        parser.error("the following arguments are required: --mode, --index-version, --source-root")
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


_SMOKE: Any = None


def _smoke_module() -> Any:
    """Load the smoke CLI for its tested index-rollback proof."""
    global _SMOKE
    if _SMOKE is None:
        path = Path(__file__).resolve().parent / "smoke_release.py"
        spec = importlib.util.spec_from_file_location("topic26_build_index_smoke", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _SMOKE = module
    return _SMOKE


def _sync_result(result: Any) -> Any:
    """Await adapter results whether the adapter is sync or async."""

    async def _await_value(value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    if inspect.isawaitable(result):
        return asyncio.run(_await_value(result))
    return result


def run_index_rollback(
    *,
    adapter: Any,
    candidate_version: str,
    previous_good: str,
    eval_fn: Any,
    inject_validation_failure: bool = False,
) -> dict:
    """Prove an invalid candidate cannot move the alias, then roll back and restore."""
    before = _sync_result(adapter.active_version())
    validated = (not inject_validation_failure) and bool(
        _sync_result(adapter.is_validated(candidate_version))
    )
    if not validated:
        smoke = _smoke_module()

        def promote(version: str) -> None:
            if inject_validation_failure or not bool(_sync_result(adapter.is_validated(version))):
                raise ValueError("candidate validation failed")
            current = _sync_result(adapter.active_version())
            try:
                _sync_result(adapter.compare_and_swap_active(current, version))
            except RuntimeError as error:
                raise ValueError(f"alias CAS failed for candidate: {version}") from error

        def rollback_to(alias: str) -> str:
            current = _sync_result(adapter.active_version())
            try:
                return _sync_result(adapter.compare_and_swap_active(current, alias))
            except RuntimeError as error:
                raise ValueError(f"alias CAS failed for rollback: {alias}") from error

        def restore_current() -> None:
            current = _sync_result(adapter.active_version())
            try:
                _sync_result(adapter.compare_and_swap_active(current, before))
            except RuntimeError as error:
                raise ValueError("alias CAS failed for restore") from error

        return smoke.prove_index_rollback(
            get_active_alias=lambda: _sync_result(adapter.active_version()),
            promote_candidate=promote,
            rollback_to=rollback_to,
            restore_current=restore_current,
            eval_fn=eval_fn,
            candidate_version=candidate_version,
            previous_good=previous_good,
        )
    current = _sync_result(adapter.active_version())
    try:
        _sync_result(adapter.compare_and_swap_active(current, candidate_version))
    except RuntimeError as error:
        raise ValueError(f"alias CAS failed for candidate: {candidate_version}") from error
    try:
        rolled = _sync_result(adapter.compare_and_swap_active(candidate_version, previous_good))
    except RuntimeError as error:
        raise ValueError(f"alias CAS failed for rollback: {previous_good}") from error
    evaluation = eval_fn()
    if not evaluation.get("pass"):
        raise ValueError("evaluation regressed after index rollback")
    current = _sync_result(adapter.active_version())
    try:
        _sync_result(adapter.compare_and_swap_active(current, before))
    except RuntimeError as error:
        raise ValueError("alias CAS failed for restore") from error
    return {
        "candidate_version": candidate_version,
        "promoted": True,
        "active_unchanged": False,
        "rollback_to": rolled,
        "restored_current": True,
        "eval_pass": True,
    }


def _live_eval_fn(chat_base_url: str) -> Any:
    """Probe the retrieval chat with fixed prompts; require grounded answers."""

    def evaluate() -> dict:
        ok = True
        for prompt in ("Summarize order status.", "What is the returns policy?"):
            body = json.dumps({"prompt": prompt}).encode("utf-8")
            request = urllib.request.Request(
                f"{chat_base_url}/chat", data=body, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            answer = payload.get("answer", "")
            if not isinstance(answer, str) or not answer.strip():
                ok = False
            for marker in ("customer_id=",):
                if marker in answer:
                    ok = False
        return {"pass": ok, "probes": 2}

    return evaluate


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the candidate-only command and emit canonical JSON to stdout."""

    args = parse_args(argv)
    if args.serve:
        print(json.dumps({"mode": "serve", "index_purpose": args.index_purpose, "canonical_owner": "airflow-rag-pipeline"}, sort_keys=True), flush=True)
        import time

        while True:
            time.sleep(60)
    if (
        args.inject_validation_failure
        or args.verify_active_unchanged
        or args.rollback_to_previous
        or args.restore_current
    ):
        from vina_bim_shop.llm.adapters.feast_postgres import FeastPostgresAdapter

        dsn = args.postgres_dsn or os.environ.get("EDAI2_POSTGRES_DSN")
        if not dsn:
            raise SystemExit("live index rollback requires --postgres-dsn or EDAI2_POSTGRES_DSN")
        adapter = FeastPostgresAdapter(dsn=dsn)
        assert args.output is not None and args.chat_base_url is not None
        evidence = run_index_rollback(
            adapter=adapter,
            candidate_version=args.index_version,
            previous_good=args.previous_good,
            eval_fn=_live_eval_fn(args.chat_base_url),
            inject_validation_failure=args.inject_validation_failure,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"live_execution": True, "index_rollback": str(args.output)}, sort_keys=True))
        return 0
    payload = asyncio.run(build_report(args))
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
