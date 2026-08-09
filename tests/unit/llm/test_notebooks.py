"""Structure-only contracts for the unexecuted Topic 14 agent walkthrough notebooks."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
NOTEBOOKS = {
    "drift_agent_mcp.ipynb": {
        "parameters": {
            "BASE_URL",
            "FIXTURE_ID",
            "MODEL_VERSION",
            "FEATURE_SERVICE_VERSION",
        },
        "request_variable": "drift_request",
        "request_keys": {"id", "baseline_window", "candidate_window", "feature_name"},
        "response_variable": "drift_response_schema",
        "response_keys": {
            "request_id",
            "scope",
            "feature_name",
            "window_days",
            "baseline_window",
            "candidate_window",
            "population_size",
            "candidate_day_count",
            "baseline_mean",
            "candidate_mean",
            "psi",
            "status",
            "drift_detected",
            "feature_service_version",
            "customer_context",
            "observed_at",
        },
    },
    "retrieval_agent_mcp.ipynb": {
        "parameters": {"BASE_URL", "FIXTURE_ID", "MODEL_VERSION", "INDEX_VERSION"},
        "request_variable": "retrieval_request",
        "request_keys": {"query", "top_k", "category", "effective_at"},
        "response_variable": "retrieval_response_schema",
        "response_keys": {
            "request_id",
            "index_version",
            "embedding_model",
            "matches",
            "retrieval_ms",
            "abstained",
            "reason",
        },
    },
}
SECRET_OR_PII = re.compile(r"authorization:\s*bearer|api[_-]?key|password|[\w.+-]+@[\w-]+\.[\w.-]+", re.I)


def _notebook(name: str) -> dict[str, object]:
    path = ROOT / "notebooks/edai2" / name
    assert path.is_file(), f"missing Topic 14 notebook: {path.relative_to(ROOT)}"
    return json.loads(path.read_text(encoding="utf-8"))


def _source(cell: dict[str, object]) -> str:
    return "".join(cell.get("source", []))


def _literal_assignment(cell: dict[str, object], variable: str) -> object:
    tree = ast.parse(_source(cell))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == variable
            for target in statement.targets
        ):
            return ast.literal_eval(statement.value)
    raise AssertionError(f"missing literal assignment for {variable}")


def test_notebooks_begin_with_exact_deterministic_parameter_cells() -> None:
    for name, contract in NOTEBOOKS.items():
        notebook = _notebook(name)
        first = notebook["cells"][0]
        assert first["cell_type"] == "code"
        assert "parameters" in first["metadata"].get("tags", [])
        source = _source(first)
        assert {
            line.split("=", 1)[0].strip() for line in source.splitlines() if "=" in line
        } == contract["parameters"]


def test_notebooks_show_exact_public_request_and_response_shapes() -> None:
    for name, contract in NOTEBOOKS.items():
        cells = _notebook(name)["cells"]
        request = next(
            _literal_assignment(cell, contract["request_variable"])
            for cell in cells
            if contract["request_variable"] in _source(cell)
        )
        response = next(
            _literal_assignment(cell, contract["response_variable"])
            for cell in cells
            if contract["response_variable"] in _source(cell)
        )
        assert set(request) == contract["request_keys"]
        assert set(response) == contract["response_keys"]


def test_notebooks_use_the_required_tutorial_narrative() -> None:
    required_sections = {
        "## Audience",
        "## Prerequisites",
        "## Learning goals",
        "## Outline",
        "## Exercise",
        "## Answer scaffold",
        "## Pitfalls",
        "## Optional extension",
    }
    for name in NOTEBOOKS:
        rendered = "\n".join(_source(cell) for cell in _notebook(name)["cells"])
        lines = {line.strip() for line in rendered.splitlines() if line.strip()}
        assert required_sections <= lines
        assert all(any(line.startswith(number) for line in lines) for number in ("1.", "2.", "3."))


def test_notebooks_are_cleared_safe_and_explicitly_defer_execution_to_task_12() -> None:
    for name in NOTEBOOKS:
        notebook = _notebook(name)
        assert notebook["nbformat"] == 4
        assert all(
            cell.get("execution_count") is None
            for cell in notebook["cells"]
            if cell["cell_type"] == "code"
        )
        assert all(
            not cell.get("outputs", [])
            for cell in notebook["cells"]
            if cell["cell_type"] == "code"
        )
        rendered = "\n".join(_source(cell) for cell in notebook["cells"])
        assert "Task 12 owns execution" in rendered
        assert not SECRET_OR_PII.search(rendered)
