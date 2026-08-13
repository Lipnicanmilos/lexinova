"""Blog: index, články, 404 pre neznámy slug, sitemap."""
import pytest

from app.routers.pages import BLOG_ARTICLES

SLUGS = [a["slug"] for a in BLOG_ARTICLES]
SLUGS_EN = [a["slug"] for a in BLOG_ARTICLES if a.get("title_en")]


def test_blog_index_loads_and_lists_articles(client):
    r = client.get("/blog")
    assert r.status_code == 200
    for article in BLOG_ARTICLES:
        assert f"/blog/{article['slug']}" in r.text
        assert article["title"] in r.text


@pytest.mark.parametrize("slug", SLUGS)
def test_blog_article_loads_with_seo_tags(client, slug):
    article = next(a for a in BLOG_ARTICLES if a["slug"] == slug)
    r = client.get(f"/blog/{slug}")
    assert r.status_code == 200
    assert article["title"] in r.text
    assert f"/blog/{slug}\"" in r.text  # canonical
    assert "application/ld+json" in r.text


@pytest.mark.parametrize("slug", SLUGS_EN)
def test_blog_article_en_loads(client, slug):
    """Dvojjazyčný článok musí mať funkčnú EN verziu s vlastným canonicalom."""
    article = next(a for a in BLOG_ARTICLES if a["slug"] == slug)
    r = client.get(f"/blog/en/{slug}")
    assert r.status_code == 200
    assert article["title_en"] in r.text
    assert f"/blog/en/{slug}\"" in r.text


@pytest.mark.parametrize("slug", SLUGS)
def test_sablona_clanku_existuje(client, slug):
    """Chýbajúca šablóna by sa inak prejavila až 500-kou na produkcii."""
    from pathlib import Path

    article = next(a for a in BLOG_ARTICLES if a["slug"] == slug)
    assert Path("app/templates").joinpath(article["template"]).is_file()


def test_blog_unknown_slug_returns_404(client):
    assert client.get("/blog/neexistujuci-clanok").status_code == 404


def test_sitemap_contains_blog(client):
    xml = client.get("/sitemap.xml").text
    assert "/blog</loc>" in xml
    for article in BLOG_ARTICLES:
        assert f"/blog/{article['slug']}</loc>" in xml
