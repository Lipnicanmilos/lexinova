"""Ikony sa servírujú ako podmnožina FontAwesome — musí obsahovať všetko použité.

Celý FontAwesome (271 kB) nahradila podmnožina (9 kB) generovaná skriptom
`scripts/build_icon_subset.py`. Riziko je jediné, zato tiché: niekto pridá do
šablóny novú ikonu, skript nepustí a ikona sa jednoducho nevykreslí — nič
nespadne, v konzole nič nie je. Preto tento test.
"""
import glob
import io
import re

from scripts.build_icon_subset import used_icon_names

ICONS_CSS = 'app/static/css/icons.css'


def test_every_used_icon_is_in_the_subset():
    css = io.open(ICONS_CSS, encoding='utf-8').read()
    defined = set(re.findall(r'\.fa-([a-z0-9-]+)::before', css))

    missing = sorted(used_icon_names() - defined)
    assert not missing, (
        "ikony chýbajú v podmnožine — spusti `python -m scripts.build_icon_subset`: "
        + ', '.join(missing)
    )


def test_subset_fonts_exist_and_are_small():
    """Podmnožina má zmysel len kým je malá; celý rez by tu nemal skončiť."""
    import os

    for path, limit_kb in (('app/static/fonts/icons-solid.woff2', 40),
                           ('app/static/fonts/icons-regular.woff2', 20)):
        assert os.path.exists(path), f'chýba {path}'
        size_kb = os.path.getsize(path) / 1024
        assert size_kb < limit_kb, f'{path} má {size_kb:.1f} kB — nie je to celý font?'


def test_no_template_loads_full_fontawesome():
    offenders = [
        path for path in sorted(glob.glob('app/templates/**/*.html', recursive=True))
        if 'fontawesome/css/all.min.css' in io.open(path, encoding='utf-8').read()
    ]
    assert not offenders, 'tieto šablóny ťahajú celý FontAwesome: ' + ', '.join(offenders)


def test_pages_with_icons_link_the_subset():
    """Šablóna s ikonou bez `icons.css` by ukázala prázdne miesta."""
    offenders = []
    for path in sorted(glob.glob('app/templates/**/*.html', recursive=True)):
        text = io.open(path, encoding='utf-8').read()
        if re.search(r'class="fa-(solid|regular)', text) and 'css/icons.css' not in text:
            offenders.append(path)
    assert not offenders, 'ikony bez štýlu v: ' + ', '.join(offenders)
