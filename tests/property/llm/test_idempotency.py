from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from vina_bim_shop.llm.evaluation import nearest_rank_p95
from vina_bim_shop.llm.safety import redact_sensitive_text


@settings(max_examples=30, deadline=None)
@given(st.lists(st.floats(min_value=0, max_value=10_000, allow_nan=False, allow_infinity=False), min_size=1, max_size=50))
def test_nearest_rank_p95_is_deterministic(values: list[float]) -> None:
    assert nearest_rank_p95(values) == nearest_rank_p95(list(reversed(values)))


@settings(max_examples=30, deadline=None)
@given(st.text(max_size=200))
def test_redaction_is_idempotent(message: str) -> None:
    assert redact_sensitive_text(redact_sensitive_text(message)) == redact_sensitive_text(message)
