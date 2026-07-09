# -*- coding: utf-8 -*-
"""
E2E test celého užívateľského toku na https://lexinova.fun.

Otvorí viditeľný Chromium prehliadač a preklikaním overí:

  1. Otvorí lexinova.fun
  2. /register — vytvorí účet (leftover účet z minulého behu najprv zmaže)
  3. Odhlási sa
  4. Prihlásenie so zlým heslom — musí zlyhať
  5. Prihlási sa správnym heslom
  6. Perzistencia session — po reload-e zostáva prihlásený
  7. Prepínač jazyka EN/SK preloží texty
  8. Vytvorí kategóriu „E2E Testovacia" a pridá 3 slovíčka ručne
  9. Importuje 3 slovíčka z TXT a 3 z Excelu (.xlsx)
 10. Duplicitný re-import XLSX — počet slov sa nesmie zmeniť
 11. Import poškodeného .xlsx — musí zobraziť chybovú hlášku
 12. Spustí flashcard test (Všetky slovíčka) a odpovie na všetkých 9 kariet
 13. Prejde režim opakovania (flip + ďalšie slovo až po koniec)
 14. Upraví slovíčko (dog → doggo) a zmaže ho
 15. Free limit slov: import sa zastaví na 30, 31. slovo server odmietne
 16. AI: vygeneruje kategóriu z textového promptu
 17. AI: vygeneruje kategóriu z fotky (vision OCR nad vyrenderovaným PNG)
 18. Free limity: 4. AI generovanie → 429, 6. kategória → 400
 19. Zmaže jednu kategóriu cez kôš (UI)
 20. Premenuje kategóriu cez ceruzku (UI)
 21. Zmení heslo na /profile a overí re-loginom (staré už neplatí)
 22. /profile → Zmazať účet → potvrdí (upratanie po sebe)
 23. Overí, že prihlásenie zmazaným účtom už neprejde

POZOR na poradie: kroky 12–15 musia bežať PRED AI krokmi — Free účet má na
serveri odomknutú len najnovšiu kategóriu (staršie presmerujú na dashboard,
pozri _check_category_access v app/routers/pages.py).

Rýchly variant (--quick): len účtový tok (kroky 1–5 + zmazanie + kontrola).

Po každom behu (aj spadnutom) sa vypíše konzolový súhrn krokov s trvaniami
a zapíše sa samostatný HTML report do koreňa repa: e2e_report.html
(pri zlyhaní obsahuje aj chybu a screenshot).

Ak testovací účet z minulého (spadnutého) behu ešte existuje, skript sa
ním najprv prihlási, zmaže ho a registráciu zopakuje.

Spustenie (jednorazová príprava):
    venv\\Scripts\\python.exe -m pip install playwright
    venv\\Scripts\\python.exe -m playwright install chromium
Potom:
    venv\\Scripts\\python.exe scripts\\e2e_smoke.py          # celý flow
    venv\\Scripts\\python.exe scripts\\e2e_smoke.py --quick  # len účtový tok
"""

import argparse
import base64
import html
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

# Windows konzola býva cp1252 — bez tohto padajú printy s diakritikou.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

BASE_URL = "https://lexinova.fun"
EMAIL = "Admin1@admin.com"
PASSWORD = "Admin1111"
PASSWORD2 = "Admin2222"  # heslo po zmene na /profile (krok 21)
PAUSE_S = 4
STEP_TIMEOUT_MS = 20_000

CATEGORY_NAME = "E2E Testovacia"
MANUAL_WORDS = [("dog", "pes"), ("cat", "mačka"), ("house", "dom")]
TXT_WORDS = [("bird", "vták"), ("tree", "strom"), ("water", "voda")]
XLSX_WORDS = [("sun", "slnko"), ("moon", "mesiac"), ("star", "hviezda")]
TOTAL_WORDS = len(MANUAL_WORDS) + len(TXT_WORDS) + len(XLSX_WORDS)

# Free limity — musia sedieť s app/services/limits.py
WORD_LIMIT_FREE = 30
CATEGORY_LIMIT_FREE = 5
AI_DAILY_LIMIT_FREE = 3

# AI generovanie (kroky 16–18). AI je nedeterministické, takže neoverujeme
# konkrétne slová — len že vznikla nová kategória. Témy promptov (ovocie /
# počasie na fotke / zvieratá) sú zámerne RÔZNE: server zlučuje kategórie
# s rovnakým názvom, čo by pokazilo kontrolu „pribudla nová kategória".
AI_TEXT_PROMPT = (
    "zakladne anglicke slovicka na temu ovocie pre zaciatocnika; "
    "kategoriu pomenuj presne 'E2E AI Ovocie'"
)
AI_TEXT_WORD_COUNT = 8
# Slovíčka vykreslené do PNG pre „AI z fotky" — vision prečíta hotové páry.
IMAGE_WORDS = [
    ("rain", "dážď"), ("snow", "sneh"), ("wind", "vietor"),
    ("cloud", "oblak"), ("storm", "búrka"),
]
AI_TIMEOUT_MS = 120_000  # AI beží dlho (LLM + prípadné fallbacky providerov)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def pause(seconds: float = PAUSE_S) -> None:
    log(f"… čakám {seconds} s")
    time.sleep(seconds)


