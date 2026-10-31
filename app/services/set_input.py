"""Jedno pole na novú sadu: čo používateľ vložil.

Predtým bolo na každý zdroj vlastné okno a človek si musel vybrať skôr, než
začal. Teraz napíše alebo vloží, čo má, a tu sa rozhodne, čo to je:

- odkaz na YouTube → slovíčka z videa,
- riadky so slovom aj prekladom → hotová sada, bez AI a bez kvóty,
- zoznam slov bez prekladu → AI ich len preloží, nič nepridá,
- čokoľvek iné → téma, AI navrhne slovíčka.

Pozor na pomlčku: sady bývajú dialógy („When did you go? – Last September."),
kde pomlčka oddeľuje otázku od odpovede, nie slovo od prekladu.
"""
import io
import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.youtube import YouTubeError, extract_video_id

VIDEO = "video"
PAIRS = "pairs"
LIST = "list"
TOPIC = "topic"

DEFAULT_TOPIC_COUNT = 20
MIN_TOPIC_COUNT = 5
MAX_TOPIC_COUNT = 200
MAX_PREVIEW_WORDS = 200
MAX_TOPIC_LENGTH = 2000
FILE_MAX_BYTES = 5 * 1024 * 1024

# Od koľkých riadkov bez prekladu je text zoznam, nie viacriadková téma.
_LIST_MIN_LINES = 3
# Koľko riadkov musí mať preklad, aby sa text bral ako hotové dvojice. Nie všetky:
# jeden nadpis či preklep v 200 riadkoch nesmie poslať všetko na preklad cez AI.
_PAIRS_MIN_SHARE = 0.7
_INLINE_MIN_ITEMS = 3
_INLINE_MAX_WORDS = 3

_STRONG_SEPARATOR = re.compile(r"\t+|\s*=\s*|\s*;\s*")
_DASH_SEPARATOR = re.compile(r"\s+[-–—]\s+")
_COUNT_RE = re.compile(r"(?<![\d.,])(\d{1,3})(?![\d.,])")


@dataclass
class ParsedInput:
    kind: str
    pairs: list = field(default_factory=list)   # [(slovo, preklad)]
    words: list = field(default_factory=list)   # slová bez prekladu
    count: int = DEFAULT_TOPIC_COUNT            # koľko slov chce téma


def is_video_link(text: str) -> bool:
    try:
        extract_video_id(text.strip())
    except YouTubeError:
        return False
    return True


def _two_sides(parts: list) -> Optional[tuple]:
    if len(parts) != 2:
        return None
    left, right = parts[0].strip(), parts[1].strip()
    return (left, right) if left and right else None


def split_pair(line: str, multiline: bool = True) -> Optional[tuple]:
    """(slovo, preklad) z jedného riadku, alebo None.

    Tabulátor, `=` a `;` sú jednoznačné. Pomlčka a čiarka môžu byť aj súčasťou
    textu, preto platia len v zozname o viacerých riadkoch a pomlčka nie po
    konci vety: to je dialóg, nie slovo s prekladom.
    """
    match = _two_sides(_STRONG_SEPARATOR.split(line.strip(), maxsplit=1))
    if match or not multiline:
        return match

    dash = _DASH_SEPARATOR.search(line)
    if dash and line[: dash.start()].rstrip()[-1:] not in {"?", "!", "."}:
        return _two_sides([line[: dash.start()], line[dash.end():]])
    if line.count(",") == 1:
        return _two_sides(line.split(","))
    return None


def _topic_count(text: str) -> int:
    """„30 slovíčok o letisku" chce 30 slov; bez čísla platí predvolený počet."""
    for match in _COUNT_RE.finditer(text):
        number = int(match.group(1))
        if MIN_TOPIC_COUNT <= number <= MAX_TOPIC_COUNT:
            return number
    return DEFAULT_TOPIC_COUNT


def _inline_list(line: str) -> list:
    """„dog, cat, bird" v jednom riadku. Čiarku má aj bežná veta, preto aspoň
    tri položky a každá krátka."""
    items = [item.strip() for item in line.split(",") if item.strip()]
    if len(items) < _INLINE_MIN_ITEMS:
        return []
    if any(len(item.split()) > _INLINE_MAX_WORDS for item in items):
        return []
    return items


def parse_input(text: str) -> ParsedInput:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if len(lines) == 1 and is_video_link(lines[0]):
        return ParsedInput(VIDEO)

    multiline = len(lines) > 1
    pairs = [pair for pair in (split_pair(line, multiline) for line in lines) if pair]
    if lines and len(pairs) >= len(lines) * _PAIRS_MIN_SHARE:
        return ParsedInput(PAIRS, pairs=pairs[:MAX_PREVIEW_WORDS])

    if len(lines) >= _LIST_MIN_LINES:
        return ParsedInput(LIST, words=lines[:MAX_PREVIEW_WORDS])
    if len(lines) == 1:
        inline = _inline_list(lines[0])
        if inline:
            return ParsedInput(LIST, words=inline[:MAX_PREVIEW_WORDS])

    return ParsedInput(TOPIC, count=_topic_count(text or ""))


def decode_text_file(contents: bytes) -> str:
    """Excel a Poznámkový blok na Windowse ukladajú CSV a TXT v cp1250 — slovenské
    znaky by inak prišli pokazené."""
    for encoding in ("utf-8-sig", "cp1250"):
        try:
            return contents.decode(encoding)
        except UnicodeDecodeError:
            continue
    return contents.decode("utf-8", errors="replace")


def pairs_from_excel(contents: bytes) -> list:
    """Dvojice z prvých dvoch stĺpcov. Prvý riadok je hlavička, ako pri importe
    do sady. Vyvolá ValueError, keď súbor nie je čitateľný Excel."""
    import pandas as pd  # drahý import, Excel je zriedkavá cesta

    try:
        frame = pd.read_excel(io.BytesIO(contents))
    except Exception as exc:
        raise ValueError("unreadable") from exc
    if len(frame.columns) < 2:
        raise ValueError("columns")

    pairs = []
    for original, translation in zip(frame.iloc[:, 0], frame.iloc[:, 1]):
        if pd.notna(original) and pd.notna(translation):
            left, right = str(original).strip(), str(translation).strip()
            if left and right:
                pairs.append((left, right))
    return pairs[:MAX_PREVIEW_WORDS]
