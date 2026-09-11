"""Settings storage. Run with: python -m unittest discover tests"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hotkey import DEFAULT_SHORTCUT, MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, Shortcut  # noqa: E402
from settings import Settings, load_settings, save_settings, settings_file  # noqa: E402
from theme import DARK, LIGHT  # noqa: E402


class SettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = Path(tempfile.mkdtemp()) / "settings.json"

    def write(self, content: str) -> None:
        self.path.write_text(content, encoding="utf-8")

    def test_fresh_install_defaults_to_dark_and_ctrl_shift_period(self) -> None:
        self.assertFalse(self.path.exists())
        settings = load_settings(self.path)
        self.assertEqual(settings.theme, DARK)
        self.assertEqual(settings.shortcut, DEFAULT_SHORTCUT)
        self.assertEqual(settings.shortcut.name, "Ctrl+Shift+.")

    def test_settings_live_in_appdata_echo(self) -> None:
        path = settings_file()
        self.assertEqual(path.name, "settings.json")
        self.assertEqual(path.parent.name, "Echo")

    def test_round_trip(self) -> None:
        shortcut = Shortcut(("ctrl", "alt"), "E", 0x45)
        save_settings(self.path, Settings(theme=LIGHT, shortcut=shortcut))

        loaded = load_settings(self.path)
        self.assertEqual(loaded.theme, LIGHT)
        self.assertEqual(loaded.shortcut, shortcut)
        self.assertEqual(loaded.shortcut.name, "Ctrl+Alt+E")
        self.assertEqual(loaded.shortcut.modifier_mask, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT)

    def test_saved_file_is_readable_json(self) -> None:
        save_settings(self.path, Settings())
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(data["shortcut"]["modifiers"], ["ctrl", "shift"])
        self.assertEqual(data["shortcut"]["key"], ".")
        self.assertEqual(data["shortcut"]["virtual_key"], 0xBE)

    def test_corrupt_file_falls_back_to_defaults(self) -> None:
        self.write('{"theme": "light"')
        settings = load_settings(self.path)
        self.assertEqual(settings.theme, DARK)
        self.assertEqual(settings.shortcut, DEFAULT_SHORTCUT)

    def test_empty_file_falls_back_to_defaults(self) -> None:
        self.write("")
        self.assertEqual(load_settings(self.path).theme, DARK)

    def test_unknown_theme_falls_back_to_dark(self) -> None:
        self.write(json.dumps({"theme": "neon"}))
        self.assertEqual(load_settings(self.path).theme, DARK)

    def test_light_theme_is_kept(self) -> None:
        self.write(json.dumps({"theme": "light"}))
        self.assertEqual(load_settings(self.path).theme, LIGHT)

    def test_broken_shortcut_falls_back_but_keeps_theme(self) -> None:
        for broken in (
            {"modifiers": [], "key": "E", "virtual_key": 0x45},   # no modifier
            {"modifiers": ["ctrl"], "key": "", "virtual_key": 0x45},
            {"modifiers": ["ctrl"], "key": "E"},                  # no virtual key
            {"modifiers": ["ctrl"], "key": "E", "virtual_key": 0},
            {"modifiers": ["ctrl"], "key": "E", "virtual_key": "0x45"},
            {"modifiers": "ctrl", "key": "E", "virtual_key": 0x45},
            "not a dict",
        ):
            with self.subTest(broken=broken):
                self.write(json.dumps({"theme": "light", "shortcut": broken}))
                settings = load_settings(self.path)
                self.assertEqual(settings.shortcut, DEFAULT_SHORTCUT)
                self.assertEqual(settings.theme, LIGHT)

    def test_unknown_modifiers_are_dropped(self) -> None:
        self.write(json.dumps({
            "shortcut": {"modifiers": ["ctrl", "hyper"], "key": "E", "virtual_key": 0x45}
        }))
        self.assertEqual(load_settings(self.path).shortcut.modifiers, ("ctrl",))

    def test_with_theme_and_with_shortcut_do_not_mutate(self) -> None:
        original = Settings()
        changed = original.with_theme(LIGHT).with_shortcut(Shortcut(("alt",), "E", 0x45))
        self.assertEqual(original.theme, DARK)
        self.assertEqual(original.shortcut, DEFAULT_SHORTCUT)
        self.assertEqual(changed.theme, LIGHT)
        self.assertEqual(changed.shortcut.name, "Alt+E")

    def test_save_leaves_no_temp_file(self) -> None:
        save_settings(self.path, Settings())
        self.assertFalse(self.path.with_name("settings.json.tmp").exists())

    def test_modifier_order_is_stable_in_the_display_name(self) -> None:
        self.assertEqual(Shortcut(("shift", "ctrl"), "E", 0x45).name, "Ctrl+Shift+E")
        self.assertEqual(Shortcut(("win", "alt"), "E", 0x45).name, "Alt+Win+E")


if __name__ == "__main__":
    unittest.main()
