"""Strict Section 03 verification and explicitly owned activation CLI."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
from collections.abc import Callable, Sequence
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
    mode.add_argument("--activate", action="store_true")
    parser.add_argument("--adapter-factory")
    args = parser.parse_args(argv)
    if not args.strict:
        parser.error("--strict is required")

    verified = Section03Loader(args.manifest).verify_only()
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
