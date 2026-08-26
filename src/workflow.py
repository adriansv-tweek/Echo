"""Keyboard workflow helpers used by the main window and tests."""

from __future__ import annotations


def enter_action(has_selection: bool, armed: bool) -> str:
    """Return 'noop', 'select', or 'copy' for an Enter keypress."""
    if not has_selection:
        return "noop"
    if not armed:
        return "select"
    return "copy"


def next_result_row(count: int, current: int, delta: int) -> int | None:
    """Move the result highlight, staying inside the list."""
    if count <= 0:
        return None
    row = 0 if current < 0 else current
    return max(0, min(count - 1, row + delta))
