"""User settings: appearance and global shortcut.

Stored in %APPDATA%\\Echo\\settings.json, outside the repository and separate
from the template library. Missing or unreadable settings fall back to the
defaults rather than failing.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path

from hotkey import DEFAULT_SHORTCUT, Shortcut
from theme import DEFAULT_THEME, normalise

APP_NAME = "Echo"
FILE_NAME = "settings.json"


def settings_file() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / ".config"
    return base / APP_NAME / FILE_NAME


@dataclass(frozen=True)
class Settings:
    theme: str = DEFAULT_THEME
    shortcut: Shortcut = DEFAULT_SHORTCUT

    def with_theme(self, theme: str) -> "Settings":
        return replace(self, theme=normalise(theme))

    def with_shortcut(self, shortcut: Shortcut) -> "Settings":
        return replace(self, shortcut=shortcut)

    def to_dict(self) -> dict:
        return {"theme": self.theme, "shortcut": self.shortcut.to_dict()}


def load_settings(path: Path) -> Settings:
    """Read settings, falling back to the defaults for anything unusable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Settings()

    if not isinstance(data, dict):
        return Settings()

    theme = data.get("theme")
    shortcut = Shortcut.from_dict(data.get("shortcut"))
    return Settings(
        theme=normalise(theme if isinstance(theme, str) else None),
        shortcut=shortcut or DEFAULT_SHORTCUT,
    )


def save_settings(path: Path, settings: Settings) -> None:
    """Write atomically so an interrupted save cannot corrupt the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(settings.to_dict(), ensure_ascii=False, indent=2) + "\n"

    temp_path = path.with_name(path.name + ".tmp")
    with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)
