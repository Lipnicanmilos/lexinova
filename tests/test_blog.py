"""Blog: index, články, 404 pre neznámy slug, sitemap."""
from app.routers.pages import BLOG_ARTICLES


def test_blog_index_loads_and_lists_articles(client):
    r = client.get("/blog")
    assert r.status_code == 200
    for article in BLOG_ARTICLES:
        assert f"/blog/{article['slug']}" in r.text
        assert article["title"] in r.text


def test_blog_article_loads_with_seo_tags(client):
    article = BLOG_ARTICLES[0]
    r = client.get(f"/blog/{article['slug']}")
    assert r.status_code == 200
    assert article["title"] in r.text
    assert f"/blog/{article['slug']}\"" in r.text  # canonical
    assert "application/ld+json" in r.text


def test_blog_unknown_slug_returns_404(client):
    assert client.get("/blog/neexistujuci-clanok").status_code == 404


def test_sitemap_contains_blog(client):
    xml = client.get("/sitemap.xml").text
    assert "/blog</loc>" in xml
    for article in BLOG_ARTICLES:
        assert f"/blog/{article['slug']}</loc>" in xml
