import re

BOOKS = [
    ("Genesis", ["Gen", "Gn"]), ("Exodus", ["Exod", "Ex"]), ("Leviticus", ["Lev"]), ("Numbers", ["Num"]),
    ("Deuteronomy", ["Deut", "Dt"]), ("Joshua", ["Josh"]), ("Judges", ["Judg", "Jdg"]), ("Ruth", ["Ru"]),
    ("1 Samuel", ["1 Sam", "1Sam"]), ("2 Samuel", ["2 Sam", "2Sam"]), ("1 Kings", ["1 Kgs", "1Kgs"]),
    ("2 Kings", ["2 Kgs", "2Kgs"]), ("1 Chronicles", ["1 Chr", "1 Chron"]), ("2 Chronicles", ["2 Chr", "2 Chron"]),
    ("Ezra", ["Ezr"]), ("Nehemiah", ["Neh"]), ("Esther", ["Esth", "Est"]), ("Job", ["Jb"]),
    ("Psalms", ["Psalm", "Ps", "Psa"]), ("Proverbs", ["Prov", "Pr"]), ("Ecclesiastes", ["Eccl", "Ecc"]),
    ("Song of Solomon", ["Song of Songs", "Song", "SoS"]), ("Isaiah", ["Isa"]), ("Jeremiah", ["Jer"]),
    ("Lamentations", ["Lam"]), ("Ezekiel", ["Ezek", "Eze"]), ("Daniel", ["Dan"]), ("Hosea", ["Hos"]),
    ("Joel", ["Jl"]), ("Amos", ["Am"]), ("Obadiah", ["Obad", "Ob"]), ("Jonah", ["Jon"]), ("Micah", ["Mic"]),
    ("Nahum", ["Nah"]), ("Habakkuk", ["Hab"]), ("Zephaniah", ["Zeph"]), ("Haggai", ["Hag"]),
    ("Zechariah", ["Zech"]), ("Malachi", ["Mal"]), ("Matthew", ["Matt", "Mt"]), ("Mark", ["Mk", "Mrk"]),
    ("Luke", ["Lk"]), ("John", ["Jn", "Jhn"]), ("Acts", ["Act"]), ("Romans", ["Rom"]),
    ("1 Corinthians", ["1 Cor", "1Cor"]), ("2 Corinthians", ["2 Cor", "2Cor"]), ("Galatians", ["Gal"]),
    ("Ephesians", ["Eph"]), ("Philippians", ["Phil", "Php"]), ("Colossians", ["Col"]),
    ("1 Thessalonians", ["1 Thess", "1 Th"]), ("2 Thessalonians", ["2 Thess", "2 Th"]),
    ("1 Timothy", ["1 Tim", "1Tim"]), ("2 Timothy", ["2 Tim", "2Tim"]), ("Titus", ["Tit"]),
    ("Philemon", ["Phlm", "Philem"]), ("Hebrews", ["Heb"]), ("James", ["Jas"]), ("1 Peter", ["1 Pet", "1Pet"]),
    ("2 Peter", ["2 Pet", "2Pet"]), ("1 John", ["1 Jn", "1Jn"]), ("2 John", ["2 Jn", "2Jn"]),
    ("3 John", ["3 Jn", "3Jn"]), ("Jude", ["Jud"]), ("Revelation", ["Rev", "Revelations"]),
]

# (regex, canonical, requires_chapter) sorted longest alias first so "1 John" wins over "John"
_PATTERNS = []
for name, abbrs in BOOKS:
    _PATTERNS.append((name, name, False))
    for a in abbrs:
        _PATTERNS.append((a, name, len(a) <= 4))
_PATTERNS.sort(key=lambda p: -len(p[0]))
_COMPILED = [
    (re.compile(r"(?<![A-Za-z0-9])" + re.escape(alias).replace(r"\ ", r"\s*") +
                (r"\.?\s*(\d+)" if needs_ch else r"\.?(?:\s*(\d+))?") + r"(?![A-Za-z])", re.I), canon)
    for alias, canon, needs_ch in _PATTERNS
]
_ORDINALS = [(r"\b(?:First|1st|I)\s+(?=[A-Z])", "1 "), (r"\b(?:Second|2nd|II)\s+(?=[A-Z])", "2 "),
             (r"\b(?:Third|3rd|III)\s+(?=[A-Z])", "3 ")]


def parse_refs(text: str) -> list:
    """Return list of (book, chapter|None) tuples found in free text."""
    if not text:
        return []
    for pat, rep in _ORDINALS:
        text = re.sub(pat, rep, text)
    taken, found = [], []
    for rx, canon in _COMPILED:
        for m in rx.finditer(text):
            if any(m.start() < e and m.end() > s for s, e in taken):
                continue
            taken.append((m.start(), m.end()))
            ch = int(m.group(1)) if m.group(1) else None
            found.append((m.start(), canon, ch))
    found.sort()
    return [(c, ch) for _, c, ch in found]


def books_in(*texts) -> list:
    seen = []
    for t in texts:
        for book, _ in parse_refs(t or ""):
            if book not in seen:
                seen.append(book)
    return seen


def chapter_keys(*texts) -> list:
    keys = []
    for t in texts:
        for book, ch in parse_refs(t or ""):
            if ch is not None and f"{book} {ch}" not in keys:
                keys.append(f"{book} {ch}")
    return keys
