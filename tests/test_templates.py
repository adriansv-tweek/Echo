"""Tests for TemplateStore. Run with: python -m unittest discover tests"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from templates import (  # noqa: E402
    TemplateStore,
    data_file,
    ensure_packaged_templates,
    keywords_from_text,
    legacy_appdata_file,
    migrate_legacy_file,
)


class TemplateStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        self.path = self.dir / "templates.json"
        self.store = TemplateStore(self.path)

    def write(self, content: str) -> None:
        self.path.write_text(content, encoding="utf-8")

    def test_missing_file_starts_empty(self) -> None:
        self.assertIsNone(self.store.load())
        self.assertEqual(self.store.templates, [])

    def test_save_and_load_round_trip(self) -> None:
        self.store.add("Refusjon Trumf", ["refusjon", "trumf"], "Hei igjen,\n\nMvh")

        reloaded = TemplateStore(self.path)
        self.assertIsNone(reloaded.load())
        self.assertEqual(len(reloaded.templates), 1)
        self.assertEqual(reloaded.templates[0].title, "Refusjon Trumf")
        self.assertEqual(reloaded.templates[0].text, "Hei igjen,\n\nMvh")
        self.assertEqual(reloaded.templates[0].keywords, ["refusjon", "trumf"])

    def test_corrupt_json_is_backed_up_and_does_not_crash(self) -> None:
        self.write('{"templates": [ {"title": "x"')

        warning = self.store.load()

        self.assertIsNotNone(warning)
        self.assertEqual(self.store.templates, [])
        backups = list(self.dir.glob("templates.corrupt-*.json"))
        self.assertEqual(len(backups), 1)
        self.assertIn('{"templates"', backups[0].read_text(encoding="utf-8"))

    def test_empty_file_does_not_crash(self) -> None:
        self.write("")

        warning = self.store.load()

        self.assertIsNotNone(warning)
        self.assertEqual(self.store.templates, [])

    def test_unexpected_structure_does_not_crash(self) -> None:
        self.write("42")

        warning = self.store.load()

        self.assertIsNotNone(warning)
        self.assertEqual(self.store.templates, [])

    def test_malformed_entries_are_skipped_and_valid_ones_kept(self) -> None:
        self.write(
            json.dumps(
                {
                    "templates": [
                        {"id": "a1", "title": "Good", "keywords": ["ok"], "text": "body"},
                        "not a dict",
                        {"title": "", "text": "no title"},
                        {"title": "No text field"},
                        {"id": "a2", "title": "Also good", "keywords": "wrong type", "text": "b"},
                    ]
                }
            )
        )

        warning = self.store.load()

        self.assertIsNotNone(warning)
        self.assertIn("Skipped 3", warning)
        self.assertEqual([t.title for t in self.store.templates], ["Good", "Also good"])
        self.assertEqual(self.store.templates[1].keywords, [])
        self.assertEqual(len(list(self.dir.glob("templates.recovered-*.json"))), 1)

    def test_search_matches_title_and_keywords(self) -> None:
        self.store.add("Manglende varer", ["mangler", "vare"], "a")
        self.store.add("Leveringstid", ["levering"], "b")

        self.assertEqual([t.title for t in self.store.search("manglende")], ["Manglende varer"])
        self.assertEqual([t.title for t in self.store.search("levering")], ["Leveringstid"])
        self.assertEqual(self.store.search("ukjent"), [])
        self.assertEqual(self.store.search(""), [])
        self.assertEqual(self.store.search("   "), [])

    def test_search_requires_all_terms(self) -> None:
        self.store.add("Manglende varer", ["mangler"], "a")

        self.assertEqual(len(self.store.search("manglende varer")), 1)
        self.assertEqual(len(self.store.search("manglende retur")), 0)

    def test_search_ranks_exact_prefix_substring_then_keyword(self) -> None:
        self.store.add("Other", ["manglende"], "a")
        self.store.add("Foo manglende bar", [], "b")
        self.store.add("Manglende varer", [], "c")
        self.store.add("Manglende", [], "d")

        self.assertEqual(
            [t.title for t in self.store.search("manglende")],
            ["Manglende", "Manglende varer", "Foo manglende bar", "Other"],
        )

    def test_search_is_case_insensitive(self) -> None:
        self.store.add("Manglende", [], "a")
        self.store.add("Refusjon bank", ["bank"], "b")
        self.store.add("Refusjon Trumf", ["trumf"], "c")
        self.store.add("Mugg", ["mat"], "d")

        self.assertEqual([t.title for t in self.store.search("manglende")], ["Manglende"])
        self.assertEqual([t.title for t in self.store.search("refusjon bank")], ["Refusjon bank"])
        self.assertEqual([t.title for t in self.store.search("REFUSJON BANK")], ["Refusjon bank"])
        self.assertEqual([t.title for t in self.store.search("refusjon trumf")], ["Refusjon Trumf"])
        self.assertEqual([t.title for t in self.store.search("mugg")], ["Mugg"])

    def test_search_collapses_extra_spaces(self) -> None:
        self.store.add("Refusjon bank", [], "a")

        self.assertEqual(
            [t.title for t in self.store.search("  refusjon   bank  ")],
            ["Refusjon bank"],
        )

    def test_add_edit_delete(self) -> None:
        template = self.store.add("Title", ["one"], "text")

        updated = self.store.update(template.id, "New title", ["two"], "new text")
        self.assertIsNotNone(updated)
        self.assertEqual(updated.title, "New title")
        self.assertEqual(updated.keywords, ["two"])

        self.assertIsNone(self.store.update("missing-id", "x", [], "y"))

        self.assertTrue(self.store.delete(template.id))
        self.assertFalse(self.store.delete(template.id))

        reloaded = TemplateStore(self.path)
        reloaded.load()
        self.assertEqual(reloaded.templates, [])

    def test_save_keeps_a_backup_of_the_previous_version(self) -> None:
        self.store.add("First", [], "a")
        self.store.add("Second", [], "b")

        backup = self.path.with_name("templates.json.bak")
        self.assertTrue(backup.exists())
        saved = json.loads(backup.read_text(encoding="utf-8"))
        self.assertEqual([t["title"] for t in saved["templates"]], ["First"])

    def test_save_leaves_no_temporary_file_behind(self) -> None:
        self.store.add("First", [], "a")

        self.assertFalse(self.path.with_name("templates.json.tmp").exists())
        self.assertTrue(self.path.exists())

    def test_failed_save_does_not_destroy_existing_file(self) -> None:
        self.store.add("Keep me", [], "body")
        before = self.path.read_text(encoding="utf-8")

        broken = TemplateStore(self.path)
        broken.load()
        broken.templates.append(object())  # not serialisable

        with self.assertRaises(Exception):
            broken.save()

        self.assertEqual(self.path.read_text(encoding="utf-8"), before)

    def test_oserror_during_save_keeps_existing_file(self) -> None:
        self.store.add("Keep me", [], "body")
        before = self.path.read_text(encoding="utf-8")

        with patch("templates.open", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.add("New", [], "nope")

        self.assertEqual(self.path.read_text(encoding="utf-8"), before)
        self.assertEqual([t.title for t in self.store.templates], ["Keep me"])

    def test_duplicate_and_blank_keywords_are_cleaned(self) -> None:
        template = self.store.add("T", ["a", " a ", "A", "", "b"], "x")
        self.assertEqual(template.keywords, ["a", "b"])

    def test_keywords_from_text(self) -> None:
        self.assertEqual(keywords_from_text("one, two ,, three"), ["one", "two", "three"])
        self.assertEqual(keywords_from_text(""), [])

    def test_failed_add_rolls_back_memory(self) -> None:
        self.store.add("Keep me", [], "body")
        original = list(self.store.templates)

        def fail_save() -> None:
            raise OSError("disk full")

        self.store.save = fail_save  # type: ignore[method-assign]
        with self.assertRaises(OSError):
            self.store.add("Lost", [], "nope")

        self.assertEqual([t.title for t in self.store.templates], [t.title for t in original])

    def test_data_file_is_repo_data_templates_json(self) -> None:
        path = data_file()
        root = Path(__file__).resolve().parent.parent
        self.assertEqual(path, root / "data" / "templates.json")
        self.assertEqual(path.parent.name, "data")
        self.assertEqual(path.name, "templates.json")

    def test_data_file_does_not_use_appdata(self) -> None:
        original = os.environ.get("APPDATA")
        os.environ["APPDATA"] = r"C:\FakeAppData\ShouldNotBeUsed"
        try:
            path = str(data_file())
            self.assertNotIn("FakeAppData", path)
            self.assertNotIn("ShouldNotBeUsed", path)
            self.assertTrue(path.replace("\\", "/").endswith("data/templates.json"))
        finally:
            if original is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = original

    def test_legacy_appdata_path_is_only_for_migration(self) -> None:
        original = os.environ.get("APPDATA")
        os.environ["APPDATA"] = r"C:\FakeAppData"
        try:
            legacy = legacy_appdata_file()
            current = data_file()
            self.assertEqual(legacy, Path(r"C:\FakeAppData") / "Echo" / "templates.json")
            self.assertNotEqual(legacy, current)
        finally:
            if original is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = original

    def test_migrate_copies_legacy_when_target_is_missing(self) -> None:
        legacy = self.dir / "legacy.json"
        target = self.dir / "data" / "templates.json"
        legacy.write_text('{"templates": [{"id": "1", "title": "Old", "text": "x"}]}', encoding="utf-8")

        self.assertTrue(migrate_legacy_file(legacy, target))
        self.assertTrue(target.exists())
        self.assertIn("Old", target.read_text(encoding="utf-8"))

    def test_migrate_does_not_overwrite_existing_target(self) -> None:
        legacy = self.dir / "legacy.json"
        target = self.dir / "templates.json"
        legacy.write_text('{"templates": [{"id": "1", "title": "Old", "text": "x"}]}', encoding="utf-8")
        target.write_text('{"templates": []}', encoding="utf-8")

        self.assertFalse(migrate_legacy_file(legacy, target))
        self.assertEqual(target.read_text(encoding="utf-8"), '{"templates": []}')

    def test_migrate_is_noop_when_legacy_missing(self) -> None:
        target = self.dir / "templates.json"
        self.assertFalse(migrate_legacy_file(self.dir / "missing.json", target))
        self.assertFalse(target.exists())

    def test_migrate_does_not_copy_onto_itself(self) -> None:
        path = self.dir / "templates.json"
        path.write_text("{}", encoding="utf-8")
        self.assertFalse(migrate_legacy_file(path, path))

    def test_ensure_packaged_templates_is_noop_when_not_frozen(self) -> None:
        target = self.dir / "Echo" / "templates.json"
        self.assertFalse(ensure_packaged_templates(target))
        self.assertFalse(target.exists())

    def test_frozen_data_file_uses_appdata(self) -> None:
        original = os.environ.get("APPDATA")
        os.environ["APPDATA"] = r"C:\FakeAppData"
        try:
            with patch("templates.sys.frozen", True, create=True):
                path = data_file()
            self.assertEqual(path, Path(r"C:\FakeAppData") / "Echo" / "templates.json")
        finally:
            if original is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = original

    def test_frozen_first_launch_copies_seed_to_appdata(self) -> None:
        bundle = Path(tempfile.mkdtemp())
        seed = bundle / "data" / "templates.json"
        seed.parent.mkdir(parents=True)
        seed.write_text(
            '{"templates": [{"id": "1", "title": "Seed", "text": "x"}]}',
            encoding="utf-8",
        )
        appdata = Path(tempfile.mkdtemp())
        target = appdata / "Echo" / "templates.json"

        with (
            patch("templates.sys.frozen", True, create=True),
            patch("templates.sys._MEIPASS", str(bundle), create=True),
            patch.dict(os.environ, {"APPDATA": str(appdata)}),
        ):
            dest = data_file()
            self.assertEqual(dest, target)
            self.assertTrue(ensure_packaged_templates(dest))
            store = TemplateStore(dest)
            self.assertIsNone(store.load())
            self.assertEqual([t.title for t in store.templates], ["Seed"])

        self.assertIn("Seed", target.read_text(encoding="utf-8"))
        self.assertIn("Seed", seed.read_text(encoding="utf-8"))

    def test_frozen_empty_seed_gives_new_users_zero_templates(self) -> None:
        bundle = Path(tempfile.mkdtemp())
        seed = bundle / "data" / "templates.json"
        seed.parent.mkdir(parents=True)
        seed.write_text('{\n  "templates": []\n}\n', encoding="utf-8")
        appdata = Path(tempfile.mkdtemp())
        target = appdata / "Echo" / "templates.json"

        with (
            patch("templates.sys.frozen", True, create=True),
            patch("templates.sys._MEIPASS", str(bundle), create=True),
            patch.dict(os.environ, {"APPDATA": str(appdata)}),
        ):
            dest = data_file()
            self.assertTrue(ensure_packaged_templates(dest))
            store = TemplateStore(dest)
            self.assertIsNone(store.load())
            self.assertEqual(store.templates, [])

        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"templates": []})

    def test_frozen_existing_appdata_library_is_kept_and_loaded(self) -> None:
        original = (
            '{"templates": [{"id": "a1", "title": "Mine", "keywords": [], "text": "keep"}]}'
        )
        appdata = Path(tempfile.mkdtemp())
        target = appdata / "Echo" / "templates.json"
        target.parent.mkdir(parents=True)
        target.write_text(original, encoding="utf-8")
        bundle = Path(tempfile.mkdtemp())
        seed = bundle / "data" / "templates.json"
        seed.parent.mkdir(parents=True)
        seed.write_text(
            '{"templates": [{"id": "1", "title": "Seed", "text": "x"}]}',
            encoding="utf-8",
        )

        with (
            patch("templates.sys.frozen", True, create=True),
            patch("templates.sys._MEIPASS", str(bundle), create=True),
            patch.dict(os.environ, {"APPDATA": str(appdata)}),
        ):
            dest = data_file()
            self.assertFalse(ensure_packaged_templates(dest))
            store = TemplateStore(dest)
            self.assertIsNone(store.load())
            self.assertEqual([t.title for t in store.templates], ["Mine"])

        self.assertEqual(target.read_text(encoding="utf-8"), original)

    def test_frozen_user_created_templates_persist(self) -> None:
        bundle = Path(tempfile.mkdtemp())
        seed = bundle / "data" / "templates.json"
        seed.parent.mkdir(parents=True)
        seed.write_text('{"templates": []}', encoding="utf-8")
        appdata = Path(tempfile.mkdtemp())

        with (
            patch("templates.sys.frozen", True, create=True),
            patch("templates.sys._MEIPASS", str(bundle), create=True),
            patch.dict(os.environ, {"APPDATA": str(appdata)}),
        ):
            dest = data_file()
            self.assertTrue(ensure_packaged_templates(dest))
            store = TemplateStore(dest)
            store.load()
            store.add("Personal", ["mine"], "only on this PC")

            reloaded = TemplateStore(dest)
            self.assertIsNone(reloaded.load())
            self.assertEqual(len(reloaded.templates), 1)
            self.assertEqual(reloaded.templates[0].title, "Personal")
            self.assertEqual(reloaded.templates[0].text, "only on this PC")

        self.assertTrue((appdata / "Echo" / "templates.json").exists())

    def test_frozen_seed_is_not_copied_into_the_bundle(self) -> None:
        bundle = Path(tempfile.mkdtemp())
        seed = bundle / "data" / "templates.json"
        seed.parent.mkdir(parents=True)
        seed.write_text("{}", encoding="utf-8")

        with (
            patch("templates.sys.frozen", True, create=True),
            patch("templates.sys._MEIPASS", str(bundle), create=True),
        ):
            self.assertFalse(ensure_packaged_templates(seed))
            self.assertFalse(ensure_packaged_templates(bundle / "data" / "user.json"))
        self.assertEqual(seed.read_text(encoding="utf-8"), "{}")
        self.assertFalse((bundle / "data" / "user.json").exists())


if __name__ == "__main__":
    unittest.main()
