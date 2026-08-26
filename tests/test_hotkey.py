"""Hotkey configuration. Run with: python -m unittest discover tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hotkey import (  # noqa: E402
    HOTKEY_MODIFIERS,
    HOTKEY_NAME,
    HOTKEY_VK,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    VK_OEM_PERIOD,
)


class HotkeyConfigTest(unittest.TestCase):
    def test_default_is_ctrl_shift_period(self) -> None:
        self.assertEqual(HOTKEY_NAME, "Ctrl+Shift+.")
        self.assertEqual(HOTKEY_VK, VK_OEM_PERIOD)
        self.assertEqual(HOTKEY_VK, 0xBE)
        self.assertEqual(HOTKEY_MODIFIERS, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT)

    def test_name_is_the_single_place_to_display_the_shortcut(self) -> None:
        self.assertTrue(HOTKEY_NAME)
        self.assertNotIn("Ctrl+Alt+E", HOTKEY_NAME)
        self.assertNotIn("Ctrl+Shift+M", HOTKEY_NAME)


if __name__ == "__main__":
    unittest.main()
