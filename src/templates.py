"""Load, search, and persist templates in a local JSON file."""

from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

APP_NAME = "Echo"
FILE_NAME = "templates.json"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _bundle_root() -> Path:
    """PyInstaller extract/bundle dir. Never use this as the writable library."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(sys.executable).resolve().parent


def seed_templates_file() -> Path:
    """Read-only seed copy: repo file in source, bundled data/ in a freeze."""
    if _frozen():
        return _bundle_root() / "data" / FILE_NAME
    return PROJECT_ROOT / "data" / FILE_NAME


def data_file() -> Path:
    """Writable template library.

    Source: repository data/templates.json so the library can be synced with Git.
    Frozen: %APPDATA%\\Echo\\templates.json, never the PyInstaller bundle.
    """
    if _frozen():
        return legacy_appdata_file()
    return PROJECT_ROOT / "data" / FILE_NAME


def ensure_packaged_templates(target: Path) -> bool:
    """Copy bundled seed to AppData on first frozen launch. No-op in source mode.

    Never overwrites an existing user library and never writes into _MEIPASS.
    """
    if not _frozen() or target.exists():
        return False
    seed = seed_templates_file()
    if not seed.exists():
        return False
    try:
        target_resolved = target.resolve()
        seed_resolved = seed.resolve()
        if target_resolved == seed_resolved:
            return False
        bundle = _bundle_root().resolve()
        if target_resolved == bundle or bundle in target_resolved.parents:
            return False
    except OSError:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed, target)
    return True


def legacy_appdata_file() -> Path:
    """User AppData library (frozen builds) and older Echo source location."""
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / ".config"
    return base / APP_NAME / FILE_NAME


def migrate_legacy_file(legacy: Path, target: Path) -> bool:
    """Copy templates from an older location if the current file does not exist.

    Never overwrites an existing target, even if that file is empty.
    """
    if target.exists() or not legacy.exists() or legacy.resolve() == target.resolve():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy, target)
    return True


@dataclass
class Template:
    id: str
    title: str
    keywords: list[str] = field(default_factory=list)
    text: str = ""

    def search_blob(self) -> str:
        return " ".join([self.title, *self.keywords]).casefold()


class TemplateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.templates: list[Template] = []

    def load(self) -> str | None:
        """Load templates. Returns a warning message if anything was wrong."""
        self.templates = []

        if not self.path.exists():
            return None

        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError as error:
            return f"Could not read {self.path.name}: {error}"

        try:
            data = json.loads(raw)
        except ValueError:
            saved = self._copy_aside("corrupt")
            return (
                f"{self.path.name} could not be read and was ignored. "
                f"A copy was kept as {saved.name}."
            )

        items = _items_from(data)
        if items is None:
            saved = self._copy_aside("corrupt")
            return (
                f"{self.path.name} did not contain a template list and was ignored. "
                f"A copy was kept as {saved.name}."
            )

        templates = []
        skipped = 0
        for item in items:
            template = _template_from(item)
            if template is None:
                skipped += 1
            else:
                templates.append(template)
        self.templates = templates

        if skipped:
            saved = self._copy_aside("recovered")
            return (
                f"Skipped {skipped} unreadable template(s). "
                f"The original file was kept as {saved.name}."
            )
        return None

    def save(self) -> None:
        """Write atomically so a failure can never truncate the library."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"templates": [asdict(template) for template in self.templates]}
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

        temp_path = self.path.with_name(self.path.name + ".tmp")
        with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())

        if self.path.exists():
            shutil.copy2(self.path, self.path.with_name(self.path.name + ".bak"))

        os.replace(temp_path, self.path)

    def search(self, query: str) -> list[Template]:
        query = " ".join(query.strip().casefold().split())
        if not query:
            return []

        terms = query.split()
        matches = [t for t in self.templates if all(term in t.search_blob() for term in terms)]
        return sorted(matches, key=lambda t: (_rank(t, query), t.title.casefold()))

    def get(self, template_id: str) -> Template | None:
        for template in self.templates:
            if template.id == template_id:
                return template
        return None

    def add(self, title: str, keywords: list[str], text: str) -> Template:
        template = Template(
            id=uuid.uuid4().hex[:8],
            title=title.strip(),
            keywords=_clean_keywords(keywords),
            text=text,
        )
        self.templates.append(template)
        try:
            self.save()
        except Exception:
            self.templates.pop()
            raise
        return template

    def update(self, template_id: str, title: str, keywords: list[str], text: str) -> Template | None:
        template = self.get(template_id)
        if template is None:
            return None
        previous = (template.title, list(template.keywords), template.text)
        template.title = title.strip()
        template.keywords = _clean_keywords(keywords)
        template.text = text
        try:
            self.save()
        except Exception:
            template.title, template.keywords, template.text = previous
            raise
        return template

    def delete(self, template_id: str) -> bool:
        remaining = [t for t in self.templates if t.id != template_id]
        if len(remaining) == len(self.templates):
            return False
        previous = self.templates
        self.templates = remaining
        try:
            self.save()
        except Exception:
            self.templates = previous
            raise
        return True

    def _copy_aside(self, label: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = self.path.with_name(f"{self.path.stem}.{label}-{stamp}.json")
        try:
            shutil.copy2(self.path, target)
        except OSError:
            pass
        return target


def keywords_from_text(value: str) -> list[str]:
    return _clean_keywords(part.strip() for part in value.split(","))


def keywords_to_text(keywords: list[str]) -> str:
    return ", ".join(keywords)


def _items_from(data) -> list | None:
    if isinstance(data, dict):
        items = data.get("templates")
        return items if isinstance(items, list) else None
    if isinstance(data, list):
        return data
    return None


def _template_from(item) -> Template | None:
    if not isinstance(item, dict):
        return None

    title = item.get("title")
    text = item.get("text")
    if not isinstance(title, str) or not isinstance(text, str) or not title.strip():
        return None

    raw_keywords = item.get("keywords", [])
    keywords = raw_keywords if isinstance(raw_keywords, list) else []

    template_id = item.get("id")
    if not isinstance(template_id, str) or not template_id:
        template_id = uuid.uuid4().hex[:8]

    return Template(
        id=template_id,
        title=title.strip(),
        keywords=_clean_keywords(k for k in keywords if isinstance(k, str)),
        text=text,
    )


def _rank(template: Template, query: str) -> int:
    """Exact title match first, then title prefix, then anywhere in the title."""
    title = template.title.casefold()
    if title == query:
        return 0
    if title.startswith(query):
        return 1
    if query in title:
        return 2
    return 3


def _clean_keywords(keywords) -> list[str]:
    cleaned = []
    seen = set()
    for keyword in keywords:
        keyword = str(keyword).strip()
        key = keyword.casefold()
        if keyword and key not in seen:
            seen.add(key)
            cleaned.append(keyword)
    return cleaned