def login(page, password: str = PASSWORD) -> None:
    """Prihlási sa a počká na presmerovanie na dashboard."""
    page.goto(f"{BASE_URL}/login")
    page.fill("#email", EMAIL)
    page.fill("#password", password)
    page.click("#loginForm button[type=submit]")
    page.wait_for_url("**/dashboard", timeout=STEP_TIMEOUT_MS)


def login_expect_fail(page, password: str, why: str) -> None:
    """Skúsi login a očakáva, že NEPREJDE (zostane na /login)."""
    page.goto(f"{BASE_URL}/login")
    page.fill("#email", EMAIL)
    page.fill("#password", password)
    page.click("#loginForm button[type=submit]")
    try:
        page.wait_for_url("**/dashboard", timeout=6_000)
        raise RuntimeError(f"Prihlásenie prešlo, hoci nemalo ({why})!")
    except PWTimeout:
        pass  # presne toto čakáme


def _login_leftover(page) -> None:
    """Prihlási leftover účet z minulého (spadnutého) behu — heslo mohlo
    zostať pôvodné aj už zmenené (krok 21), skúsi obe."""
    for pw in (PASSWORD, PASSWORD2):
        page.goto(f"{BASE_URL}/login")
        page.fill("#email", EMAIL)
        page.fill("#password", pw)
        page.click("#loginForm button[type=submit]")
        try:
            page.wait_for_url("**/dashboard", timeout=STEP_TIMEOUT_MS)
            return
        except PWTimeout:
            continue
    raise RuntimeError("Leftover účet sa nedá prihlásiť ani jedným heslom.")


def logout(page) -> None:
    """Klikne na odhlásenie (dashboard aj profil majú rovnaké tlačidlo)."""
    page.locator('[onclick="logout()"]').first.click()
    page.wait_for_url("**/login", timeout=STEP_TIMEOUT_MS)


def delete_account(page) -> None:
    """Na /profile otvorí Nebezpečnú zónu, zmaže účet a potvrdí."""
    page.goto(f"{BASE_URL}/profile")
    page.click('[onclick="openDeleteModal()"]')
    page.click('#deleteModal [onclick="confirmDeleteAccount()"]')
    page.wait_for_url("**/login", timeout=STEP_TIMEOUT_MS)


def register(page) -> bool:
    """Vyplní registráciu; True = účet vytvorený (redirect na dashboard)."""
    page.goto(f"{BASE_URL}/register")
    page.fill("#email", EMAIL)
    page.fill("#password", PASSWORD)
    page.fill("#confirmPassword", PASSWORD)
    page.click("#submitBtn")
    try:
        page.wait_for_url("**/dashboard", timeout=STEP_TIMEOUT_MS)
        return True
    except PWTimeout:
        return False


def create_category(page) -> int:
    """Na dashboarde vytvorí kategóriu, otvorí ju a vráti jej ID z URL."""
    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_load_state("networkidle")
    page.click('[onclick="openCreateModal()"]')
    page.fill("#createName", CATEGORY_NAME)
    page.fill("#createDescription", "Automatický E2E test — po behu sa zmaže.")
    page.click("#createCategoryForm button[type=submit]")
    # Nová karta sa objaví po reloade zoznamu — klik na názov otvorí slovíčka.
    card = page.locator(".category-name", has_text=CATEGORY_NAME)
    card.wait_for(state="visible", timeout=STEP_TIMEOUT_MS)
    pause(1)
    card.click()
    page.wait_for_url(re.compile(r"/category/\d+/words"), timeout=STEP_TIMEOUT_MS)
    return int(re.search(r"/category/(\d+)/words", page.url).group(1))


def add_words(page) -> None:
    """Pridá slovíčka cez formulár na stránke kategórie."""
    for original, translation in MANUAL_WORDS:
        page.fill('#addWordForm input[name="original_word"]', original)
        page.fill('#addWordForm input[name="translation"]', translation)
        page.click('#addWordForm button[type=submit]')
        # Slovo pribudne do zoznamu — počkáme, kým sa objaví.
        page.locator("#wordsList", has_text=original).wait_for(timeout=STEP_TIMEOUT_MS)
        log(f"   + {original} → {translation}")
        time.sleep(0.6)


def _make_txt(directory: Path) -> Path:
    """TXT vo formáte „originál, preklad" na riadok (parsuje ho prehliadač)."""
    path = directory / "e2e_import.txt"
    path.write_text(
        "\n".join(f"{o}, {t}" for o, t in TXT_WORDS), encoding="utf-8"
    )
    return path


