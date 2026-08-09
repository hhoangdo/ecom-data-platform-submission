from __future__ import annotations

from pathlib import Path


LOCUSTFILE = Path(__file__).with_name("locustfile.py")


def test_locust_shape_is_fixed_and_uses_the_future_runtime_paths() -> None:
    source = LOCUSTFILE.read_text(encoding="utf-8")
    assert "fixed_count = 1" in source
    assert '"/v1/retrieval/search"' in source
    assert "success" in source
    assert "abstention" in source
    assert "error" in source
    assert "evidence/04_2_llm_design/load/locust.html" in source
    assert "evidence/04_2_llm_design/load/locust_stats" in source
