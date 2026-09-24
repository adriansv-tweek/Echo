"""Auto-paste after a successful copy. Run with: python -m unittest discover tests"""

import ctypes
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from paste import INPUT, paste_ready, send_ctrl_v  # noqa: E402
from templates import TemplateStore  # noqa: E402
from ui import MainWindow  # noqa: E402


class PasteReadyTest(unittest.TestCase):
    def test_waits_until_previous_window_is_foreground(self) -> None:
        self.assertFalse(paste_ready(1, 99))

    def test_ready_only_when_previous_window_is_foreground(self) -> None:
        self.assertTrue(paste_ready(99, 99))

    def test_timeout_does_not_count_as_ready(self) -> None:
        self.assertFalse(paste_ready(1, 99))

    def test_missing_window_is_not_ready(self) -> None:
        self.assertFalse(paste_ready(0, 0))


class InputStructTest(unittest.TestCase):
    def test_win64_input_is_40_bytes(self) -> None:
        if ctypes.sizeof(ctypes.c_void_p) != 8:
            self.skipTest("64-bit Windows layout")
        self.assertEqual(ctypes.sizeof(INPUT), 40)

    def test_send_input_must_deliver_all_four_keystrokes(self) -> None:
        user32 = MagicMock()
        user32.SendInput.return_value = 0
        with (
            patch("paste._interactive", return_value=True),
            patch("paste.ctypes.WinDLL", return_value=user32),
        ):
            self.assertFalse(send_ctrl_v())
        count, _events, size = user32.SendInput.call_args[0]
        self.assertEqual(count, 4)
        self.assertEqual(size, ctypes.sizeof(INPUT))

    def test_send_input_succeeds_when_windows_accepts_every_event(self) -> None:
        user32 = MagicMock()
        user32.SendInput.return_value = 4
        with (
            patch("paste._interactive", return_value=True),
            patch("paste.ctypes.WinDLL", return_value=user32),
        ):
            self.assertTrue(send_ctrl_v())


class AutoPasteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        path = Path(tempfile.mkdtemp()) / "templates.json"
        self.store = TemplateStore(path)
        self.window = MainWindow(self.store)

    def test_show_remembers_the_window_that_was_active(self) -> None:
        with patch("ui.foreground_window", return_value=4242):
            self.window.show_and_focus()
        self.assertEqual(self.window._return_hwnd, 4242)

    def test_show_does_not_remember_echo_itself(self) -> None:
        self.window._return_hwnd = 7
        with patch("ui.foreground_window", return_value=int(self.window.winId())):
            self.window.show_and_focus()
        self.assertEqual(self.window._return_hwnd, 7)

    def test_paste_happens_only_after_previous_window_is_foreground_then_hides(self) -> None:
        template = self.store.add("Manglende", [], "generic text")
        self.window._return_hwnd = 55
        self.window.show()
        events = []
        seen = {"n": 0}

        def focus(hwnd: int) -> None:
            events.append(("focus", hwnd, self.window.isHidden()))

        def foreground() -> int:
            seen["n"] += 1
            return 1 if seen["n"] < 3 else 55

        def paste() -> bool:
            events.append(("paste", self.window.isHidden(), foreground_now()))
            return True

        def foreground_now() -> int:
            return 55

        with (
            patch("ui.copy_text", return_value=True) as copied,
            patch("ui.focus_window", side_effect=focus),
            patch("ui.foreground_window", side_effect=foreground),
            patch("ui.send_ctrl_v", side_effect=paste),
            patch("ui.PASTE_RETRY_MS", 10),
        ):
            self.window._copy_template(template)
            self.assertFalse(self.window.isHidden())
            self.assertEqual(events, [("focus", 55, False)])
            QTest.qWait(80)

        copied.assert_called_once_with("generic text")
        self.assertEqual(events[0], ("focus", 55, False))
        self.assertEqual(events[-1][0], "paste")
        self.assertFalse(events[-1][1])
        self.assertTrue(self.window.isHidden())

    def test_timeout_hides_without_pasting_or_an_error(self) -> None:
        template = self.store.add("Manglende", [], "generic text")
        self.window._return_hwnd = 55
        self.window.show()
        with (
            patch("ui.copy_text", return_value=True),
            patch("ui.focus_window"),
            patch("ui.foreground_window", return_value=1),
            patch("ui.send_ctrl_v") as paste,
            patch("ui.PASTE_RETRIES", 2),
            patch("ui.PASTE_RETRY_MS", 10),
        ):
            self.window._copy_template(template)
            QTest.qWait(80)
        paste.assert_not_called()
        self.assertTrue(self.window.isHidden())
        self.assertNotIn("error", self.window.status.property("state") or "")

    def test_rejected_ctrl_v_is_sent_once_and_echo_hides(self) -> None:
        template = self.store.add("Manglende", [], "generic text")
        self.window._return_hwnd = 55
        self.window.show()
        with (
            patch("ui.copy_text", return_value=True),
            patch("ui.focus_window"),
            patch("ui.foreground_window", return_value=55),
            patch("ui.send_ctrl_v", return_value=False) as paste,
        ):
            self.window._copy_template(template)
        paste.assert_called_once()
        self.assertTrue(self.window.isHidden())
        self.assertNotIn("error", self.window.status.property("state") or "")

    def test_failed_copy_does_not_hide_or_paste(self) -> None:
        template = self.store.add("Manglende", [], "generic text")
        self.window.show()
        with (
            patch("ui.copy_text", return_value=False),
            patch("ui.send_ctrl_v") as paste,
        ):
            self.window._copy_template(template)
        self.assertFalse(self.window.isHidden())
        paste.assert_not_called()


if __name__ == "__main__":
    unittest.main()
