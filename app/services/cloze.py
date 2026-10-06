"""Dopĺňanie do viet — zo slovíčka spraví úlohu s medzerou a výberom možností.

Úloha vzniká dvoma cestami, podľa toho, čo heslo je:

- **Slovo** („gate", „to travel"): medzera je v jeho príkladovej vete a vyberá
  sa spomedzi hesiel sady. Veta sa ukladá celá („The gate is closed."); kde
  v nej slovo stojí, sa zisťuje až tu. AI má slovo použiť „pokiaľ možno
  v danom tvare", ale nie vždy to urobí, preto sa okrem presnej zhody hľadá aj
  tvar s rovnakým začiatkom. Čo sa nenájde ani tak („go" → „went"), do úlohy
  nejde: radšej o slovo menej než veta s medzerou na nesprávnom mieste.
- **Fráza** („When did you go? – Last September."): heslo je samo vetou, takže
  sa vynechá jedno slovo priamo z neho a vyberá sa spomedzi slov ostatných
  fráz. Príkladová veta tu netreba — sady s frázami a dialógmi tak fungujú
  hneď, bez dopĺňania viet cez AI.
"""
import random
import re
from dataclasses import dataclass
from typing import Optional

from app.services.word_dedupe import headword_key

BLANK_OPTIONS = 4

# Od koľkých slov je heslo fráza („look forward to" áno, „to travel" nie).
PHRASE_MIN_WORDS = 3

# Kratšie heslo sa ohýbaným tvarom nehľadá — „go" by chytilo „good", „got", „gone".
_STEM_MIN_WORD_LENGTH = 4
# O koľko smie byť ohnutý tvar dlhší než heslo („travel" → „travelling").
_INFLECTION_MAX_EXTRA = 4
# Z frázy sa nevynechávajú krátke slová („the", „you", „si") — nič neprecvičia.
_PHRASE_GAP_MIN_LENGTH = 4

# Slovo vrátane apostrofu („I've", „don't"), bez číslic na okrajoch nezáleží.
_WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")


@dataclass
class ClozeTask:
    before: str
    hidden: str          # tvar, ktorý v texte naozaj stojí
    after: str
    answer: str          # správna možnosť (heslo, alebo vynechané slovo frázy)
    options: list
    translation: Optional[str]


def phrase_words(text: str) -> list:
    """Slová hesla tak, ako v ňom stoja."""
    return [m.group(0) for m in _WORD_RE.finditer(text or "")]


def is_phrase(headword: str) -> bool:
    return len(phrase_words(headword)) >= PHRASE_MIN_WORDS


def _gap_matches(phrase: str) -> list:
    """Slová frázy, ktoré sa oplatí vynechať: dlhšie a nie na začiatku vety.

    Začiatok vety je aj vnútri hesla („When did you go? – Last September.").
    Veľké písmeno by také slovo medzi možnosťami prezradilo, krátke slová
    („the", „you", „si") zas nič neprecvičia.
    """
    out = []
    for match in _WORD_RE.finditer(phrase or ""):
        lead = phrase[: match.start()].rstrip(" \t\"'“”‘’(")
        starts_sentence = not lead or lead[-1] in ".?!:;–—-"
        if not starts_sentence and len(match.group(0)) >= _PHRASE_GAP_MIN_LENGTH:
            out.append(match)
    return out


@dataclass
class ClozePools:
    """Z čoho sa v jednej sade berú nesprávne možnosti. Počíta sa raz na sadu,
    nie pre každé slovíčko zvlášť."""
    headwords: list      # všetky heslá sady
    plain: list          # heslá, ktoré nie sú frázy — možnosti pri slove
    gap_words: list      # slová z fráz + jednoslovné heslá — možnosti pri fráze

    @classmethod
    def from_headwords(cls, headwords: list[str]) -> "ClozePools":
        plain, gaps = [], []
        for headword in headwords:
            words = phrase_words(headword)
            if len(words) >= PHRASE_MIN_WORDS:
                # Len slová, ktoré by sa dali aj vynechať — možnosti sú potom
                # rovnakého druhu ako správna odpoveď.
                gaps.extend(m.group(0) for m in _gap_matches(headword))
            elif headword and headword.strip():
                plain.append(headword)
                gaps.append(headword.strip())
        return cls(headwords=list(headwords), plain=plain, gap_words=gaps)


def _candidates(headword: str) -> list[str]:
    """Čo sa vo vete hľadá: celé heslo, potom jeho slová od najdlhšieho.

    Heslo býva aj „to travel" alebo „the gate"; veta potom obsahuje len
    „travel". Zátvorky („go (went, gone)") sa zahadzujú celé.
    """
    cleaned = re.sub(r"\([^)]*\)", " ", headword or "")
    cleaned = " ".join(cleaned.split()).strip(" .,;:!?")
    if not cleaned:
        return []
    tokens = sorted(
        {t for t in re.findall(r"\w+", cleaned) if len(t) >= 3},
        key=lambda t: (-len(t), t),
    )
    return [cleaned] + [t for t in tokens if t != cleaned]


