"""Opakovanie s rozostupmi: Leitnerove priehradky.

Každé slovo je v jednej z priehradok. Správna odpoveď ho posunie o jednu vyššie
a vráti sa neskôr, chyba ho vráti na začiatok a príde znova zajtra. Predtým malo
slovo len dva stavy a jedno „Viem" platilo navždy, takže appka nevedela povedať,
čo sa má človek dnes učiť.
"""
from datetime import datetime, timedelta
from typing import Optional

from app.utils import utcnow

# Priehradka → o koľko dní sa slovo vráti.
BOX_INTERVAL_DAYS = {1: 1, 2: 3, 3: 7, 4: 16, 5: 35}
MAX_BOX = max(BOX_INTERVAL_DAYS)
# Slovo označené „Viem" ručne (alebo v starých dátach) ide rovno sem.
KNOWN_BOX = 2


def _due_after(days: int, now: datetime) -> datetime:
    """Začiatok dňa o `days` dní. Bez zaokrúhlenia by slovo zopakované o ôsmej
    nebolo na druhý deň ráno o siedmej ešte na rade."""
    return (now + timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)


def apply_answer(
    box: Optional[int], due_at: Optional[datetime], is_correct: bool, now: Optional[datetime] = None
) -> tuple[int, datetime]:
    """Nová priehradka a termín po odpovedi.

    Správna odpoveď pred termínom (test zo sady, „Chcem ešte") slovo neposúva —
    inak by sa dalo za jeden večer dostať do poslednej priehradky. Chyba platí
    vždy: keď slovo nevieš, je jedno, kedy sa to ukázalo.
    """
    now = now or utcnow()
    box = box or 0
    if not is_correct:
        return 1, _due_after(BOX_INTERVAL_DAYS[1], now)
    if due_at is not None and due_at > now:
        return box, due_at
    new_box = min(box + 1, MAX_BOX)
    return new_box, _due_after(BOX_INTERVAL_DAYS[new_box], now)


def apply_manual_level(
    box: Optional[int], knows: bool, now: Optional[datetime] = None
) -> tuple[int, datetime]:
    """Ručná zmena úrovne na stránke sady. „Neviem" dá slovo na rad hneď."""
    now = now or utcnow()
    if not knows:
        return 1, now
    new_box = max(box or 0, KNOWN_BOX)
    return new_box, _due_after(BOX_INTERVAL_DAYS[new_box], now)
