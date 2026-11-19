"""Text článku z odkazu, ktorý používateľ vložil pri tvorbe sady.

Odkaz sťahuje server, takže si ho nesmie dať podstrčiť smerom dovnútra: na
localhost, do vnútornej siete Cloud Runu ani na metadata server (169.254.169.254).
Preto sa adresa pred každým požiadavkom preloží a kontroluje, a presmerovania
sa sledujú ručne, aby ani presmerovanie neviedlo tam, kam priamy odkaz nesmie.
"""
import asyncio
import ipaddress
import re
import socket
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin, urlsplit

import httpx

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

# Čo z článku ide do AI. Bezplatný Groq ráta prompt aj odpoveď do 8000 tokenov
# za minútu; 6000 znakov je zhruba 1500 tokenov a na 60 slov s vetami ostane dosť.
ARTICLE_MAX_CHARS = 6000
_MAX_BYTES = 3 * 1024 * 1024
_MAX_REDIRECTS = 4
_TIMEOUT_S = 12
# Odstavec kratší než toto je väčšinou menu, popis fotky alebo „Zdieľať".
_MIN_PARAGRAPH_CHARS = 40


class ArticleError(Exception):
    """Článok sa nedá použiť. Text je hláška pre používateľa."""


def find_url(text: str) -> Optional[str]:
    match = URL_RE.search(text or "")
    return match.group(0).rstrip(".,;:!?)]}") if match else None


def strip_url(text: str, url: str) -> str:
    """Pokyny okolo odkazu („aspoň 60 slovíčok, hlavne slovesá")."""
    return " ".join((text or "").replace(url, " ").split())


def _is_public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_global and not ip.is_multicast


async def _check_host(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ArticleError("Odkaz musí začínať na http:// alebo https://.")
    if parts.port not in (None, 80, 443):
        raise ArticleError("Tento odkaz sa nedá otvoriť.")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            parts.hostname, parts.port or (443 if parts.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ArticleError("Stránku z odkazu sa nepodarilo nájsť.") from exc
    if not infos or not all(_is_public_ip(info[4][0]) for info in infos):
        raise ArticleError("Tento odkaz sa nedá otvoriť.")


class _TextExtractor(HTMLParser):
    """Odstavce a nadpisy, bez skriptov, menu a pätičky."""

    _SKIP = {"script", "style", "noscript", "nav", "footer", "header", "aside", "form", "svg", "figure"}
    _BLOCKS = {"p", "h1", "h2", "h3", "li", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.blocks: list[str] = []
        self._skip_depth = 0
        self._in_title = False
        self._current: Optional[list[str]] = None

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self._BLOCKS and not self._skip_depth:
            self._flush()
            self._current = []

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self._BLOCKS:
            self._flush()

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._current is not None and not self._skip_depth:
            self._current.append(data)

    def _flush(self) -> None:
        if self._current is not None:
            block = " ".join("".join(self._current).split())
            if len(block) >= _MIN_PARAGRAPH_CHARS:
                self.blocks.append(block)
        self._current = None


def extract_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    parser._flush()
    seen, unique = set(), []
    for block in parser.blocks:
        if block not in seen:
            seen.add(block)
            unique.append(block)
    title = " ".join(parser.title.split())
    text = "\n".join(([title] if title else []) + unique)
    return text[:ARTICLE_MAX_CHARS]


async def fetch_article_text(url: str) -> str:
    """Stiahne stránku a vráti jej čitateľný text. Pri chybe ArticleError."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; LexiNovaBot/1.0; +https://lexinova.fun)",
        "Accept": "text/html,application/xhtml+xml",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT_S, follow_redirects=False, headers=headers) as client:
        for _ in range(_MAX_REDIRECTS + 1):
            await _check_host(url)
            try:
                async with client.stream("GET", url) as resp:
                    if resp.is_redirect and resp.headers.get("location"):
                        url = urljoin(url, resp.headers["location"])
                        continue
                    if resp.status_code >= 400:
                        raise ArticleError(
                            "Stránka z odkazu sa nedá otvoriť (napríklad je za prihlásením alebo platenou bránou)."
                        )
                    if "html" not in resp.headers.get("content-type", "").lower():
                        raise ArticleError("Odkaz nevedie na článok, ale na iný typ súboru.")
                    body = b""
                    async for chunk in resp.aiter_bytes():
                        body += chunk
                        if len(body) > _MAX_BYTES:
                            break
                    html = body.decode(resp.encoding or "utf-8", errors="replace")
            except httpx.HTTPError as exc:
                raise ArticleError("Stránku z odkazu sa nepodarilo stiahnuť. Skús to znova.") from exc
            text = extract_text(html)
            if len(text) < 200:
                raise ArticleError(
                    "V článku som nenašla text. Skopíruj jeho text a vlož ho sem namiesto odkazu."
                )
            return text
    raise ArticleError("Odkaz príliš veľakrát presmeroval.")