def _make_xlsx(directory: Path) -> Path:
    """XLSX s hlavičkou + 2 stĺpcami (spracúva ho server cez pandas)."""
    from openpyxl import Workbook

    path = directory / "e2e_import.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["original", "translation"])  # 1. riadok berie pandas ako hlavičku
    for original, translation in XLSX_WORDS:
        ws.append([original, translation])
    wb.save(path)
    return path


def import_file(page, path: Path, expected: list) -> None:
    """Nahrá súbor cez import formulár a počká na naimportované slová."""
    page.set_input_files("#excelFile", str(path))
    page.click('#importForm button[type=submit]')
    for original, _ in expected:
        page.locator("#wordsList", has_text=original).wait_for(timeout=STEP_TIMEOUT_MS)
    log(f"   import {path.name}: {', '.join(o for o, _ in expected)} ✓")
    time.sleep(0.8)


def run_flashcard_test(page, category_id: int) -> None:
    """Spustí test Všetky slovíčka a odpovie na všetky karty."""
    # Po AI krokoch sme na dashboarde — otvor najprv stránku kategórie.
    page.goto(f"{BASE_URL}/category/{category_id}/words")
    page.wait_for_load_state("networkidle")
    page.click(f'a[href="/test?category={category_id}"]')
    page.wait_for_url("**/test?category=*", timeout=STEP_TIMEOUT_MS)
    page.wait_for_load_state("networkidle")
    for i in range(TOTAL_WORDS):
        know = i % 2 == 0  # striedavo viem / neviem
        page.click("#flashcard")                       # otoč kartu
        btn = "#btnKnow" if know else "#btnDont"
        page.wait_for_selector(f"{btn}.visible", timeout=STEP_TIMEOUT_MS)
        page.click(btn)
        log(f"   karta {i + 1}/{TOTAL_WORDS}: {'✅ viem' if know else '😕 neviem'}")
        time.sleep(0.8)
    page.wait_for_selector("#resultsScreen", state="visible", timeout=STEP_TIMEOUT_MS)
    log("   výsledková obrazovka zobrazená (odpovede uložené)")


def run_repeat(page, category_id: int) -> None:
    """Prejde režim opakovania: flip + ďalšie slovo až po posledné."""
    page.goto(f"{BASE_URL}/category/{category_id}/words")
    page.click(f'a[href="/repeat?category={category_id}"]')
    page.wait_for_url("**/repeat?category=*", timeout=STEP_TIMEOUT_MS)
    page.wait_for_load_state("networkidle")
    for i in range(TOTAL_WORDS):
        page.click("#flashcard")                       # ukáž preklad
        time.sleep(0.5)
        if i < TOTAL_WORDS - 1:
            page.click("#nextBtn")
            time.sleep(0.4)
    log("   opakovanie prešlo všetky slovíčka")


def _category_count(page) -> int:
    """Počet kariet kategórií vykreslených na dashboarde."""
    return page.locator(".category-name").count()


def _wait_ai_category_created(page, modal_id: str, before: int) -> None:
    """Počká, kým sa AI modál zavrie (úspech) a v zozname pribudne kategória.

    Ak AI zlyhá, modál zostane otvorený s chybou → wait_for_selector spadne na
    timeout a smoke test to nahlási ako FAIL (presne to chceme)."""
    page.wait_for_selector(f"#{modal_id}", state="hidden", timeout=AI_TIMEOUT_MS)
    page.wait_for_function(
        "n => document.querySelectorAll('.category-name').length > n",
        arg=before,
        timeout=STEP_TIMEOUT_MS,
    )


def run_ai_create_from_text(page) -> None:
    """Na dashboarde vygeneruje kategóriu z textového promptu (AI)."""
    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_load_state("networkidle")
    before = _category_count(page)
    page.click('[onclick="openAICreateModal()"]')
    page.fill("#aiCategoryPrompt", AI_TEXT_PROMPT)
    page.fill("#aiLanguageFrom", "en")
    page.fill("#aiLanguageTo", "sk")
    page.fill("#aiWordCount", str(AI_TEXT_WORD_COUNT))
    page.click('[onclick="aiCreateCategoryFromDashboard()"]')
    log("   AI generuje z textu — čakám na výsledok (môže trvať ~1 min)")
    _wait_ai_category_created(page, "aiCreateModal", before)
    log(f"   ✓ AI kategória z textu vytvorená (kategórií: {before} → {before + 1})")


def _make_vocab_image(context, directory: Path) -> Path:
    """Vyrenderuje slovíčka do PNG cez prehliadač (bez extra závislostí),
    aby ich AI vision vedel prečítať ako hotové páry."""
    path = directory / "e2e_vocab.png"
    rows = "".join(
        f"<tr><td style='padding:6px 60px 6px 0'>{o}</td><td>{t}</td></tr>"
        for o, t in IMAGE_WORDS
    )
    html = (
        "<!doctype html><meta charset='utf-8'>"
        "<body style='margin:0;padding:48px;background:#fff;"
        "font-family:Arial,Helvetica,sans-serif;color:#111'>"
        "<h1 style='font-size:44px;margin:0 0 24px'>Weather / Počasie</h1>"
        f"<table style='font-size:40px;border-collapse:collapse'>{rows}</table>"
        "</body>"
    )
    shot_page = context.new_page()
    shot_page.set_content(html, wait_until="load")
    shot_page.screenshot(path=str(path), full_page=True)
    shot_page.close()
    return path


