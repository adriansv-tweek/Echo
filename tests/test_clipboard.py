"""Clipboard write behaviour. Run with: python -m unittest discover tests"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

try:
    from clipboard import copy_text
except ImportError:  # PySide6 is not installed
    copy_text = None  # type: ignore[assignment]


@unittest.skipIf(copy_text is None, "PySide6 is required for clipboard tests")
class CopyTextTest(unittest.TestCase):
    def test_success_writes_the_template_text(self) -> None:
        clipboard = MagicMock()
        clipboard.text.return_value = "generic template"
        with patch("clipboard.QGuiApplication.clipboard", return_value=clipboard):
            self.assertTrue(copy_text("generic template"))
        clipboard.setText.assert_called_once_with("generic template")

    def test_success_accepts_windows_newlines(self) -> None:
        clipboard = MagicMock()
        clipboard.text.return_value = "line1\r\nline2"
        with patch("clipboard.QGuiApplication.clipboard", return_value=clipboard):
            self.assertTrue(copy_text("line1\nline2"))

    def test_missing_clipboard_is_failure(self) -> None:
        with patch("clipboard.QGuiApplication.clipboard", return_value=None):
            self.assertFalse(copy_text("generic template"))

    def test_exception_is_failure(self) -> None:
        clipboard = MagicMock()
        clipboard.setText.side_effect = RuntimeError("busy")
        with patch("clipboard.QGuiApplication.clipboard", return_value=clipboard):
            self.assertFalse(copy_text("generic template"))

    def test_readback_mismatch_is_failure(self) -> None:
        clipboard = MagicMock()
        clipboard.text.return_value = "something else"
        with patch("clipboard.QGuiApplication.clipboard", return_value=clipboard):
            self.assertFalse(copy_text("generic template"))

    def test_none_readback_is_failure(self) -> None:
        clipboard = MagicMock()
        clipboard.text.return_value = None
        with patch("clipboard.QGuiApplication.clipboard", return_value=clipboard):
            self.assertFalse(copy_text("generic template"))


if __name__ == "__main__":
    unittest.main()
