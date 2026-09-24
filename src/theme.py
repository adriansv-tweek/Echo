"""Dark and light colour schemes for Echo's existing minimal design."""

from __future__ import annotations

from string import Template

from PySide6.QtGui import QColor, QFont, QPalette

DARK = "dark"
LIGHT = "light"
DEFAULT_THEME = DARK
THEMES = (DARK, LIGHT)

_COLOURS = {
    DARK: {
        "window_bg": "#1c1c1e",
        "text": "#f4f4f5",
        "muted_text": "#d4d4d8",
        "heading_text": "#fafafa",
        "field_bg": "#27272a",
        "field_text": "#fafafa",
        "border": "#3f3f46",
        "placeholder": "#a1a1aa",
        "select_bg": "#2563eb",
        "select_text": "#ffffff",
        "item_hover": "#3f3f46",
        "warning_bg": "#713f12",
        "warning_text": "#fde68a",
        "ok_text": "#86efac",
        "error_text": "#fca5a5",
        "button_bg": "#27272a",
        "button_border": "#52525b",
        "button_hover": "#3f3f46",
        "button_pressed": "#18181b",
        "disabled_text": "#71717a",
        "disabled_border": "#3f3f46",
        "icon_text": "#d4d4d8",
        "icon_hover_bg": "#3f3f46",
        "icon_hover_text": "#fafafa",
        "icon_disabled": "#52525b",
        "primary_bg": "#2563eb",
        "primary_hover": "#3b82f6",
        "primary_disabled_bg": "#1e3a8a",
        "primary_disabled_text": "#93c5fd",
        "scroll_handle": "#52525b",
    },
    LIGHT: {
        "window_bg": "#f4f4f5",
        "text": "#18181b",
        "muted_text": "#52525b",
        "heading_text": "#09090b",
        "field_bg": "#ffffff",
        "field_text": "#18181b",
        "border": "#d4d4d8",
        "placeholder": "#71717a",
        "select_bg": "#2563eb",
        "select_text": "#ffffff",
        "item_hover": "#e4e4e7",
        "warning_bg": "#fef3c7",
        "warning_text": "#854d0e",
        "ok_text": "#15803d",
        "error_text": "#b91c1c",
        "button_bg": "#ffffff",
        "button_border": "#d4d4d8",
        "button_hover": "#e4e4e7",
        "button_pressed": "#d4d4d8",
        "disabled_text": "#a1a1aa",
        "disabled_border": "#e4e4e7",
        "icon_text": "#52525b",
        "icon_hover_bg": "#e4e4e7",
        "icon_hover_text": "#18181b",
        "primary_bg": "#2563eb",
        "primary_hover": "#1d4ed8",
        "icon_disabled": "#c4c4c8",
        "primary_disabled_bg": "#93c5fd",
        "primary_disabled_text": "#1e3a8a",
        "scroll_handle": "#c4c4c8",
    },
}

