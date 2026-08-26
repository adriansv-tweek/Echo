"""Main Echo window: search, preview, and template editing."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from clipboard import copy_text
from templates import Template, TemplateStore, keywords_from_text, keywords_to_text

HINT = "Type to search. Enter selects, Enter again copies. Esc hides Echo."


def _bring_to_front(window: QMainWindow) -> None:
    """Ask Windows to actually focus Echo after the global hotkey."""
    if sys.platform != "win32":
        return

    user32 = ctypes.WinDLL("user32")
    kernel32 = ctypes.WinDLL("kernel32")

    user32.GetForegroundWindow.argtypes = ()
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
    user32.AttachThreadInput.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = (wintypes.HWND,)
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.SetForegroundWindow.restype = wintypes.BOOL
    kernel32.GetCurrentThreadId.argtypes = ()
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    hwnd = wintypes.HWND(int(window.winId()))
    foreground = user32.GetForegroundWindow()
    current_thread = kernel32.GetCurrentThreadId()
    foreground_thread = user32.GetWindowThreadProcessId(foreground, None)

    attached = user32.AttachThreadInput(current_thread, foreground_thread, True)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    if attached:
        user32.AttachThreadInput(current_thread, foreground_thread, False)


STYLESHEET = """
QMainWindow, QWidget#central {
    background: #f4f4f5;
}
QLineEdit#search {
    padding: 10px 12px;
    font-size: 16px;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    background: #ffffff;
}
QListWidget {
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    background: #ffffff;
    padding: 4px;
}
QListWidget::item {
    padding: 8px 10px;
    border-radius: 6px;
}
QListWidget::item:selected {
    background: #dbeafe;
    color: #0f172a;
}
QPlainTextEdit {
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    background: #ffffff;
    padding: 8px;
}
QLabel#previewTitle {
    font-size: 14px;
    font-weight: 600;
    color: #18181b;
}
QLabel#warning {
    padding: 8px 10px;
    border-radius: 8px;
    background: #fef3c7;
    color: #92400e;
}
QLabel#status {
    padding: 8px 10px;
    border-radius: 8px;
    color: #3f3f46;
}
QLabel#status[state="copied"] {
    background: #dcfce7;
    color: #166534;
}
QLabel#status[state="error"] {
    background: #fee2e2;
    color: #991b1b;
}
QPushButton {
    padding: 6px 12px;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    background: #ffffff;
}
QPushButton:hover {
    background: #e4e4e7;
}
"""


class TemplateEditorDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, template: Template | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit template" if template else "New template")
        self.resize(560, 480)

        self.title_edit = QLineEdit()
        self.keywords_edit = QLineEdit()
        self.keywords_edit.setPlaceholderText("comma, separated, keywords")
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Template text")
        self.text_edit.setMinimumHeight(240)

        if template is not None:
            self.title_edit.setText(template.title)
            self.keywords_edit.setText(keywords_to_text(template.keywords))
            self.text_edit.setPlainText(template.text)

        self._original = self._current_values()

        form = QFormLayout()
        form.addRow("Title", self.title_edit)
        form.addRow("Keywords", self.keywords_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QLabel("Text"))
        layout.addWidget(self.text_edit, 1)
        layout.addWidget(buttons)

        save_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        save_shortcut.activated.connect(self._accept_if_valid)

        self.title_edit.setFocus()

    def reject(self) -> None:
        if self._current_values() != self._original:
            confirm = QMessageBox.question(
                self,
                "Discard changes",
                "Discard your unsaved changes?",
                QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if confirm != QMessageBox.Discard:
                return
        super().reject()

    def values(self) -> tuple[str, list[str], str]:
        title, keywords, text = self._current_values()
        return title.strip(), keywords_from_text(keywords), text

    def _current_values(self) -> tuple[str, str, str]:
        return (
            self.title_edit.text(),
            self.keywords_edit.text(),
            self.text_edit.toPlainText(),
        )

    def _accept_if_valid(self) -> None:
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Missing title", "Please enter a title.")
            self.title_edit.setFocus()
            return
        if not self.text_edit.toPlainText().strip():
            QMessageBox.warning(self, "Missing text", "Please enter template text.")
            self.text_edit.setFocus()
            return
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, store: TemplateStore) -> None:
        super().__init__()
        self.store = store
        self.hide_on_close = True
        self._armed = False
        self._warnings: list[str] = []
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._clear_status)

        self.setWindowTitle("Echo")
        self.resize(820, 560)

        self.warning = QLabel()
        self.warning.setObjectName("warning")
        self.warning.setWordWrap(True)
        self.warning.hide()

        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Search templates…")
        self.search.setClearButtonEnabled(True)
        self.search.installEventFilter(self)
        self.search.textChanged.connect(self.refresh_results)

        self.results = QListWidget()
        self.results.installEventFilter(self)
        self.results.currentItemChanged.connect(self._on_current_changed)
        self.results.itemDoubleClicked.connect(self._on_item_double_clicked)

        self.preview_title = QLabel("No template selected")
        self.preview_title.setObjectName("previewTitle")
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)

        new_button = QPushButton("New")
        edit_button = QPushButton("Edit")
        delete_button = QPushButton("Delete")
        new_button.clicked.connect(self.add_template)
        edit_button.clicked.connect(self.edit_template)
        delete_button.clicked.connect(self.delete_template)

        self.status = QLabel(HINT)
        self.status.setObjectName("status")

        preview_pane = QWidget()
        preview_layout = QVBoxLayout(preview_pane)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addWidget(self.preview_title)
        preview_layout.addWidget(self.preview, 1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.results)
        splitter.addWidget(preview_pane)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        buttons = QHBoxLayout()
        buttons.addWidget(new_button)
        buttons.addWidget(edit_button)
        buttons.addWidget(delete_button)
        buttons.addStretch()

        central = QWidget()
        central.setObjectName("central")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.warning)
        layout.addWidget(self.search)
        layout.addWidget(splitter, 1)
        layout.addLayout(buttons)
        layout.addWidget(self.status)
        self.setCentralWidget(central)
        self.setStyleSheet(STYLESHEET)

        QShortcut(QKeySequence("Ctrl+N"), self, self.add_template)
        QShortcut(QKeySequence("Ctrl+E"), self, self.edit_template)
        QShortcut(QKeySequence("Ctrl+D"), self, self.delete_template)
        QShortcut(QKeySequence("Escape"), self, self.hide)

        self.refresh_results()
        self.search.setFocus()

    def closeEvent(self, event) -> None:
        """With a tray icon present, closing only hides; Echo keeps running."""
        if self.hide_on_close:
            event.ignore()
            self.hide()
        else:
            super().closeEvent(event)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.KeyPress:
            key = event.key()
            if watched is self.search:
                if key == Qt.Key_Down:
                    self._move_selection(1)
                    return True
                if key == Qt.Key_Up:
                    self._move_selection(-1)
                    return True
            if watched in (self.search, self.results) and key in (Qt.Key_Return, Qt.Key_Enter):
                self._handle_enter()
                return True
        return super().eventFilter(watched, event)

    def show_warning(self, message: str) -> None:
        self._warnings.append(message)
        self.warning.setText("\n".join(self._warnings))
        self.warning.show()

    def refresh_results(self, _text: str | None = None) -> None:
        self._armed = False
        matches = self.store.search(self.search.text())
        current_id = self._current_id()

        self.results.blockSignals(True)
        self.results.clear()
        selected_row = 0
        for index, template in enumerate(matches):
            item = QListWidgetItem(template.title)
            item.setData(Qt.UserRole, template.id)
            item.setToolTip(", ".join(template.keywords))
            self.results.addItem(item)
            if template.id == current_id:
                selected_row = index
        self.results.blockSignals(False)

        if self.results.count() > 0:
            self.results.setCurrentRow(selected_row)
            self._show_preview(self._current_template())
        else:
            self._show_preview(None)

    def show_and_focus(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        _bring_to_front(self)
        self.search.setFocus()
        self.search.selectAll()

    def add_template(self) -> None:
        dialog = TemplateEditorDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        title, keywords, text = dialog.values()
        template = self._guard_save(lambda: self.store.add(title, keywords, text))
        if template is None:
            return
        self.search.clear()
        self.refresh_results()
        self._select_id(template.id)
        self._set_status(f"Added “{template.title}”.")

    def edit_template(self) -> None:
        template = self._current_template()
        if template is None:
            return
        dialog = TemplateEditorDialog(self, template)
        if dialog.exec() != QDialog.Accepted:
            return
        title, keywords, text = dialog.values()
        updated = self._guard_save(
            lambda: self.store.update(template.id, title, keywords, text)
        )
        if updated is None:
            return
        self.refresh_results()
        self._select_id(updated.id)
        self._set_status(f"Updated “{updated.title}”.")

    def delete_template(self) -> None:
        template = self._current_template()
        if template is None:
            return
        confirm = QMessageBox.question(self, "Delete template", f"Delete “{template.title}”?")
        if confirm != QMessageBox.Yes:
            return
        if self._guard_save(lambda: self.store.delete(template.id)) is None:
            return
        self.refresh_results()
        self._set_status(f"Deleted “{template.title}”.")

    def _guard_save(self, action):
        """Run a store action, reporting disk errors instead of crashing."""
        try:
            return action()
        except OSError as error:
            self._set_status(f"Could not save templates: {error}", state="error")
            return None

    def _handle_enter(self) -> None:
        template = self._current_template()
        if template is None:
            return
        if not self._armed:
            self._armed = True
            self._set_status(f"Selected “{template.title}”. Press Enter to copy.")
            return
        self._copy_template(template)

    def _on_item_double_clicked(self, _item: QListWidgetItem) -> None:
        template = self._current_template()
        if template is not None:
            self._copy_template(template)

    def _on_current_changed(self, _current, _previous) -> None:
        self._armed = False
        self._show_preview(self._current_template())

    def _copy_template(self, template: Template) -> None:
        self._armed = False
        if not copy_text(template.text):
            self._set_status(
                "Could not copy: the clipboard is in use by another program. Try again.",
                state="error",
            )
            return
        self._set_status(f"Copied “{template.title}” to the clipboard.", state="copied")
        QTimer.singleShot(400, self.hide)

    def _move_selection(self, delta: int) -> None:
        if self.results.count() == 0:
            return
        row = self.results.currentRow()
        row = 0 if row < 0 else max(0, min(self.results.count() - 1, row + delta))
        self.results.setCurrentRow(row)
        self._armed = False

    def _current_id(self) -> str | None:
        item = self.results.currentItem()
        return None if item is None else item.data(Qt.UserRole)

    def _current_template(self) -> Template | None:
        template_id = self._current_id()
        return None if template_id is None else self.store.get(template_id)

    def _select_id(self, template_id: str) -> None:
        for row in range(self.results.count()):
            if self.results.item(row).data(Qt.UserRole) == template_id:
                self.results.setCurrentRow(row)
                return

    def _show_preview(self, template: Template | None) -> None:
        if template is None:
            self.preview_title.setText("No template selected")
            self.preview.setPlainText("")
            return
        keywords = keywords_to_text(template.keywords)
        subtitle = f" — {keywords}" if keywords else ""
        self.preview_title.setText(f"{template.title}{subtitle}")
        self.preview.setPlainText(template.text)

    def _set_status(self, message: str, state: str = "") -> None:
        self.status.setText(message)
        self._apply_status_state(state)
        self._status_timer.start(4000 if state == "error" else 2500)

    def _clear_status(self) -> None:
        self.status.setText(HINT)
        self._apply_status_state("")

    def _apply_status_state(self, state: str) -> None:
        self.status.setProperty("state", state)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
