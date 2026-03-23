"""Snapshot comparison / diffing.

Recursively compares two snapshots and reports differences in a compact,
human-readable format suitable for test output.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, asdict
from typing import Any


@dataclass
class DiffResult:
    """Result of comparing two snapshots."""

    changes: list[Change]

    @property
    def has_changes(self) -> bool:
        return len(self.changes) > 0

    def format(self) -> str:
        if not self.changes:
            return "No differences."
        lines = [str(c) for c in self.changes]
        lines.append(f"\n{len(self.changes)} difference(s).")
        return "\n".join(lines)


@dataclass
class Change:
    """A single difference between two snapshots."""

    kind: str  # "added", "removed", "changed", "array_changed"
    path: str
    detail: str

    def __str__(self) -> str:
        sym = {"added": "+", "removed": "-", "changed": "~", "array_changed": "~"}
        return f"  {sym.get(self.kind, '?')} {self.path}: {self.detail}"


def diff_snapshots(old: Any, new: Any) -> DiffResult:
    """Compare two snapshot objects (or any nested dataclass/dict/list structure).

    Both arguments can be Snapshot dataclasses or plain dicts (from JSON).
    """
    changes: list[Change] = []
    _diff(old, new, "", changes)
    return DiffResult(changes=changes)


def _to_dict(obj: Any) -> Any:
    """Convert dataclasses to dicts for uniform comparison."""
    if hasattr(obj, "__dataclass_fields__"):
        return {f.name: _to_dict(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, list):
        return [_to_dict(v) for v in obj]
    return obj


def _diff(old: Any, new: Any, prefix: str, changes: list[Change]) -> None:
    old_d = _to_dict(old)
    new_d = _to_dict(new)
    _diff_values(old_d, new_d, prefix, changes)


def _diff_values(old: Any, new: Any, prefix: str, changes: list[Change]) -> None:
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(set(list(old.keys()) + list(new.keys()))):
            path = f"{prefix}.{key}" if prefix else key
            if key not in old:
                changes.append(Change("added", path, _summarize(new[key])))
            elif key not in new:
                changes.append(Change("removed", path, _summarize(old[key])))
            else:
                _diff_values(old[key], new[key], path, changes)
    elif isinstance(old, list) and isinstance(new, list):
        if old != new:
            path = prefix
            if all(isinstance(x, (int, float)) for x in old) and all(
                isinstance(x, (int, float)) for x in new
            ):
                if len(old) == len(new):
                    diffs = [abs(a - b) for a, b in zip(old, new)]
                    changed = sum(1 for d in diffs if d > 0)
                    changes.append(
                        Change(
                            "array_changed",
                            path,
                            f"{changed}/{len(old)} values changed, "
                            f"max \u0394={max(diffs):.4f}, "
                            f"avg \u0394={sum(diffs) / len(diffs):.4f}",
                        )
                    )
                else:
                    changes.append(
                        Change("changed", path, f"length {len(old)} -> {len(new)}")
                    )
            else:
                changes.append(Change("changed", path, "changed"))
    elif old != new:
        changes.append(Change("changed", prefix, f"{old} -> {new}"))


def _summarize(val: Any) -> str:
    if isinstance(val, list):
        return f"[{len(val)} items]"
    if isinstance(val, dict):
        return f"{{{len(val)} keys}}"
    return str(val)
