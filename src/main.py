"""Launch the Echo desktop app."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

import theme
from hotkey import HotkeyError, HotkeyListener
from settings import load_settings, save_settings, settings_file
from templates import (
    TemplateStore,
    data_file,
    ensure_packaged_templates,
    legacy_appdata_file,
    migrate_legacy_file,
)
from ui import MainWindow

INSTANCE_SERVER = "EchoStandaloneInstance"


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


def build_tray(app: QApplication, window: MainWindow, shortcut_name: str) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(app_icon(), app)
    tray.setToolTip(f"Echo — {shortcut_name}")

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


def _claim_instance(app: QApplication) -> QLocalServer | None:
    """Keep a single Echo process. Activate the existing one if it is already running."""
    socket = QLocalSocket()
    socket.connectToServer(INSTANCE_SERVER)
    if socket.waitForConnected(200):
        socket.write(b"show")
        socket.waitForBytesWritten(200)
        socket.disconnectFromServer()
        return None

    QLocalServer.removeServer(INSTANCE_SERVER)
    server = QLocalServer(app)
    if not server.listen(INSTANCE_SERVER):
        return None
    return server


def _bind_activation(server: QLocalServer, window: MainWindow) -> None:
    def _on_connection() -> None:
        connection = server.nextPendingConnection()
        if connection is not None:
            connection.readyRead.connect(window.show_and_focus)
        window.show_and_focus()

    server.newConnection.connect(_on_connection)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Echo")

    settings_path = settings_file()
    settings = load_settings(settings_path)
    theme.apply_to_app(app, settings.theme)
    app.setWindowIcon(app_icon())

    instance_server = _claim_instance(app)
    if instance_server is None:
        return 0

    path = data_file()
    ensure_packaged_templates(path)
    migrate_legacy_file(legacy_appdata_file(), path)
    store = TemplateStore(path)
    warning = store.load()

    listener = HotkeyListener()
    tray: QSystemTrayIcon | None = None

    def on_settings_changed(updated) -> None:
        save_settings(settings_path, updated)
        if tray is not None:
            tray.setToolTip(f"Echo — {updated.shortcut.name}")

    window = MainWindow(store, settings, listener, on_settings_changed)
    _bind_activation(instance_server, window)
    if warning:
        window.show_warning(warning)

    tray_available = QSystemTrayIcon.isSystemTrayAvailable()
    window.hide_on_close = tray_available
    app.setQuitOnLastWindowClosed(not tray_available)

    if tray_available:
        tray = build_tray(app, window, settings.shortcut.name)
    else:
        window.show_warning(
            "The Windows system tray is unavailable, so closing this window quits Echo."
        )

    listener.activated.connect(window.show_and_focus, Qt.QueuedConnection)
    hotkey_error = None
    try:
        listener.register(app, settings.shortcut)
    except HotkeyError as error:
        hotkey_error = error
        window.show_warning(str(error))
    app.aboutToQuit.connect(listener.unregister)

    # Stay in the tray until the hotkey (or tray) is used. Show the window only
    # when there is no tray, or when the user needs to see a startup warning.
    if tray is None or warning or hotkey_error:
        window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
