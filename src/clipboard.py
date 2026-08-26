"""Copy text to the local system clipboard."""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication


def copy_text(text: str) -> bool:
    """Copy text and confirm it arrived. Returns False if the clipboard was busy."""
    clipboard = QGuiApplication.clipboard()
    if clipboard is None:
        return False
    try:
        clipboard.setText(text)
        return clipboard.text() == text
    except Exception:
        return False
