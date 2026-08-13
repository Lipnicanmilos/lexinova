"""Tematické stránky slovíčok — routy, sitemap a integrita obsahu."""
import re

import pytest

from app.services.seo_topics import TOPICS, TOPICS_BY_SLUG, get_topic, related_topics

SLUGS = [t["slug"] for t in TOPICS]


def test_zoznam_tem_sa_nacita(client):
    r = client.get("/slovicka")
    assert r.status_code == 200
    for slug in SLUGS:
        assert f"/slovicka/{slug}" in r.text


@pytest.mark.parametrize("slug", SLUGS)
def test_stranka_temy_sa_nacita(client, slug):
    r = client.get(f"/slovicka/{slug}")
    assert r.status_code == 200
    topic = TOPICS_BY_SLUG[slug]
    assert topic["title"] in r.text
    # Všetky slovíčka musia byť naozaj v HTML (nie len prvých pár).
    for w in topic["words"]:
        assert w["sk"] in r.text


@pytest.mark.parametrize("slug", SLUGS)
def test_stranka_temy_ma_canonical_a_je_indexovatelna(client, slug):
    text = client.get(f"/slovicka/{slug}").text
    assert f'<link rel="canonical" href="https://lexinova.fun/slovicka/{slug}">' in text
    assert 'name="robots" content="index, follow"' in text


@pytest.mark.parametrize("slug", SLUGS)
def test_stranka_temy_ma_strukturovane_data(client, slug):
    text = client.get(f"/slovicka/{slug}").text
    assert "BreadcrumbList" in text
    assert "LearningResource" in text


def test_neznama_tema_vracia_404(client):
    assert client.get("/slovicka/tato-tema-neexistuje").status_code == 404


def test_temy_su_v_sitemape(client):
    body = client.get("/sitemap.xml").text
    assert "<loc>https://lexinova.fun/slovicka</loc>" in body
    for slug in SLUGS:
        assert f"<loc>https://lexinova.fun/slovicka/{slug}</loc>" in body


# ── integrita obsahu (chyba v dátach sa prejaví ako rozbité SEO, nie ako pád) ──

def test_slugy_su_unikatne_a_bez_diakritiky():
    assert len(SLUGS) == len(set(SLUGS))
    for slug in SLUGS:
        assert re.fullmatch(r"[a-z0-9-]+", slug), slug


def test_prilinkovane_temy_existuju():
    """Preklep v `related` by vyrobil mŕtvy interný odkaz."""
    for t in TOPICS:
        for slug in t.get("related", []):
            assert slug in TOPICS_BY_SLUG, f"{t['slug']} odkazuje na neexistujúce {slug}"


def test_tema_neodkazuje_sama_na_seba():
    for t in TOPICS:
        assert t["slug"] not in t.get("related", [])


def test_meta_description_ma_rozumnu_dlzku():
    """Nad ~160 znakov Google popis oreže."""
    for t in TOPICS:
        assert 70 <= len(t["description"]) <= 175, (t["slug"], len(t["description"]))


def test_kazda_tema_ma_dost_slov_a_priklady():
    for t in TOPICS:
        assert len(t["words"]) >= 15, t["slug"]
        for w in t["words"]:
            assert w["en"] and w["sk"] and w["example"], (t["slug"], w)


def test_slovicka_sa_v_ramci_temy_neopakuju():
    for t in TOPICS:
        en = [w["en"] for w in t["words"]]
        assert len(en) == len(set(en)), t["slug"]


def test_helpery():
    assert get_topic("v-restauracii")["slug"] == "v-restauracii"
    assert get_topic("neexistuje") is None
    rel = related_topics(TOPICS_BY_SLUG["v-restauracii"])
    assert all(isinstance(r, dict) and "slug" in r for r in rel)


def test_odkaz_na_temy_je_v_globalnej_paticke():
    """Sitewide interný odkaz — bez neho by stránky viseli mimo štruktúry webu."""
    from pathlib import Path

    footer = Path("app/static/js/site-footer.js").read_text(encoding="utf-8")
    assert 'href="/slovicka"' in footer
