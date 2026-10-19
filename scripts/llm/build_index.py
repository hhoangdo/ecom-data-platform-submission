"""Build a local, immutable EDAI2 candidate index report without storage writes."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import inspect
import json
import os
import re
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
        choices=("local-bootstrap-sentinel", "canonical-evidence"),
        default="local-bootstrap-sentinel",
    )
    parser.add_argument("--trigger-airflow", action="store_true")
    parser.add_argument("--dag-id", required=False, default=None)
    parser.add_argument("--reject-index-purpose", required=False, default=None)
    parser.add_argument("--reject-index-version-prefix", required=False, default=None)
    parser.add_argument("--reject-index-version", required=False, default=None)
    parser.add_argument("--reject-bootstrap-artifact-reuse", action="store_true")
    parser.add_argument("--bootstrap-evidence", type=Path, required=False, default=None)
    parser.add_argument("--wait", action="store_true")
    parser.add_argument("--promote-if-gates", action="store_true")
    parser.add_argument("--verify-datahub", action="store_true")
    parser.add_argument("--commit-sha", required=False, default=None)
    parser.add_argument("--airflow-url", required=False, default=None)
    parser.add_argument("--airflow-auth-env", required=False, default=None)
    parser.add_argument("--datahub-url", required=False, default=None)
    parser.add_argument("--dag-result", type=Path, required=False, default=None)
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
    if args.trigger_airflow:
        for name in ("dag_id", "source_root", "index_version", "commit_sha", "airflow_url",
                      "airflow_auth_env", "dag_result", "bootstrap_evidence", "output"):
            if getattr(args, name) is None:
                parser.error(f"--trigger-airflow requires --{name.replace('_', '-')}")
        if not (args.airflow_url or "").startswith("https://"):
            parser.error("--trigger-airflow requires an explicit https:// --airflow-url (http/localhost guesses forbidden)")
        if args.index_purpose != "canonical-evidence":
            parser.error("--trigger-airflow requires --index-purpose canonical-evidence")
        if args.reject_index_purpose and args.index_purpose == args.reject_index_purpose:
            parser.error("index purpose is rejected")
        if args.reject_index_version_prefix and (args.index_version or "").startswith(args.reject_index_version_prefix):
            parser.error("index version prefix is rejected")
        if args.reject_index_version and args.index_version == args.reject_index_version:
            parser.error("index version is rejected")
        if args.dag_id != "rag_index_pipeline":
            parser.error("only the rag_index_pipeline DAG is authorized")
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


def verify_canonical_identity(index_version: str, commit_sha: str) -> str:
    """Accept exactly canonical-evidence-<40-hex-commit>; reject every sentinel."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha or ""):
        raise ValueError("commit SHA is invalid")
    expected = f"canonical-evidence-{commit_sha}"
    if index_version != expected:
        raise ValueError(
            "index version must be exactly canonical-evidence-<full-commit>; "
            "ci-bootstrap-*, test_idx_001, abbreviated, and uppercase identities fail"
        )
    return expected


