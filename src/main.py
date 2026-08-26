"""Launch the Echo desktop app."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from hotkey import HotkeyError, HotkeyListener
from templates import FILE_NAME, TemplateStore, data_file, migrate_legacy_file
from ui import MainWindow

ROOT = Path(__file__).resolve().parent.parent
LEGACY_DATA_FILE = ROOT / "data" / FILE_NAME


def app_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#2563eb"))
    painter.drawRoundedRect(2, 2, 60, 60, 14, 14)
    font = painter.font()
    font.setPixelSize(38)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "E")
    painter.end()
    return QIcon(pixmap)


def build_tray(app: QApplication, window: MainWindow) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(app_icon(), app)
    tray.setToolTip("Echo — Ctrl+Shift+M")

    menu = QMenu()
    menu.addAction("Show Echo", window.show_and_focus)
    menu.addSeparator()
    menu.addAction("Quit Echo", app.quit)
    tray.setContextMenu(menu)

    tray.activated.connect(
        lambda reason: window.show_and_focus()
        if reason == QSystemTrayIcon.Trigger
        else None
    )
    tray.show()
    return tray


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Echo")
    app.setWindowIcon(app_icon())

    path = data_file()
    migrate_legacy_file(LEGACY_DATA_FILE, path)
    store = TemplateStore(path)
    warning = store.load()

    window = MainWindow(store)
    if warning:
        window.show_warning(warning)

    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    window.hide_on_close = tray_available
    app.setQuitOnLastWindowClosed(not tray_available)

    tray = build_tray(app, window) if tray_available else None
    if tray is None:
        window.show_warning(
            "The Windows system tray is unavailable, so closing this window quits Echo."
        )

    window.show()

    listener = HotkeyListener()
    listener.activated.connect(window.show_and_focus, Qt.QueuedConnection)
    try:
        listener.register(app)
    except HotkeyError as error:
        window.show_warning(str(error))
    app.aboutToQuit.connect(listener.unregister)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
