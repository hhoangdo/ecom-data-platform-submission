from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (_repo_root() / relative_path).read_text(encoding="utf-8")


def test_section03_deliverable_locks_contracts_evidence_and_rubric_traceability() -> None:
    content = _read("deliverables/03_data_generator_improvement.md")

    for phrase in [
        "Sheet3!E32",
        "Sheet3!E33",
        "Sheet3!E34",
        "customer_order_frequency",
        "config_snapshot.yaml",
        "ml_customer_label.csv",
        "ml_customer_purchase_training.csv",
        "f_customer_order_frequency_7d",
        "warning at `psi >= 0.10`",
        "alert at `psi >= 0.15`",
        "id,label",
        "Feast-ready offline export",
        "evidence/03_data_generator_improvement/section03_candidate_manifest.json",
        "evidence/03_data_generator_improvement/section03_manifest.json",
        "section03_config_and_training_join.png",
    ]:
        assert phrase in content

    lowered = content.lower()
    assert "out of scope for current platform evidence" not in lowered
    assert "placeholder" not in lowered
    assert "feast installation" in lowered
    assert "no live airflow/datahub" in lowered


def test_section03_operator_commands_and_script_inventory_are_discoverable() -> None:
    repo_root = _repo_root()
    makefile = _read("Makefile")
    scripts_readme = _read("scripts/README.md")
    readme = _read("README.md")

    for target in ["generate-section03", "build-section03-dbt", "test-section03"]:
        assert f"{target}:" in makefile
        assert f"{target}" in scripts_readme

    assert "uv run python scripts/generate/run_generator.py" in makefile
    assert "uv run python scripts/analytics/run_section03_dbt.py" in makefile
    assert "uv run pytest tests/unit/test_section03_drift.py" in makefile

    for operator_command in [
        "rtk make generate-section03 SCALE=medium SEED=42",
        "rtk make build-section03-dbt SCALE=medium",
        "rtk make test-section03",
    ]:
        assert operator_command in readme

    for script_path in [
        "scripts/analytics/run_section03_dbt.py",
        "scripts/orchestration/run_section03_dp3.py",
        "scripts/generate/finalize_section03_evidence.py",
        "scripts/generate/verify_section03_manifest.py",
    ]:
        assert f"`{script_path}`" in scripts_readme

    assert (repo_root / "scripts" / "generate" / "verify_section03_manifest.py").is_file()


def test_section03_public_docs_define_scenario_config_and_feast_boundary() -> None:
    scenario_readme = _read("configs/scenarios/README.md")
    masterplan = _read("architecture/masterplan.md")
    business_context = _read("architecture/domain/business-context.md")
    readme = _read("README.md")

    for phrase in [
        "configs/generator/base.yaml",
        "customer_order_frequency",
        "pre-drift",
        "post-drift",
        "canonical YAML",
    ]:
        assert phrase in scenario_readme

    for content in [masterplan, business_context, readme]:
        assert "Section 03" in content
        assert "Feast-ready" in content or "Feast" in content

    assert "drift scenarios are outside the current project scope" not in masterplan
    assert "drift scenarios, ML implementation, and LLM implementation remain outside" not in masterplan
    assert "campaign" in business_context.lower()
    assert "AI" in business_context
    assert "deliverables/03_data_generator_improvement.md" in readme

