"""Copy a generic template to the local system clipboard.

Echo only writes the selected template. It does not read customer information,
watch clipboard changes, keep clipboard history, or send clipboard contents
anywhere.
"""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication


def copy_text(text: str) -> bool:
    """Write text and confirm it arrived. Returns False if the clipboard was busy."""
    clipboard = QGuiApplication.clipboard()
    if clipboard is None:
        return False
    try:
        clipboard.setText(text)
        written = clipboard.text()
    except Exception:
        return False
    if written is None:
        return False
    return _normalize(written) == _normalize(text)


def _normalize(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")
