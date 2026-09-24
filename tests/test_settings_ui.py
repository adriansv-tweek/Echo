"""Settings view behaviour. Run with: python -m unittest discover tests"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import theme  # noqa: E402
from hotkey import DEFAULT_SHORTCUT, HotkeyError, Shortcut  # noqa: E402
from settings import Settings, load_settings, save_settings  # noqa: E402
from templates import TemplateStore  # noqa: E402
from ui import BROWSE_PAGE, SETTINGS_PAGE, MainWindow  # noqa: E402


class FakeHotkey:
    """Stands in for HotkeyListener without touching the Windows API."""

    def __init__(self, shortcut=DEFAULT_SHORTCUT, fails=False) -> None:
        self.shortcut = shortcut
        self.fails = fails
        self.rebinds = []

    def rebind(self, shortcut: Shortcut) -> None:
        self.rebinds.append(shortcut)
        if self.fails:
            raise HotkeyError(f"{shortcut.name} is already used by another application.")
        self.shortcut = shortcut


def key_event(key, modifiers, virtual_key):
    return QKeyEvent(QEvent.KeyPress, key, modifiers, 0, virtual_key, 0)


class SettingsViewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        self.store = TemplateStore(self.dir / "templates.json")
        self.saved = []
        self.hotkey = FakeHotkey()

    def make_window(self, settings=None, hotkey=None):
        return MainWindow(
            self.store,
            settings or Settings(),
            hotkey if hotkey is not None else self.hotkey,
            self.saved.append,
        )

    # --- defaults -----------------------------------------------------------

    def test_fresh_install_defaults_to_dark_and_ctrl_shift_period(self) -> None:
        window = self.make_window()
        window.open_settings()
        self.assertEqual(window.settings.theme, theme.DARK)
        self.assertTrue(window.dark_button.isChecked())
        self.assertFalse(window.light_button.isChecked())
        self.assertEqual(window.shortcut_value.text(), "Ctrl+Shift+.")

    def test_settings_button_is_present_and_compact(self) -> None:
        window = self.make_window()
        self.assertEqual(window.settings_button.objectName(), "iconButton")
        self.assertEqual(window.settings_button.accessibleName(), "Settings")

    def test_settings_open_and_close_stay_in_the_same_window(self) -> None:
        window = self.make_window()
        self.assertIsNone(window.findChild(type(window)))
        window.open_settings()
        self.assertEqual(window.pages.currentIndex(), SETTINGS_PAGE)
        self.assertEqual(window._mode, "settings")
        window.close_settings()
        self.assertEqual(window.pages.currentIndex(), BROWSE_PAGE)
        self.assertEqual(window._mode, "browse")

    def test_escape_closes_settings_without_hiding_echo(self) -> None:
        window = self.make_window()
        window.show()
        window.open_settings()
        window._on_escape()
        self.assertEqual(window.pages.currentIndex(), BROWSE_PAGE)
        self.assertFalse(window.isHidden())

    # --- appearance ---------------------------------------------------------

    def test_switching_to_light_applies_immediately_and_saves(self) -> None:
        window = self.make_window()
        window.open_settings()
        dark_css = window.styleSheet()

        window.set_theme(theme.LIGHT)

        self.assertEqual(window.settings.theme, theme.LIGHT)
        self.assertNotEqual(window.styleSheet(), dark_css)
        self.assertEqual(window.styleSheet(), theme.stylesheet(theme.LIGHT))
        self.assertTrue(window.light_button.isChecked())
        self.assertFalse(window.dark_button.isChecked())
        self.assertEqual(self.saved[-1].theme, theme.LIGHT)

    def test_appearance_persists_across_restart(self) -> None:
        path = self.dir / "settings.json"
        window = self.make_window()
        window.on_settings_changed = lambda s: save_settings(path, s)
        window.open_settings()
        window.set_theme(theme.LIGHT)

        restarted = self.make_window(settings=load_settings(path))
        self.assertEqual(restarted.settings.theme, theme.LIGHT)
        self.assertEqual(restarted.styleSheet(), theme.stylesheet(theme.LIGHT))
        restarted.open_settings()
        self.assertTrue(restarted.light_button.isChecked())

    def test_both_themes_define_every_colour_the_stylesheet_needs(self) -> None:
        for name in (theme.DARK, theme.LIGHT):
            with self.subTest(theme=name):
                css = theme.stylesheet(name)
                self.assertNotIn("$", css)
                self.assertIn("QListWidget::item:selected", css)

    def test_themes_use_distinct_backgrounds_and_text(self) -> None:
        dark, light = theme.colours(theme.DARK), theme.colours(theme.LIGHT)
        self.assertNotEqual(dark["window_bg"], light["window_bg"])
        self.assertNotEqual(dark["text"], light["text"])
        for colours in (dark, light):
            self.assertNotEqual(colours["text"], colours["window_bg"])
            self.assertNotEqual(colours["field_text"], colours["field_bg"])
            self.assertNotEqual(colours["placeholder"], colours["field_bg"])
            self.assertNotEqual(colours["select_text"], colours["select_bg"])

    # --- global shortcut ----------------------------------------------------

    def test_capture_button_prompts_and_reports_a_combination(self) -> None:
        window = self.make_window()
        window.open_settings()
        button = window.capture_button

        button.start_capture()
        self.assertTrue(button.capturing)
        self.assertEqual(button.text(), "Press your desired shortcut…")

        button.keyPressEvent(key_event(Qt.Key_E, Qt.ControlModifier | Qt.AltModifier, 0x45))

        self.assertFalse(button.capturing)
        self.assertEqual(window.settings.shortcut.name, "Ctrl+Alt+E")
        self.assertEqual(window.shortcut_value.text(), "Ctrl+Alt+E")

    def test_modifier_only_press_does_not_end_capture(self) -> None:
        window = self.make_window()
        window.open_settings()
        button = window.capture_button
        button.start_capture()

        button.keyPressEvent(key_event(Qt.Key_Control, Qt.ControlModifier, 0x11))
        self.assertTrue(button.capturing)

        button.keyPressEvent(key_event(Qt.Key_E, Qt.NoModifier, 0x45))
        self.assertTrue(button.capturing)
        self.assertIn("modifier", button.text())

    def test_escape_cancels_capture_and_keeps_the_shortcut(self) -> None:
        window = self.make_window()
        window.open_settings()
        window.capture_button.start_capture()
        window.capture_button.keyPressEvent(key_event(Qt.Key_Escape, Qt.NoModifier, 0x1B))

        self.assertFalse(window.capture_button.capturing)
        self.assertEqual(window.settings.shortcut, DEFAULT_SHORTCUT)
        self.assertEqual(self.saved, [])

    def test_successful_change_activates_immediately_and_saves(self) -> None:
        window = self.make_window()
        window.open_settings()
        new = Shortcut(("ctrl", "alt"), "E", 0x45)

        window._on_shortcut_captured(new)

        self.assertEqual(self.hotkey.rebinds, [new])
        self.assertEqual(self.hotkey.shortcut, new)
        self.assertEqual(window.settings.shortcut, new)
        self.assertEqual(self.saved[-1].shortcut, new)
        self.assertIn("Ctrl+Alt+E", window.settings_status.text())

    def test_failed_registration_keeps_the_working_shortcut(self) -> None:
        window = self.make_window(hotkey=FakeHotkey(fails=True))
        window.open_settings()

        window._on_shortcut_captured(Shortcut(("ctrl", "alt"), "E", 0x45))

        self.assertEqual(window.settings.shortcut, DEFAULT_SHORTCUT)
        self.assertEqual(window.shortcut_value.text(), "Ctrl+Shift+.")
        self.assertEqual(self.saved, [], "a failed shortcut must not be saved")
        self.assertIn("already used", window.settings_status.text())

    def test_shortcut_persists_across_restart(self) -> None:
        path = self.dir / "settings.json"
        window = self.make_window()
        window.on_settings_changed = lambda s: save_settings(path, s)
        window.open_settings()
        window._on_shortcut_captured(Shortcut(("ctrl", "alt"), "E", 0x45))

        reloaded = load_settings(path)
        self.assertEqual(reloaded.shortcut.name, "Ctrl+Alt+E")
        restarted = self.make_window(settings=reloaded)
        restarted.open_settings()
        self.assertEqual(restarted.shortcut_value.text(), "Ctrl+Alt+E")

    def test_settings_still_change_when_no_hotkey_is_attached(self) -> None:
        window = MainWindow(self.store, Settings(), None, self.saved.append)
        window.open_settings()
        window._on_shortcut_captured(Shortcut(("ctrl", "alt"), "E", 0x45))
        self.assertEqual(window.settings.shortcut.name, "Ctrl+Alt+E")

    # --- existing workflow is untouched -------------------------------------

    def test_core_workflow_still_works_with_settings_present(self) -> None:
        self.store.add("Manglende", [], "generic text")
        window = self.make_window()
        window.show()
        window.search.setText("manglende")
        self.assertEqual(window.results.count(), 1)

        window._handle_enter()
        self.assertTrue(window._armed)
        self.assertFalse(window.isHidden())

        window._return_hwnd = 55
        with (
            patch("ui.copy_text", return_value=True),
            patch("ui.foreground_window", return_value=55),
            patch("ui.focus_window"),
            patch("ui.send_ctrl_v", return_value=True),
        ):
            window._handle_enter()
        self.assertTrue(window.isHidden())

    def test_enter_does_nothing_while_settings_are_open(self) -> None:
        self.store.add("Manglende", [], "generic text")
        window = self.make_window()
        window.search.setText("manglende")
        window.open_settings()
        with patch("ui.copy_text", return_value=True) as copied:
            window._handle_enter()
            window._handle_enter()
        copied.assert_not_called()

    def test_hotkey_reopen_from_settings_keeps_settings_visible(self) -> None:
        window = self.make_window()
        window.open_settings()
        window.show_and_focus()
        self.assertEqual(window.pages.currentIndex(), SETTINGS_PAGE)

    def test_settings_cannot_be_opened_while_editing(self) -> None:
        window = self.make_window()
        window.add_template()
        window.open_settings()
        self.assertEqual(window._mode, "edit")


if __name__ == "__main__":
    unittest.main()
