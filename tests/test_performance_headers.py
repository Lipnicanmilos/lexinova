"""Kompresia a cache statiky.

PageSpeed ukázal, že Cloud Run neposiela ani jedno: homepage chodila
nekomprimovaná (29 kB) a statika bez `Cache-Control`, takže sa pri každej
návšteve sťahovala znova.
"""


def test_html_sa_komprimuje(client):
    r = client.get("/", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip"


def test_verzovana_statika_sa_cachuje_natrvalo(client):
    """Vlastné JS/CSS majú v URL verziu, takže sa môžu cachovať navždy."""
    r = client.get("/static/css/design-system.css?v=1.0.0")
    assert r.status_code == 200
    assert "immutable" in r.headers["cache-control"]
    assert "max-age=31536000" in r.headers["cache-control"]


def test_neverzovana_statika_ma_kratsiu_cache(client):
    """Vendor a fonty verziu v URL nemajú — po týždni si ich prehliadač overí."""
    r = client.get("/static/css/design-system.css")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=604800"
