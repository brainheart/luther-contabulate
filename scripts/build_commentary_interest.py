#!/usr/bin/env python3
"""Build compact commentary-interest counts from HistoricalChristianFaith SQLite."""

import argparse
import bisect
import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from pathlib import Path


PREFERRED_COMMENTATOR_KEYS = {
    "Ambrose of Milan": "ambrose",
    "Augustine of Hippo": "augustine",
    "Bede": "bede",
    "Jerome": "jerome",
    "John Chrysostom": "chrysostom",
    "Martin Luther": "luther",
    "Origen of Alexandria": "origen",
    "Tertullian": "tertullian",
    "Thomas Aquinas": "aquinas",
}

OSIS_TO_HCF_BOOK = {
    "Gen": "genesis",
    "Exod": "exodus",
    "Lev": "leviticus",
    "Num": "numbers",
    "Deut": "deuteronomy",
    "Josh": "joshua",
    "Judg": "judges",
    "Ruth": "ruth",
    "1Sam": "1samuel",
    "2Sam": "2samuel",
    "1Kgs": "1kings",
    "2Kgs": "2kings",
    "1Chr": "1chronicles",
    "2Chr": "2chronicles",
    "Ezra": "ezra",
    "Neh": "nehemiah",
    "Esth": "esther",
    "Job": "job",
    "Ps": "psalms",
    "Prov": "proverbs",
    "Eccl": "ecclesiastes",
    "Song": "songofsolomon",
    "Isa": "isaiah",
    "Jer": "jeremiah",
    "Lam": "lamentations",
    "Ezek": "ezekiel",
    "Dan": "daniel",
    "Hos": "hosea",
    "Joel": "joel",
    "Amos": "amos",
    "Obad": "obadiah",
    "Jonah": "jonah",
    "Mic": "micah",
    "Nah": "nahum",
    "Hab": "habakkuk",
    "Zeph": "zephaniah",
    "Hag": "haggai",
    "Zech": "zechariah",
    "Mal": "malachi",
    "Matt": "matthew",
    "Mark": "mark",
    "Luke": "luke",
    "John": "john",
    "Acts": "acts",
    "Rom": "romans",
    "1Cor": "1corinthians",
    "2Cor": "2corinthians",
    "Gal": "galatians",
    "Eph": "ephesians",
    "Phil": "philippians",
    "Col": "colossians",
    "1Thess": "1thessalonians",
    "2Thess": "2thessalonians",
    "1Tim": "1timothy",
    "2Tim": "2timothy",
    "Titus": "titus",
    "Phlm": "philemon",
    "Heb": "hebrews",
    "Jas": "james",
    "1Pet": "1peter",
    "2Pet": "2peter",
    "1John": "1john",
    "2John": "2john",
    "3John": "3john",
    "Jude": "jude",
    "Rev": "revelation",
}


def hcf_location(chapter, verse):
    return int(chapter) * 1_000_000 + int(verse)


def slugify_commentator_name(name):
    preferred = PREFERRED_COMMENTATOR_KEYS.get(name)
    if preferred:
        return preferred
    ascii_name = (
        unicodedata.normalize("NFKD", name)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_")
    return slug or "commentator"


def build_commentator_metadata(names, total_by_commentator):
    used_keys = set()
    metadata = []
    for name in sorted(names, key=lambda value: value.casefold()):
        base_key = slugify_commentator_name(name)
        key = base_key
        suffix = 2
        while key in used_keys:
            key = f"{base_key}_{suffix}"
            suffix += 1
        used_keys.add(key)
        metadata.append(
            {
                "key": key,
                "name": name,
                "label": name,
                "reference_count": int(total_by_commentator.get(name) or 0),
            }
        )
    return metadata


def build_verse_index(chunks):
    by_book = defaultdict(list)
    for row in chunks:
        canonical_id = row.get("canonical_id", "")
        parts = canonical_id.split(".")
        if len(parts) != 3:
            continue
        book = OSIS_TO_HCF_BOOK.get(parts[0])
        if not book:
            continue
        by_book[book].append(
            {
                "canonical_id": canonical_id,
                "location": row.get("location", ""),
                "hcf_location": hcf_location(row.get("act", 0), row.get("scene", 0)),
            }
        )
    for rows in by_book.values():
        rows.sort(key=lambda item: item["hcf_location"])
    return by_book


def build_interest(sqlite_path, chunks_path):
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    verses_by_book = build_verse_index(chunks)
    locations_by_book = {
        book: [item["hcf_location"] for item in rows]
        for book, rows in verses_by_book.items()
    }
    valid_books = set(verses_by_book)

    verse_totals = defaultdict(int)
    verse_by_commentator = defaultdict(lambda: defaultdict(int))
    names = set()
    total_by_commentator = defaultdict(int)

    conn = sqlite3.connect(sqlite_path)
    try:
        rows = conn.execute(
            """
            select father_name, book, location_start, location_end
            from commentary
            where book in ({})
            """.format(",".join("?" for _ in valid_books)),
            sorted(valid_books),
        )
        for father_name, book, start, end in rows:
            if start is None or end is None:
                continue
            book_verses = verses_by_book.get(book)
            book_locations = locations_by_book.get(book)
            if not book_verses or not book_locations:
                continue
            start = int(start)
            end = int(end)
            if end < start:
                start, end = end, start
            left = bisect.bisect_left(book_locations, start)
            right = bisect.bisect_right(book_locations, end)
            if father_name:
                names.add(father_name)
            for idx in range(left, right):
                canonical_id = book_verses[idx]["canonical_id"]
                verse_totals[canonical_id] += 1
                if father_name:
                    total_by_commentator[father_name] += 1
                    verse_by_commentator[canonical_id][father_name] += 1
    finally:
        conn.close()

    commentators = build_commentator_metadata(names, total_by_commentator)
    key_by_name = {item["name"]: item["key"] for item in commentators}
    verses = {}
    for canonical_id in sorted(verse_totals):
        by_commentator = {
            key_by_name[name]: count
            for name, count in sorted(verse_by_commentator[canonical_id].items())
            if count
        }
        item = {"total": verse_totals[canonical_id]}
        if by_commentator:
            item["by_commentator"] = by_commentator
        verses[canonical_id] = item
    return verses, commentators


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sqlite", type=Path, help="HistoricalChristianFaith commentaries.sqlite")
    parser.add_argument(
        "--chunks",
        type=Path,
        default=Path("docs/data/chunks.json"),
        help="Bible chunks JSON to align against",
    )
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("commentary/historical_christian_faith_interest.json"),
        help="Output compact JSON source",
    )
    args = parser.parse_args()

    verses, commentators = build_interest(args.sqlite, args.chunks)
    payload = {
        "metadata": {
            "source_id": "historical_christian_faith",
            "source_name": "HistoricalChristianFaith Commentaries Database",
            "source_url": "https://github.com/HistoricalChristianFaith/Commentaries-Database",
            "release_url": "https://github.com/HistoricalChristianFaith/Commentaries-Database/releases/tag/latest",
            "license_url": "https://github.com/HistoricalChristianFaith/Commentaries-Database/blob/master/LICENSE",
            "commentators": commentators,
            "count_meaning": "Number of commentary excerpts whose mapped passage overlaps the verse.",
        },
        "verses": verses,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {args.out} with {len(verses)} verses carrying commentary interest.")


if __name__ == "__main__":
    main()