def run_ai_create_from_image(page, context) -> None:
    """Na dashboarde vygeneruje kategóriu z fotky so slovíčkami (AI vision)."""
    with tempfile.TemporaryDirectory() as tmp:
        image_path = _make_vocab_image(context, Path(tmp))
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_load_state("networkidle")
        before = _category_count(page)
        page.click('[onclick="openAIImageModal()"]')
        page.set_input_files("#aiImageFile", str(image_path))
        page.fill("#aiImageLanguageFrom", "en")
        page.fill("#aiImageLanguageTo", "sk")
        page.click('[onclick="aiCreateCategoryFromImage()"]')
        log("   AI číta fotku — čakám na výsledok (môže trvať ~1 min)")
        _wait_ai_category_created(page, "aiImageModal", before)
    log(f"   ✓ AI kategória z fotky vytvorená (kategórií: {before} → {before + 1})")


def api_json(page, method: str, url: str, payload: dict | None = None):
    """Zavolá API v kontexte prihlásenej stránky (session cookie ide sama).
    Vráti (status, body). Používame na negatívne testy limitov, kde UI
    nemá spoľahlivo overiteľnú odozvu."""
    result = page.evaluate(
        """async ({ method, url, payload }) => {
            const opts = { method, headers: { 'Content-Type': 'application/json' } };
            if (payload !== null) opts.body = JSON.stringify(payload);
            const res = await fetch(url, opts);
            let body = null;
            try { body = await res.json(); } catch (e) {}
            return { status: res.status, body };
        }""",
        {"method": method, "url": url, "payload": payload},
    )
    return result["status"], result["body"] or {}


def _word_total(page, category_id: int) -> int:
    """Aktuálny počet slov v kategórii (cez API — spoľahlivejšie než DOM)."""
    status, body = api_json(page, "GET", f"/api/v1/words?category_id={category_id}&limit=1")
    if status != 200:
        raise RuntimeError(f"GET /words zlyhal ({status})")
    return int(body.get("total") or 0)


def _hide_message(page) -> None:
    """Skryje toast #message, aby čakanie nechytilo hlášku z minulej akcie
    (showMessage ju necháva 5 s)."""
    page.evaluate("() => { const m = document.getElementById('message'); if (m) m.style.display = 'none'; }")


def check_session_persistence(page) -> None:
    """Reload dashboardu nesmie používateľa odhlásiť."""
    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_load_state("networkidle")
    page.reload()
    page.wait_for_load_state("networkidle")
    time.sleep(2)  # priestor na prípadný JS redirect na /login
    if "/dashboard" not in page.url:
        raise RuntimeError(f"Po reload-e ma odhlásilo (som na {page.url})")
    log("   ✓ session prežila reload")


def check_language_toggle(page) -> None:
    """Prepne jazyk na EN, overí preklad tlačidla, prepne späť na SK."""
    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_load_state("networkidle")
    ai_span = '[onclick="openAICreateModal()"] span'
    page.locator('.lang-btn[data-lang="en"]:visible').first.click()
    page.wait_for_function(
        f"() => document.querySelector('{ai_span}').textContent.trim() === 'AI Create'",
        timeout=STEP_TIMEOUT_MS,
    )
    log("   ✓ EN preklad aktívny (AI Create)")
    page.locator('.lang-btn[data-lang="sk"]:visible').first.click()
    page.wait_for_function(
        f"() => document.querySelector('{ai_span}').textContent.trim() === 'AI vytvoriť'",
        timeout=STEP_TIMEOUT_MS,
    )
    log("   ✓ SK preklad späť (AI vytvoriť)")


def reimport_duplicates(page, category_id: int) -> None:
    """Re-import toho istého XLSX nesmie zmeniť počet slov (server duplicitné
    slová aktualizuje, nie pridáva)."""
    page.goto(f"{BASE_URL}/category/{category_id}/words")
    page.wait_for_load_state("networkidle")
    before = _word_total(page, category_id)
    with tempfile.TemporaryDirectory() as tmp:
        _hide_message(page)
        page.set_input_files("#excelFile", str(_make_xlsx(Path(tmp))))
        page.click('#importForm button[type=submit]')
        page.wait_for_selector("#message.success", state="visible", timeout=STEP_TIMEOUT_MS)
    after = _word_total(page, category_id)
    if after != before:
        raise RuntimeError(f"Duplicitný import zmenil počet slov: {before} → {after}")
    log(f"   ✓ duplicitný import nič nepridal (slov: {after})")


