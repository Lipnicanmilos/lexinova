"""Lexi na nástenke: pokyn (hlasom alebo písaním) → jedna akcia appky.

AI (rovnaký reťazec ako tútor — Gemini, záloha Groq) z pokynu spraví JSON
s akciou a krátkou odpoveďou. Samotnú prácu robia existujúce časti appky:
návrh sady `/categories/ai-preview` a jej uloženie `/ai-save` (až keď to
používateľ potvrdí), test `/test?category=`, rozhovor `/tutor?set=`.
Server tu nič nevytvára ani nemení — len rozumie, čo používateľ chce.
"""
from typing import Any, Dict, List, Optional

from app.services import tutor_service

ACTIONS = ("create_set", "practice", "talk", "clarify")
SET_LANGUAGES = tutor_service.TUTOR_LANGUAGES
NATIVE_LANGUAGES = ("sk", "cs", "en")
COUNT_DEFAULT = 20
COUNT_MIN, COUNT_MAX = 5, 50
# Koľko sád ide do pokynov — AI podľa nich páruje „precvič ma z …" na id.
SETS_IN_PROMPT = 150
REPLY_MAX_LENGTH = 300
TOPIC_MAX_LENGTH = 300

_UI_LANGUAGE_NAMES = {"sk": "Slovak", "en": "English"}


def build_prompt(sets: List[dict], ui_lang: str) -> str:
    ui = _UI_LANGUAGE_NAMES.get(ui_lang, "Slovak")
    if sets:
        listing = "\n".join(f"- {s['id']}: {s['name']}" for s in sets[:SETS_IN_PROMPT])
    else:
        listing = "(the user has no sets yet)"
    return f"""You are "Lexi", the assistant on the dashboard of LexiNova, a vocabulary learning app.
The user tells you, in Slovak or English (often by voice, so the text is a speech transcript),
what they want to do. Map it to exactly ONE action and return ONLY a JSON object:

{{"action": "create_set" | "practice" | "talk" | "clarify",
  "reply": "...",
  "topic": "...", "count": 20, "language_from": "en", "language_to": "sk",
  "set_id": null}}

Actions:
- create_set: they want a new set (category, list, lesson) of words or phrases.
  "topic": a short description for a word-list generator with every detail they gave
  (topic, situation, level, word type), e.g. "airport and travel, A2, useful phrases".
  "count": how many words they asked for, {COUNT_MIN}-{COUNT_MAX}, default {COUNT_DEFAULT}.
  "language_from": the language they learn (en, de, fr, es, it; default en).
  "language_to": their native language (sk, cs, en; default sk).
- practice: they want to test, practise, revise or repeat one of their existing sets → "set_id".
- talk: they want to talk or have a conversation with you (the tutor), optionally about one of
  their sets → "set_id" or null.
- clarify: the instruction is unclear, is about something else than learning words, or names a
  set that matches none of theirs. Ask one short question that helps them.

"reply": what you say back, in {ui}, ONE short friendly sentence. For create_set say what you will
prepare (e.g. "Pripravím ti 20 slovíčok o letisku."); for practice and talk say where you take them.
Pick "set_id" only from this list and never invent one; match names loosely (case, typos,
"lesson 12" = "12 lesson"). The user's sets (id: name):
{listing}"""


def _clean_text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _count(value: Any) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return COUNT_DEFAULT
    return max(COUNT_MIN, min(COUNT_MAX, count))


def normalize(data: Any, sets: List[dict]) -> Dict[str, Any]:
    """Odpoveď AI → bezpečná akcia. Čokoľvek nečakané skončí ako `clarify`;
    id sady musí patriť používateľovi (AI ho mohla vymyslieť)."""
    if not isinstance(data, dict):
        return {"action": "clarify", "reply": ""}
    action = data.get("action") if data.get("action") in ACTIONS else "clarify"
    reply = _clean_text(data.get("reply"), REPLY_MAX_LENGTH)
    names = {s["id"]: s["name"] for s in sets}

    set_id: Optional[int] = None
    try:
        candidate = int(data.get("set_id")) if data.get("set_id") is not None else None
    except (TypeError, ValueError):
        candidate = None
    if candidate in names:
        set_id = candidate

    if action == "create_set":
        topic = _clean_text(data.get("topic"), TOPIC_MAX_LENGTH)
        if len(topic) < 3:
            return {"action": "clarify", "reply": reply}
        language_from = str(data.get("language_from") or "en").lower()
        language_to = str(data.get("language_to") or "sk").lower()
        return {
            "action": action, "reply": reply, "topic": topic, "count": _count(data.get("count")),
            "language_from": language_from if language_from in SET_LANGUAGES else "en",
            "language_to": language_to if language_to in NATIVE_LANGUAGES else "sk",
        }
    if action == "practice":
        if set_id is None:
            return {"action": "clarify", "reply": reply}
        return {"action": action, "reply": reply, "set": {"id": set_id, "name": names[set_id]},
                "url": f"/test?category={set_id}"}
    if action == "talk":
        return {
            "action": action, "reply": reply,
            "set": {"id": set_id, "name": names[set_id]} if set_id else None,
            "url": f"/tutor?set={set_id}" if set_id else "/tutor",
        }
    return {"action": "clarify", "reply": reply}


async def interpret(text: str, sets: List[dict], ui_lang: str = "sk") -> Dict[str, Any]:
    """Pokyn → akcia. Výnimky AI (`GeminiRateLimited`, `RuntimeError`) nechá prejsť."""
    # Pokyn ide ako prvá (a jediná) správa — dve správy používateľa za sebou
    # by niektorý provider nemusel prijať.
    raw = await tutor_service._ask(
        system=[build_prompt(sets, ui_lang)],
        history=[],
        opening_turn=text,
        json_mode=True,
        max_tokens=600,
        claude_model=("TUTOR_MODEL", tutor_service.TUTOR_MODEL_DEFAULT),
    )
    try:
        data = tutor_service._parse_json_text(raw)
    except ValueError:
        data = None
    return normalize(data, sets)
