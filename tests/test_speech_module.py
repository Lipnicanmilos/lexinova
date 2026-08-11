"""Zdieľané čítanie slovíčok (`static/js/speech.js`).

Regresia: reč mala tri kópie a rozchádzali sa. `repeat` mapoval jazyk na locale
a vyberal konkrétny hlas, kartičky a demo posielali holé „sk"/„en" bez hlasu —
prehliadač potom čítal slovenský text anglickým hlasom, alebo mlčal.
"""

SPEAKING_PAGES = ["/test", "/repeat", "/demo"]


def _login(client, email="test-speech@example.com"):
    res = client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    assert res.status_code == 200


def test_modul_je_dostupny(client):
    res = client.get("/static/js/speech.js")

    assert res.status_code == 200
    assert "LexiSpeech" in res.text


def test_stranky_citaju_cez_zdielany_modul(client):
    _login(client)

    for path in SPEAKING_PAGES:
        page = client.get(path).text
        assert "/static/js/speech.js" in page, path
        # vlastná reč mimo modulu = návrat driftu (holý jazyk, žiadny výber hlasu)
        assert "new SpeechSynthesisUtterance" not in page, path


def test_modul_je_v_offline_cache(client):
    """Stránky sú precachované — bez modulu v ASSETS by offline prestali čítať."""
    sw = client.get("/sw.js").text

    assert "'/static/js/speech.js'" in sw
