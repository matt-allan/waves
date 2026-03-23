"""Pytest configuration and snapshot testing fixtures."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Update snapshot files instead of comparing against them.",
    )


@pytest.fixture
def update_snapshots(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-snapshots"))


@pytest.fixture
def snapshot(request: pytest.FixtureRequest, update_snapshots: bool):
    """Fixture that returns an assertion helper for JSON snapshot testing.

    Usage::

        def test_something(snapshot):
            data = {"key": "value"}
            snapshot.assert_match(data, "my_snapshot.json")

    On first run (or with ``--update-snapshots``), the snapshot file is
    created.  On subsequent runs, the stored snapshot is loaded and compared.

    The *data* argument can be any JSON-serializable value: a dict, list,
    dataclass (converted via ``dataclasses.asdict``), etc.
    """
    return SnapshotAssertion(
        test_name=request.node.name,
        update=update_snapshots,
    )


class SnapshotAssertion:
    """Compare data against a stored JSON snapshot file."""

    def __init__(self, test_name: str, update: bool) -> None:
        self._test_name = test_name
        self._update = update

    def assert_match(self, data: Any, name: str | None = None) -> None:
        """Assert *data* matches the stored snapshot.

        *name* is the snapshot filename (e.g. ``"audio_button_a.json"``).
        If omitted, it is derived from the test function name.
        """
        if name is None:
            name = f"{self._test_name}.json"

        if not name.endswith(".json"):
            name += ".json"

        path = SNAPSHOT_DIR / name

        # Normalize dataclasses to plain dicts.
        if hasattr(data, "__dataclass_fields__"):
            data = asdict(data)

        if self._update or not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2) + "\n")
            if not self._update:
                # First run — snapshot created, nothing to compare yet.
                return
            return

        stored = json.loads(path.read_text())
        assert data == stored, (
            f"Snapshot mismatch for {name}.\n"
            f"Run with --update-snapshots to update.\n"
            f"Diff:\n{_format_diff(stored, data)}"
        )


def _format_diff(old: Any, new: Any, prefix: str = "") -> str:
    """Produce a human-readable diff between two JSON-like structures."""
    lines: list[str] = []
    _diff(old, new, prefix, lines)
    return "\n".join(lines) if lines else "  (no differences)"


def _diff(old: Any, new: Any, prefix: str, lines: list[str]) -> None:
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(set(list(old.keys()) + list(new.keys()))):
            path = f"{prefix}.{key}" if prefix else key
            if key not in old:
                lines.append(f"  + {path}: {_short(new[key])}")
            elif key not in new:
                lines.append(f"  - {path}: {_short(old[key])}")
            else:
                _diff(old[key], new[key], path, lines)
    elif isinstance(old, list) and isinstance(new, list):
        if old != new:
            if len(old) != len(new):
                lines.append(f"  ~ {prefix}: length {len(old)} -> {len(new)}")
            else:
                changed = sum(1 for a, b in zip(old, new) if a != b)
                lines.append(f"  ~ {prefix}: {changed}/{len(old)} values changed")
    elif old != new:
        lines.append(f"  ~ {prefix}: {_short(old)} -> {_short(new)}")


def _short(val: Any) -> str:
    s = repr(val)
    return s if len(s) < 80 else s[:77] + "..."
