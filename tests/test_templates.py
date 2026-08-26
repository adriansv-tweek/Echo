"""Tests for TemplateStore. Run with: python -m unittest discover tests"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from templates import TemplateStore, keywords_from_text  # noqa: E402


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
        self.assertEqual(len(self.store.search("")), 2)
        self.assertEqual(len(self.store.search("   ")), 2)

    def test_search_requires_all_terms(self) -> None:
        self.store.add("Manglende varer", ["mangler"], "a")

        self.assertEqual(len(self.store.search("manglende varer")), 1)
        self.assertEqual(len(self.store.search("manglende retur")), 0)

    def test_search_ranks_exact_then_prefix_then_keyword(self) -> None:
        self.store.add("Retur av varer", [], "a")
        self.store.add("Refusjon", ["retur"], "b")
        self.store.add("Retur", [], "c")

        self.assertEqual(
            [t.title for t in self.store.search("retur")],
            ["Retur", "Retur av varer", "Refusjon"],
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

    def test_duplicate_and_blank_keywords_are_cleaned(self) -> None:
        template = self.store.add("T", ["a", " a ", "A", "", "b"], "x")
        self.assertEqual(template.keywords, ["a", "b"])

    def test_keywords_from_text(self) -> None:
        self.assertEqual(keywords_from_text("one, two ,, three"), ["one", "two", "three"])
        self.assertEqual(keywords_from_text(""), [])


if __name__ == "__main__":
    unittest.main()
