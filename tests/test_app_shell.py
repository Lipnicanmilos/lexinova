"""Spoločný rám appky: záložky Dnes / Sady / Lexi a profil v rohu.

Každá obrazovka mala vlastnú hlavičku a jazyk, tmavý režim, notifikácie či
odhlásenie boli rozhádzané po nich. Teraz je rám jeden a všetko ostatné je
v Profile.
"""
import pytest

from app.models.user import User

SCREENS = ["/dashboard", "/sady", "/statistiky", "/profile", "/classes", "/tutor"]


def _login(client, email):
    client.post("/api/v1/register", json={"email": email, "password": "Abcdef12"})
    client.post("/api/v1/login", json={"email": email, "password": "Abcdef12"})


@pytest.mark.parametrize("path", SCREENS)
def test_every_screen_has_the_same_frame(client, path):
    _login(client, "shell@example.com")
    page = client.get(path).text

    assert 'class="app-tabs"' in page
    assert 'href="/profile" class="app-profile"' in page
    assert "css/icons.css" in page
    assert 'id="menuToggle"' not in page


@pytest.mark.parametrize("path, tab", [
    ("/dashboard", "/dashboard"), ("/sady", "/sady"), ("/tutor", "/tutor"),
])
def test_active_tab_is_marked(client, path, tab):
    _login(client, "shell2@example.com")
    page = client.get(path).text

    assert f'<a href="{tab}" class="app-tab" aria-current="page">' in page
    assert page.count('class="app-tab" aria-current="page"') == 1


@pytest.mark.parametrize("path", ["/sady", "/statistiky"])
def test_new_screens_need_login(client, path):
    client.post("/api/v1/logout")
    res = client.get(path, follow_redirects=False)
    assert res.status_code in (302, 303)
    assert res.headers["location"] == "/login"


def test_student_account_has_no_lexi_tab(client, db_factory):
    """Žiaci môžu byť deti — AI rozhovor nemajú, odkaz naň by viedol do prázdna."""
    email = "shell-student@example.com"
    _login(client, email)
    assert 'href="/tutor"' in client.get("/dashboard").text

    db = db_factory()
    try:
        db.query(User).filter(User.email == email).one().is_pseudonymous = True
        db.commit()
    finally:
        db.close()

    page = client.get("/dashboard").text
    assert 'class="app-tabs"' in page
    assert 'href="/tutor"' not in page


def test_today_screen_stays_simple(client):
    _login(client, "shell3@example.com")
    page = client.get("/dashboard").text

    assert 'id="todayBtn"' in page
    # Čísla, graf a modály tvorby sady majú vlastné obrazovky.
    assert 'id="activityChart"' not in page
    assert 'id="newSetModal"' not in page
    assert 'id="lexiForm"' not in page


def test_server_error_is_not_reported_as_offline(client):
    """Chyba servera ukazovala „Si offline", hoci internet išiel."""
    core = client.get("/static/js/app-core.js").text
    today = client.get("/static/js/page-dashboard.js").text

    assert "if (!navigator.onLine) failure = 'offline';" in core
    assert "if (failure === 'offline') {" in today
    assert "Skúsiť znova" in today


def test_full_local_storage_does_not_fail_the_load(client):
    """Záloha na offline nesmie zhodiť načítanie živých dát."""
    core = client.get("/static/js/app-core.js").text

    assert "saveLocal('wk_cached_stats'" in core
    assert "localStorage.setItem('wk_cached_stats'" not in core


def test_sets_screen_keeps_editing_and_links_to_new_set(client):
    _login(client, "shell4@example.com")
    page = client.get("/sady").text

    assert 'href="/sady/nova"' in page
    for element in ('id="editModal"', 'id="deleteModal"', 'id="shareModal"'):
        assert element in page
    for element in ('id="newSetModal"', 'id="aiCreateModal"', 'id="aiImageModal"', 'id="aiVideoModal"'):
        assert element not in page


def test_statistics_moved_to_their_own_screen(client):
    _login(client, "shell5@example.com")
    page = client.get("/statistiky").text

    for element in ('id="activityChart"', 'id="badgesGrid"', 'id="weakPanel"', 'id="masteryRing"'):
        assert element in page


def test_profile_holds_what_left_the_header(client):
    _login(client, "shell6@example.com")
    page = client.get("/profile").text

    assert 'data-lang="sk"' in page and 'data-lang="en"' in page
    assert 'onclick="toggleDarkMode()"' in page
    assert 'onclick="requestNotificationPermission()"' in page
    assert 'onclick="logout()"' in page
    assert 'href="/statistiky"' in page and 'href="/classes"' in page


@pytest.mark.parametrize("path", ["/test", "/repeat", "/hra"])
def test_learning_screens_have_no_tabs_only_a_way_back(client, path):
    _login(client, "shell7@example.com")
    page = client.get(path).text

    assert 'class="focus-bar"' in page
    assert 'class="app-tabs"' not in page


def test_test_returns_where_it_started(client):
    script = client.get("/static/js/page-flashcard_test.js").text
    assert "_q.get('from') === 'dnes'" in script
    assert "window.location.href = BACK_URL" in script


def test_new_screens_are_cached_and_hidden_from_search(client):
    sw = client.get("/sw.js").text
    assert "'/sady'" in sw and "'/statistiky'" in sw
    assert "/static/js/app-core.js" in sw

    robots = client.get("/robots.txt").text
    assert "Disallow: /sady" in robots and "Disallow: /statistiky" in robots
