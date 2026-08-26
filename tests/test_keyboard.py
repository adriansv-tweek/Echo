"""Keyboard selection logic. Run with: python -m unittest discover tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from workflow import enter_action, next_result_row  # noqa: E402


class EnterActionTest(unittest.TestCase):
    def test_enter_with_no_selection_is_noop(self) -> None:
        self.assertEqual(enter_action(False, False), "noop")
        self.assertEqual(enter_action(False, True), "noop")

    def test_first_enter_selects(self) -> None:
        self.assertEqual(enter_action(True, False), "select")

    def test_second_enter_copies(self) -> None:
        self.assertEqual(enter_action(True, True), "copy")


class ResultNavigationTest(unittest.TestCase):
    def test_empty_list_does_not_move(self) -> None:
        self.assertIsNone(next_result_row(0, 0, 1))
        self.assertIsNone(next_result_row(0, -1, -1))

    def test_down_from_first_selects_second(self) -> None:
        self.assertEqual(next_result_row(3, 0, 1), 1)

    def test_up_from_first_stays_on_first(self) -> None:
        self.assertEqual(next_result_row(3, 0, -1), 0)

    def test_down_from_last_stays_on_last(self) -> None:
        self.assertEqual(next_result_row(3, 2, 1), 2)

    def test_no_current_row_starts_at_first(self) -> None:
        self.assertEqual(next_result_row(3, -1, 1), 1)
        self.assertEqual(next_result_row(3, -1, 0), 0)


if __name__ == "__main__":
    unittest.main()
