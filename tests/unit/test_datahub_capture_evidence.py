from __future__ import annotations

import importlib.util
import json
import hashlib
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image

from compose_model import load_compose_model


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_script_module():
    script_path = _repo_root() / "scripts" / "datahub" / "capture_evidence.py"
    spec = importlib.util.spec_from_file_location("datahub_capture_evidence_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_gx_assertions_module(monkeypatch):
    emitter_stub = types.ModuleType("vina_bim_shop.datahub_lineage.emitter")
    emitter_stub.DataHubLineageEmitter = object
    emitter_stub.ice_urn = lambda table_name: f"urn:li:dataset:{table_name}"
    monkeypatch.setitem(sys.modules, "vina_bim_shop.datahub_lineage.emitter", emitter_stub)
    path = _repo_root() / "src" / "vina_bim_shop" / "datahub_lineage" / "gx_assertions.py"
    spec = importlib.util.spec_from_file_location("gx_assertions_for_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_emitter_module(monkeypatch):
    emitter_mcp = types.ModuleType("datahub.emitter.mcp")
    emitter_mcp.MetadataChangeProposalWrapper = object
    emitter_rest = types.ModuleType("datahub.emitter.rest_emitter")
    emitter_rest.DataHubRestEmitter = object
    schema_classes = types.ModuleType("datahub.metadata.schema_classes")
    schema_classes.__getattr__ = lambda name: type(name, (), {})
    for name, module in {
        "datahub": types.ModuleType("datahub"),
        "datahub.emitter": types.ModuleType("datahub.emitter"),
        "datahub.emitter.mcp": emitter_mcp,
        "datahub.emitter.rest_emitter": emitter_rest,
        "datahub.metadata": types.ModuleType("datahub.metadata"),
        "datahub.metadata.schema_classes": schema_classes,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    path = _repo_root() / "src" / "vina_bim_shop" / "datahub_lineage" / "emitter.py"
    spec = importlib.util.spec_from_file_location("datahub_emitter_for_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_datahub_capture_evidence_exits_nonzero_and_writes_failed_manifest(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module()

    monkeypatch.setattr(module, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(module, "COURSEWORK_PIPELINE_EVIDENCE_ROOT", tmp_path / "coursework_pipeline")
    monkeypatch.setattr(module, "capture_gms_health", lambda: {"healthy": False, "error": "gms unavailable"})
    monkeypatch.setattr(
        module,
        "capture_dataset_evidence",
        lambda: {"status": "missing", "error": "No successful datahub_ingestion manifest found"},
    )
    monkeypatch.setattr(module, "capture_tag_evidence", lambda: {"status": "success", "failed_tags": []})
    monkeypatch.setattr(module, "capture_search_evidence", lambda: {"status": "success"})
    monkeypatch.setattr(module, "capture_coursework_pipeline_evidence", lambda: {"status": "success", "indexed_search": {"status": "success"}})
    monkeypatch.setattr(module, "validate_coursework_screenshot_manifest", lambda: {"status": "success", "failures": []})

    with pytest.raises(SystemExit) as exc_info:
        module.main()

    assert exc_info.value.code == 1
    manifest = json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["failures"] == [
        {"step": "gms_health", "error": "gms unavailable"},
        {"step": "dataset_evidence", "error": "No successful datahub_ingestion manifest found"},
    ]


def test_datahub_capture_evidence_marks_tag_failures_as_partial(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module()

    monkeypatch.setattr(module, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(module, "COURSEWORK_PIPELINE_EVIDENCE_ROOT", tmp_path / "coursework_pipeline")
    monkeypatch.setattr(module, "capture_gms_health", lambda: {"healthy": True, "status_code": 200})
    monkeypatch.setattr(module, "capture_dataset_evidence", lambda: {"status": "success", "latest_successful_run_id": "manual__ok"})
    monkeypatch.setattr(
        module,
        "capture_tag_evidence",
        lambda: {"status": "partial", "failed_tags": [{"urn": "urn:li:tag:gold", "error": "Tag not found"}]},
    )
    monkeypatch.setattr(module, "capture_search_evidence", lambda: {"status": "success"})
    monkeypatch.setattr(module, "capture_coursework_pipeline_evidence", lambda: {"status": "success", "indexed_search": {"status": "success"}})
    monkeypatch.setattr(module, "validate_coursework_screenshot_manifest", lambda: {"status": "success", "failures": []})

    manifest = module.capture_evidence()

    assert manifest["status"] == "partial"
    assert manifest["failures"] == [{"step": "tag_evidence", "error": "1 tag lookups failed"}]
    assert (tmp_path / "run_manifest.json").is_file()


def test_datahub_capture_evidence_fails_when_indexed_search_is_unavailable(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module()

    monkeypatch.setattr(module, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(module, "COURSEWORK_PIPELINE_EVIDENCE_ROOT", tmp_path / "coursework_pipeline")
    monkeypatch.setattr(module, "capture_gms_health", lambda: {"healthy": True, "status_code": 200})
    monkeypatch.setattr(module, "capture_dataset_evidence", lambda: {"status": "success", "latest_successful_run_id": "manual__ok"})
    monkeypatch.setattr(module, "capture_tag_evidence", lambda: {"status": "success", "failed_tags": []})
    monkeypatch.setattr(module, "capture_search_evidence", lambda: {"status": "failed", "error": "indexed search returned no datasets"})
    monkeypatch.setattr(module, "capture_coursework_pipeline_evidence", lambda: {"status": "success", "indexed_search": {"status": "success"}})
    monkeypatch.setattr(module, "validate_coursework_screenshot_manifest", lambda: {"status": "success", "failures": []})

    manifest = module.capture_evidence()

    assert manifest["status"] == "failed"
    assert manifest["failures"] == [{"step": "search_evidence", "error": "indexed search returned no datasets"}]


def test_coursework_screenshot_manifest_requires_all_real_pngs_and_matching_hashes(tmp_path: Path) -> None:
    module = _load_script_module()
    screenshots = tmp_path.parent / "screenshots"
    screenshots.mkdir()
    entries = []
    for target in module.COURSEWORK_SCREENSHOT_TARGETS:
        image_path = screenshots / Path(target["path"]).name
        Image.new("RGB", (32, 24), color="white").save(image_path)
        entries.append(
            {
                **target,
                "captured_at": "2026-07-12T00:00:00+00:00",
                "width": 32,
                "height": 24,
                "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                "reloaded": True,
            }
        )
    (tmp_path / "ui_screenshot_manifest.json").write_text(json.dumps({"screenshots": entries}), encoding="utf-8")

    assert module.validate_coursework_screenshot_manifest(tmp_path)["status"] == "success"

    (screenshots / Path(entries[0]["path"]).name).unlink()
    failed = module.validate_coursework_screenshot_manifest(tmp_path)
    assert failed["status"] == "failed"
    assert failed["failures"][0]["id"] == "dp1_lineage"


def test_coursework_gate_cannot_pass_with_direct_evidence_when_index_or_screenshots_fail() -> None:
    module = _load_script_module()
    machine = {"status": "success", "direct_graphql": {"status": "success"}, "indexed_search": {"status": "failed"}}
    screenshots = {"status": "failed", "failures": [{"id": "dp1_lineage", "error": "missing"}]}

    status, failures = module.coursework_gate_status(machine, screenshots)

    assert status == "failed"
    assert {failure["step"] for failure in failures} == {"coursework_indexed_search", "coursework_screenshots"}


def test_coursework_capture_queries_match_datahub_1_6_property_and_assertion_shapes() -> None:
    module = _load_script_module()

    assert "properties {" in module.GRAPHQL_DATAFLOW_QUERY
    assert "properties {" in module.GRAPHQL_DATAJOB_QUERY
    assert "datasetUrn" in module.GRAPHQL_ASSERTION_QUERY
    assert "runEvents(limit: 1)" in module.GRAPHQL_ASSERTION_QUERY
    assert "latestRunEvent" not in module.GRAPHQL_ASSERTION_QUERY


def test_section03_runtime_context_binds_candidate_and_airflow_capture(tmp_path: Path) -> None:
    module = _load_script_module()
    repo_root = _repo_root()
    config_path = repo_root / "configs" / "generator" / "base.yaml"
    candidate = tmp_path / "section03_candidate_manifest.json"
    candidate.write_text(
        json.dumps(
            {
                "section": "03_data_generator_improvement",
                "bundle_id": "b" * 64,
                "source_config_path": "configs/generator/base.yaml",
                "source_config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
                "scale": "medium",
                "random_seed": 42,
                "windows": {
                    "feature_cutoff_ts": "2026-04-24T23:59:00Z",
                    "label_end_ts": "2026-05-01T23:59:00Z",
                },
            }
        ),
        encoding="utf-8",
    )
    airflow = tmp_path / "airflow"
    airflow.mkdir()
    (airflow / "run_manifest.json").write_text(
        json.dumps({"status": "success", "run_id": "section03-medium-seed42"}),
        encoding="utf-8",
    )

    context = module._load_section03_runtime_context(candidate, airflow)

    assert context == {
        "section": "03_data_generator_improvement",
        "run_id": "section03-medium-seed42",
        "candidate_bundle_id": "b" * 64,
        "candidate_manifest_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
        "source_config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "scale": "medium",
        "random_seed": 42,
        "feature_cutoff_ts": "2026-04-24T23:59:00Z",
        "label_end_ts": "2026-05-01T23:59:00Z",
    }


def test_manual_section03_run_id_uses_locked_feature_cutoff_for_assertion_timestamp(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_gx_assertions_module(monkeypatch)
    (tmp_path / "dp3_validate.json").write_text(
        json.dumps({"feature_cutoff_ts": "2026-04-24T23:59:00Z"}),
        encoding="utf-8",
    )

    timestamp_ms = module._run_timestamp_ms("section03-medium-seed42", run_root=tmp_path)

    assert timestamp_ms == int(
        datetime(2026, 4, 24, 23, 59, tzinfo=timezone.utc).timestamp() * 1000
    )


def test_datahub_assertion_field_urns_split_multi_column_contracts(monkeypatch) -> None:
    module = _load_emitter_module(monkeypatch)
    dataset_urn = "urn:li:dataset:(urn:li:dataPlatform:iceberg,vina_bim_shop.ml_customer_purchase_training,PROD)"

    assert module._schema_field_urns(dataset_urn, "event_timestamp,created") == [
        f"urn:li:schemaField:({dataset_urn},event_timestamp)",
        f"urn:li:schemaField:({dataset_urn},created)",
    ]


def test_datahub_services_bypass_inherited_proxy_for_internal_runtime() -> None:
    compose = load_compose_model(_repo_root())
    internal_no_proxy = {
        "datahub-elasticsearch",
        "datahub-gms",
        "kafka",
        "schema-registry",
        "lakehouse-postgres",
        "localhost",
        "127.0.0.1",
        "::1",
    }
    for service_name in (
        "datahub-elasticsearch",
        "datahub-system-update",
        "datahub-gms",
        "datahub-frontend",
        "datahub-actions",
    ):
        environment = compose["services"][service_name]["environment"]
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            assert environment[key] == ""
        assert internal_no_proxy <= set(environment["NO_PROXY"].split(","))
        assert environment["no_proxy"] == environment["NO_PROXY"]


def test_coursework_assertion_verification_accepts_every_dp1_and_dp3_output() -> None:
    module = _load_script_module()

    assert module._expected_assertion_datasets("dp1_raw_to_bronze", {}) == {
        "urn:li:dataset:(urn:li:dataPlatform:s3,bronze.batch,PROD)",
        "urn:li:dataset:(urn:li:dataPlatform:s3,bronze.events,PROD)",
    }
    assert module._expected_assertion_datasets("dp3_offline_features", {}) == {
        "urn:li:dataset:(urn:li:dataPlatform:iceberg,vina_bim_shop.feat_customer_90d,PROD)",
        "urn:li:dataset:(urn:li:dataPlatform:iceberg,vina_bim_shop.feat_stream_60m,PROD)",
        "urn:li:dataset:(urn:li:dataPlatform:iceberg,vina_bim_shop.feat_customer_unified,PROD)",
        "urn:li:dataset:(urn:li:dataPlatform:iceberg,vina_bim_shop.ml_customer_label,PROD)",
        "urn:li:dataset:(urn:li:dataPlatform:iceberg,vina_bim_shop.agg_feature_health_daily,PROD)",
        "urn:li:dataset:(urn:li:dataPlatform:iceberg,vina_bim_shop.feature_drift_alerts,PROD)",
        "urn:li:dataset:(urn:li:dataPlatform:iceberg,vina_bim_shop.ml_customer_purchase_training,PROD)",
    }


def test_section03_capture_emits_and_reads_back_exact_graph_without_secrets(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module()
    entities = module.coursework_pipeline_entities()
    jobs = {str(job["id"]): job for job in entities["data_jobs"]}
    schemas = {
        module.ice_urn(table_name): module.COURSEWORK_SCHEMA_TARGETS[module.ice_urn(table_name)]
        for table_name in module.FEATURE_TABLES
    }
    assertion_datasets = {
        "coursework_dp3_ml_customer_label_unique": module.ice_urn("ml_customer_label"),
        "coursework_dp3_ml_customer_label_binary": module.ice_urn("ml_customer_label"),
        "coursework_dp3_ml_customer_purchase_training_point_in_time": module.ice_urn("ml_customer_purchase_training"),
        "coursework_dp3_agg_feature_health_daily_psi_finite": module.ice_urn("agg_feature_health_daily"),
        "coursework_dp3_feature_drift_alerts_alert_threshold": module.ice_urn("feature_drift_alerts"),
    }
    lineage_parents = {
        module.ice_urn("feat_customer_90d"): [
            module.ice_urn("dim_customer"),
            module.ice_urn("fact_order"),
            module.ice_urn("fact_payment_attempt"),
        ],
        module.ice_urn("feat_stream_60m"): [module.ice_urn("stg_commerce_events")],
        module.ice_urn("feat_customer_unified"): [
            module.ice_urn("feat_customer_90d"),
            module.ice_urn("feat_stream_60m"),
        ],
        module.ice_urn("ml_customer_label"): [
            module.ice_urn("dim_customer"),
            module.ice_urn("fact_payment_attempt"),
        ],
        module.ice_urn("agg_feature_health_daily"): [
            module.ice_urn("dim_customer"),
            module.ice_urn("fact_order"),
        ],
        module.ice_urn("feature_drift_alerts"): [module.ice_urn("agg_feature_health_daily")],
        module.ice_urn("ml_customer_purchase_training"): [
            module.ice_urn("ml_customer_label"),
            module.ice_urn("feat_customer_unified"),
        ],
    }
    index_ready = {"value": False}

    def fake_graphql(query: str, variables: dict[str, object]) -> dict[str, object]:
        urn = str(variables.get("urn", ""))
        if "dataFlow(urn" in query:
            return {"data": {"dataFlow": {"urn": module.COURSEWORK_DATAFLOW_URN}}}
        if "dataJob(urn" in query:
            job = next(job for job in jobs.values() if job["urn"] == urn)
            return {
                "data": {
                    "dataJob": {
                        "urn": urn,
                        "dataFlow": {"urn": module.COURSEWORK_DATAFLOW_URN},
                        "inputOutput": {
                            "inputDatasets": [{"urn": value} for value in job["inputs"]],
                            "outputDatasets": [{"urn": value} for value in job["outputs"]],
                        },
                    }
                }
            }
        if "lineage(input" in query:
            return {
                "data": {
                    "dataset": {
                        "urn": urn,
                        "lineage": {
                            "relationships": [
                                {"entity": {"urn": "urn:li:dataJob:(example,producer)"}},
                                *({"entity": {"urn": parent}} for parent in lineage_parents[urn]),
                            ]
                        },
                    }
                }
            }
        if "schemaMetadata" in query:
            return {
                "data": {
                    "dataset": {
                        "urn": urn,
                        "schemaMetadata": {
                            "fields": [{"fieldPath": field, "nativeDataType": "string"} for field in schemas[urn]]
                        },
                    }
                }
            }
        if "assertion(urn" in query:
            assertion_id = urn.rsplit(":", 1)[-1]
            return {
                "data": {
                    "assertion": {
                        "urn": urn,
                        "info": {"datasetAssertion": {"datasetUrn": assertion_datasets[assertion_id]}},
                        "runEvents": {
                            "runEvents": [{"asserteeUrn": assertion_datasets[assertion_id], "result": {"type": "SUCCESS"}}]
                        },
                    }
                }
            }
        if "search(input" in query:
            search_input = variables["input"]
            assert isinstance(search_input, dict)
            search_type = search_input["type"]
            query_text = str(search_input["query"])
            if not index_ready["value"]:
                found = []
            elif search_type == "DATA_FLOW":
                found = [module.COURSEWORK_DATAFLOW_URN]
            elif search_type == "DATA_JOB":
                found = [job["urn"] for job in jobs.values() if str(job["id"]) == query_text]
            elif search_type == "DATASET":
                found = [dataset_urn for dataset_urn in schemas if query_text in dataset_urn]
            else:
                found = [f"urn:li:assertion:{assertion_id}" for assertion_id in assertion_datasets if query_text in assertion_id]
            return {"data": {"search": {"total": len(found), "searchResults": [{"entity": {"urn": value}} for value in found]}}}
        raise AssertionError(query)

    monkeypatch.setattr(module, "emit_coursework_pipeline", lambda **_kwargs: {"status": "success", "password": "secret-value"})
    monkeypatch.setattr(module, "emit_spark_batch_lineage", lambda **_kwargs: {"status": "success", "token": "secret-token"})
    monkeypatch.setattr(module, "emit_coursework_assertions_to_datahub", lambda **_kwargs: {"status": "success", "secret": "secret-value"})
    monkeypatch.setattr(module, "_graphql", fake_graphql)

    result = module.capture_section03_evidence(
        output_root=tmp_path,
        gms_url="http://localhost:8087",
        airflow_capture=tmp_path / "airflow",
        section03_manifest=tmp_path / "section03_candidate_manifest.json",
        index_timeout_seconds=1,
        index_poll_interval_seconds=0,
        sleep=lambda _seconds: index_ready.update(value=True),
    )

    assert result["status"] == "success"
    assert result["indexed_search"]["status"] == "success"
    assert set(result["datasets"]) == set(schemas)
    assert set(result["assertions"]) == set(assertion_datasets)
    assert set(result["edges"]) == set(lineage_parents)
    assert all(edge["status"] == "success" for edge in result["edges"].values())
    assert result["emitted"]["spark_lineage"]["status"] == "success"
    serialized = (tmp_path / "lineage.json").read_text(encoding="utf-8")
    assert "secret-value" not in serialized
    assert "secret-token" not in serialized
    assert (tmp_path / "run_manifest.json").is_file()


def test_section03_capture_fails_when_indexed_dataset_search_is_missing(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module()

    monkeypatch.setattr(module, "emit_coursework_pipeline", lambda **_kwargs: {"status": "success"})
    monkeypatch.setattr(module, "emit_spark_batch_lineage", lambda **_kwargs: {"status": "success"})
    monkeypatch.setattr(module, "emit_coursework_assertions_to_datahub", lambda **_kwargs: {"status": "success"})

    def missing_search(query: str, variables: dict[str, object]) -> dict[str, object]:
        if "search(input" in query:
            return {"data": {"search": {"total": 0, "searchResults": []}}}
        if "dataFlow(urn" in query:
            return {"data": {"dataFlow": {"urn": module.COURSEWORK_DATAFLOW_URN}}}
        return {"data": {}}

    monkeypatch.setattr(module, "_graphql", missing_search)

    result = module.capture_section03_evidence(
        output_root=tmp_path,
        gms_url="http://localhost:8087",
        index_timeout_seconds=0,
        index_poll_interval_seconds=0,
        sleep=lambda _seconds: None,
    )

    assert result["status"] == "failed"
    assert result["indexed_search"]["status"] == "failed"
    assert (tmp_path / "run_manifest.json").is_file()


def test_capture_evidence_fails_closed_when_coursework_job_search_is_missing(monkeypatch, tmp_path: Path) -> None:
    module = _load_script_module()

    monkeypatch.setattr(module, "EVIDENCE_ROOT", tmp_path)
    monkeypatch.setattr(module, "COURSEWORK_PIPELINE_EVIDENCE_ROOT", tmp_path / "coursework_pipeline")
    monkeypatch.setattr(module, "capture_gms_health", lambda: {"healthy": True, "status_code": 200})
    monkeypatch.setattr(module, "capture_dataset_evidence", lambda: {"status": "success", "latest_successful_run_id": "manual__ok"})
    monkeypatch.setattr(module, "capture_tag_evidence", lambda: {"status": "success", "failed_tags": []})
    monkeypatch.setattr(module, "capture_search_evidence", lambda: {"status": "success"})
    monkeypatch.setattr(
        module,
        "capture_coursework_pipeline_evidence",
        lambda: {"status": "success", "indexed_search": {"status": "failed", "error": "DP2 job not indexed"}},
    )
    monkeypatch.setattr(module, "validate_coursework_screenshot_manifest", lambda: {"status": "success", "failures": []})

    manifest = module.capture_evidence()

    assert manifest["status"] == "failed"
    assert manifest["failures"] == [{"step": "coursework_indexed_search", "error": "DP2 job not indexed"}]
