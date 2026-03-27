import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import build


class BibleSourceSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = build.resolve_source_path(Path(__file__).parent)
        cls.root = ET.parse(cls.source).getroot()

    def test_allowed_books_excludes_apocrypha(self):
        books = list(build.iter_allowed_books(self.root))
        self.assertEqual(len(books), 66)
        abbrs = [book.attrib.get("osisID") for _, book in books]
        self.assertNotIn("Tob", abbrs)
        self.assertIn("Gen", abbrs)
        self.assertIn("Matt", abbrs)

    def test_extract_genesis_opening_verse(self):
        genesis = None
        for _, book in build.iter_allowed_books(self.root):
            if book.attrib.get("osisID") == "Gen":
                genesis = book
                break
        self.assertIsNotNone(genesis)
        verses = build.extract_verses(genesis)
        by_id = {verse["osis_id"]: verse["text"] for verse in verses}
        self.assertIn("Gen.1.1", by_id)
        self.assertTrue(by_id["Gen.1.1"].strip())

    def test_extract_revelation_handles_terminal_verse(self):
        revelation = None
        for testament, book in build.iter_allowed_books(self.root):
            if testament == "New Testament" and book.attrib.get("osisID") == "Rev":
                revelation = book
                break
        self.assertIsNotNone(revelation)
        verses = build.extract_verses(revelation)
        by_id = {verse["osis_id"]: verse["text"] for verse in verses}
        self.assertIn("Rev.22.21", by_id)
        self.assertTrue(by_id["Rev.22.21"].strip())

    def test_format_location_zero_pads_for_sorting(self):
        self.assertEqual(build.format_location(1, "Gen"), "01.Gen")
        self.assertEqual(build.format_location(1, "Gen", 7), "01.Gen.007")
        self.assertEqual(build.format_location(1, "Gen", 7, 12), "01.Gen.007.012")
        self.assertEqual(build.format_location(19, "Ps", 119, 105), "19.Ps.119.105")


if __name__ == "__main__":
    unittest.main()