_STYLESHEET = Template("""
* {
    font-family: "Segoe UI", "Segoe UI Variable Text", sans-serif;
}
QMainWindow, QWidget#central, QWidget#browsePage, QWidget#editPage, QWidget#settingsPage {
    background: $window_bg;
    color: $text;
}
QLineEdit, QPlainTextEdit {
    background: $field_bg;
    color: $field_text;
    border: 1px solid $border;
    border-radius: 4px;
    padding: 8px 10px;
    selection-background-color: $select_bg;
    selection-color: $select_text;
}
QLineEdit#search {
    padding: 10px 12px;
    font-size: 15px;
}
QListWidget {
    background: $field_bg;
    color: $text;
    border: 1px solid $border;
    border-radius: 4px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    padding: 7px 10px;
    border-radius: 3px;
    color: $text;
}
QListWidget::item:selected {
    background: $select_bg;
    color: $select_text;
}
QListWidget::item:hover:!selected {
    background: $item_hover;
}
QPlainTextEdit#preview, QPlainTextEdit#editText {
    font-size: 13px;
    line-height: 1.4;
}
QLabel {
    color: $text;
    background: transparent;
}
QLabel#previewTitle, QLabel#editHeading, QLabel#settingsHeading {
    font-size: 13px;
    font-weight: 600;
    color: $heading_text;
}
QLabel#fieldLabel {
    font-size: 12px;
    color: $muted_text;
}
QLabel#shortcutValue {
    font-size: 15px;
    font-weight: 600;
    color: $heading_text;
}
QLabel#warning {
    padding: 8px 10px;
    border-radius: 4px;
    background: $warning_bg;
    color: $warning_text;
}
QLabel#status {
    padding: 6px 2px;
    color: $muted_text;
    font-size: 12px;
}
QLabel#status[state="copied"] {
    color: $ok_text;
}
QLabel#status[state="error"] {
    color: $error_text;
}
QPushButton {
    padding: 6px 12px;
    border: 1px solid $button_border;
    border-radius: 4px;
    background: $button_bg;
    color: $text;
}
QPushButton:hover {
    background: $button_hover;
}
QPushButton:pressed {
    background: $button_pressed;
}
QPushButton:disabled {
    color: $disabled_text;
    border-color: $disabled_border;
    background: $button_bg;
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
    color: $icon_text;
}
QPushButton#iconButton:hover {
    background: $icon_hover_bg;
    color: $icon_hover_text;
}
QPushButton#iconButton:disabled {
    background: transparent;
    color: $icon_disabled;
}
QPushButton#headerButton {
    padding: 0;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    font-size: 14px;
    border: none;
    background: transparent;
    color: $icon_text;
}
QPushButton#headerButton:hover {
    background: $icon_hover_bg;
    color: $icon_hover_text;
}
QPushButton#headerButton:checked {
    background: $select_bg;
    color: $select_text;
}
QPushButton#themeOption {
    padding: 6px 18px;
}
QPushButton#themeOption:checked {
    background: $select_bg;
    border-color: $select_bg;
    color: $select_text;
}
QPushButton#primary {
    background: $primary_bg;
    border-color: $primary_bg;
    color: #ffffff;
}
QPushButton#primary:hover {
    background: $primary_hover;
}
QPushButton#primary:disabled {
    background: $primary_disabled_bg;
    border-color: $primary_disabled_bg;
    color: $primary_disabled_text;
}
QScrollBar:vertical {
    background: $window_bg;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: $scroll_handle;
    min-height: 24px;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
""")


def normalise(name: str | None) -> str:
    return name if name in THEMES else DEFAULT_THEME


def colours(name: str) -> dict[str, str]:
    return _COLOURS[normalise(name)]


def stylesheet(name: str) -> str:
    return _STYLESHEET.substitute(colours(name))


def palette(name: str) -> QPalette:
    """Keep native dialogs readable against Echo's window."""
    c = colours(name)
    result = QPalette()
    result.setColor(QPalette.Window, QColor(c["window_bg"]))
    result.setColor(QPalette.WindowText, QColor(c["text"]))
    result.setColor(QPalette.Base, QColor(c["field_bg"]))
    result.setColor(QPalette.AlternateBase, QColor(c["window_bg"]))
    result.setColor(QPalette.Text, QColor(c["field_text"]))
    result.setColor(QPalette.Button, QColor(c["button_bg"]))
    result.setColor(QPalette.ButtonText, QColor(c["text"]))
    result.setColor(QPalette.Highlight, QColor(c["select_bg"]))
    result.setColor(QPalette.HighlightedText, QColor(c["select_text"]))
    result.setColor(QPalette.ToolTipBase, QColor(c["field_bg"]))
    result.setColor(QPalette.ToolTipText, QColor(c["field_text"]))
    result.setColor(QPalette.PlaceholderText, QColor(c["placeholder"]))
    result.setColor(QPalette.Disabled, QPalette.Text, QColor(c["disabled_text"]))
    result.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(c["disabled_text"]))
    result.setColor(QPalette.Disabled, QPalette.WindowText, QColor(c["disabled_text"]))
    return result


def apply_to_app(app, name: str) -> None:
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setPalette(palette(name))