def import_corrupt_file(page) -> None:
    """Poškodený .xlsx musí server odmietnuť a UI ukázať chybovú hlášku."""
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "e2e_pokazeny.xlsx"
        bad.write_bytes(b"toto rozhodne nie je platny excel \x00\x01\x02\xff")
        _hide_message(page)
        page.set_input_files("#excelFile", str(bad))
        page.click('#importForm button[type=submit]')
        page.wait_for_selector("#message.error", state="visible", timeout=STEP_TIMEOUT_MS)
    log("   ✓ poškodený súbor odmietnutý s chybovou hláškou")


def edit_and_delete_word(page, category_id: int) -> None:
    """Upraví slovíčko dog → doggo (ceruzka) a potom ho zmaže (kôš)."""
    page.goto(f"{BASE_URL}/category/{category_id}/words")
    page.wait_for_load_state("networkidle")
    row = page.locator("li.word-item", has_text="dog").first
    row.locator('button[title="Edit"]').click()
    page.fill("#editOriginal", "doggo")
    page.click('#editWordForm button[type=submit]')
    page.locator("li.word-item", has_text="doggo").first.wait_for(
        state="visible", timeout=STEP_TIMEOUT_MS
    )
    log("   ✓ slovíčko upravené (dog → doggo)")

    _hide_message(page)
    page.locator("li.word-item", has_text="doggo").first.locator(
        'button[title="Delete"]'
    ).click()
    page.click("#confirmationModal .modal-btn.confirm")
    page.wait_for_function(
        "() => !document.querySelector('#wordsList').textContent.includes('doggo')",
        timeout=STEP_TIMEOUT_MS,
    )
    total = _word_total(page, category_id)
    if total != TOTAL_WORDS - 1:
        raise RuntimeError(f"Po zmazaní čakám {TOTAL_WORDS - 1} slov, je {total}")
    log(f"   ✓ slovíčko zmazané (slov v kategórii: {total})")


def _make_limit_xlsx(directory: Path) -> Path:
    """XLSX s 25 novými slovami — pretečie limit 30 slov/kategóriu."""
    from openpyxl import Workbook

    path = directory / "e2e_limit.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["original", "translation"])
    for i in range(1, 26):
        ws.append([f"limitword{i:02d}", f"limitpreklad{i:02d}"])
    wb.save(path)
    return path


def check_word_limit(page, category_id: int) -> None:
    """Free limit slov: import sa zastaví presne na 30, 31. slovo → chyba.
    Musí bežať PRED AI krokmi (kategória potom už nie je najnovšia = zamknutá)."""
    page.goto(f"{BASE_URL}/category/{category_id}/words")
    page.wait_for_load_state("networkidle")
    with tempfile.TemporaryDirectory() as tmp:
        _hide_message(page)
        page.set_input_files("#excelFile", str(_make_limit_xlsx(Path(tmp))))
        page.click('#importForm button[type=submit]')
        page.wait_for_selector("#message", state="visible", timeout=STEP_TIMEOUT_MS)
    total = _word_total(page, category_id)
    if total != WORD_LIMIT_FREE:
        raise RuntimeError(f"Limit slov: čakám presne {WORD_LIMIT_FREE}, je {total}")
    log(f"   ✓ import zastavený na limite {WORD_LIMIT_FREE} slov")

    _hide_message(page)
    page.fill('#addWordForm input[name="original_word"]', "overflow")
    page.fill('#addWordForm input[name="translation"]', "pretečenie")
    page.click('#addWordForm button[type=submit]')
    page.wait_for_selector("#message.error", state="visible", timeout=STEP_TIMEOUT_MS)
    if _word_total(page, category_id) != WORD_LIMIT_FREE:
        raise RuntimeError("31. slovo sa napriek limitu uložilo!")
    log("   ✓ 31. slovo server odmietol s chybovou hláškou")


