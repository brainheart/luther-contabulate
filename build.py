import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

OSIS_NS = "http://www.bibletechnologies.net/2003/OSIS/namespace"
TOKEN_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?", re.UNICODE)
IGNORED_TEXT_TAGS = {
    "date",
    "header",
    "language",
    "note",
    "publisher",
    "refSystem",
    "revisionDesc",
    "rights",
    "title",
    "work",
}
ALLOWED_TESTAMENTS = {"Old Testament", "New Testament"}
SOURCE_CANDIDATES = (
    "deu-luther1912.osis.xml",
    "ger-luther1912.osis.xml",
    "eng-kjv.osis.xml",
)
BOOK_ORDER = [
    "Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "Ruth", "1Sam", "2Sam", "1Kgs", "2Kgs",
    "1Chr", "2Chr", "Ezra", "Neh", "Esth", "Job", "Ps", "Prov", "Eccl", "Song", "Isa", "Jer",
    "Lam", "Ezek", "Dan", "Hos", "Joel", "Amos", "Obad", "Jonah", "Mic", "Nah", "Hab", "Zeph",
    "Hag", "Zech", "Mal", "Matt", "Mark", "Luke", "John", "Acts", "Rom", "1Cor", "2Cor", "Gal",
    "Eph", "Phil", "Col", "1Thess", "2Thess", "1Tim", "2Tim", "Titus", "Phlm", "Heb", "Jas",
    "1Pet", "2Pet", "1John", "2John", "3John", "Jude", "Rev",
]
BOOK_METADATA = {
    "Gen": ("1. Mose", "Gen", "Old Testament"),
    "Exod": ("2. Mose", "Exod", "Old Testament"),
    "Lev": ("3. Mose", "Lev", "Old Testament"),
    "Num": ("4. Mose", "Num", "Old Testament"),
    "Deut": ("5. Mose", "Deut", "Old Testament"),
    "Josh": ("Josua", "Josh", "Old Testament"),
    "Judg": ("Richter", "Judg", "Old Testament"),
    "Ruth": ("Ruth", "Ruth", "Old Testament"),
    "1Sam": ("1. Samuel", "1Sam", "Old Testament"),
    "2Sam": ("2. Samuel", "2Sam", "Old Testament"),
    "1Kgs": ("1. Könige", "1Kgs", "Old Testament"),
    "2Kgs": ("2. Könige", "2Kgs", "Old Testament"),
    "1Chr": ("1. Chronik", "1Chr", "Old Testament"),
    "2Chr": ("2. Chronik", "2Chr", "Old Testament"),
    "Ezra": ("Esra", "Ezra", "Old Testament"),
    "Neh": ("Nehemia", "Neh", "Old Testament"),
    "Esth": ("Ester", "Esth", "Old Testament"),
    "Job": ("Hiob", "Job", "Old Testament"),
    "Ps": ("Psalmen", "Ps", "Old Testament"),
    "Prov": ("Sprüche", "Prov", "Old Testament"),
    "Eccl": ("Prediger", "Eccl", "Old Testament"),
    "Song": ("Hohelied", "Song", "Old Testament"),
    "Isa": ("Jesaja", "Isa", "Old Testament"),
    "Jer": ("Jeremia", "Jer", "Old Testament"),
    "Lam": ("Klagelieder", "Lam", "Old Testament"),
    "Ezek": ("Hesekiel", "Ezek", "Old Testament"),
    "Dan": ("Daniel", "Dan", "Old Testament"),
    "Hos": ("Hosea", "Hos", "Old Testament"),
    "Joel": ("Joel", "Joel", "Old Testament"),
    "Amos": ("Amos", "Amos", "Old Testament"),
    "Obad": ("Obadja", "Obad", "Old Testament"),
    "Jonah": ("Jona", "Jonah", "Old Testament"),
    "Mic": ("Micha", "Mic", "Old Testament"),
    "Nah": ("Nahum", "Nah", "Old Testament"),
    "Hab": ("Habakuk", "Hab", "Old Testament"),
    "Zeph": ("Zephanja", "Zeph", "Old Testament"),
    "Hag": ("Haggai", "Hag", "Old Testament"),
    "Zech": ("Sacharja", "Zech", "Old Testament"),
    "Mal": ("Maleachi", "Mal", "Old Testament"),
    "Matt": ("Matthäus", "Matt", "New Testament"),
    "Mark": ("Markus", "Mark", "New Testament"),
    "Luke": ("Lukas", "Luke", "New Testament"),
    "John": ("Johannes", "John", "New Testament"),
    "Acts": ("Apostelgeschichte", "Acts", "New Testament"),
    "Rom": ("Römer", "Rom", "New Testament"),
    "1Cor": ("1. Korinther", "1Cor", "New Testament"),
    "2Cor": ("2. Korinther", "2Cor", "New Testament"),
    "Gal": ("Galater", "Gal", "New Testament"),
    "Eph": ("Epheser", "Eph", "New Testament"),
    "Phil": ("Philipper", "Phil", "New Testament"),
    "Col": ("Kolosser", "Col", "New Testament"),
    "1Thess": ("1. Thessalonicher", "1Thess", "New Testament"),
    "2Thess": ("2. Thessalonicher", "2Thess", "New Testament"),
    "1Tim": ("1. Timotheus", "1Tim", "New Testament"),
    "2Tim": ("2. Timotheus", "2Tim", "New Testament"),
    "Titus": ("Titus", "Titus", "New Testament"),
    "Phlm": ("Philemon", "Phlm", "New Testament"),
    "Heb": ("Hebräer", "Heb", "New Testament"),
    "Jas": ("Jakobus", "Jas", "New Testament"),
    "1Pet": ("1. Petrus", "1Pet", "New Testament"),
    "2Pet": ("2. Petrus", "2Pet", "New Testament"),
    "1John": ("1. Johannes", "1John", "New Testament"),
    "2John": ("2. Johannes", "2John", "New Testament"),
    "3John": ("3. Johannes", "3John", "New Testament"),
    "Jude": ("Judas", "Jude", "New Testament"),
    "Rev": ("Offenbarung", "Rev", "New Testament"),
}


