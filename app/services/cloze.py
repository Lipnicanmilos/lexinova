"""Dopĺňanie do viet — z príkladovej vety slova spraví úlohu s medzerou.

Veta sa pri slove ukladá celá („The gate is closed."); kde v nej slovo stojí,
sa zisťuje až tu. AI má slovo použiť „pokiaľ možno v danom tvare", ale nie vždy
to urobí — sloveso časuje, podstatné meno dá do množného čísla. Preto sa okrem
presnej zhody hľadá aj tvar s rovnakým začiatkom. Čo sa nenájde ani tak
(„go" → „went"), do úlohy nejde: radšej o slovo menej než veta, v ktorej je
vynechané nesprávne miesto.
"""
import random
import re
from typing import Optional

from app.services.word_dedupe import headword_key

BLANK_OPTIONS = 4

# Kratšie heslo sa ohýbaným tvarom nehľadá — „go" by chytilo „good", „got", „gone".
_STEM_MIN_WORD_LENGTH = 4
# O koľko smie byť ohnutý tvar dlhší než heslo („travel" → „travelling").
_INFLECTION_MAX_EXTRA = 4


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


def split_sentence(sentence: str, headword: str) -> Optional[tuple[str, str, str]]:
    """Rozdelí vetu na (pred, vynechané, za). None, ak sa slovo vo vete nenašlo.

    `vynechané` je tvar presne tak, ako vo vete stojí — po odpovedi sa ukáže
    namiesto medzery, aj keď heslo je v základnom tvare.
    """
    if not sentence:
        return None
    candidates = _candidates(headword)

    def _split(match) -> Optional[tuple[str, str, str]]:
        before, after = sentence[: match.start()], sentence[match.end():]
        # Keď je heslo celá veta (sady s frázami), po vynechaní by neostal
        # žiadny kontext — to nie je dopĺňanie, len hádanie.
        if not re.search(r"\w", before + after):
            return None
        return before, match.group(0), after

    for candidate in candidates:
        match = re.search(rf"(?<!\w){re.escape(candidate)}(?!\w)", sentence, re.IGNORECASE)
        if match:
            return _split(match)

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


def pick_options(answer: str, pool: list[str], rng: Optional[random.Random] = None) -> list[str]:
    """Správne slovo a najviac tri iné zo sady, v náhodnom poradí.

    `pool` sú heslá, z ktorých sa vyberajú nesprávne možnosti. To isté heslo
    (bez ohľadu na veľkosť písmen) sa medzi možnosťami neopakuje. Keď sada iné
    slovo nemá, vráti sa prázdny zoznam — výber z jednej možnosti nie je úloha.
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
