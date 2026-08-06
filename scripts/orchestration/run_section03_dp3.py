"""Strict local Airflow REST wrapper for Section 03 DP3 evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


REPO_ROOT = Path(__file__).resolve().parents[2]
COURSEWORK_RUNS_ROOT = REPO_ROOT / "evidence" / "08_airflow_gx" / "coursework_pipeline"
DEFAULT_AIRFLOW_URL = "http://localhost:8082"
DAG_ID = "mini_coursework_pipeline"
TASK_IDS = (
    "dp1_raw_to_bronze.ingest_raw_to_bronze",
    "dp1_raw_to_bronze.validate_bronze",
    "dp2_bronze_to_silver_gold.transform_bronze_to_silver_gold",
    "dp2_bronze_to_silver_gold.validate_silver_gold",
    "dp3_offline_features.compute_offline_features",
    "dp3_offline_features.validate_offline_features",
)
FEATURE_TABLES = (
    "feat_customer_90d",
    "feat_stream_60m",
    "feat_customer_unified",
    "ml_customer_label",
    "agg_feature_health_daily",
    "feature_drift_alerts",
    "ml_customer_purchase_training",
)
SECTION03_PARAMETER_KEYS = (
    "drift_start_ts",
    "feature_cutoff_ts",
    "label_end_ts",
    "baseline_date",
)
REQUIRED_ARTIFACTS = (
    "dp1_ingest.json",
    "dp1_validate.json",
    "dp2_transform.json",
    "dp2_validate.json",
    "dp3_compute.json",
    "dp3_validate.json",
    "quality/coursework_feature_contract.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"topic05_dp3_{stamp}"


def _resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _load_candidate(candidate_manifest: Path) -> tuple[dict[str, Any], str, str]:
    manifest_path = _resolve_path(candidate_manifest).resolve()
    if not manifest_path.is_file():
        raise RuntimeError("Section 03 candidate manifest is missing.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_config_path = Path(str(manifest.get("source_config_path", "")))
    if source_config_path.is_absolute() or ".." in source_config_path.parts:
        raise RuntimeError("Section 03 source config path is not repository-relative.")
    config_path = (REPO_ROOT / source_config_path).resolve()
    if not config_path.is_file():
        raise RuntimeError("Section 03 source config is missing.")
    if _sha256(config_path) != manifest.get("source_config_sha256"):
        raise RuntimeError("Section 03 source config hash mismatch.")
    scale = manifest.get("scale")
    if not isinstance(scale, str) or not scale:
        raise RuntimeError("Section 03 candidate scale is missing.")
    windows = manifest.get("windows")
    if not isinstance(windows, dict) or any(not isinstance(windows.get(key), str) for key in SECTION03_PARAMETER_KEYS):
        raise RuntimeError("Section 03 candidate windows are missing or invalid.")
    return manifest, _sha256(manifest_path), source_config_path.as_posix()


def _sanitize(value: object) -> object:
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            sanitized[str(key)] = "[REDACTED]" if any(
                marker in lowered for marker in ("authorization", "password", "secret", "token")
            ) else _sanitize(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _request_json(session: Any, method: str, url: str, *, auth: tuple[str, str], **kwargs: object) -> dict[str, Any]:
    response = getattr(session, method)(url, auth=auth, timeout=20, **kwargs)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"Airflow REST response was not an object: {url}")
    return payload


def _poll_run(
    *, session: Any, airflow_url: str, dag_id: str, run_id: str, auth: tuple[str, str],
    timeout_seconds: float, poll_interval_seconds: float, sleep: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    run_url = f"{airflow_url.rstrip('/')}/api/v1/dags/{dag_id}/dagRuns/{run_id}"
    task_url = f"{run_url}/taskInstances"
    while True:
        run_payload = _request_json(session, "get", run_url, auth=auth)
        task_payload = _request_json(session, "get", task_url, auth=auth)
        state = str(run_payload.get("state", "")).lower()
        task_instances = task_payload.get("task_instances") or []
        task_states = {str(item.get("task_id")): str(item.get("state", "")).lower() for item in task_instances}
        if state in {"failed", "upstream_failed", "up_for_retry", "cancelled"}:
            raise RuntimeError(f"Airflow DAG run failed with state {state!r}.")
        if state == "success" and all(task_states.get(task_id) == "success" for task_id in TASK_IDS):
            return run_payload, task_payload
        if time.monotonic() >= deadline:
            raise RuntimeError("Airflow DAG run or task polling timed out.")
        sleep(poll_interval_seconds)


def _validate_artifacts(
    *,
    run_root: Path,
    candidate_sha256: str,
    scale: str,
    config_path: str,
    expected_section03_parameters: dict[str, str],
) -> list[dict[str, str]]:
    missing = [relative for relative in REQUIRED_ARTIFACTS if not (run_root / relative).is_file()]
    if missing:
        raise RuntimeError(f"Section 03 runtime artifact inventory is stale or incomplete: {missing}")

    compute = json.loads((run_root / "dp3_compute.json").read_text(encoding="utf-8"))
    validate = json.loads((run_root / "dp3_validate.json").read_text(encoding="utf-8"))
    quality = json.loads((run_root / "quality" / "coursework_feature_contract.json").read_text(encoding="utf-8"))
    if compute.get("state") != "success" or compute.get("strict_section03") is not True:
        raise RuntimeError("Section 03 DP3 compute artifact is not strict and successful.")
    if compute.get("generator_config_path") != config_path or compute.get("generator_scale") != scale:
        raise RuntimeError("Section 03 DP3 compute artifact does not match the candidate.")
    expected_config_sha256 = _sha256(_resolve_path(Path(config_path)))
    if compute.get("generator_config_sha256") != expected_config_sha256:
        raise RuntimeError("Section 03 DP3 compute artifact has a stale config hash.")
    if compute.get("section03_candidate_manifest_sha256") != candidate_sha256:
        raise RuntimeError("Section 03 DP3 compute artifact has a stale candidate hash.")
    if compute.get("feature_tables") != list(FEATURE_TABLES):
        raise RuntimeError("Section 03 DP3 compute artifact has the wrong table inventory.")
    if compute.get("feature_cutoff_ts") != expected_section03_parameters["feature_cutoff_ts"]:
        raise RuntimeError("Section 03 DP3 compute artifact has a stale feature cutoff.")
    if compute.get("section03_parameters") != expected_section03_parameters:
        raise RuntimeError("Section 03 DP3 compute artifact has stale Section 03 parameters.")
    if validate.get("state") != "success" or validate.get("contract_success") is not True:
        raise RuntimeError("Section 03 DP3 validation artifact is not successful.")
    if (
        validate.get("strict_section03") is not True
        or validate.get("generator_config_path") != config_path
        or validate.get("generator_config_sha256") != expected_config_sha256
        or validate.get("generator_scale") != scale
        or validate.get("section03_candidate_manifest_sha256") != candidate_sha256
        or validate.get("feature_cutoff_ts") != expected_section03_parameters["feature_cutoff_ts"]
    ):
        raise RuntimeError("Section 03 DP3 validation artifact does not match the candidate.")
    result_tables = [item.get("table_name") for item in validate.get("feature_results", [])]
    if result_tables != list(FEATURE_TABLES):
        raise RuntimeError("Section 03 DP3 validation artifact has the wrong table order.")
    if not all(item.get("contract_success") is True for item in validate.get("feature_results", [])):
        raise RuntimeError("Section 03 DP3 validation artifact contains a failed table contract.")
    if quality.get("success") is not True:
        raise RuntimeError("Section 03 coursework feature quality report is not successful.")

    return [
        {"path": relative, "sha256": _sha256(run_root / relative)}
        for relative in REQUIRED_ARTIFACTS
    ]


def run_section03_dp3(
    *, candidate_manifest: Path, airflow_url: str, output_root: Path,
    username: str, password: str, session: Any | None = None,
    dag_id: str = DAG_ID, timeout_seconds: float = 900, poll_interval_seconds: float = 5,
    sleep: Any = time.sleep, run_id: str | None = None,
    expected_config_path: str | None = None, expected_scale: str | None = None,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = run_id or _new_run_id()
    try:
        manifest, candidate_sha256, config_path = _load_candidate(candidate_manifest)
        if expected_config_path is not None and config_path != Path(expected_config_path).as_posix():
            raise RuntimeError("Section 03 CLI config does not match the candidate.")
        if expected_scale is not None and str(manifest["scale"]) != expected_scale:
            raise RuntimeError("Section 03 CLI scale does not match the candidate.")
        conf = {
            "generator_config_path": config_path,
            "generator_scale": str(manifest["scale"]),
            "section03_candidate_manifest_sha256": candidate_sha256,
        }
        client = session or requests.Session()
        auth = (username, password)
        trigger_url = f"{airflow_url.rstrip('/')}/api/v1/dags/{dag_id}/dagRuns"
        run_payload = _request_json(
            client,
            "post",
            trigger_url,
            auth=auth,
            json={"dag_run_id": run_id, "conf": conf},
        )
        run_id = str(run_payload.get("dag_run_id") or run_id)
        run_state, task_state = _poll_run(
            session=client,
            airflow_url=airflow_url,
            dag_id=dag_id,
            run_id=run_id,
            auth=auth,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
            sleep=sleep,
        )
        task_state_path = output_root / "airflow_task_instances.json"
        _write_json(task_state_path, _sanitize(task_state))
        run_root = COURSEWORK_RUNS_ROOT / run_id
        artifacts = _validate_artifacts(
            run_root=run_root,
            candidate_sha256=candidate_sha256,
            scale=str(manifest["scale"]),
            config_path=config_path,
            expected_section03_parameters={
                key: str(manifest["windows"][key])
                for key in SECTION03_PARAMETER_KEYS
            },
        )
        artifacts.append(
            {
                "path": "airflow_task_instances.json",
                "sha256": _sha256(task_state_path),
            }
        )
        result = {
            "status": "success",
            "dag_id": dag_id,
            "run_id": run_id,
            "conf": conf,
            "airflow_run": run_state,
            "task_instances": task_state,
            "artifacts": artifacts,
        }
    except Exception as exc:
        result = {"status": "failed", "dag_id": dag_id, "run_id": run_id, "error": str(exc)}
        _write_json(output_root / "run_manifest.json", _sanitize(result))
        raise RuntimeError(str(exc)) from exc

    _write_json(output_root / "run_manifest.json", _sanitize(result))
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-manifest", "--section03-manifest", dest="candidate_manifest", type=Path, required=True)
    parser.add_argument("--airflow-url", default=os.getenv("VBS_AIRFLOW_UI_URL", DEFAULT_AIRFLOW_URL))
    parser.add_argument("--dag-id", default=DAG_ID)
    parser.add_argument("--output-root", "--output", dest="output_root", type=Path, default=Path("tmp/section03-runtime/airflow"))
    parser.add_argument("--run-id")
    parser.add_argument("--config")
    parser.add_argument("--scale")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=900)
    parser.add_argument("--poll-interval-seconds", type=float, default=5)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    username = os.getenv("VBS_AIRFLOW_ADMIN_USERNAME")
    password = os.getenv("VBS_AIRFLOW_ADMIN_PASSWORD")
    if not username or not password:
        raise SystemExit("VBS_AIRFLOW_ADMIN_USERNAME and VBS_AIRFLOW_ADMIN_PASSWORD are required.")
    result = run_section03_dp3(
        candidate_manifest=args.candidate_manifest,
        airflow_url=args.airflow_url,
        output_root=args.output_root,
        username=username,
        password=password,
        dag_id=args.dag_id,
        timeout_seconds=args.timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        run_id=args.run_id,
        expected_config_path=args.config,
        expected_scale=args.scale,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