def localname(tag):
    return tag.rsplit("}", 1)[-1]


def normalize_ws(text):
    return " ".join((text or "").split())


def tokenize(text):
    return TOKEN_RE.findall((text or "").lower())


def resolve_source_path(base: Path):
    osis_dir = base / "osis"
    for candidate in SOURCE_CANDIDATES:
        path = osis_dir / candidate
        if path.exists():
            return path
    xml_files = sorted(osis_dir.glob("*.xml"))
    if xml_files:
        return xml_files[0]
    raise FileNotFoundError(f"No OSIS XML source found under {osis_dir}")


def iter_allowed_books(root):
    grouped = False
    for group in root.iter():
        if localname(group.tag) != "div" or group.attrib.get("type") != "bookGroup":
            continue
        grouped = True
        titles = [
            normalize_ws((child.text or ""))
            for child in group
            if localname(child.tag) == "title"
        ]
        testament = titles[0] if titles else ""
        if testament not in ALLOWED_TESTAMENTS:
            continue
        for child in group:
            if localname(child.tag) == "div" and child.attrib.get("type") == "book":
                yield testament, child
    if grouped:
        return

    # Some OSIS files (including Luther 1912 from open-bibles) omit bookGroup
    # wrappers and expose books directly under the main div. In that case we use
    # canonical OSIS order + explicit metadata to determine testament/title.
    books = []
    for elem in root.iter():
        if localname(elem.tag) == "div" and elem.attrib.get("type") == "book":
            books.append(elem)
    order_index = {osis: i for i, osis in enumerate(BOOK_ORDER)}
    books.sort(key=lambda elem: order_index.get(elem.attrib.get("osisID", ""), 999))
    for book in books:
        osis_id = book.attrib.get("osisID", "")
        meta = BOOK_METADATA.get(osis_id)
        if not meta:
            continue
        testament = meta[2]
        yield testament, book


def extract_book_title(book_elem):
    for child in book_elem:
        if localname(child.tag) != "title":
            continue
        short = normalize_ws(child.attrib.get("short"))
        if short:
            return short
        text = normalize_ws(child.text)
        if text:
            return text
    osis_id = book_elem.attrib.get("osisID", "Unknown")
    return BOOK_METADATA.get(osis_id, (osis_id, osis_id, ""))[0]