def split_sentence(
    sentence: str, headword: str, whole_only: bool = False
) -> Optional[tuple[str, str, str]]:
    """Rozdelí vetu na (pred, vynechané, za). None, ak sa slovo vo vete nenašlo.

    `vynechané` je tvar presne tak, ako vo vete stojí — po odpovedi sa ukáže
    namiesto medzery, aj keď heslo je v základnom tvare. S `whole_only` sa
    uzná len celé heslo v presnom znení (pre frázy: jedno jej slovo nájdené
    v inej vete by dalo medzeru na slovo a možnosti na celé frázy).
    """
    if not sentence:
        return None
    candidates = _candidates(headword)
    if whole_only:
        candidates = candidates[:1]

    def _split(match) -> Optional[tuple[str, str, str]]:
        before, after = sentence[: match.start()], sentence[match.end():]
        # Keď je heslo celá veta, po vynechaní by neostal žiadny kontext —
        # to nie je dopĺňanie, len hádanie.
        if not re.search(r"\w", before + after):
            return None
        return before, match.group(0), after

    for candidate in candidates:
        match = re.search(rf"(?<!\w){re.escape(candidate)}(?!\w)", sentence, re.IGNORECASE)
        if match:
            return _split(match)

    if whole_only:
        return None

    # Ohnutý tvar: rovnaký začiatok, o pár písmen dlhší. Posledné písmeno hesla
    # sa neporovnáva — „study" → „studies", „make" → „making".
    for candidate in candidates:
        if " " in candidate or len(candidate) < _STEM_MIN_WORD_LENGTH:
            continue
        stem = re.escape(candidate[:-1])
        for match in re.finditer(rf"(?<!\w){stem}\w*", sentence, re.IGNORECASE):
            if len(match.group(0)) <= len(candidate) + _INFLECTION_MAX_EXTRA:
                return _split(match)

    return None


def split_phrase(phrase: str, rng: Optional[random.Random] = None) -> Optional[tuple[str, str, str]]:
    """Vynechá jedno slovo priamo z frázy: (pred, vynechané, za).

    Vyberá sa náhodne spomedzi vhodných slov (viď `_gap_matches`), aby tá istá
    fráza nemala vždy medzeru na tom istom mieste. Keď fráza žiadne také
    nemá („How are you?"), vezme sa hociktoré aspoň trojpísmenové.
    """
    rng = rng or random
    matches = list(_WORD_RE.finditer(phrase or ""))
    if len(matches) < PHRASE_MIN_WORDS:
        return None
    gaps = _gap_matches(phrase)
    if not gaps:
        gaps = [m for m in matches if len(m.group(0)) >= 3]
    if not gaps:
        return None
    match = rng.choice(gaps)
    return phrase[: match.start()], match.group(0), phrase[match.end():]


def pick_options(answer: str, pool: list[str], rng: Optional[random.Random] = None) -> list[str]:
    """Správna možnosť a najviac tri iné z `pool`, v náhodnom poradí.

    To isté znenie (bez ohľadu na veľkosť písmen) sa medzi možnosťami
    neopakuje. Keď niet inej možnosti, vráti sa prázdny zoznam — výber
    z jednej nie je úloha.
    """
    rng = rng or random
    seen = {headword_key(answer)}
    others = []
    for word in pool:
        key = headword_key(word)
        if key and key not in seen:
            seen.add(key)
            others.append(word)
    if not others:
        return []
    options = rng.sample(others, min(BLANK_OPTIONS - 1, len(others))) + [answer]
    rng.shuffle(options)
    return options


def build_task(
    headword: str,
    translation: Optional[str],
    example_sentence: Optional[str],
    example_translation: Optional[str],
    pools: ClozePools,
    rng: Optional[random.Random] = None,
) -> Optional[ClozeTask]:
    """Úloha pre jedno slovíčko, alebo None, ak sa z neho spraviť nedá."""
    if is_phrase(headword):
        # Fráza použitá celá v dlhšej príkladovej vete je to isté čo slovo.
        parts = split_sentence(example_sentence, headword, whole_only=True)
        if parts:
            options = pick_options(headword, pools.headwords, rng)
            if options:
                return ClozeTask(*parts, answer=headword, options=options,
                                 translation=example_translation)
        parts = split_phrase(headword, rng)
        if not parts:
            return None
        # Slovo, ktoré vo fráze už stojí, by ako nesprávna možnosť mätlo.
        own = {headword_key(w) for w in phrase_words(headword)}
        pool = [w for w in pools.gap_words if headword_key(w) not in own]
        # Najprv možnosti s rovnakým začiatočným písmenom (veľké/malé) ako
        # odpoveď — „September" medzi samými malými slovami by bolo jasné hneď.
        same_case = [w for w in pool if w[:1].isupper() == parts[1][:1].isupper()]
        options = pick_options(parts[1], same_case, rng)
        if len(options) < BLANK_OPTIONS:
            options = pick_options(parts[1], pool, rng)
        if not options:
            return None
        return ClozeTask(*parts, answer=parts[1], options=options, translation=translation)

    parts = split_sentence(example_sentence, headword)
    if not parts:
        return None
    # Pri slove sú možnosťami iné slová; celé frázy by sa dali vylúčiť na prvý
    # pohľad, takže prídu na rad, len keď sada iné slovo nemá.
    options = pick_options(headword, pools.plain, rng) or pick_options(headword, pools.headwords, rng)
    if not options:
        return None
    return ClozeTask(*parts, answer=headword, options=options, translation=example_translation)
