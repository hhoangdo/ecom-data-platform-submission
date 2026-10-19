from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]


def _load_script():
    path = ROOT / "scripts/qa/verify_edai2_test_scope.py"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "src/vina_bim_shop").mkdir(parents=True)
    (tmp_path / "src/vina_bim_shop/a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/t.py").write_text("y = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "one"], cwd=tmp_path, check=True)
    (tmp_path / "src/vina_bim_shop/a.py").write_text("x = 2\n", encoding="utf-8")
    (tmp_path / "src/vina_bim_shop/generated").mkdir()
    (tmp_path / "src/vina_bim_shop/generated/b.py").write_text("z = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "two"], cwd=tmp_path, check=True)
    return tmp_path


def test_derive_scope_keeps_only_changed_production_python() -> None:
    """Generated, vendor, and test files can never enter the denominator."""
    scope_mod = _load_script()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        repo = _git_repo(Path(tmp))
        base = subprocess.run(["git", "rev-parse", "HEAD~1"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
        scope = scope_mod.derive_scope(
            repo, base, head, ROOT / "configs/llm/test_scope.yaml"
        )
        assert scope["files"] == ["src/vina_bim_shop/a.py"]
        assert set(scope["hashes"]) == {"src/vina_bim_shop/a.py"}
        assert all(len(value) == 64 for value in scope["hashes"].values())


def test_derive_scope_rejects_unknown_ref() -> None:
    scope_mod = _load_script()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        repo = _git_repo(Path(tmp))
        with pytest.raises(ValueError, match="ref"):
            scope_mod.derive_scope(repo, "0" * 40, "HEAD", ROOT / "configs/llm/test_scope.yaml")


def test_write_coverage_report_enforces_fail_under() -> None:
    scope_mod = _load_script()
    import tempfile

    coverage_data = {
        "files": {"src/vina_bim_shop/llm/x.py": {"summary": {"percent_covered": 95.0}}},
        "totals": {"percent_covered": 95.0},
    }
    scope = {"files": ["src/vina_bim_shop/llm/x.py"], "hashes": {"src/vina_bim_shop/llm/x.py": "a" * 64}}
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "coverage.json"
        assert scope_mod.write_coverage_report(coverage_data, scope, output, 91) == 95.0
        assert json.loads(output.read_text(encoding="utf-8"))["percent"] == 95.0
        with pytest.raises(ValueError, match="coverage"):
            scope_mod.write_coverage_report(coverage_data, scope, output, 96)


def test_write_mutation_report_rejects_unknown_and_zero_denominator() -> None:
    scope_mod = _load_script()
    import tempfile

    scope = {"files": ["src/vina_bim_shop/llm/x.py"], "hashes": {}}
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "mutation.json"
        good = "x.py:1: killed\nx.py:2: survived\nx.py:3: killed\nx.py:4: killed\nx.py:5: killed\nx.py:6: killed\n"
        assert scope_mod.write_mutation_report(scope, good, output, 0.80, ["mutmut", "run"])["score"] == pytest.approx(5 / 6)
        with pytest.raises(ValueError, match="unknown"):
            scope_mod.write_mutation_report(scope, "x.py:1: vaporized\n", output, 0.80, ["mutmut"])
        with pytest.raises(ValueError, match="denominator"):
            scope_mod.write_mutation_report(scope, "\n", output, 0.80, ["mutmut"])
