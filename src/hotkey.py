"""Global hotkey using the Windows RegisterHotKey API.

Echo registers only the one combination defined below. It never installs a
keyboard hook and never sees any other keystroke.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
ERROR_HOTKEY_ALREADY_REGISTERED = 1409

HOTKEY_ID = 1

# Change the global shortcut here. Echo registers this combination only.
# Virtual-key codes: https://learn.microsoft.com/windows/win32/inputdev/virtual-key-codes
VK_OEM_PERIOD = 0xBE  # "." on a standard US keyboard
HOTKEY_MODIFIERS = MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT
HOTKEY_VK = VK_OEM_PERIOD
HOTKEY_NAME = "Ctrl+Shift+."


class HotkeyError(RuntimeError):
    pass


class _WindowsMessageFilter(QAbstractNativeEventFilter):
    """Watch the Qt message loop for the single WM_HOTKEY we registered."""

    def __init__(self, on_hotkey) -> None:
        super().__init__()
        self._on_hotkey = on_hotkey

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self._on_hotkey()
        return False, 0


class HotkeyListener(QObject):
    activated = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._filter = _WindowsMessageFilter(self.activated.emit)
        self._user32 = None
        self._registered = False

    def register(self, app) -> None:
        """Claim the configured hotkey. Raises HotkeyError if it is unavailable."""
        if sys.platform != "win32":
            raise HotkeyError("The global hotkey is only supported on Windows.")

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

        app.installNativeEventFilter(self._filter)
        ok = user32.RegisterHotKey(None, HOTKEY_ID, HOTKEY_MODIFIERS, HOTKEY_VK)
        if not ok:
            app.removeNativeEventFilter(self._filter)
            code = ctypes.get_last_error()
            if code == ERROR_HOTKEY_ALREADY_REGISTERED:
                raise HotkeyError(
                    f"{HOTKEY_NAME} is already used by another application, so the "
                    "global shortcut is unavailable. Echo still works from the tray icon."
                )
            raise HotkeyError(
                f"Could not register {HOTKEY_NAME} (Windows error {code}). "
                "Echo still works from the tray icon."
            )
        self._registered = True

    def unregister(self) -> None:
        if not self._registered or self._user32 is None:
            return
        self._user32.UnregisterHotKey(None, HOTKEY_ID)
        self._registered = False
