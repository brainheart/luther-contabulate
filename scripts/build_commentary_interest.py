#!/usr/bin/env python3
"""Build compact commentary-interest counts from HistoricalChristianFaith SQLite."""

import argparse
import bisect
import hashlib
import json
import re
import shutil
import sqlite3
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
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

HCF_BASE_URL = "https://historicalchristian.faith"
PUBLIC_DOMAIN_THROUGH_YEAR = 1930
RESTRICTED_PREVIEW_WORDS = 24

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


def build_commentator_metadata(names, total_by_commentator, father_metadata=None):
    father_metadata = father_metadata or {}
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
        item = {
            "key": key,
            "name": name,
            "label": name,
            "reference_count": int(total_by_commentator.get(name) or 0),
        }
        source_meta = father_metadata.get(name) or {}
        if source_meta.get("category"):
            item["category"] = source_meta["category"]
        if source_meta.get("wiki_url"):
            item["wiki_url"] = source_meta["wiki_url"]
        if source_meta.get("default_year") is not None:
            item["default_year"] = source_meta["default_year"]
        if source_meta.get("condemned_by_council"):
            item["condemned_by_council"] = True
        metadata.append(item)
    return metadata


def load_father_metadata(conn):
    try:
        rows = conn.execute(
            """
            select name, default_year, wiki_url, father_category, condemned_by_council
            from father_meta
            """
        )
    except sqlite3.OperationalError:
        return {}
    output = {}
    for name, default_year, wiki_url, category, condemned in rows:
        if not name:
            continue
        try:
            year = int(default_year) if default_year is not None else None
        except (TypeError, ValueError):
            year = None
        output[name] = {
            "default_year": year,
            "wiki_url": wiki_url or "",
            "category": category or "",
            "condemned_by_council": bool(condemned),
        }
    return output


def split_hcf_location(value):
    location = int(value or 0)
    return divmod(location, 1_000_000)


def is_restricted_modern_text(year):
    try:
        value = int(year)
    except (TypeError, ValueError):
        return False
    return PUBLIC_DOMAIN_THROUGH_YEAR < value < 9_999


def short_preview(text, word_limit=RESTRICTED_PREVIEW_WORDS):
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    words = normalized.split()
    if len(words) <= word_limit:
        return normalized
    return " ".join(words[:word_limit]) + "..."


def stable_comment_id(*parts):
    payload = "\x1f".join(str(part or "") for part in parts).encode("utf-8")
    return "hcf-" + hashlib.sha256(payload).hexdigest()[:20]


def hcf_passage_url(book, start, end):
    start_chapter, start_verse = split_hcf_location(start)
    end_chapter, end_verse = split_hcf_location(end)
    verse_part = str(start_verse)
    if start_chapter == end_chapter and end_verse > start_verse:
        verse_part = f"{start_verse}-{end_verse}"
    return f"{HCF_BASE_URL}/{book}/{start_chapter}/{verse_part}"


def detail_author_index(payload, name, key, father_metadata):
    indexes = payload["_author_indexes"]
    if name in indexes:
        return indexes[name]
    meta = father_metadata.get(name) or {}
    author = {
        "key": key,
        "name": name,
        "category": meta.get("category") or "",
        "wiki_url": meta.get("wiki_url") or "",
    }
    if meta.get("default_year") is not None:
        author["default_year"] = meta["default_year"]
    if meta.get("condemned_by_council"):
        author["condemned_by_council"] = True
    indexes[name] = len(payload["authors"])
    payload["authors"].append(author)
    return indexes[name]


def detail_work_index(payload, title, source_url):
    identity = (title or "", source_url or "")
    indexes = payload["_work_indexes"]
    if identity in indexes:
        return indexes[identity]
    indexes[identity] = len(payload["works"])
    payload["works"].append([identity[0], identity[1]])
    return indexes[identity]


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


