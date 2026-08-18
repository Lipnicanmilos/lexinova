"""Jazyk verejných stránok sa vyberá na serveri, nie až v prehliadači.

Šablóny sú dvojjazyčné dvoma spôsobmi:

  1. atribúty ``data-en`` / ``data-sk`` na jednotlivých elementoch
     (index, demo, register, login) — presne to, čo v prehliadači robí
     ``partials/lang_boot.html``,
  2. dva bloky ``#content-sk`` a ``#content-en``, kde je jeden skrytý cez
     ``display:none`` (cenník, právne stránky).

Crawler nemá ``localStorage``, takže dosiaľ vždy videl len tú verziu, ktorá
bola zapečená v HTML — pri homepage anglickú, hoci primárny trh je SK. Táto
funkcia prepíše hotové HTML do požadovaného jazyka ešte pred odoslaním a
doplní ``canonical`` aj ``hreflang`` alternatívy.

Zámerne pracujeme s hotovým HTML, nie so šablónami: to isté pravidlo tak
platí pre všetkých osem verejných stránok bez toho, aby sa každý reťazec
musel prepísať na ``{{ ... }}``.
"""
import html as html_lib
import json
import re
from urllib.parse import urlsplit

LANGS = ("sk", "en")
OG_LOCALE = {"sk": "sk_SK", "en": "en_US"}

# Element s prekladom je vždy list (v prehliadači sa mu prepisuje textContent,
# takže vnorené značky by aj tak zanikli). Ak niekto vnorenú značku pridá,
# radšej element preskočíme, než by sme mu zmazali obsah.
_TRANSLATABLE = re.compile(
    r"<(?P<tag>[a-zA-Z][a-zA-Z0-9]*)(?P<attrs>[^>]*\sdata-(?:en|sk)=\"[^\"]*\"[^>]*)>"
    r"(?P<inner>[^<]*)"
    r"</(?P=tag)>"
)
_PLACEHOLDER_TAG = re.compile(r"<(?:input|textarea)\s[^>]*>", re.I)


def _attr(attrs: str, name: str):
    m = re.search(r'\s%s="([^"]*)"' % re.escape(name), attrs)
    return m.group(1) if m else None


def _apply_data_attributes(html: str, lang: str) -> str:
    """Text elementov s ``data-{lang}`` (a placeholder polí) nastaví na daný jazyk."""

    def swap(m: re.Match) -> str:
        value = _attr(m.group("attrs"), f"data-{lang}")
        if value is None:
            return m.group(0)
        return f'<{m.group("tag")}{m.group("attrs")}>{value}</{m.group("tag")}>'

    html = _TRANSLATABLE.sub(swap, html)

    def swap_placeholder(m: re.Match) -> str:
        tag = m.group(0)
        value = _attr(tag, f"data-{lang}-placeholder")
        if value is None:
            return tag
        if re.search(r'\splaceholder="[^"]*"', tag):
            return re.sub(r'\splaceholder="[^"]*"', f' placeholder="{value}"', tag, count=1)
        return tag[:-1].rstrip() + f' placeholder="{value}">'

    return _PLACEHOLDER_TAG.sub(swap_placeholder, html)


def _block_span(html: str, block_id: str):
    """Nájde rozsah <div id="content-xx"> ... </div> vrátane vnorených divov."""
    start = re.search(r'<div[^>]*\sid="%s"[^>]*>' % re.escape(block_id), html)
    if not start:
        return None
    depth = 0
    for tag in re.finditer(r"<(/?)div\b[^>]*>", html[start.start():]):
        depth += -1 if tag.group(1) else 1
        if depth == 0:
            return start.start(), start.start() + tag.end()
    return None


def _apply_content_blocks(html: str, lang: str) -> str:
    """Nechá v HTML len jazykový blok ``#content-{lang}``.

    Druhú verziu odstraňujeme, nie skrývame: skrytá kópia znamenala druhý H1 a
    celý text stránky dvakrát v DOM. Každý jazyk má teraz vlastnú URL, takže
    prepínač jazyka na ne len prekliká (skript nižšie).
    """
    other = "en" if lang == "sk" else "sk"
    span = _block_span(html, f"content-{other}")
    if span:
        html = html[: span[0]] + html[span[1]:]
    shown = re.search(r'<div[^>]*\sid="content-%s"[^>]*>' % lang, html)
    if shown:
        visible = re.sub(r'\sstyle="display:\s*none;?"', "", shown.group(0))
        html = html[: shown.start()] + visible + html[shown.end():]
    return html