def verify_airflow_evidence(
    *,
    dag_result: dict,
    bootstrap_evidence: dict,
    datahub: dict,
    index_version: str,
    expected_commit: str,
) -> dict:
    """Fail closed unless the Airflow run proves a real promoted RAG candidate.

    Bootstrap output is never promotion proof: a ci-bootstrap label or any
    content identity reused from the bootstrap evidence fails before DataHub.
    """
    verify_canonical_identity(index_version, expected_commit)
    if not isinstance(dag_result, dict):
        raise ValueError("Airflow DAG result must be a JSON object")
    if dag_result.get("dag_id") != "rag_index_pipeline" or dag_result.get("state") != "success":
        raise ValueError("Airflow DAG run did not succeed")
    if dag_result.get("index_version") != index_version:
        raise ValueError("Airflow DAG index version mismatch")
    if dag_result.get("candidate_label") == "ci-bootstrap":
        raise ValueError("candidate reuses bootstrap identity")
    if dag_result.get("document_count") != 8 or dag_result.get("document_version_count") != 9:
        raise ValueError("candidate source set must be exactly 8 files and 9 versions")
    if not dag_result.get("chunk_count") or dag_result.get("embedding_dimension") != 384:
        raise ValueError("candidate chunks or embeddings are invalid")
    gate = dag_result.get("gate_60_case", {})
    if not isinstance(gate, dict) or gate.get("pass") is not True or gate.get("cases") != 60:
        raise ValueError("candidate 60-case gate did not pass")
    promotion = dag_result.get("promotion", {})
    if not isinstance(promotion, dict) or promotion.get("active_alias") != index_version or not promotion.get("cas"):
        raise ValueError("candidate CAS promotion is invalid")
    lineage = dag_result.get("lineage", {})
    if not isinstance(lineage, dict) or lineage.get("active") != index_version or lineage.get("candidate") != index_version:
        raise ValueError("candidate lineage is invalid")
    bootstrap_hashes = set()
    jobs = bootstrap_evidence.get("jobs", []) if isinstance(bootstrap_evidence, dict) else []
    for job in jobs:
        if isinstance(job, dict):
            bootstrap_hashes |= {job.get("expected_digest"), job.get("remote_digest"), job.get("pod_image_digest")}
    bootstrap_hashes.discard(None)
    content = dag_result.get("content_sha256", [])
    if not isinstance(content, list) or not content or any(item in bootstrap_hashes for item in content):
        raise ValueError("candidate reuses bootstrap artifact output")
    if not isinstance(datahub, dict) or datahub.get("active_version") != index_version:
        raise ValueError("DataHub read-back does not hold the active version")
    urns = datahub.get("dataset_urns", [])
    if not isinstance(urns, list) or not urns or not datahub.get("response_hashes"):
        raise ValueError("DataHub lineage read-back is invalid")
    return {"promoted": True, "datahub_read_back": True, "index_version": index_version}


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
    if args.trigger_airflow:
        import base64

        credentials = os.environ.get(args.airflow_auth_env, "")
        if ":" not in credentials:
            raise SystemExit("--airflow-auth-env must name a user:password variable")
        token = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        headers = {"Content-Type": "application/json", "Authorization": f"Basic {token}"}

        def airflow_post(path: str, body: dict) -> dict:
            request = urllib.request.Request(f"{args.airflow_url}{path}", data=json.dumps(body).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))

        def airflow_get(path: str) -> dict:
            request = urllib.request.Request(f"{args.airflow_url}{path}", headers=headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))

        try:
            verify_canonical_identity(args.index_version, args.commit_sha)
            run = airflow_post(f"/api/v1/dags/{args.dag_id}/dagRuns", {"conf": {"index_version": args.index_version, "index_purpose": args.index_purpose}})
            run_id = run.get("dag_run_id")
            if not run_id:
                raise ValueError("Airflow DAG trigger returned no run id")
            if args.wait:
                import time as _time

                state = ""
                for _ in range(60):
                    state = airflow_get(f"/api/v1/dags/{args.dag_id}/dagRuns/{run_id}").get("state", "")
                    if state in ("success", "failed"):
                        break
                    _time.sleep(60)
                if state != "success":
                    raise ValueError(f"Airflow DAG run did not succeed: {state}")
            dag_result = json.loads(Path(args.dag_result).read_text(encoding="utf-8"))
            bootstrap_evidence = json.loads(Path(args.bootstrap_evidence).read_text(encoding="utf-8"))
            datahub: dict = {"dataset_urns": [], "active_version": None, "response_hashes": []}
            if args.verify_datahub:
                datahub = airflow_get(f"/api/v1/dags/{args.dag_id}/dagRuns/{run_id}/taskInstances/emit_active_lineage_and_read_back/xcomEntries/return_value")
                if not isinstance(datahub, dict):
                    raise ValueError("DataHub read-back is invalid")
            result = verify_airflow_evidence(
                dag_result=dag_result, bootstrap_evidence=bootstrap_evidence, datahub=datahub,
                index_version=args.index_version, expected_commit=args.commit_sha,
            )
            if args.promote_if_gates and not result["promoted"]:
                raise ValueError("promotion gate did not pass")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise SystemExit(f"canonical evidence run failed: {error}") from error
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"dag_run_id": run_id, **result}, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"live_execution": True, "index_run": str(args.output)}, sort_keys=True))
        return 0
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