def check_ai_and_category_limits(page) -> str:
    """Free limity cez API: 3. AI generovanie prejde (dočerpá kvótu),
    4. vráti 429; 5. kategória prejde, 6. vráti 400. Vráti názov kategórie
    z 3. AI generovania — ďalší krok ju zmaže cez UI kôš."""
    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_load_state("networkidle")

    log("   3. AI generovanie (dočerpanie dennej kvóty) — chvíľu potrvá…")
    payload = {
        "prompt": ("5 anglickych slovicok na temu zvierata; "
                   "kategoriu pomenuj presne 'E2E AI Zvierata'"),
        "language_from": "en",
        "language_to": "sk",
        "count": 5,
    }
    status, body = api_json(page, "POST", "/api/v1/categories/ai-create", payload)
    if status != 200:
        raise RuntimeError(f"3. AI generovanie malo prejsť, vrátilo {status}: {body}")
    extra_cat_name = body.get("category_name") or "E2E AI Zvierata"
    log(f"   ✓ 3. AI generovanie prešlo (kategória „{extra_cat_name}“)")

    status, body = api_json(page, "POST", "/api/v1/categories/ai-create", payload)
    if status != 429:
        raise RuntimeError(f"4. AI generovanie malo vrátiť 429, vrátilo {status}: {body}")
    log(f"   ✓ 4. AI generovanie odmietnuté (429 — denný limit {AI_DAILY_LIMIT_FREE})")

    status, body = api_json(page, "POST", "/api/v1/categories",
                            {"name": "E2E Limitná", "description": "test limitu"})
    if status != 200:
        raise RuntimeError(f"5. kategória mala prejsť, vrátilo {status}: {body}")
    fifth_id = body.get("id")
    status, body = api_json(page, "POST", "/api/v1/categories",
                            {"name": "E2E Šiesta", "description": "nemá vzniknúť"})
    if status != 400:
        raise RuntimeError(f"6. kategória mala vrátiť 400, vrátilo {status}: {body}")
    log(f"   ✓ 6. kategória odmietnutá (400 — limit {CATEGORY_LIMIT_FREE})")

    status, _ = api_json(page, "DELETE", f"/api/v1/categories/{fifth_id}")
    if status != 200:
        raise RuntimeError(f"Upratanie pomocnej kategórie zlyhalo ({status})")
    return extra_cat_name


def delete_category_ui(page, name: str) -> None:
    """Zmaže kategóriu cez kôš na jej karte + potvrdenie v modáli."""
    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_load_state("networkidle")
    before = _category_count(page)
    card = page.locator("li.category-item", has_text=name).first
    card.locator(".card-action-btn.del").click()
    page.click('#deleteModal [onclick="confirmDelete()"]')
    page.wait_for_function(
        "n => document.querySelectorAll('.category-name').length < n",
        arg=before,
        timeout=STEP_TIMEOUT_MS,
    )
    log(f"   ✓ kategória „{name}“ zmazaná cez UI ({before} → {before - 1})")


def rename_category_ui(page, old_name: str, new_name: str) -> None:
    """Premenuje kategóriu cez ceruzku na jej karte."""
    page.goto(f"{BASE_URL}/dashboard")
    page.wait_for_load_state("networkidle")
    card = page.locator("li.category-item", has_text=old_name).first
    card.locator(".card-action-btn:not(.del)").click()
    page.fill("#editName", new_name)
    page.click('#editCategoryForm button[type=submit]')
    page.locator(".category-name", has_text=new_name).wait_for(
        state="visible", timeout=STEP_TIMEOUT_MS
    )
    log(f"   ✓ kategória premenovaná ({old_name} → {new_name})")


def change_password(page, old: str, new: str) -> None:
    """Na /profile zmení heslo a overí potvrdzujúcu hlášku."""
    page.goto(f"{BASE_URL}/profile")
    page.wait_for_load_state("networkidle")
    page.fill("#currentPassword", old)
    page.fill("#newPassword", new)
    _hide_message(page)
    page.click('#changePasswordForm button[type=submit]')
    page.wait_for_selector("#message", state="visible", timeout=STEP_TIMEOUT_MS)
    text = (page.locator("#message").text_content() or "").lower()
    if "zmenen" not in text and "changed" not in text:
        raise RuntimeError(f"Zmena hesla zlyhala: {text!r}")
    log("   ✓ heslo zmenené")


