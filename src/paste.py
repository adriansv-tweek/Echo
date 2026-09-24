"""Restore the previous window and paste template text with Ctrl+V.

Echo never types into other programs. It only puts the template on the
clipboard, returns focus to the window that was active before Echo opened,
and sends Ctrl+V.
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

# Poll until the previous window is actually foreground. 40 ms × 25 ≈ 1 s.
PASTE_RETRY_MS = 40
PASTE_RETRIES = 25

VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    """Present so the INPUT union is as large as Windows requires."""

    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT)]


def paste_ready(foreground: int, target: int) -> bool:
    """Ctrl+V is sent only when the remembered window is actually foreground."""
    return bool(target) and foreground == target


def _interactive() -> bool:
    """Real Windows session. Unit tests use an offscreen Qt platform."""
    return sys.platform == "win32" and os.environ.get("QT_QPA_PLATFORM") != "offscreen"


def foreground_window() -> int:
    if not _interactive():
        return 0
    user32 = ctypes.WinDLL("user32")
    user32.GetForegroundWindow.restype = wintypes.HWND
    return int(user32.GetForegroundWindow() or 0)


def focus_window(hwnd: int) -> None:
    """Ask Windows to foreground a window Echo did not create."""
    if not _interactive() or not hwnd:
        return

    user32 = ctypes.WinDLL("user32")
    kernel32 = ctypes.WinDLL("kernel32")
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.IsWindow.restype = wintypes.BOOL
    target = wintypes.HWND(hwnd)
    if not user32.IsWindow(target):
        return

    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
    user32.AttachThreadInput.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = (wintypes.HWND,)
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.SetForegroundWindow.restype = wintypes.BOOL
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    foreground = user32.GetForegroundWindow()
    current_thread = kernel32.GetCurrentThreadId()
    foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
    attached = user32.AttachThreadInput(current_thread, foreground_thread, True)
    user32.BringWindowToTop(target)
    user32.SetForegroundWindow(target)
    if attached:
        user32.AttachThreadInput(current_thread, foreground_thread, False)


def send_ctrl_v() -> bool:
    """Simulate Ctrl+V. Returns False if Windows did not accept every keystroke."""
    if not _interactive():
        return True

    user32 = ctypes.WinDLL("user32")
    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT

    def key(vk: int, flags: int) -> INPUT:
        return INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk, 0, flags, 0, 0))

    keys = (
        key(VK_CONTROL, 0),
        key(VK_V, 0),
        key(VK_V, KEYEVENTF_KEYUP),
        key(VK_CONTROL, KEYEVENTF_KEYUP),
    )
    events = (INPUT * len(keys))(*keys)
    sent = user32.SendInput(len(keys), events, ctypes.sizeof(INPUT))
    return sent == len(keys)
