from __future__ import annotations

import copy
import json
from importlib import resources
from typing import Any

import pytest
from hypothesis import HealthCheck, settings

settings.register_profile(
    "ci",
    derandomize=True,
    deadline=None,
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("ci")


def raw_data() -> dict[str, Any]:
    text = resources.files("roadmap_calc").joinpath("data/roadmap-2026.json").read_text("utf-8")
    data: dict[str, Any] = json.loads(text)
    return data


@pytest.fixture
def raw() -> dict[str, Any]:
    """A fresh mutable copy of the bundled JSON data."""
    return copy.deepcopy(raw_data())


def set_path(data: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        data = data[int(part)] if isinstance(data, list) else data[part]
    last = parts[-1]
    if isinstance(data, list):
        data[int(last)] = value
    else:
        data[last] = value


def del_path(data: Any, path: str) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        data = data[int(part)] if isinstance(data, list) else data[part]
    last = parts[-1]
    if isinstance(data, list):
        del data[int(last)]
    else:
        del data[last]
