import json
from typing import Any, Dict

import anthropic
import httpx
from pydantic import ValidationError

from app.schemas.ai_category import (
    AICategoryCreateResponse,
)


GEMINI_BASE_URL_V1BETA = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_BASE_URL_V1 = "https://generativelanguage.googleapis.com/v1"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GeminiRateLimited(RuntimeError):
    """Gemini vrátilo 429 — kvóta je vyčerpaná.

    Vlastný typ, aby volajúci vedel rozlíšiť „skús iný model" od „nemá zmysel
    skúšať ďalej"; pri 429 je ďalší request len ďalšia rana do toho istého limitu."""


def _build_prompt(prompt: str, language_from: str, language_to: str, count: int) -> str:
    # STRICT JSON request: no markdown, no commentary.
    return f"""You are a language-learning assistant.

Task:
User prompt: {prompt!r}
Create vocabulary for a learner.

Rules:
- Generate EXACTLY {count} items.
- The items must be base-form verbs (e.g., 'go', 'make', 'travel') unless language rules strongly suggest otherwise.
- language_from words must be in {language_from}.
- translations must be in {language_to}.
- Return ONLY valid JSON (no markdown, no backticks, no extra keys, no explanations).
- Output MINIFIED JSON on a single line (no pretty-printing, no extra whitespace).

JSON schema to follow:
{{
  \"category_name\": string,
  \"category_description\": string | null,
  \"words\": [
    {{
      \"original_word\": string,
      \"translation\": string,
      \"language_from\": string,
      \"language_to\": string
    }}
  ]
}}
"""


def _build_image_prompt(language_from: str, language_to: str, max_count: int) -> str:
    # Vision/OCR request: extract vocabulary visible in an image into STRICT JSON.
    return f"""You are a language-learning assistant with OCR and vision ability.

Look carefully at the attached image. It is usually a screenshot or photo that
contains vocabulary the learner wants to study (a word list, flashcards, a page
from a textbook, or a scene with labelled objects).

Task:
- Extract the vocabulary the learner should study from the image.
- If the image already shows word PAIRS (a word together with its translation),
  preserve those pairs exactly: original_word = the foreign/source word,
  translation = its translation.
- If only single words or labels are visible, treat them as {language_from} and
  translate them into {language_to}.
- Detect the language actually seen in the image. Set language_from to that
  language and language_to to {language_to}. If the source already matches
  {language_to}, translate into {language_from} instead so the pair is useful.
- Choose a short, descriptive category_name (max 50 chars) based on the image
  content, written in {language_to}.
- Extract at most {max_count} items. Ignore page numbers, headers, UI chrome,
  watermarks and any text that is not vocabulary. Skip duplicates.
- Do NOT invent words that are not present in the image.

Rules:
- Return ONLY valid JSON (no markdown, no backticks, no extra keys, no explanations).
- Output MINIFIED JSON on a single line (no pretty-printing, no extra whitespace).

JSON schema to follow:
{{
  \"category_name\": string,
  \"category_description\": string | null,
  \"words\": [
    {{
      \"original_word\": string,
      \"translation\": string,
      \"language_from\": string,
      \"language_to\": string
    }}
  ]
}}
"""


def _build_video_prompt(
    video_title: str, language_from: str, language_to: str, max_count: int
) -> str:
    # Video/audio request: pull study vocabulary out of a YouTube video.
    return f"""You are a language-learning assistant.

Watch and listen to the attached video (title: {video_title!r}).

Task:
- Pick the vocabulary a learner should study from this video: words that are
  actually spoken or shown on screen and that carry the video's meaning.
- Prefer useful, reusable words (verbs, nouns, adjectives, common phrases).
  Skip filler words, names of people, brands, and interjections.
- Detect the language actually spoken in the video. Set language_from to that
  language and language_to to {language_to}. If the spoken language already
  matches {language_to}, translate into {language_from} instead so the pair
  is useful.
- Choose a short, descriptive category_name (max 50 chars) based on the video
  content, written in {language_to}. Do not just copy the video title.
- Write category_description as one sentence in {language_to} summarising the
  video.
- Extract at most {max_count} items. Skip duplicates.
- Do NOT invent words that are not present in the video.

Rules:
- Return ONLY valid JSON (no markdown, no backticks, no extra keys, no explanations).
- Output MINIFIED JSON on a single line (no pretty-printing, no extra whitespace).

JSON schema to follow:
{{
  \"category_name\": string,
  \"category_description\": string | null,
  \"words\": [
    {{
      \"original_word\": string,
      \"translation\": string,
      \"language_from\": string,
      \"language_to\": string
    }}
  ]
}}
"""


def _salvage_truncated_json(text: str) -> Dict[str, Any]:
    """Zachráň JSON odseknutý na max_tokens: odrež po posledný kompletný
    objekt slova a douzatváraj zátvorky. Vráti aspoň časť slov namiesto 500."""
    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    s = text[start:]
    end = len(s)
    for _ in range(200):
        end = s.rfind("}", 0, end)
        if end <= 0:
            break
        candidate = s[: end + 1]
        for suffix in ("", "]}", "}", "]}}"):
            try:
                return json.loads(candidate + suffix)
            except json.JSONDecodeError:
                continue
    raise json.JSONDecodeError("Unable to salvage truncated JSON", text, 0)


