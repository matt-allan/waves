"""Pytest configuration and snapshot testing fixtures."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

import pytest

from pcmsnap import Snapshot, render_svg

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

    def assert_match(
        self,
        data: Any,
        name: str | None = None,
        snap: Optional[Snapshot] = None,
    ) -> None:
        """Assert *data* matches the stored snapshot.

        *name* is the snapshot filename (e.g. ``"audio_button_a.json"``).
        If omitted, it is derived from the test function name.

        If *snap* is provided, an SVG rendering is written alongside the
        JSON file for human review.
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
            if snap is not None:
                svg_path = path.with_suffix(".svg")
                svg_path.write_text(render_svg(snap))
            return

        stored = json.loads(path.read_text())
        assert data == stored, (
            f"Snapshot mismatch for {name}. "
            f"Run with --update-snapshots to update."
        )
