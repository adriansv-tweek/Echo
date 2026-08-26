"""Main Echo window: search, preview, and inline template editing."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from clipboard import copy_text
from templates import Template, TemplateStore, keywords_from_text, keywords_to_text
from workflow import enter_action, next_result_row

HINT = "Type to search. Enter selects, Enter copies, Esc hides."


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
* {
    font-family: "Segoe UI", "Segoe UI Variable Text", sans-serif;
}
QMainWindow, QWidget#central, QWidget#browsePage, QWidget#editPage {
    background: #1c1c1e;
    color: #f4f4f5;
}
QLineEdit, QPlainTextEdit {
    background: #27272a;
    color: #fafafa;
    border: 1px solid #3f3f46;
    border-radius: 4px;
    padding: 8px 10px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}
QLineEdit#search {
    padding: 10px 12px;
    font-size: 15px;
}
QLineEdit::placeholder, QPlainTextEdit::placeholder {
    color: #a1a1aa;
}
QListWidget {
    background: #27272a;
    color: #f4f4f5;
    border: 1px solid #3f3f46;
    border-radius: 4px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    padding: 7px 10px;
    border-radius: 3px;
    color: #f4f4f5;
}
QListWidget::item:selected {
    background: #2563eb;
    color: #ffffff;
}
QListWidget::item:hover:!selected {
    background: #3f3f46;
}
QPlainTextEdit#preview, QPlainTextEdit#editText {
    font-size: 13px;
    line-height: 1.4;
}
QLabel {
    color: #f4f4f5;
    background: transparent;
}
QLabel#previewTitle, QLabel#editHeading {
    font-size: 13px;
    font-weight: 600;
    color: #fafafa;
}
QLabel#fieldLabel {
    font-size: 12px;
    color: #d4d4d8;
}
QLabel#warning {
    padding: 8px 10px;
    border-radius: 4px;
    background: #713f12;
    color: #fde68a;
}
QLabel#status {
    padding: 6px 2px;
    color: #d4d4d8;
    font-size: 12px;
}
QLabel#status[state="copied"] {
    color: #86efac;
}
QLabel#status[state="error"] {
    color: #fca5a5;
}
QPushButton {
    padding: 6px 12px;
    border: 1px solid #52525b;
    border-radius: 4px;
    background: #27272a;
    color: #f4f4f5;
}
QPushButton:hover {
    background: #3f3f46;
}
QPushButton:pressed {
    background: #18181b;
}
QPushButton:disabled {
    color: #71717a;
    border-color: #3f3f46;
    background: #27272a;
}
QPushButton#iconButton {
    padding: 0;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    font-size: 14px;
    border: none;
    background: transparent;
    color: #d4d4d8;
}
QPushButton#iconButton:hover {
    background: #3f3f46;
    color: #fafafa;
}
QPushButton#iconButton:disabled {
    background: transparent;
    color: #52525b;
}
QPushButton#primary {
    background: #2563eb;
    border-color: #2563eb;
    color: #ffffff;
}
QPushButton#primary:hover {
    background: #3b82f6;
}
QPushButton#primary:disabled {
    background: #1e3a8a;
    border-color: #1e3a8a;
    color: #93c5fd;
}
QScrollBar:vertical {
    background: #1c1c1e;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #52525b;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


class MainWindow(QMainWindow):
    def __init__(self, store: TemplateStore) -> None:
        super().__init__()
        self.store = store
        self.hide_on_close = True
        self._armed = False
        self._mode = "browse"
        self._edit_id: str | None = None
        self._edit_original: tuple[str, str, str] = ("", "", "")
        self._warnings: list[str] = []
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._clear_status)

        self.setWindowTitle("Echo")
        self.resize(500, 540)
        self.setMinimumSize(420, 420)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_browse_page())
        self.pages.addWidget(self._build_edit_page())

        central = QWidget()
        central.setObjectName("central")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.pages)
        self.setCentralWidget(central)
        self.setStyleSheet(STYLESHEET)

        QShortcut(QKeySequence("Ctrl+N"), self, self.add_template)
        QShortcut(QKeySequence("Ctrl+E"), self, self.edit_template)
        QShortcut(QKeySequence("Ctrl+D"), self, self.delete_template)
        QShortcut(QKeySequence("Ctrl+Return"), self, self._save_if_editing)
        QShortcut(QKeySequence("Escape"), self, self._on_escape)

        self.refresh_results()
        self.search.setFocus()

    def _build_browse_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("browsePage")

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

        self.preview_title = QLabel("")
        self.preview_title.setObjectName("previewTitle")
        self.preview = QPlainTextEdit()
        self.preview.setObjectName("preview")
        self.preview.setReadOnly(True)

        self.new_button = QPushButton("+")
        self.new_button.setObjectName("iconButton")
        self.new_button.setToolTip("New")
        self.new_button.setAccessibleName("New")
        self.edit_button = QPushButton("✎")
        self.edit_button.setObjectName("iconButton")
        self.edit_button.setToolTip("Edit")
        self.edit_button.setAccessibleName("Edit")
        self.delete_button = QPushButton("✕")
        self.delete_button.setObjectName("iconButton")
        self.delete_button.setToolTip("Delete")
        self.delete_button.setAccessibleName("Delete")
        self.new_button.clicked.connect(self.add_template)
        self.edit_button.clicked.connect(self.edit_template)
        self.delete_button.clicked.connect(self.delete_template)

        self.status = QLabel(HINT)
        self.status.setObjectName("status")

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addStretch()
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.edit_button)
        buttons.addWidget(self.delete_button)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.warning)
        layout.addWidget(self.search)
        layout.addWidget(self.results, 1)
        layout.addWidget(self.preview_title)
        layout.addWidget(self.preview, 1)
        layout.addLayout(buttons)
        layout.addWidget(self.status)
        return page

    def _build_edit_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("editPage")

        self.edit_heading = QLabel("New template")
        self.edit_heading.setObjectName("editHeading")

        title_label = QLabel("Title")
        title_label.setObjectName("fieldLabel")
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Template title")

        keywords_label = QLabel("Keywords")
        keywords_label.setObjectName("fieldLabel")
        self.keywords_edit = QLineEdit()
        self.keywords_edit.setPlaceholderText("optional, comma separated")

        text_label = QLabel("Template")
        text_label.setObjectName("fieldLabel")
        self.text_edit = QPlainTextEdit()
        self.text_edit.setObjectName("editText")
        self.text_edit.setPlaceholderText("Generic template text")

        self.cancel_button = QPushButton("Cancel")
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("primary")
        self.cancel_button.clicked.connect(self._cancel_edit)
        self.save_button.clicked.connect(self._save_edit)

        self.edit_status = QLabel("")
        self.edit_status.setObjectName("status")

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addWidget(self.cancel_button)
        buttons.addStretch()
        buttons.addWidget(self.save_button)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.edit_heading)
        layout.addWidget(title_label)
        layout.addWidget(self.title_edit)
        layout.addWidget(keywords_label)
        layout.addWidget(self.keywords_edit)
        layout.addWidget(text_label)
        layout.addWidget(self.text_edit, 1)
        layout.addLayout(buttons)
        layout.addWidget(self.edit_status)
        return page

    def closeEvent(self, event) -> None:
        """With a tray icon present, closing only hides; Echo keeps running."""
        if self._mode == "edit" and not self._confirm_leave_edit():
            event.ignore()
            return
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

        self.results.blockSignals(True)
        self.results.clear()
        for template in matches:
            item = QListWidgetItem(template.title)
            item.setData(Qt.UserRole, template.id)
            item.setToolTip(", ".join(template.keywords))
            self.results.addItem(item)
        self.results.blockSignals(False)

        if self.results.count() > 0:
            self.results.setCurrentRow(0)
            self._show_preview(self._current_template())
        else:
            self._show_preview(None)
        self._update_action_buttons()

    def show_and_focus(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        _bring_to_front(self)
        if self._mode == "edit":
            self.title_edit.setFocus()
            self.title_edit.selectAll()
            return
        self._armed = False
        self._clear_status()
        self.search.clear()
        self.search.setFocus()

    def add_template(self) -> None:
        if self._mode == "edit":
            return
        self._enter_edit(None)

    def edit_template(self) -> None:
        if self._mode == "edit":
            return
        template = self._current_template()
        if template is None:
            return
        self._enter_edit(template)

    def delete_template(self) -> None:
        if self._mode == "edit":
            return
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

    def _enter_edit(self, template: Template | None) -> None:
        self._mode = "edit"
        self._edit_id = None if template is None else template.id
        if template is None:
            self.edit_heading.setText("New template")
            self.setWindowTitle("Echo — New")
            self.title_edit.clear()
            self.keywords_edit.clear()
            self.text_edit.clear()
        else:
            self.edit_heading.setText("Editing")
            self.setWindowTitle("Echo — Editing")
            self.title_edit.setText(template.title)
            self.keywords_edit.setText(keywords_to_text(template.keywords))
            self.text_edit.setPlainText(template.text)
        self._edit_original = self._edit_values()
        self.edit_status.setText("Ctrl+Enter saves. Esc cancels.")
        self.edit_status.setProperty("state", "")
        self.pages.setCurrentIndex(1)
        self.title_edit.setFocus()

    def _leave_edit(self) -> None:
        self._mode = "browse"
        self._edit_id = None
        self._edit_original = ("", "", "")
        self.setWindowTitle("Echo")
        self.pages.setCurrentIndex(0)
        self.search.setFocus()

    def _edit_values(self) -> tuple[str, str, str]:
        return (
            self.title_edit.text(),
            self.keywords_edit.text(),
            self.text_edit.toPlainText(),
        )

    def _confirm_leave_edit(self) -> bool:
        if self._edit_values() == self._edit_original:
            self._leave_edit()
            return True
        confirm = QMessageBox.question(
            self,
            "Discard changes",
            "Discard your unsaved changes?",
            QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if confirm != QMessageBox.Discard:
            return False
        self._leave_edit()
        return True

    def _cancel_edit(self) -> None:
        self._confirm_leave_edit()

    def _save_if_editing(self) -> None:
        if self._mode == "edit":
            self._save_edit()

    def _save_edit(self) -> None:
        if self._mode != "edit":
            return
        title = self.title_edit.text().strip()
        text = self.text_edit.toPlainText()
        keywords = keywords_from_text(self.keywords_edit.text())
        if not title:
            self._set_edit_status("Please enter a title.", "error")
            self.title_edit.setFocus()
            return
        if not text.strip():
            self._set_edit_status("Please enter template text.", "error")
            self.text_edit.setFocus()
            return

        if self._edit_id is None:
            template = self._guard_save(lambda: self.store.add(title, keywords, text))
            action = "Added"
        else:
            edit_id = self._edit_id
            template = self._guard_save(lambda: self.store.update(edit_id, title, keywords, text))
            action = "Updated"
        if template is None:
            return

        self._leave_edit()
        self.search.clear()
        self.refresh_results()
        self._select_id(template.id)
        self._set_status(f"{action} “{template.title}”.")

    def _on_escape(self) -> None:
        if self._mode == "edit":
            self._cancel_edit()
            return
        self.hide()

    def _guard_save(self, action):
        """Run a store action, reporting disk errors instead of crashing."""
        try:
            return action()
        except OSError as error:
            message = f"Could not save templates: {error}"
            if self._mode == "edit":
                self._set_edit_status(message, "error")
            else:
                self._set_status(message, state="error")
            return None

    def _handle_enter(self) -> None:
        if self._mode != "browse":
            return
        template = self._current_template()
        action = enter_action(template is not None, self._armed)
        if action == "noop":
            return
        if action == "select":
            self._armed = True
            self._set_status(f"Selected “{template.title}”. Press Enter to copy.")
            return
        self._copy_template(template)

    def _on_item_double_clicked(self, _item: QListWidgetItem) -> None:
        if self._mode != "browse":
            return
        template = self._current_template()
        if template is not None:
            self._copy_template(template)

    def _on_current_changed(self, _current, _previous) -> None:
        self._armed = False
        self._show_preview(self._current_template())
        self._update_action_buttons()

    def _copy_template(self, template: Template) -> None:
        self._armed = False
        if not copy_text(template.text):
            self._set_status(
                "Could not copy: the clipboard is in use by another program. Try again.",
                state="error",
            )
            return
        self._set_status(f"Copied “{template.title}”.", state="copied")
        self.hide()

    def _move_selection(self, delta: int) -> None:
        row = next_result_row(self.results.count(), self.results.currentRow(), delta)
        if row is None:
            return
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
            self.preview_title.setText("")
            self.preview.setPlainText("")
            return
        keywords = keywords_to_text(template.keywords)
        subtitle = f" — {keywords}" if keywords else ""
        self.preview_title.setText(f"{template.title}{subtitle}")
        self.preview.setPlainText(template.text)

    def _update_action_buttons(self) -> None:
        has_selection = self._current_template() is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def _set_status(self, message: str, state: str = "") -> None:
        self.status.setText(message)
        self._apply_status_state(self.status, state)
        self._status_timer.start(4000 if state == "error" else 2500)

    def _set_edit_status(self, message: str, state: str = "") -> None:
        self.edit_status.setText(message)
        self._apply_status_state(self.edit_status, state)

    def _clear_status(self) -> None:
        self.status.setText(HINT)
        self._apply_status_state(self.status, "")

    def _apply_status_state(self, label: QLabel, state: str) -> None:
        label.setProperty("state", state)
        label.style().unpolish(label)
        label.style().polish(label)