def _parse_json_text(text: str) -> Dict[str, Any]:
    """Parse a model text response into JSON, tolerating stray prose/markdown
    and responses truncated at the token limit."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return _salvage_truncated_json(text)


def _normalize_model_for_rest(model: str) -> str:
    """
    Generative Language REST expects the model id without a leading `models/`.
    We defensively strip any repeated prefix like `models/models/...`.
    """
    m = (model or "").strip()
    while m.startswith("models/"):
        m = m[len("models/") :].strip()
    return m


def _candidate_gemini_models(raw_model: str) -> list[str]:
    raw_model = _normalize_model_for_rest(raw_model)

    fallbacks = [
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ]

    if not raw_model:
        return fallbacks

    candidates = [raw_model] + [m for m in fallbacks if m != raw_model]

    seen = set()
    out = []
    for m in candidates:
        nm = _normalize_model_for_rest(m)
        if nm and nm not in seen:
            seen.add(nm)
            out.append(nm)
    return out


async def _post_gemini_generate_content(
    *,
    api_key: str,
    model: str,
    full_prompt: str,
    timeout_s: int,
) -> Dict[str, Any]:
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": full_prompt}
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
        },
    }

    # Try both v1beta and v1. Some projects/accounts differ in what's enabled.
    base_urls = [GEMINI_BASE_URL_V1BETA, GEMINI_BASE_URL_V1]
    errors: list[str] = []

    # REST path must not include a leading `models/`
    model_for_rest = _normalize_model_for_rest(model)

    for base in base_urls:
        url = f"{base}/models/{model_for_rest}:generateContent?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code in (404, 429):
                    errors.append(f"{base}/models/{model}:generateContent ({resp.status_code})")
                    continue
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code if e.response is not None else 0
            errors.append(f"{base}/models/{model}:generateContent ({status})")

    raise RuntimeError(
        "Gemini generateContent failed (tried v1beta and v1) for model. "
        f"Tried errors: {errors}"
    )


async def generate_category_and_words_gemini(
    *,
    api_key: str,
    model: str,
    prompt: str,
    language_from: str,
    language_to: str,
    count: int,
    timeout_s: int = 60,
) -> Dict[str, Any]:
    full_prompt = _build_prompt(prompt, language_from, language_to, count)

    last_error: Exception | None = None
    data: Dict[str, Any] | None = None

    for candidate_model in _candidate_gemini_models(model):
        try:
            data = await _post_gemini_generate_content(
                api_key=api_key,
                model=candidate_model,
                full_prompt=full_prompt,
                timeout_s=timeout_s,
            )
            break
        except Exception as exc:
            last_error = exc
            continue
    else:
        raise RuntimeError(f"Gemini generateContent failed for all model candidates. Last error: {last_error}")

    if data is None:
        raise RuntimeError("Gemini generateContent returned no data")

    # Gemini response shape varies; try common paths.
    text = None
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        pass

    if not text:
        raise RuntimeError("Gemini returned empty content")

    return _parse_json_text(text)


async def generate_category_and_words_groq(
    *,
    api_key: str,
    model: str,
    prompt: str,
    language_from: str,
    language_to: str,
    count: int,
    timeout_s: int = 60,
) -> Dict[str, Any]:
    full_prompt = _build_prompt(prompt, language_from, language_to, count)

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": full_prompt}],
        "temperature": 0.4,
        # 200 slov v JSON-e sa do 4096 nezmestilo; 16384 zas prekračuje
        # limit Groq účtu na request (413). 8192 je overené OK.
        "max_tokens": 8192,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        resp = await client.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    text = data["choices"][0]["message"]["content"]
    if not text:
        raise RuntimeError("Groq returned empty content")

    return _parse_json_text(text)


async def generate_category_and_words_claude(
    *,
    api_key: str,
    model: str,
    prompt: str,
    language_from: str,
    language_to: str,
    count: int,
    timeout_s: int = 60,
) -> Dict[str, Any]:
    full_prompt = _build_prompt(prompt, language_from, language_to, count)

    client = anthropic.AsyncAnthropic(api_key=api_key)

    stream = await client.messages.create(
        model=model,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": full_prompt}],
        stream=True,
    )

    message = await stream.get_final_message()

    text = None
    for block in message.content:
        if block.type == "text":
            text = block.text
            break

    if not text:
        raise RuntimeError("Claude returned empty content")

    return _parse_json_text(text)


async def generate_category_and_words_from_image_claude(
    *,
    api_key: str,
    model: str,
    image_b64: str,
    media_type: str,
    language_from: str,
    language_to: str,
    max_count: int,
    timeout_s: int = 90,
) -> Dict[str, Any]:
    full_prompt = _build_image_prompt(language_from, language_to, max_count)

    client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout_s)

    stream = await client.messages.create(
        model=model,
        max_tokens=8192,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": full_prompt},
                ],
            }
        ],
        stream=True,
    )

    message = await stream.get_final_message()

    text = None
    for block in message.content:
        if block.type == "text":
            text = block.text
            break

    if not text:
        raise RuntimeError("Claude returned empty content")

    return _parse_json_text(text)


async def generate_category_and_words_from_image_groq(
    *,
    api_key: str,
    model: str,
    image_b64: str,
    media_type: str,
    language_from: str,
    language_to: str,
    max_count: int,
    timeout_s: int = 90,
) -> Dict[str, Any]:
    full_prompt = _build_image_prompt(language_from, language_to, max_count)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": full_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
                    },
                ],
            }
        ],
        # Obrázok sa počíta do vstupných tokenov — vyšší max_tokens tu spôsobil
        # 413 na Groq limite. 4096 stačí (foto má max 60 slov) a je overené.
        "temperature": 0.4,
        "max_tokens": 4096,
    }

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        resp = await client.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    text = data["choices"][0]["message"]["content"]
    if not text:
        raise RuntimeError("Groq returned empty content")

    return _parse_json_text(text)


async def generate_category_and_words_from_image_gemini(
    *,
    api_key: str,
    model: str,
    image_b64: str,
    media_type: str,
    language_from: str,
    language_to: str,
    max_count: int,
    timeout_s: int = 90,
) -> Dict[str, Any]:
    full_prompt = _build_image_prompt(language_from, language_to, max_count)

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": media_type, "data": image_b64}},
                    {"text": full_prompt},
                ],
            }
        ],
        "generationConfig": {"temperature": 0.4},
    }

    errors: list[str] = []
    data: Dict[str, Any] | None = None

    for candidate_model in _candidate_gemini_models(model):
        model_for_rest = _normalize_model_for_rest(candidate_model)
        for base in (GEMINI_BASE_URL_V1BETA, GEMINI_BASE_URL_V1):
            url = f"{base}/models/{model_for_rest}:generateContent?key={api_key}"
            try:
                async with httpx.AsyncClient(timeout=timeout_s) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code in (404, 429):
                        errors.append(f"{base}/models/{model_for_rest} ({resp.status_code})")
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    break
            except httpx.HTTPStatusError as e:
                status = e.response.status_code if e.response is not None else 0
                errors.append(f"{base}/models/{model_for_rest} ({status})")
        if data is not None:
            break

    if data is None:
        raise RuntimeError(f"Gemini vision generateContent failed. Tried: {errors}")

    text = None
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        pass

    if not text:
        raise RuntimeError("Gemini returned empty content")

    return _parse_json_text(text)


async def generate_category_and_words_from_video_gemini(
    *,
    api_key: str,
    model: str,
    video_url: str,
    video_title: str,
    language_from: str,
    language_to: str,
    max_count: int,
    timeout_s: int = 180,
) -> Dict[str, Any]:
    """Vytiahne slovíčka z verejného YouTube videa.

    Len Gemini — Groq ani Claude YouTube odkaz nestiahnu, takže tu neexistuje
    fallback na iného providera. Len v1beta: `file_data` s YouTube URL vo v1
    nefunguje. Pri 429 sa nepokúšame o ďalší model (spoločná kvóta projektu)."""
    full_prompt = _build_video_prompt(video_title, language_from, language_to, max_count)

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    # YouTube URL sa posiela bez mime_type — Google si ho určí sám.
                    {"file_data": {"file_uri": video_url}},
                    {"text": full_prompt},
                ],
            }
        ],
        "generationConfig": {"temperature": 0.4},
    }

    errors: list[str] = []
    data: Dict[str, Any] | None = None

    for candidate_model in _candidate_gemini_models(model):
        model_for_rest = _normalize_model_for_rest(candidate_model)
        url = f"{GEMINI_BASE_URL_V1BETA}/models/{model_for_rest}:generateContent?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 429:
                    raise GeminiRateLimited(
                        f"Gemini kvóta vyčerpaná (model {model_for_rest})."
                    )
                if resp.status_code == 404:
                    errors.append(f"{model_for_rest} (404)")
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
        except httpx.HTTPStatusError as e:
            status = e.response.status_code if e.response is not None else 0
            errors.append(f"{model_for_rest} ({status})")

    if data is None:
        raise RuntimeError(f"Gemini video generateContent failed. Tried: {errors}")

    text = None
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        pass

    if not text:
        raise RuntimeError("Gemini returned empty content")

    return _parse_json_text(text)


def validate_ai_category_payload(payload: Dict[str, Any]) -> AICategoryCreateResponse:
    # We map AI payload to our response model; inserted/skipped are filled by endpoint.
    # The endpoint will re-embed words; here we only validate structure.
    # Build a partial response for validation.
    words = payload.get("words", [])

    # Validate word fields exist.
    normalized_payload = {
        "category_id": 0,
        "category_name": payload.get("category_name"),
        "category_description": payload.get("category_description"),
        "inserted_words": 0,
        "skipped_words": 0,
        "words": words,
    }

    return AICategoryCreateResponse(**normalized_payload)

