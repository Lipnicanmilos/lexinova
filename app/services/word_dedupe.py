"""Zlučovanie rovnakých hesiel do jednej kartičky.

Prečo to vôbec treba: v jednej AI dávke prišlo `subject → téma` aj
`subject → predmet` a v databáze z toho vznikli **dve** kartičky. Kontrola
existujúceho slova sa robí dotazom, ale session má `autoflush=False`, takže
ešte neuložené slovo z tej istej dávky dotaz nevidí. Používateľ potom to isté
slovo dostal dvakrát s iným „správnym" prekladom — a keďže si pri druhom
výskyte pamätal ten prvý, označil ho ako neznáme. Odtiaľ „Success: 0 %" pri
slovách, ktoré vie.

Riešenie je jedna kartička s viacerými prijateľnými prekladmi: `téma, predmet`.
Hodnotenie je aj tak samoopravné („Viem"/„Neviem"), takže stačí ukázať obe
možnosti — nič sa neporovnáva strojovo.

Diakritika sa **nezahadzuje**: „šport" a „sport" sú v slovenčine dve rôzne
veci, zlúčiť ich by bola chyba. Rozlišuje sa len veľkosť písmen a medzery.
"""
import re

# Stĺpec `words.translation` je VARCHAR(100) — dlhší zlúčený preklad by
# databáza odmietla, takže sa varianta radšej nepridá.
TRANSLATION_MAX_LENGTH = 100

SEPARATOR = ", "


def headword_key(word: str) -> str:
    """Kľúč, podľa ktorého sa heslá považujú za to isté slovo."""
    return re.sub(r"\s+", " ", (word or "").strip()).casefold()


def translation_variants(translation: str) -> list:
    """Rozloží uložený preklad späť na jednotlivé varianty."""
    return [part.strip() for part in (translation or "").split(",") if part.strip()]


def merge_translations(existing: str, incoming: str):
    """Pridá `incoming` medzi varianty `existing`. Vráti None, ak sa nič nemení.

    Nemení sa nič, keď je varianta už prítomná (bez ohľadu na veľkosť písmen)
    alebo keď by zlúčený reťazec prekročil dĺžku stĺpca.
    """
    incoming = (incoming or "").strip()
    if not incoming:
        return None

    variants = translation_variants(existing)
    if not variants:
        return incoming if incoming != existing else None

    if any(v.casefold() == incoming.casefold() for v in variants):
        return None

    merged = SEPARATOR.join(variants + [incoming])
    if len(merged) > TRANSLATION_MAX_LENGTH:
        return None
    return merged
