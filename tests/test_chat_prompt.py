"""Precvičiť v AI chate — prompt so slovíčkami sady na skopírovanie.

Celé sa to deje v prehliadači: appka prompt len poskladá a skopíruje, do AI
chatu ho vloží používateľ sám. Test preto stráži dve veci — že voľba na stránke
sady je, a že za ňou nie je žiadne volanie servera (to by znamenalo posielať
slovíčka tretej strane a patrilo by to do Ochrany súkromia).
"""
import re

from app.models.user import User


def _register_and_login(client, email):
    client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    client.post("/api/v1/login", json={"email": email, "password": "Abcdef12"})


def _set_page(client, db_factory, email):
    db = db_factory()
    try:
        user_id = db.query(User).filter(User.email == email).one().id
    finally:
        db.close()
    category_id = client.post(
        "/api/v1/categories", json={"name": "Chat", "description": "", "user_id": user_id}
    ).json()["id"]
    return client.get(f"/category/{category_id}/words").text


def test_set_page_offers_the_chat_prompt(client, db_factory):
    _register_and_login(client, "chat1@example.com")
    page = _set_page(client, db_factory, "chat1@example.com")

    assert 'id="chatPromptBtn"' in page
    assert 'onclick="copyChatPrompt()"' in page
    # Úroveň si používateľ volí sám — prompt bez nej dáva príliš ťažký rozhovor.
    levels = re.search(r'<select id="chatLevel".*?</select>', page, re.S).group(0)
    assert re.findall(r"<option[^>]*>(\w+)</option>", levels) == ["A1", "A2", "B1", "B2", "C1"]


def test_chat_prompt_is_built_in_the_browser_without_any_request(client):
    script = client.get("/static/js/page-category_words.js").text
    start = script.index("function pickChatWords")
    body = script[start:script.index("function updateBulkUI")]

    assert "navigator.clipboard.writeText" in body
    assert "fetch(" not in body, "prompt sa má len skopírovať, nie niekam posielať"
    # Prompt má obe jazykové verzie a nesie slovo aj s prekladom.
    assert "Učím sa cudzí jazyk" in body and "I am learning" in body
    assert "${w.original_word} (${w.translation})" in body
