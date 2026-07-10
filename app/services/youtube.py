"""Pomocné funkcie pre YouTube odkazy (tvorba kategórie z videa).

Gemini prijme YouTube URL priamo cez `file_data.file_uri`, ale nič nám
nepovie o videu vopred. Preto tu robíme dve lacné predkontroly, aby sme
neminuli Gemini kvótu na video, ktoré aj tak neprejde:

1. oEmbed — verejné video vráti 200 (+ názov), súkromné/zmazané 400/404.
2. Dĺžka — vie ju len YouTube Data API v3, ktoré potrebuje vlastný kľúč
   (`YOUTUBE_API_KEY`). Bez kľúča sa kontrola preskočí.
"""
import os
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

import httpx


OEMBED_URL = "https://www.youtube.com/oembed"
DATA_API_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

VIDEO_MAX_SECONDS = 20 * 60  # 20 min — dlhšie video žerie kvótu a hrozí timeout

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_ISO_DURATION_RE = re.compile(
    r"^P(?:\d+D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$"
)


class YouTubeError(Exception):
    """Video sa nedá použiť — správa je určená priamo používateľovi."""


def extract_video_id(url: str) -> str:
    """Vytiahne 11-znakové video ID z bežných tvarov YouTube odkazu.

    Podporené: youtube.com/watch?v=ID, youtu.be/ID, /shorts/ID, /embed/ID,
    /live/ID. Iné domény odmietneme — nechceme, aby sa dal `file_uri`
    zneužiť na ľubovoľnú adresu."""
    raw = (url or "").strip()
    if not raw:
        raise YouTubeError("Chýba odkaz na video.")

    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw

    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]

    video_id: Optional[str] = None

    if host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
    elif host in ("youtube.com", "music.youtube.com", "youtube-nocookie.com"):
        if parsed.path == "/watch":
            video_id = (parse_qs(parsed.query).get("v") or [None])[0]
        else:
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v"):
                video_id = parts[1]
    else:
        raise YouTubeError("Podporované sú len odkazy na YouTube.")

    if not video_id or not _VIDEO_ID_RE.match(video_id):
        raise YouTubeError("Neplatný odkaz na YouTube video.")

    return video_id


def canonical_watch_url(video_id: str) -> str:
    """Tvar, ktorý Gemini spoľahlivo prijme v `file_data.file_uri`."""
    return f"https://www.youtube.com/watch?v={video_id}"


def _parse_iso8601_duration(value: str) -> Optional[int]:
    """`PT8M32S` → 512 sekúnd. None, ak sa tvar nedá rozparsovať."""
    m = _ISO_DURATION_RE.match((value or "").strip())
    if not m:
        return None
    hours, minutes, seconds = (int(g) if g else 0 for g in m.groups())
    return hours * 3600 + minutes * 60 + seconds


async def fetch_video_title(video_id: str, timeout_s: int = 10) -> str:
    """Overí, že video je verejné, a vráti jeho názov.

    oEmbed vracia 400/404 pre neexistujúce, súkromné aj zmazané video —
    presne tie prípady, v ktorých by Gemini zlyhalo až po spálení kvóty."""
    params = {"url": canonical_watch_url(video_id), "format": "json"}
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(OEMBED_URL, params=params)
    except httpx.HTTPError as exc:
        raise YouTubeError("Nepodarilo sa overiť video na YouTube.") from exc

    if resp.status_code in (400, 401, 403, 404):
        raise YouTubeError(
            "Video sa nenašlo alebo nie je verejné. "
            "Gemini vie spracovať len verejné YouTube videá."
        )
    if resp.status_code != 200:
        raise YouTubeError("Nepodarilo sa overiť video na YouTube.")

    return (resp.json().get("title") or "").strip()


async def fetch_video_duration_seconds(
    video_id: str, timeout_s: int = 10
) -> Optional[int]:
    """Dĺžka videa v sekundách, alebo None ak sa nedá zistiť.

    Vyžaduje `YOUTUBE_API_KEY` (YouTube Data API v3). Bez kľúča vracia None
    a volajúci kontrolu dĺžky preskočí — radšej pustíme dlhé video ďalej,
    než by sme funkciu zablokovali kvôli nenastavenému kľúču."""
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return None

    params = {"part": "contentDetails", "id": video_id, "key": api_key}
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(DATA_API_VIDEOS_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError:
        return None

    items = data.get("items") or []
    if not items:
        raise YouTubeError("Video sa nenašlo alebo nie je verejné.")

    duration = items[0].get("contentDetails", {}).get("duration")
    return _parse_iso8601_duration(duration or "")


async def validate_youtube_url(url: str) -> tuple[str, str]:
    """Skontroluje odkaz a vráti `(video_id, title)`.

    Vyhodí `YouTubeError` so správou pre používateľa, ak video nie je
    verejné alebo je dlhšie ako `VIDEO_MAX_SECONDS`."""
    video_id = extract_video_id(url)
    title = await fetch_video_title(video_id)

    seconds = await fetch_video_duration_seconds(video_id)
    if seconds is not None and seconds > VIDEO_MAX_SECONDS:
        raise YouTubeError(
            f"Video je príliš dlhé ({seconds // 60} min). "
            f"Maximum je {VIDEO_MAX_SECONDS // 60} minút."
        )

    return video_id, title
