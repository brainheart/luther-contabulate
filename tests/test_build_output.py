"""Sanity checks on the generated Bible build output."""

import json
import unittest
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "docs" / "data"
LINES_DIR = Path(__file__).parent.parent / "docs" / "lines"


class TestBuildOutputExists(unittest.TestCase):
    EXPECTED_FILES = [
        "plays.json",
        "chunks.json",
        "characters.json",
        "tokens.json",
        "tokens2.json",
        "tokens3.json",
        "tokens_char.json",
        "tokens_char2.json",
        "tokens_char3.json",
        "character_name_filter_config.json",
    ]

    def test_all_data_files_exist(self):
        for filename in self.EXPECTED_FILES:
            self.assertTrue((DATA_DIR / filename).exists(), f"{filename} must exist")

    def test_lines_file_exists(self):
        self.assertTrue((LINES_DIR / "all_lines.json").exists(), "all_lines.json must exist")


class TestBooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.books = json.loads((DATA_DIR / "plays.json").read_text())

    def test_has_66_books(self):
        self.assertEqual(len(self.books), 66)

    def test_book_has_required_fields(self):
        required = {
            "play_id",
            "location",
            "title",
            "abbr",
            "genre",
            "total_words",
            "total_lines",
            "num_acts",
            "num_scenes",
        }
        for book in self.books:
            self.assertTrue(required.issubset(book.keys()), f"Missing fields for {book.get('title')}")

    def test_testament_counts(self):
        counts = Counter(book["genre"] for book in self.books)
        self.assertEqual(counts["Old Testament"], 39)
        self.assertEqual(counts["New Testament"], 27)

    def test_unique_ids_and_abbreviations(self):
        book_ids = [book["play_id"] for book in self.books]
        abbrs = [book["abbr"] for book in self.books]
        self.assertEqual(len(book_ids), len(set(book_ids)))
        self.assertEqual(len(abbrs), len(set(abbrs)))

    def test_locations_follow_canonical_order(self):
        self.assertEqual(self.books[0]["location"], "01.Gen")
        self.assertEqual(self.books[-1]["location"], "66.Rev")


class TestVerses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verses = json.loads((DATA_DIR / "chunks.json").read_text())
        cls.books = {book["play_id"] for book in json.loads((DATA_DIR / "plays.json").read_text())}

    def test_verses_are_present(self):
        self.assertGreater(len(self.verses), 30000)

    def test_first_verse_shape(self):
        first = self.verses[0]
        self.assertEqual(first["canonical_id"], "Gen.1.1")
        self.assertEqual(first["location"], "01.Gen.001.001")
        self.assertEqual(first["act"], 1)
        self.assertEqual(first["scene"], 1)

    def test_verse_has_required_fields(self):
        required = {"scene_id", "canonical_id", "location", "play_id", "act", "scene", "total_words"}
        for verse in self.verses[:25]:
            self.assertTrue(required.issubset(verse.keys()))

    def test_all_verses_reference_valid_books(self):
        for verse in self.verses:
            self.assertIn(verse["play_id"], self.books)

    def test_unique_scene_ids(self):
        verse_ids = [verse["scene_id"] for verse in self.verses]
        self.assertEqual(len(verse_ids), len(set(verse_ids)))


class TestTokens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokens = json.loads((DATA_DIR / "tokens.json").read_text())
        cls.tokens2 = json.loads((DATA_DIR / "tokens2.json").read_text())
        cls.tokens3 = json.loads((DATA_DIR / "tokens3.json").read_text())

    def test_token_index_sizes(self):
        self.assertGreater(len(self.tokens), 10000)
        self.assertGreater(len(self.tokens2), 100000)
        self.assertGreater(len(self.tokens3), 300000)

    def test_posting_format(self):
        sample_key = next(iter(self.tokens))
        postings = self.tokens[sample_key]
        self.assertIsInstance(postings, list)
        self.assertGreater(len(postings), 0)
        for posting in postings[:5]:
            self.assertIsInstance(posting, list)
            self.assertEqual(len(posting), 2)
            self.assertIsInstance(posting[0], int)
            self.assertIsInstance(posting[1], int)


class TestVerseRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((LINES_DIR / "all_lines.json").read_text())
        cls.verses = json.loads((DATA_DIR / "chunks.json").read_text())

    def test_all_lines_matches_verse_count(self):
        self.assertEqual(len(self.rows), len(self.verses))

    def test_first_and_last_rows_have_text(self):
        self.assertEqual(self.rows[0]["canonical_id"], "Gen.1.1")
        self.assertEqual(self.rows[-1]["canonical_id"], "Rev.22.21")
        self.assertTrue(self.rows[0]["text"].strip())
        self.assertTrue(self.rows[-1]["text"].strip())


class TestCharacterOutputs(unittest.TestCase):
    def test_characters_are_empty_for_bible_build(self):
        chars = json.loads((DATA_DIR / "characters.json").read_text())
        self.assertEqual(chars, [])


if __name__ == "__main__":
    unittest.main()
