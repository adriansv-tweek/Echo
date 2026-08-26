"""Inline editor stays in the main window. Run with: python -m unittest discover tests"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from templates import TemplateStore  # noqa: E402
from ui import MainWindow  # noqa: E402
import ui as ui_module  # noqa: E402


class InlineEditorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        path = Path(tempfile.mkdtemp()) / "templates.json"
        self.store = TemplateStore(path)
        self.window = MainWindow(self.store)

    def test_there_is_no_separate_editor_dialog(self) -> None:
        self.assertFalse(hasattr(ui_module, "TemplateEditorDialog"))
        self.window.add_template()
        self.assertIsNone(self.window.findChild(QDialog))
        self.assertEqual(self.window.pages.currentIndex(), 1)

    def test_new_and_save_stay_in_the_same_window(self) -> None:
        self.assertEqual(self.window._mode, "browse")
        self.window.add_template()
        self.assertEqual(self.window._mode, "edit")
        self.window.title_edit.setText("Manglende")
        self.window.keywords_edit.setText("mangler")
        self.window.text_edit.setPlainText("Hei igjen")
        self.window._save_edit()

        self.assertEqual(self.window._mode, "browse")
        self.assertEqual(self.window.pages.currentIndex(), 0)
        self.assertEqual(len(self.store.templates), 1)
        self.assertEqual(self.store.templates[0].title, "Manglende")

        reloaded = TemplateStore(self.store.path)
        self.assertIsNone(reloaded.load())
        self.assertEqual(reloaded.templates[0].text, "Hei igjen")

    def test_edit_populates_the_same_window(self) -> None:
        template = self.store.add("Refusjon bank", ["bank"], "body")
        self.window.search.setText("refusjon")
        self.window._select_id(template.id)
        self.window.edit_template()

        self.assertEqual(self.window._mode, "edit")
        self.assertEqual(self.window.title_edit.text(), "Refusjon bank")
        self.assertEqual(self.window.text_edit.toPlainText(), "body")
        self.window.title_edit.setText("Refusjon Trumf")
        self.window._save_edit()
        self.assertEqual(self.store.get(template.id).title, "Refusjon Trumf")

    def test_cancel_without_changes_returns_to_browse(self) -> None:
        self.window.add_template()
        self.window._cancel_edit()
        self.assertEqual(self.window._mode, "browse")
        self.assertEqual(self.window.pages.currentIndex(), 0)

    def test_search_selects_the_top_ranked_result(self) -> None:
        self.store.add("Other", ["manglende"], "a")
        self.store.add("Manglende varer", [], "b")
        self.store.add("Manglende", [], "c")
        self.window.search.setText("manglende")
        self.assertEqual(self.window.results.count(), 3)
        self.assertEqual(self.window.results.item(0).text(), "Manglende")
        self.assertEqual(self.window._current_template().title, "Manglende")

    def test_enter_then_enter_copies_and_hides(self) -> None:
        self.store.add("Manglende", [], "generic text")
        self.window.search.setText("manglende")
        self.window.show()
        self.assertFalse(self.window.isHidden())

        self.window._handle_enter()
        self.assertTrue(self.window._armed)
        self.assertFalse(self.window.isHidden())

        with patch("ui.copy_text", return_value=True):
            self.window._handle_enter()
        self.assertTrue(self.window.isHidden())

    def test_failed_copy_does_not_hide(self) -> None:
        self.store.add("Manglende", [], "generic text")
        self.window.search.setText("manglende")
        self.window.show()
        self.window._handle_enter()
        with patch("ui.copy_text", return_value=False):
            self.window._handle_enter()
        self.assertFalse(self.window.isHidden())
        self.assertIn("Could not copy", self.window.status.text())

    def test_enter_with_no_results_is_safe(self) -> None:
        self.window.search.setText("does-not-exist")
        self.window._handle_enter()
        self.assertFalse(self.window._armed)
        self.assertEqual(self.window.results.count(), 0)

    def test_empty_search_shows_no_templates(self) -> None:
        self.store.add("Manglende", [], "body")
        self.window.refresh_results()
        self.assertEqual(self.window.results.count(), 0)
        self.assertEqual(self.window.preview.toPlainText(), "")
        self.assertEqual(self.window.preview_title.text(), "")
        self.assertTrue(self.window.new_button.isEnabled())
        self.assertFalse(self.window.edit_button.isEnabled())
        self.assertFalse(self.window.delete_button.isEnabled())

    def test_typing_reveals_matches_and_enables_edit_delete(self) -> None:
        self.store.add("Manglende", [], "body")
        self.window.search.setText("manglende")
        self.assertEqual(self.window.results.count(), 1)
        self.assertTrue(self.window.edit_button.isEnabled())
        self.assertTrue(self.window.delete_button.isEnabled())

    def test_reopen_clears_search(self) -> None:
        self.store.add("Manglende", [], "body")
        self.window.search.setText("manglende")
        self.assertEqual(self.window.results.count(), 1)
        self.window.show_and_focus()
        self.assertEqual(self.window.search.text(), "")
        self.assertEqual(self.window.results.count(), 0)


if __name__ == "__main__":
    unittest.main()
