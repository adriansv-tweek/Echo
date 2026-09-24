"""Main Echo window: search, preview, inline template editing, and settings."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
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

import theme as theme_module
from clipboard import copy_text
from hotkey import HotkeyError, Shortcut
from paste import (
    PASTE_RETRIES,
    PASTE_RETRY_MS,
    focus_window,
    foreground_window,
    send_ctrl_v,
)
from settings import Settings
from templates import Template, TemplateStore, keywords_from_text, keywords_to_text
from workflow import enter_action, next_result_row

HINT = "Type to search. Enter selects, Enter copies, Esc hides."
LIBRARY_HINT = "All templates. Enter selects, Enter copies, Esc returns."

BROWSE_PAGE, EDIT_PAGE, SETTINGS_PAGE = 0, 1, 2


def _bring_to_front(window: QMainWindow) -> None:
    """Ask Windows to actually focus Echo after the global hotkey."""
    focus_window(int(window.winId()))


class ShortcutCaptureButton(QPushButton):
    """Button that listens for one modifier + key combination when activated."""

    captured = Signal(object)
    cancelled = Signal()

    IDLE_TEXT = "Change shortcut"
    PROMPT = "Press your desired shortcut…"

    MODIFIERS = (
        (Qt.ControlModifier, "ctrl"),
        (Qt.AltModifier, "alt"),
        (Qt.ShiftModifier, "shift"),
        (Qt.MetaModifier, "win"),
    )
    BARE_KEYS = (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_AltGr)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(self.IDLE_TEXT, parent)
        self.capturing = False
        self.clicked.connect(self.start_capture)

    def start_capture(self) -> None:
        self.capturing = True
        self.setText(self.PROMPT)
        self.setFocus()

    def stop_capture(self) -> None:
        self.capturing = False
        self.setText(self.IDLE_TEXT)

    def event(self, incoming):
        # Let the combination reach keyPressEvent instead of firing Echo's own
        # Ctrl+N / Ctrl+E / Escape shortcuts while capturing.
        if self.capturing and incoming.type() == QEvent.ShortcutOverride:
            incoming.accept()
            return True
        return super().event(incoming)

    def keyPressEvent(self, event) -> None:
        if not self.capturing:
            super().keyPressEvent(event)
            return

        key = event.key()
        if key in self.BARE_KEYS:
            return
        if key == Qt.Key_Escape:
            self.stop_capture()
            self.cancelled.emit()
            return

        modifiers = tuple(
            name for flag, name in self.MODIFIERS if event.modifiers() & flag
        )
        if not modifiers:
            self.setText("Add a modifier, e.g. Ctrl+Shift+…")
            return

        virtual_key = event.nativeVirtualKey()
        label = QKeySequence(key).toString()
        if not virtual_key or not label:
            self.setText("That key cannot be used. Try another…")
            return

        self.stop_capture()
        self.captured.emit(Shortcut(modifiers, label, int(virtual_key)))


class MainWindow(QMainWindow):
    def __init__(
        self,
        store: TemplateStore,
        settings: Settings | None = None,
        hotkey=None,
        on_settings_changed=None,
    ) -> None:
        super().__init__()
        self.store = store
        self.settings = settings or Settings()
        self.hotkey = hotkey
        self.on_settings_changed = on_settings_changed
        self.hide_on_close = True
        self._armed = False
        self._library = False
        self._return_hwnd = 0
        self._paste_hwnd = 0
        self._paste_attempts = 0
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
        self.pages.addWidget(self._build_settings_page())

        central = QWidget()
        central.setObjectName("central")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.pages)
        self.setCentralWidget(central)
        self.apply_theme(self.settings.theme)

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

        self.library_button = QPushButton("☰")
        self.library_button.setObjectName("headerButton")
        self.library_button.setToolTip("All templates")
        self.library_button.setAccessibleName("Templates")
        self.library_button.setCheckable(True)
        self.library_button.clicked.connect(self._on_library_button)

        self.settings_button = QPushButton("⚙")
        self.settings_button.setObjectName("iconButton")
        self.settings_button.setToolTip("Settings")
        self.settings_button.setAccessibleName("Settings")
        self.settings_button.clicked.connect(self.open_settings)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.library_button)
        header.addStretch()
        header.addWidget(self.settings_button)

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
        layout.addLayout(header)
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

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("settingsPage")

        heading = QLabel("Settings")
        heading.setObjectName("settingsHeading")

        appearance_label = QLabel("Appearance")
        appearance_label.setObjectName("fieldLabel")
        self.dark_button = QPushButton("Dark")
        self.light_button = QPushButton("Light")
        for button, name in ((self.dark_button, theme_module.DARK),
                             (self.light_button, theme_module.LIGHT)):
            button.setObjectName("themeOption")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.clicked.connect(lambda _checked=False, n=name: self.set_theme(n))

        appearance_row = QHBoxLayout()
        appearance_row.setContentsMargins(0, 0, 0, 0)
        appearance_row.addWidget(self.dark_button)
        appearance_row.addWidget(self.light_button)
        appearance_row.addStretch()

        shortcut_label = QLabel("Global shortcut")
        shortcut_label.setObjectName("fieldLabel")
        self.shortcut_value = QLabel(self.settings.shortcut.name)
        self.shortcut_value.setObjectName("shortcutValue")

        self.capture_button = ShortcutCaptureButton()
        self.capture_button.captured.connect(self._on_shortcut_captured)
        self.capture_button.cancelled.connect(
            lambda: self._set_settings_status("Shortcut unchanged.")
        )

        shortcut_row = QHBoxLayout()
        shortcut_row.setContentsMargins(0, 0, 0, 0)
        shortcut_row.addWidget(self.capture_button)
        shortcut_row.addStretch()

        self.settings_status = QLabel("")
        self.settings_status.setObjectName("status")

        self.settings_back_button = QPushButton("Back")
        self.settings_back_button.clicked.connect(self.close_settings)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addWidget(self.settings_back_button)
        footer.addStretch()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(heading)
        layout.addSpacing(6)
        layout.addWidget(appearance_label)
        layout.addLayout(appearance_row)
        layout.addSpacing(10)
        layout.addWidget(shortcut_label)
        layout.addWidget(self.shortcut_value)
        layout.addLayout(shortcut_row)
        layout.addStretch()
        layout.addWidget(self.settings_status)
        layout.addLayout(footer)
        return page

    # --- settings -----------------------------------------------------------

    def open_settings(self) -> None:
        if self._mode == "edit":
            return
        self._mode = "settings"
        self.setWindowTitle("Echo — Settings")
        self._sync_settings_page()
        self._set_settings_status("")
        self.pages.setCurrentIndex(SETTINGS_PAGE)
        self.capture_button.setFocus()

    def close_settings(self) -> None:
        self.capture_button.stop_capture()
        self._mode = "browse"
        self.setWindowTitle("Echo")
        self.pages.setCurrentIndex(BROWSE_PAGE)
        self.search.setFocus()

    def apply_theme(self, name: str) -> None:
        name = theme_module.normalise(name)
        self.setStyleSheet(theme_module.stylesheet(name))
        app = QApplication.instance()
        if app is not None:
            theme_module.apply_to_app(app, name)

    def set_theme(self, name: str) -> None:
        name = theme_module.normalise(name)
        self.settings = self.settings.with_theme(name)
        self.apply_theme(name)
        self._sync_settings_page()
        self._persist_settings()
        self._set_settings_status(f"{name.capitalize()} appearance applied.")

    def _sync_settings_page(self) -> None:
        self.dark_button.setChecked(self.settings.theme == theme_module.DARK)
        self.light_button.setChecked(self.settings.theme == theme_module.LIGHT)
        self.shortcut_value.setText(self.settings.shortcut.name)

    def _on_shortcut_captured(self, shortcut: Shortcut) -> None:
        """Activate a new shortcut, keeping the old one if registration fails."""
        if self.hotkey is not None:
            try:
                self.hotkey.rebind(shortcut)
            except HotkeyError as error:
                self._set_settings_status(str(error), "error")
                self._sync_settings_page()
                return

        self.settings = self.settings.with_shortcut(shortcut)
        self._sync_settings_page()
        self._persist_settings()
        self._set_settings_status(f"Global shortcut is now {shortcut.name}.", "copied")

    def _persist_settings(self) -> None:
        if self.on_settings_changed is None:
            return
        try:
            self.on_settings_changed(self.settings)
        except OSError as error:
            self._set_settings_status(f"Could not save settings: {error}", "error")

    def _set_settings_status(self, message: str, state: str = "") -> None:
        self.settings_status.setText(message)
        self._apply_status_state(self.settings_status, state)

    # --- window -------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """With a tray icon present, closing only hides; Echo keeps running."""
        if self._mode == "edit" and not self._confirm_leave_edit():
            event.ignore()
            return
        if self._mode == "settings":
            self.close_settings()
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

    def _on_library_button(self) -> None:
        """Toggle the overview. The button's checked state is already updated."""
        if self._mode == "edit":
            self.library_button.setChecked(False)
            return
        if self.library_button.isChecked():
            self.open_library()
            return
        self.close_library()

    def open_library(self) -> None:
        if self._mode == "edit":
            self.library_button.setChecked(False)
            return
        if self._mode == "settings":
            self.close_settings()
        self._mode = "browse"
        self._library = True
        self.library_button.setChecked(True)
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.refresh_results()
        self._set_status(LIBRARY_HINT)
        if self.results.count() > 0:
            self.results.setFocus()
        else:
            self.search.setFocus()

    def close_library(self) -> None:
        self._library = False
        self.library_button.setChecked(False)
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.refresh_results()
        self._clear_status()
        self.search.setFocus()

    def refresh_results(self, _text: str | None = None) -> None:
        self._armed = False
        if self._library and self.search.text().strip():
            self._library = False
            self.library_button.setChecked(False)
        if self._library:
            matches = sorted(self.store.templates, key=lambda template: template.title.casefold())
        else:
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
        previous = foreground_window()
        own = int(self.winId())
        if previous and previous != own:
            self._return_hwnd = previous
        if self._library:
            self._library = False
            self.library_button.setChecked(False)
            self.refresh_results()
        self.showNormal()
        self.raise_()
        self.activateWindow()
        _bring_to_front(self)
        if self._mode == "edit":
            self.title_edit.setFocus()
            self.title_edit.selectAll()
            return
        if self._mode == "settings":
            self.capture_button.setFocus()
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
        if self._mode != "browse":
            return
        template = self._current_template()
        if template is None:
            return
        self._enter_edit(template)

    def delete_template(self) -> None:
        if self._mode != "browse":
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
        self.pages.setCurrentIndex(EDIT_PAGE)
        self.title_edit.setFocus()

    def _leave_edit(self) -> None:
        self._mode = "browse"
        self._edit_id = None
        self._edit_original = ("", "", "")
        self.setWindowTitle("Echo")
        self.pages.setCurrentIndex(BROWSE_PAGE)
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
        if self._mode == "settings":
            self.close_settings()
            return
        if self._library:
            self.close_library()
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
        self._paste_hwnd = self._return_hwnd
        self._paste_attempts = PASTE_RETRIES
        self._paste_tick()

    def _paste_tick(self) -> None:
        """Restore the previous window, paste once it is foreground, then hide.

        Ctrl+V is best-effort. A rejected keystroke is not shown as an error.
        """
        if self._paste_hwnd:
            focus_window(self._paste_hwnd)
        if self._paste_hwnd and foreground_window() == self._paste_hwnd:
            send_ctrl_v()
            self.hide()
            return
        self._paste_attempts -= 1
        if self._paste_attempts <= 0:
            self.hide()
            return
        QTimer.singleShot(PASTE_RETRY_MS, self, self._paste_tick)

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