def extract_verses(book_elem):
    verses = []

    # Simple OSIS style: <chapter osisID="Gen.1"><verse osisID="Gen.1.1">Text…</verse>
    simple_chapters = [child for child in book_elem if localname(child.tag) == "chapter" and child.attrib.get("osisID")]
    if simple_chapters:
        for chapter_elem in simple_chapters:
            chapter_id = chapter_elem.attrib.get("osisID", "")
            try:
                chapter_num = int(chapter_id.split(".")[-1])
            except ValueError:
                chapter_num = None
            for verse_elem in chapter_elem:
                if localname(verse_elem.tag) != "verse":
                    continue
                osis_id = verse_elem.attrib.get("osisID", "")
                verse_num_raw = verse_elem.attrib.get("n") or (osis_id.split(".")[-1] if osis_id else "")
                try:
                    verse_num = int(verse_num_raw)
                except ValueError:
                    verse_num = None
                text = normalize_ws(" ".join(filter(None, verse_elem.itertext())))
                if not text:
                    continue
                verses.append(
                    {
                        "osis_id": osis_id,
                        "chapter": chapter_num,
                        "verse": verse_num,
                        "text": text,
                    }
                )
        return verses

    # Marker-based OSIS style: verse/chapter start and end milestones.
    current_chapter = None
    current_verse = None

    def append_text(text):
        if current_verse is not None and text:
            current_verse["parts"].append(text)

    def finalize_current_verse():
        nonlocal current_verse
        if current_verse is None:
            return
        text = normalize_ws(" ".join(current_verse["parts"]))
        if text:
            current_verse["text"] = text
            verses.append(current_verse)
        current_verse = None

    def visit(elem):
        nonlocal current_chapter, current_verse
        tag = localname(elem.tag)
        if tag in IGNORED_TEXT_TAGS:
            return
        if current_verse is not None and tag not in {"chapter", "verse"}:
            append_text(elem.text)
        for child in elem:
            child_tag = localname(child.tag)
            if child_tag == "chapter" and "sID" in child.attrib:
                ref = child.attrib.get("osisRef") or child.attrib.get("n") or ""
                try:
                    current_chapter = int((ref.split(".")[-1] if "." in ref else ref) or 0)
                except ValueError:
                    current_chapter = None
            elif child_tag == "verse" and "sID" in child.attrib:
                osis_id = child.attrib.get("osisID", "")
                verse_num = child.attrib.get("n") or (osis_id.split(".")[-1] if osis_id else "")
                try:
                    verse_number = int(verse_num)
                except ValueError:
                    verse_number = None
                current_verse = {
                    "osis_id": osis_id,
                    "chapter": current_chapter,
                    "verse": verse_number,
                    "parts": [],
                }
            visit(child)
            if child_tag == "verse" and "eID" in child.attrib:
                finalize_current_verse()
                continue
            if current_verse is not None:
                append_text(child.tail)

    visit(book_elem)
    finalize_current_verse()
    return verses


def clean_dir_json_files(path):
    path.mkdir(parents=True, exist_ok=True)
    for json_path in path.glob("*.json"):
        json_path.unlink()


def format_location(book_id, book_abbr, chapter=None, verse=None):
    location = f"{int(book_id):02d}.{book_abbr}"
    if chapter is not None:
        location = f"{location}.{int(chapter):03d}"
    if verse is not None:
        location = f"{location}.{int(verse):03d}"
    return location


