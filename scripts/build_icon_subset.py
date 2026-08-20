"""Vyrobí podmnožinu FontAwesome — len ikony, ktoré appka naozaj používa.

Celý FontAwesome stál 271 kB (CSS 100 kB + solid 147 kB + regular 24 kB) kvôli
necelej päťdesiatke ikon. Skript prejde šablóny aj skripty, nájde použité názvy
ikon, vytiahne k nim kódy z pôvodného CSS a vygeneruje:

    app/static/css/icons.css                  — len potrebné pravidlá
    app/static/fonts/icons-solid.woff2        — podmnožina fa-solid-900
    app/static/fonts/icons-regular.woff2      — podmnožina fa-regular-400

Spustenie po pridaní novej ikony do šablóny (inak sa nevykreslí):

    python -m scripts.build_icon_subset

Potrebuje `fonttools[woff]` (dev závislosť, nie je v requirements.txt — výstup
sa commituje, takže produkcia ju nepotrebuje).
"""
import glob
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

VENDOR_CSS = 'app/static/vendor/fontawesome/css/all.min.css'
VENDOR_FONTS = 'app/static/vendor/fontawesome/webfonts'
OUT_CSS = 'app/static/css/icons.css'
OUT_FONTS = 'app/static/fonts'

# Triedy, ktoré nie sú ikony, ale modifikátory — do podmnožiny nepatria.
MODIFIERS = {'solid', 'regular', 'brands', 'spin', 'fw', 'pulse', 'beat', 'border',
             'spin-pulse', 'flip', 'rotate-90', 'rotate-180', 'rotate-270'}


def used_icon_names() -> set:
    names = set()
    files = sorted(glob.glob('app/templates/**/*.html', recursive=True)) + \
        sorted(glob.glob('app/static/js/*.js'))
    for path in files:
        text = io.open(path, encoding='utf-8').read()
        for match in re.finditer(r'\bfa-(?:solid|regular|brands)\b([^"\'>]*)', text):
            for name in re.findall(r'fa-([a-z0-9-]+)', match.group(1)):
                if name not in MODIFIERS:
                    names.add(name)
    return names


def icon_codepoints(css: str) -> dict:
    """Mapa názov ikony → kódový bod z pôvodného CSS FontAwesome."""
    table = {}
    for selectors, code in re.findall(r'([^{}]+)\{--fa:\s*"\\([0-9a-f]{2,5})"', css):
        for name in re.findall(r'\.fa-([a-z0-9-]+):{1,2}before', selectors):
            table[name] = code
    # Staršie vydania nemajú premennú --fa, len content
    for selectors, code in re.findall(r'([^{}]+)\{content:\s*"\\([0-9a-f]{2,5})"', css):
        for name in re.findall(r'\.fa-([a-z0-9-]+):{1,2}before', selectors):
            table.setdefault(name, code)
    return table


def subset_font(src: str, dst: str, codepoints: set) -> None:
    # Import až tu: `fonttools` je vývojová závislosť a testy si z tohto modulu
    # berú len `used_icon_names()` — bez nej by import celého modulu spadol.
    from fontTools import subset

    options = subset.Options()
    options.flavor = 'woff2'
    options.desubroutinize = True
    options.layout_features = []
    options.notdef_outline = True
    font = subset.load_font(src, options)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)
    subset.save_font(font, dst, options)


def main() -> int:
    css = io.open(VENDOR_CSS, encoding='utf-8').read()
    table = icon_codepoints(css)

    names = sorted(used_icon_names())
    missing = [n for n in names if n not in table]
    if missing:
        print('!! v CSS FontAwesome sa nenašli:', ', '.join(missing))
        return 1

    # Ktorá ikona patrí ktorému rezu: regular má vlastnú sadu, zvyšok je solid.
    regular_names = set()
    for path in sorted(glob.glob('app/templates/**/*.html', recursive=True)) + \
            sorted(glob.glob('app/static/js/*.js')):
        text = io.open(path, encoding='utf-8').read()
        for match in re.finditer(r'\bfa-regular\b([^"\'>]*)', text):
            for name in re.findall(r'fa-([a-z0-9-]+)', match.group(1)):
                if name not in MODIFIERS:
                    regular_names.add(name)

    solid_names = [n for n in names if n not in regular_names]
    regular_list = sorted(regular_names)

    os.makedirs(OUT_FONTS, exist_ok=True)
    subset_font(f'{VENDOR_FONTS}/fa-solid-900.ttf', f'{OUT_FONTS}/icons-solid.woff2',
                {int(table[n], 16) for n in solid_names})
    subset_font(f'{VENDOR_FONTS}/fa-regular-400.ttf', f'{OUT_FONTS}/icons-regular.woff2',
                {int(table[n], 16) for n in regular_list} or {0x20})

    rules = '\n'.join(
        f'.fa-{name}::before {{ content: "\\{table[name]}"; }}' for name in names
    )
    out = f'''/* ============================================================================
   icons.css — podmnožina FontAwesome, len ikony ktoré appka používa ({len(names)}).

   Vygenerované: python -m scripts.build_icon_subset
   NEUPRAVOVAŤ ručne. Po pridaní novej ikony do šablóny skript pusti znova,
   inak sa ikona nevykreslí (nie je vo fonte ani v tomto súbore).

   Pôvodný FontAwesome mal 271 kB (CSS + dva fonty) pre necelých päťdesiat ikon.
   ========================================================================== */

@font-face {{
  font-family: 'LexiIcons';
  font-style: normal;
  font-weight: 900;
  font-display: swap;
  src: url('/static/fonts/icons-solid.woff2') format('woff2');
}}
@font-face {{
  font-family: 'LexiIconsRegular';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url('/static/fonts/icons-regular.woff2') format('woff2');
}}

.fa-solid, .fas, .fa-regular, .far, .fa {{
  -moz-osx-font-smoothing: grayscale;
  -webkit-font-smoothing: antialiased;
  display: var(--fa-display, inline-block);
  font-style: normal;
  font-variant: normal;
  line-height: 1;
  text-rendering: auto;
}}
.fa-solid, .fas, .fa {{ font-family: 'LexiIcons'; font-weight: 900; }}
.fa-regular, .far {{ font-family: 'LexiIconsRegular'; font-weight: 400; }}

.fa-fw {{ text-align: center; width: 1.25em; }}
.fa-spin {{ animation: fa-spin 2s infinite linear; }}
@keyframes fa-spin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
@media (prefers-reduced-motion: reduce) {{ .fa-spin {{ animation: none; }} }}

{rules}
'''
    io.open(OUT_CSS, 'w', encoding='utf-8', newline='').write(out)

    solid_size = os.path.getsize(f'{OUT_FONTS}/icons-solid.woff2')
    regular_size = os.path.getsize(f'{OUT_FONTS}/icons-regular.woff2')
    css_size = os.path.getsize(OUT_CSS)
    before = (os.path.getsize(VENDOR_CSS)
              + os.path.getsize(f'{VENDOR_FONTS}/fa-solid-900.woff2')
              + os.path.getsize(f'{VENDOR_FONTS}/fa-regular-400.woff2'))
    print(f'ikon: {len(names)} (solid {len(solid_names)}, regular {len(regular_list)})')
    print(f'pôvodne: {before/1024:.1f} kB')
    print(f'teraz:   {(solid_size+regular_size+css_size)/1024:.1f} kB '
          f'(css {css_size/1024:.1f} + solid {solid_size/1024:.1f} + regular {regular_size/1024:.1f})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
