"""Pure input-safety boundaries for later grounded-response services."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SafetyDecision:
    """Sanitized decision that carries no raw secret or PII."""

    action: str
    reason_code: str


def inspect_message(message: str) -> SafetyDecision:
    """Reject obvious prompt-injection markers without external calls."""

    if re.search(r"ignore\s+(all|previous)\s+instructions", message, re.IGNORECASE):
        return SafetyDecision(action="reject", reason_code="prompt_injection")
    return SafetyDecision(action="allow", reason_code="none")


__all__ = ["SafetyDecision", "inspect_message"]
