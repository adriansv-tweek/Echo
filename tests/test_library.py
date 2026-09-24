"""All-templates overview. Run with: python -m unittest discover tests"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from templates import TemplateStore  # noqa: E402
from ui import LIBRARY_HINT, MainWindow  # noqa: E402


class LibraryViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        path = Path(tempfile.mkdtemp()) / "templates.json"
        self.store = TemplateStore(path)
        self.store.add("Zebra", [], "z")
        self.store.add("alpha", [], "a")
        self.store.add("Manglende", [], "generic text")
        self.window = MainWindow(self.store)

    def titles(self) -> list[str]:
        return [self.window.results.item(row).text() for row in range(self.window.results.count())]

    def test_button_sits_opposite_settings(self) -> None:
        page = self.window.library_button.parentWidget()
        header = page.layout().itemAt(0).layout()
        self.assertIs(header.itemAt(0).widget(), self.window.library_button)
        self.assertIs(header.itemAt(header.count() - 1).widget(), self.window.settings_button)
        self.assertEqual(self.window.library_button.text(), "☰")
        self.assertEqual(self.window.library_button.accessibleName(), "Templates")
        self.assertFalse(self.window._library)

    def test_button_toggles_the_overview_without_hiding(self) -> None:
        self.window.show()
        self.window.library_button.click()
        self.assertTrue(self.window._library)
        self.assertEqual(self.window.results.count(), 3)
        self.assertFalse(self.window.isHidden())

        self.window.library_button.click()
        self.assertFalse(self.window._library)
        self.assertEqual(self.window.results.count(), 0)
        self.assertFalse(self.window.library_button.isChecked())
        self.assertFalse(self.window.isHidden())
        self.assertEqual(self.window.search.text(), "")
        self.window.activateWindow()
        self.assertIs(self.window.focusWidget(), self.window.search)

    def test_reopen_starts_with_the_overview_closed(self) -> None:
        self.window.open_library()
        self.assertTrue(self.window._library)
        with patch("ui.foreground_window", return_value=0):
            self.window.show_and_focus()
        self.assertFalse(self.window._library)
        self.assertFalse(self.window.library_button.isChecked())
        self.assertEqual(self.window.results.count(), 0)

    def test_library_lists_every_template_alphabetically(self) -> None:
        self.window.open_library()
        self.assertEqual(self.titles(), ["alpha", "Manglende", "Zebra"])
        self.assertEqual(self.window.results.currentItem().text(), "alpha")
        self.assertTrue(self.window.library_button.isChecked())

    def test_arrow_keys_move_the_selection(self) -> None:
        self.window.open_library()
        self.window._move_selection(1)
        self.assertEqual(self.window._current_template().title, "Manglende")
        self.window._move_selection(-1)
        self.assertEqual(self.window._current_template().title, "alpha")

    def test_enter_enter_still_copies_from_the_library(self) -> None:
        self.window.show()
        self.window.open_library()
        self.window._handle_enter()
        self.assertTrue(self.window._armed)
        self.assertFalse(self.window.isHidden())
        self.window._return_hwnd = 55
        with (
            patch("ui.copy_text", return_value=True) as copied,
            patch("ui.foreground_window", return_value=55),
            patch("ui.focus_window"),
            patch("ui.send_ctrl_v", return_value=True),
        ):
            self.window._handle_enter()
        copied.assert_called_once_with("a")
        self.assertTrue(self.window.isHidden())

    def test_escape_returns_to_search_without_hiding(self) -> None:
        self.window.show()
        self.window.open_library()
        self.window._on_escape()
        self.assertFalse(self.window._library)
        self.assertFalse(self.window.library_button.isChecked())
        self.assertEqual(self.window.results.count(), 0)
        self.assertFalse(self.window.isHidden())

    def test_edit_and_delete_use_the_library_selection(self) -> None:
        self.window.open_library()
        self.window._move_selection(1)
        self.window.edit_template()
        self.assertEqual(self.window._mode, "edit")
        self.assertEqual(self.window.title_edit.text(), "Manglende")
        self.window._cancel_edit()

        self.window.open_library()
        self.window._move_selection(2)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.window.delete_template()
        self.assertEqual(self.titles(), ["alpha", "Manglende"])
        self.assertEqual([template.title for template in self.store.templates], ["alpha", "Manglende"])

    def test_library_status_mentions_enter_and_escape(self) -> None:
        self.window.open_library()
        self.assertEqual(self.window.status.text(), LIBRARY_HINT)
        self.assertIn("Esc", LIBRARY_HINT)


if __name__ == "__main__":
    unittest.main()
