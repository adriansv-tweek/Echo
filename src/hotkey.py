"""Global hotkey using the Windows RegisterHotKey API.

Echo registers only the one combination the user has chosen. It never installs
a keyboard hook and never sees any other keystroke.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
ERROR_HOTKEY_ALREADY_REGISTERED = 1409

# Two ids so a new shortcut can be registered before the old one is released.
HOTKEY_ID = 1
HOTKEY_ID_ALT = 2

# Virtual-key codes: https://learn.microsoft.com/windows/win32/inputdev/virtual-key-codes
VK_OEM_PERIOD = 0xBE  # "." on a standard US keyboard

MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")
MODIFIER_FLAGS = {"ctrl": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT, "win": MOD_WIN}
MODIFIER_LABELS = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win"}


class HotkeyError(RuntimeError):
    pass


@dataclass(frozen=True)
class Shortcut:
    """A modifier combination plus one key, e.g. Ctrl+Shift+."""

    modifiers: tuple[str, ...]
    key: str
    virtual_key: int

    @property
    def name(self) -> str:
        parts = [MODIFIER_LABELS[m] for m in MODIFIER_ORDER if m in self.modifiers]
        return "+".join([*parts, self.key])

    @property
    def modifier_mask(self) -> int:
        mask = MOD_NOREPEAT
        for modifier in self.modifiers:
            mask |= MODIFIER_FLAGS[modifier]
        return mask

    def to_dict(self) -> dict:
        return {
            "modifiers": list(self.modifiers),
            "key": self.key,
            "virtual_key": self.virtual_key,
        }

    @staticmethod
    def from_dict(data) -> "Shortcut | None":
        """Rebuild a shortcut from settings.json, or None if it is unusable."""
        if not isinstance(data, dict):
            return None

        raw_modifiers = data.get("modifiers")
        if not isinstance(raw_modifiers, list):
            return None
        modifiers = tuple(
            m for m in MODIFIER_ORDER if isinstance(m, str) and m in raw_modifiers
        )
        if not modifiers:
            return None

        key = data.get("key")
        virtual_key = data.get("virtual_key")
        if not isinstance(key, str) or not key:
            return None
        if not isinstance(virtual_key, int) or isinstance(virtual_key, bool):
            return None
        if not 1 <= virtual_key <= 0xFF:
            return None

        return Shortcut(modifiers, key, virtual_key)


DEFAULT_SHORTCUT = Shortcut(("ctrl", "shift"), ".", VK_OEM_PERIOD)

# Kept for display and tests: the out-of-the-box shortcut.
HOTKEY_NAME = DEFAULT_SHORTCUT.name
HOTKEY_MODIFIERS = DEFAULT_SHORTCUT.modifier_mask
HOTKEY_VK = DEFAULT_SHORTCUT.virtual_key


class _WindowsMessageFilter(QAbstractNativeEventFilter):
    """Watch the Qt message loop for the single WM_HOTKEY we registered."""

    def __init__(self, listener: "HotkeyListener") -> None:
        super().__init__()
        self._listener = listener

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == self._listener.active_id:
                self._listener.activated.emit()
        return False, 0


class HotkeyListener(QObject):
    activated = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._filter = _WindowsMessageFilter(self)
        self._user32 = None
        self._app = None
        self.active_id: int | None = None
        self.shortcut: Shortcut | None = None

    def register(self, app, shortcut: Shortcut | None = None) -> None:
        """Claim the shortcut. Raises HotkeyError if it is unavailable."""
        if sys.platform != "win32":
            raise HotkeyError("The global hotkey is only supported on Windows.")

        shortcut = shortcut or DEFAULT_SHORTCUT
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.RegisterHotKey.argtypes = (
            wintypes.HWND,
            ctypes.c_int,
            wintypes.UINT,
            wintypes.UINT,
        )
        user32.RegisterHotKey.restype = wintypes.BOOL
        user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
        user32.UnregisterHotKey.restype = wintypes.BOOL
        self._user32 = user32
        self._app = app

        app.installNativeEventFilter(self._filter)
        try:
            self._claim(HOTKEY_ID, shortcut)
        except HotkeyError:
            app.removeNativeEventFilter(self._filter)
            raise
        self.active_id = HOTKEY_ID
        self.shortcut = shortcut

    def rebind(self, shortcut: Shortcut) -> None:
        """Switch to a new shortcut, keeping the old one if the new one fails.

        The new combination is registered under a spare id first, so a failure
        leaves the currently working shortcut untouched.
        """
        if self.active_id is None:
            raise HotkeyError("No global shortcut is active.")
        if self.shortcut == shortcut:
            return

        spare_id = HOTKEY_ID_ALT if self.active_id == HOTKEY_ID else HOTKEY_ID
        self._claim(spare_id, shortcut)  # raises before anything is released

        self._user32.UnregisterHotKey(None, self.active_id)
        self.active_id = spare_id
        self.shortcut = shortcut

    def unregister(self) -> None:
        if self.active_id is None or self._user32 is None:
            return
        self._user32.UnregisterHotKey(None, self.active_id)
        self.active_id = None

    def _claim(self, hotkey_id: int, shortcut: Shortcut) -> None:
        ok = self._user32.RegisterHotKey(
            None, hotkey_id, shortcut.modifier_mask, shortcut.virtual_key
        )
        if ok:
            return
        code = ctypes.get_last_error()
        if code == ERROR_HOTKEY_ALREADY_REGISTERED:
            raise HotkeyError(
                f"{shortcut.name} is already used by another application. "
                "Echo still works from the tray icon."
            )
        raise HotkeyError(
            f"Could not register {shortcut.name} (Windows error {code}). "
            "Echo still works from the tray icon."
        )
