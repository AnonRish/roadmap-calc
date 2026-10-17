from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_committed_reproduction_report_is_up_to_date() -> None:
    spec = importlib.util.spec_from_file_location(
        "make_reproduction", ROOT / "scripts" / "make_reproduction.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (ROOT / "docs" / "REPRODUCTION.md").read_text() == module.build(), (
        "run scripts/make_reproduction.py to regenerate docs/REPRODUCTION.md"
    )