class RunReport:
    """Zbiera výsledky krokov; na konci vypíše konzolový súhrn a zapíše
    samostatný HTML report (vrátane screenshotu pri zlyhaní)."""

    def __init__(self, mode: str, total: int):
        self.mode = mode
        self.total = total
        self.started_at = time.time()
        self.steps: list[dict] = []
        self.error: str | None = None
        self.screenshot: str | None = None

    @contextmanager
    def step(self, num: int, name: str):
        """Obalí krok: zaloguje hlavičku, odmeria trvanie, zaznamená OK/FAIL."""
        log(f"{num}/{self.total} {name}")
        t0 = time.time()
        try:
            yield
        except Exception as exc:
            self.steps.append({"num": num, "name": name, "status": "FAIL",
                               "seconds": time.time() - t0, "detail": str(exc)})
            raise
        self.steps.append({"num": num, "name": name, "status": "OK",
                           "seconds": time.time() - t0, "detail": ""})

    def print_summary(self) -> None:
        duration = time.time() - self.started_at
        ok = sum(1 for s in self.steps if s["status"] == "OK")
        fail = sum(1 for s in self.steps if s["status"] == "FAIL")
        skipped = self.total - len(self.steps)
        log("")
        log("═" * 64)
        log(f" SÚHRN ({self.mode}): {ok} OK, {fail} FAIL"
            + (f", {skipped} nespustených" if skipped else "")
            + f" — {duration:.0f} s")
        log("─" * 64)
        for s in self.steps:
            icon = "✅" if s["status"] == "OK" else "❌"
            log(f" {icon} {s['num']:>2}. {s['name']}  ({s['seconds']:.1f} s)")
        if self.error:
            log("─" * 64)
            log(f" Chyba: {self.error}")
        log("═" * 64)

    def write_html(self, path: Path) -> None:
        duration = time.time() - self.started_at
        passed = self.error is None
        badge_txt = "PASS ✅" if passed else "FAIL ❌"
        badge_cls = "pass" if passed else "fail"
        started = time.strftime("%d.%m.%Y %H:%M:%S", time.localtime(self.started_at))

        rows = []
        for s in self.steps:
            cls = "ok" if s["status"] == "OK" else "fail"
            detail = (f"<div class='detail'>{html.escape(s['detail'])}</div>"
                      if s["detail"] else "")
            rows.append(
                f"<tr class='{cls}'><td>{s['num']}</td>"
                f"<td>{html.escape(s['name'])}{detail}</td>"
                f"<td class='st'>{s['status']}</td>"
                f"<td class='dur'>{s['seconds']:.1f} s</td></tr>"
            )
        skipped = self.total - len(self.steps)
        if skipped > 0:
            rows.append(
                f"<tr class='skip'><td>—</td><td>{skipped} krokov sa už"
                f" nespustilo (beh skončil skôr)</td><td class='st'>SKIP</td><td></td></tr>"
            )

        error_html = ""
        if self.error:
            error_html = (f"<h2>Chyba</h2><div class='errbox'>"
                          f"{html.escape(self.error)}</div>")

        shot_html = ""
        if self.screenshot and Path(self.screenshot).exists():
            b64 = base64.b64encode(Path(self.screenshot).read_bytes()).decode("ascii")
            shot_html = ("<h2>Screenshot zlyhania</h2>"
                         f"<img class='shot' src='data:image/png;base64,{b64}' "
                         "alt='screenshot zlyhania'>")

        doc = f"""<!doctype html>
<html lang="sk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>E2E report — lexinova.fun</title>
<style>
  body {{ font-family: system-ui, Segoe UI, Arial, sans-serif; margin: 2rem auto;
         max-width: 900px; padding: 0 1rem; color: #1a202c; background: #f7fafc; }}
  h1 {{ font-size: 1.4rem; }}  h2 {{ font-size: 1.05rem; margin-top: 1.6rem; }}
  .badge {{ display: inline-block; padding: .25rem .8rem; border-radius: 999px;
           font-weight: 800; color: #fff; margin-left: .6rem; }}
  .badge.pass {{ background: #38a169; }}  .badge.fail {{ background: #e53e3e; }}
  .meta {{ color: #4a5568; font-size: .9rem; margin-bottom: 1.2rem; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff;
          box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  th, td {{ text-align: left; padding: .5rem .7rem; border-bottom: 1px solid #e2e8f0;
           font-size: .9rem; }}
  th {{ background: #edf2f7; }}
  tr.ok .st {{ color: #38a169; font-weight: 700; }}
  tr.fail .st {{ color: #e53e3e; font-weight: 700; }}
  tr.fail {{ background: #fff5f5; }}
  tr.skip {{ color: #a0aec0; }}
  .dur {{ white-space: nowrap; color: #4a5568; }}
  .detail {{ color: #c53030; font-size: .8rem; margin-top: .25rem; }}
  .errbox {{ background: #fff5f5; border: 1px solid #feb2b2; border-radius: 8px;
            padding: .8rem 1rem; color: #c53030; white-space: pre-wrap;
            font-family: Consolas, monospace; font-size: .85rem; }}
  .shot {{ max-width: 100%; border: 1px solid #e2e8f0; border-radius: 8px;
          margin-top: .5rem; }}
</style></head><body>
<h1>E2E smoke test — lexinova.fun <span class="badge {badge_cls}">{badge_txt}</span></h1>
<div class="meta">
  Režim: <b>{self.mode}</b> &nbsp;·&nbsp; Spustené: {started}
  &nbsp;·&nbsp; Trvanie: {duration:.0f} s &nbsp;·&nbsp; Cieľ: {BASE_URL}
</div>
<table>
<tr><th>#</th><th>Krok</th><th>Stav</th><th>Trvanie</th></tr>
{''.join(rows)}
</table>
{error_html}
{shot_html}
</body></html>
"""
        path.write_text(doc, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="E2E test lexinova.fun")
    parser.add_argument("--quick", action="store_true",
                        help="len účtový tok (bez kategórií, importu, testu a opakovania)")
    args = parser.parse_args()
    total = 7 if args.quick else 23
    rep = RunReport("quick" if args.quick else "full", total)
    report_path = Path(__file__).resolve().parent.parent / "e2e_report.html"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        # Cookie lišta by prekrývala spodok stránky — predznačíme ju ako zatvorenú.
        context.add_init_script(
            "localStorage.setItem('cookieNoticeDismissed', '1');"
            "localStorage.setItem('preferredLang', 'sk');"
        )
        page = context.new_page()

        try:
            with rep.step(1, f"Otvorenie {BASE_URL}"):
                page.goto(BASE_URL)
                pause()

            with rep.step(2, f"Registrácia {EMAIL}"):
                if not register(page):
                    log("   Registrácia neprešla — účet asi zostal z minulého behu, upratujem…")
                    _login_leftover(page)
                    delete_account(page)
                    log("   Starý účet zmazaný, skúšam registráciu znova")
                    if not register(page):
                        raise RuntimeError("Registrácia zlyhala aj po upratovaní.")
                log("   Účet vytvorený, som na dashboarde")

            with rep.step(3, "Odhlásenie"):
                logout(page)
                pause()

            with rep.step(4, "Prihlásenie so zlým heslom — musí zlyhať"):
                login_expect_fail(page, "ZleHeslo123!", "zlé heslo")
                log("   ✓ zlé heslo odmietnuté")

            with rep.step(5, f"Prihlásenie správnym heslom ({EMAIL})"):
                login(page)
                pause()

            current_password = PASSWORD

            if not args.quick:
                with rep.step(6, "Perzistencia session — reload stránky"):
                    check_session_persistence(page)

                with rep.step(7, "Prepínač jazyka EN/SK"):
                    check_language_toggle(page)
                    pause()

                with rep.step(8, f"Vytvorenie kategórie „{CATEGORY_NAME}“ + ručné slovíčka"):
                    category_id = create_category(page)
                    add_words(page)
                    pause()

                with rep.step(9, "Import slovíčok z TXT a Excelu"):
                    with tempfile.TemporaryDirectory() as tmp:
                        tmp_dir = Path(tmp)
                        import_file(page, _make_txt(tmp_dir), TXT_WORDS)
                        import_file(page, _make_xlsx(tmp_dir), XLSX_WORDS)
                    pause()

                with rep.step(10, "Duplicitný re-import XLSX — počet slov sa nesmie zmeniť"):
                    reimport_duplicates(page, category_id)

                with rep.step(11, "Import poškodeného súboru — musí zobraziť chybu"):
                    import_corrupt_file(page)
                    pause()

                with rep.step(12, f"Flashcard test — Všetky slovíčka ({TOTAL_WORDS})"):
                    run_flashcard_test(page, category_id)
                    pause()

                with rep.step(13, "Režim opakovania"):
                    run_repeat(page, category_id)
                    pause()

                with rep.step(14, "Úprava a zmazanie slovíčka"):
                    edit_and_delete_word(page, category_id)
                    pause()

                with rep.step(15, f"Free limit slov ({WORD_LIMIT_FREE}/kategóriu)"):
                    check_word_limit(page, category_id)
                    pause()

                with rep.step(16, "AI generovanie kategórie z textu (prompt)"):
                    run_ai_create_from_text(page)
                    pause()

                with rep.step(17, "AI generovanie kategórie z fotky (vision)"):
                    run_ai_create_from_image(page, context)
                    pause()

                with rep.step(18, f"Free limity: AI kvóta ({AI_DAILY_LIMIT_FREE}/deň) "
                                  f"a kategórie ({CATEGORY_LIMIT_FREE})"):
                    extra_cat_name = check_ai_and_category_limits(page)
                    pause()

                with rep.step(19, "Zmazanie kategórie cez kôš (UI)"):
                    delete_category_ui(page, extra_cat_name)
                    pause()

                with rep.step(20, "Premenovanie kategórie cez ceruzku (UI)"):
                    rename_category_ui(page, CATEGORY_NAME, "E2E Premenovaná")
                    pause()

                with rep.step(21, "Zmena hesla na /profile + overenie re-loginom"):
                    change_password(page, PASSWORD, PASSWORD2)
                    logout(page)
                    login_expect_fail(page, PASSWORD, "staré heslo po zmene")
                    log("   ✓ staré heslo už neplatí")
                    login(page, PASSWORD2)
                    current_password = PASSWORD2
                    pause()

            step = 6 if args.quick else 22
            with rep.step(step, "Zmazanie účtu na /profile"):
                delete_account(page)

            with rep.step(step + 1, "Kontrola: prihlásenie zmazaným účtom nesmie prejsť"):
                login_expect_fail(page, current_password, "účet je zmazaný")

            log("✅ OK — celý tok prešiel" + (" (quick)" if args.quick else ""))
            return 0

        except Exception as exc:  # noqa: BLE001 — smoke test hlási čokoľvek
            rep.error = str(exc)
            shot = "e2e_smoke_fail.png"
            try:
                page.screenshot(path=shot)
                rep.screenshot = shot
                log(f"Screenshot zlyhania: {shot}")
            except Exception:
                pass
            log(f"❌ FAIL — {exc}")
            return 1

        finally:
            browser.close()
            rep.print_summary()
            try:
                rep.write_html(report_path)
                log(f"HTML report: {report_path}")
            except Exception as report_exc:
                log(f"HTML report sa nepodarilo zapísať: {report_exc}")


if __name__ == "__main__":
    sys.exit(main())
