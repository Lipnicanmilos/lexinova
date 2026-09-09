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

# Anglické náprotivky verejných URL. Prepínač jazyka aj navigácia na /en/*
# musia viesť do anglickej vetvy — bez toho je /en slepá ulička, z ktorej
# každý odkaz vracia návštevníka aj crawlera späť do slovenského stromu.
# /slovicka tu zámerne nie je: tematické stránky slovíčok EN verziu nemajú.
EN_EQUIVALENT = {
    "/": "/en",
    "/pricing": "/en/pricing",
    "/demo": "/en/demo",
    "/pre-ucitelov": "/en/pre-ucitelov",
    "/register": "/en/register",
    "/login": "/en/login",
    "/terms": "/en/terms",
    "/privacy": "/en/privacy",
    "/refunds": "/en/refunds",
    "/blog": "/blog/en",
}

_LANG_BUTTON = re.compile(
    r'<button(?P<attrs>[^>]*\sdata-lang="(?P<lang>sk|en)"[^>]*)>(?P<label>[^<]*)</button>'
)

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


def _localize_internal_links(html: str, lang: str) -> str:
    """Na anglických stránkach prepíše interné odkazy na ich EN náprotivky.

    Prepisujeme len presné zhody z ``EN_EQUIVALENT``, takže statické súbory,
    kotvy ani externé odkazy sa pokaziť nemôžu. Musí bežať skôr než sa
    postaví prepínač jazyka — jeho slovenský odkaz má mieriť do SK vetvy.
    """
    if lang != "en":
        return html

    def swap(m: re.Match) -> str:
        target = EN_EQUIVALENT.get(m.group(1))
        return 'href="%s"' % target if target else m.group(0)

    return re.sub(r'href="([^"]*)"', swap, html)


def _crawlable_lang_switcher(html: str, lang: str, *, sk_path: str, en_path: str) -> str:
    """Prepínač jazyka prepíše z ``<button>`` na ``<a href>``.

    Tlačidlo prepínalo jazyk iba skriptom, takže na anglické verzie stránok
    neviedol z webu ani jeden odkaz, ktorý by crawler vedel prejsť — Google
    ich poznal nanajvýš zo sitemapy, čo je najslabší možný signál. Ako ``<a>``
    je to bežný odkaz a navyše funguje aj bez JavaScriptu.

    Pri tej príležitosti nastavíme aj triedu ``active``: jazyk stránky určuje
    URL, takže ju vieme na serveri a netreba na ňu čakať na skript stránky.
    """
    targets = {"sk": sk_path, "en": en_path}

    def swap(m: re.Match) -> str:
        attrs = m.group("attrs")
        btn_lang = m.group("lang")
        classes = [c for c in (_attr(attrs, "class") or "").split() if c != "active"]
        if btn_lang == lang:
            classes.append("active")
        attrs = re.sub(r'\sclass="[^"]*"', "", attrs)
        return '<a class="%s" href="%s" hreflang="%s"%s>%s</a>' % (
            " ".join(classes), targets[btn_lang], btn_lang, attrs, m.group("label")
        )

    return _LANG_BUTTON.sub(swap, html)


def localize(html: str, lang: str, *, sk_url: str, en_url: str, description: str = None) -> str:
    """Vráti HTML v danom jazyku aj s canonical a hreflang alternatívami."""
    if lang not in LANGS:
        raise ValueError("neznamy jazyk: %r" % lang)

    html = _apply_content_blocks(html, lang)
    html = _apply_data_attributes(html, lang)
    html = _localize_internal_links(html, lang)
    html = _crawlable_lang_switcher(
        html,
        lang,
        sk_path=urlsplit(sk_url).path or "/",
        en_path=urlsplit(en_url).path or "/",
    )
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
    # z window.__serverLang. Prepínač je po _crawlable_lang_switcher normálny
    # <a href>, takže preklik zvládne prehliadač sám; my si len zapamätáme voľbu
    # a v capture fáze umlčíme pôvodný handler stránky, ktorý prepínal text.
    # preventDefault dávame len tam, kde odkaz nie je — inak by sme zobrali
    # Ctrl+klik a stredné tlačidlo, teda otvorenie v novej karte.
    switcher = (
        "<script>window.__serverLang={lang};(function(){{var u={{sk:{sk},en:{en}}};"
        "document.addEventListener('click',function(e){{"
        "var b=e.target.closest&&e.target.closest('[data-lang]');"
        "if(!b||!u[b.getAttribute('data-lang')])return;"
        "e.stopImmediatePropagation();"
        "try{{localStorage.setItem('preferredLang',b.getAttribute('data-lang'));}}catch(_){{}}"
        "if(b.tagName!=='A'){{e.preventDefault();"
        "location.href=u[b.getAttribute('data-lang')];}}}},true);}})();</script>"
    ).format(
        lang=json.dumps(lang),
        # Relatívne cesty, nie absolútne: prepínač musí fungovať aj na localhose
        # a v náhľadoch, nielen na produkčnej doméne.
        sk=json.dumps(urlsplit(sk_url).path or "/"),
        en=json.dumps(urlsplit(en_url).path or "/"),
    )
    return html.replace("</head>", switcher + "</head>", 1)