def build_interest(sqlite_path, chunks_path, include_details=True):
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
    detail_books = defaultdict(
        lambda: {
            "authors": [],
            "works": [],
            "comments": [],
            "verses": defaultdict(list),
            "_author_indexes": {},
            "_work_indexes": {},
        }
    )
    detail_summary = {
        "mapped_comment_count": 0,
        "full_text_comment_count": 0,
        "restricted_preview_comment_count": 0,
        "comments_with_source_url": 0,
    }

    conn = sqlite3.connect(sqlite_path)
    try:
        father_metadata = load_father_metadata(conn)
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

        commentators = build_commentator_metadata(
            names, total_by_commentator, father_metadata
        )
        key_by_name = {item["name"]: item["key"] for item in commentators}

        if include_details:
            detail_rows = conn.execute(
                """
                select father_name, file_name, ts, book, location_start, location_end,
                       txt, source_url, source_title
                from commentary
                where book in ({})
                order by book, location_start, location_end, father_name,
                         file_name, source_title, txt
                """.format(",".join("?" for _ in valid_books)),
                sorted(valid_books),
            )
            for (
                father_name,
                file_name,
                year,
                book,
                start,
                end,
                comment_text,
                source_url,
                source_title,
            ) in detail_rows:
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
                if left >= right:
                    continue

                canonical_ids = [
                    book_verses[idx]["canonical_id"] for idx in range(left, right)
                ]
                osis_book = canonical_ids[0].split(".", 1)[0]
                payload = detail_books[osis_book]
                author_index = detail_author_index(
                    payload,
                    father_name,
                    key_by_name[father_name],
                    father_metadata,
                )
                work_index = detail_work_index(
                    payload, source_title or "", source_url or ""
                )
                restricted = is_restricted_modern_text(year)
                display_text = (
                    short_preview(comment_text) if restricted else str(comment_text or "")
                )
                start_chapter, start_verse = split_hcf_location(start)
                end_chapter, end_verse = split_hcf_location(end)
                comment_id = stable_comment_id(
                    father_name,
                    file_name,
                    book,
                    start,
                    end,
                    source_title,
                    comment_text,
                )
                comment_index = len(payload["comments"])
                payload["comments"].append(
                    [
                        author_index,
                        work_index,
                        comment_id,
                        start_chapter,
                        start_verse,
                        end_chapter,
                        end_verse,
                        int(year or 0),
                        display_text,
                        1 if restricted else 0,
                        hcf_passage_url(book, start, end),
                    ]
                )
                for canonical_id in canonical_ids:
                    payload["verses"][canonical_id].append(comment_index)
                detail_summary["mapped_comment_count"] += 1
                if restricted:
                    detail_summary["restricted_preview_comment_count"] += 1
                else:
                    detail_summary["full_text_comment_count"] += 1
                if source_url:
                    detail_summary["comments_with_source_url"] += 1
    finally:
        conn.close()

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
    return verses, commentators, detail_books, detail_summary


def canonical_sort_key(canonical_id):
    parts = str(canonical_id or "").split(".")
    if len(parts) != 3:
        return (str(canonical_id or ""), 0, 0)
    return (parts[0], int(parts[1]), int(parts[2]))


def write_detail_books(detail_books, out_dir):
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for book in sorted(detail_books):
        payload = detail_books[book]
        output = {
            "book": book,
            "authors": payload["authors"],
            "works": payload["works"],
            "comments": payload["comments"],
            "verses": {
                canonical_id: payload["verses"][canonical_id]
                for canonical_id in sorted(
                    payload["verses"], key=canonical_sort_key
                )
            },
        }
        (out_dir / f"{book}.json").write_text(
            json.dumps(output, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )


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
    parser.add_argument(
        "--details-dir",
        type=Path,
        default=Path("docs/commentary"),
        help="Output directory for lazy per-book commentary detail JSON",
    )
    parser.add_argument(
        "--no-details",
        action="store_true",
        help="Only write compact counts, without individual comment files",
    )
    args = parser.parse_args()

    include_details = not args.no_details
    verses, commentators, detail_books, detail_summary = build_interest(
        args.sqlite, args.chunks, include_details=include_details
    )
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    metadata = {
        "source_id": "historical_christian_faith",
        "source_name": "HistoricalChristianFaith Commentaries Database",
        "source_url": "https://github.com/HistoricalChristianFaith/Commentaries-Database",
        "release_url": "https://github.com/HistoricalChristianFaith/Commentaries-Database/releases/tag/latest",
        "license_url": "https://github.com/HistoricalChristianFaith/Commentaries-Database/blob/master/LICENSE",
        "commentators": commentators,
        "count_meaning": "Number of commentary excerpts whose mapped passage overlaps the verse.",
        "generated_at": generated_at,
        "rights_policy": {
            "full_text_through_year": PUBLIC_DOMAIN_THROUGH_YEAR,
            "restricted_preview_words": RESTRICTED_PREVIEW_WORDS,
            "note": (
                "Records dated after 1930 include only a short identifying preview; "
                "follow the source or HCF link to read the record."
            ),
        },
    }
    if include_details:
        metadata["detail_path_template"] = "commentary/{book}.json"
        metadata["detail_books"] = sorted(detail_books)
    payload = {
        "metadata": metadata,
        "summary": {
            **detail_summary,
            "verses_with_interest": len(verses),
            "total_interest": sum(item["total"] for item in verses.values()),
        },
        "verses": verses,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if include_details:
        write_detail_books(detail_books, args.details_dir)
    print(
        f"Wrote {args.out} with {len(verses)} verses carrying commentary interest"
        + (f" and {len(detail_books)} detail files." if include_details else ".")
    )


if __name__ == "__main__":
    main()