def build(source_path: Path, out_dir: Path):
    tree = ET.parse(source_path)
    root = tree.getroot()

    data_dir = out_dir / "data"
    lines_dir = out_dir / "lines"
    clean_dir_json_files(data_dir)
    clean_dir_json_files(lines_dir)

    plays = []
    chunks = []
    all_lines = []
    tokens = {}
    tokens2 = {}
    tokens3 = {}

    verse_id = 0

    for book_id, (testament, book_elem) in enumerate(iter_allowed_books(root), start=1):
        osis_id = book_elem.attrib.get("osisID", f"BOOK{book_id}")
        meta = BOOK_METADATA.get(osis_id)
        book_abbr = meta[1] if meta else osis_id
        book_title = meta[0] if meta else extract_book_title(book_elem)
        verses = extract_verses(book_elem)
        chapter_numbers = sorted({v["chapter"] for v in verses if v.get("chapter") is not None})
        book_total_words = 0

        for verse in verses:
            text = verse["text"]
            toks = tokenize(text)
            if not toks:
                continue
            verse_id += 1
            chapter_num = int(verse["chapter"] or 0)
            verse_num = int(verse["verse"] or 0)
            canonical_id = verse["osis_id"] or f"{book_abbr}.{chapter_num}.{verse_num}"
            location = format_location(book_id, book_abbr, chapter_num, verse_num)
            unique_words = len(set(toks))
            total_words = len(toks)
            book_total_words += total_words

            chunk_row = {
                "scene_id": verse_id,
                "canonical_id": canonical_id,
                "location": location,
                "play_id": book_id,
                "play_title": book_title,
                "play_abbr": book_abbr,
                "genre": testament,
                "act": chapter_num,
                "scene": verse_num,
                "heading": f"{book_title} {chapter_num}:{verse_num}",
                "total_words": total_words,
                "unique_words": unique_words,
                "num_speeches": 0,
                "num_lines": 1,
                "characters_present_count": 0,
            }
            chunks.append(chunk_row)
            all_lines.append(
                {
                    "play_id": book_id,
                    "canonical_id": canonical_id,
                    "location": location,
                    "act": chapter_num,
                    "scene": verse_num,
                    "line_num": verse_id,
                    "speaker": "",
                    "text": text,
                }
            )

            verse_unigrams = {}
            verse_bigrams = {}
            verse_trigrams = {}
            for tok in toks:
                verse_unigrams[tok] = verse_unigrams.get(tok, 0) + 1
            for idx in range(len(toks) - 1):
                bigram = f"{toks[idx]} {toks[idx + 1]}"
                verse_bigrams[bigram] = verse_bigrams.get(bigram, 0) + 1
            for idx in range(len(toks) - 2):
                trigram = f"{toks[idx]} {toks[idx + 1]} {toks[idx + 2]}"
                verse_trigrams[trigram] = verse_trigrams.get(trigram, 0) + 1

            for term, count in verse_unigrams.items():
                tokens.setdefault(term, []).append([verse_id, count])
            for term, count in verse_bigrams.items():
                tokens2.setdefault(term, []).append([verse_id, count])
            for term, count in verse_trigrams.items():
                tokens3.setdefault(term, []).append([verse_id, count])

        plays.append(
            {
                "play_id": book_id,
                "location": format_location(book_id, book_abbr),
                "title": book_title,
                "abbr": book_abbr,
                "genre": testament,
                "first_performance_year": None,
                "num_acts": len(chapter_numbers),
                "num_scenes": len(verses),
                "num_speeches": 0,
                "total_words": book_total_words,
                "total_lines": len(verses),
            }
        )

    (data_dir / "plays.json").write_text(
        json.dumps(plays, ensure_ascii=False), encoding="utf-8"
    )
    (data_dir / "chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False), encoding="utf-8"
    )
    (data_dir / "characters.json").write_text("[]", encoding="utf-8")
    (data_dir / "tokens.json").write_text(
        json.dumps(tokens, ensure_ascii=False), encoding="utf-8"
    )
    (data_dir / "tokens2.json").write_text(
        json.dumps(tokens2, ensure_ascii=False), encoding="utf-8"
    )
    (data_dir / "tokens3.json").write_text(
        json.dumps(tokens3, ensure_ascii=False), encoding="utf-8"
    )
    (data_dir / "tokens_char.json").write_text("{}", encoding="utf-8")
    (data_dir / "tokens_char2.json").write_text("{}", encoding="utf-8")
    (data_dir / "tokens_char3.json").write_text("{}", encoding="utf-8")
    (data_dir / "character_name_filter_config.json").write_text(
        json.dumps(
            {
                "global_additions": [],
                "global_removals": [],
                "play_additions": {},
                "play_removals": {},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (lines_dir / "all_lines.json").write_text(
        json.dumps(all_lines, ensure_ascii=False), encoding="utf-8"
    )

    return {
        "book_count": len(plays),
        "verse_count": len(chunks),
        "line_count": len(all_lines),
    }


if __name__ == "__main__":
    base = Path(__file__).parent
    source_path = resolve_source_path(base)
    out_dir = base / "docs"
    print(f"Building from {source_path} -> {out_dir}")
    result = build(source_path, out_dir)
    print(
        "Done: "
        f"{result['book_count']} books, "
        f"{result['verse_count']} verses, "
        f"{result['line_count']} verse rows written to {out_dir}"
    )
