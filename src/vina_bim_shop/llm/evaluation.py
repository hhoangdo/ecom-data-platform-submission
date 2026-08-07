"""Small configuration and evaluation contracts for successor evidence tasks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr


class EvaluationGate(BaseModel):
    """One named measured gate with a fail-closed result."""

    model_config = ConfigDict(extra="forbid")

    name: StrictStr
    threshold: StrictFloat
    measured: StrictFloat
    passed: StrictBool


def load_yaml_config(path: str | Path) -> dict[str, Any]:
    """Load a local YAML contract without reaching a network or runtime."""

    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("configuration root must be an object")
    return value


def load_json_config(path: str | Path) -> dict[str, Any] | list[Any]:
    """Load a local JSON contract without executing it."""

    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, (dict, list)):
        raise ValueError("configuration root must be an object or array")
    return value


__all__ = ["EvaluationGate", "load_json_config", "load_yaml_config"]