def _replace_meta(html: str, pattern: str, value: str) -> str:
    """Prepíše content="..." v tagu, ktorý sedí na `pattern` (jeden výskyt)."""
    tag = re.search(pattern, html, re.I)
    if not tag:
        return html
    new_tag = re.sub(r'content="[^"]*"', 'content="%s"' % html_lib.escape(value, quote=True), tag.group(0), count=1)
    return html[: tag.start()] + new_tag + html[tag.end():]


def _document_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return m.group(1).strip() if m else ""


def localize(html: str, lang: str, *, sk_url: str, en_url: str, description: str = None) -> str:
    """Vráti HTML v danom jazyku aj s canonical a hreflang alternatívami."""
    if lang not in LANGS:
        raise ValueError("neznamy jazyk: %r" % lang)

    html = _apply_content_blocks(html, lang)
    html = _apply_data_attributes(html, lang)
    html = re.sub(r"(<html[^>]*\slang=)\"[^\"]*\"", r'\1"%s"' % lang, html, count=1)

    canonical = sk_url if lang == "sk" else en_url
    html = re.sub(
        r'(<link[^>]*\srel="canonical"[^>]*\shref=)"[^"]*"',
        lambda m: m.group(1) + '"%s"' % canonical,
        html,
        count=1,
    )

    title = _document_title(html)
    if description:
        for pattern in (
            r'<meta[^>]*\sname="description"[^>]*>',
            r'<meta[^>]*\sproperty="og:description"[^>]*>',
            r'<meta[^>]*\sname="twitter:description"[^>]*>',
        ):
            html = _replace_meta(html, pattern, description)
    if title:
        for pattern in (
            r'<meta[^>]*\sproperty="og:title"[^>]*>',
            r'<meta[^>]*\sname="twitter:title"[^>]*>',
        ):
            html = _replace_meta(html, pattern, title)
    html = _replace_meta(html, r'<meta[^>]*\sproperty="og:url"[^>]*>', canonical)
    html = _replace_meta(html, r'<meta[^>]*\sproperty="og:locale"[^>]*>', OG_LOCALE[lang])

    # hreflang: x-default mieri na slovenskú verziu — primárny trh je SK/CZ.
    alternates = (
        f'<link rel="alternate" hreflang="sk" href="{sk_url}">\n'
        f'    <link rel="alternate" hreflang="en" href="{en_url}">\n'
        f'    <link rel="alternate" hreflang="x-default" href="{sk_url}">\n'
    )
    html = re.sub(r'\s*<link[^>]*\shreflang="[^"]*"[^>]*>', "", html)
    html = html.replace("</head>", "    " + alternates + "</head>", 1)

    # Jazyk stránky určuje URL, nie localStorage — skripty stránok si ho prečítajú
    # z window.__serverLang. Prepínač EN/SK preto musí prekliknúť na druhú URL;
    # zachytávame ho v capture fáze, aby sa nespustil pôvodný handler stránky.
    switcher = (
        "<script>window.__serverLang={lang};(function(){{var u={{sk:{sk},en:{en}}};"
        "document.addEventListener('click',function(e){{"
        "var b=e.target.closest&&e.target.closest('[data-lang]');"
        "if(!b||!u[b.getAttribute('data-lang')])return;"
        "e.preventDefault();e.stopImmediatePropagation();"
        "try{{localStorage.setItem('preferredLang',b.getAttribute('data-lang'));}}catch(_){{}}"
        "location.href=u[b.getAttribute('data-lang')];}},true);}})();</script>"
    ).format(
        lang=json.dumps(lang),
        # Relatívne cesty, nie absolútne: prepínač musí fungovať aj na localhose
        # a v náhľadoch, nielen na produkčnej doméne.
        sk=json.dumps(urlsplit(sk_url).path or "/"),
        en=json.dumps(urlsplit(en_url).path or "/"),
    )
    return html.replace("</head>", switcher + "</head>", 1)
