# -*- coding: utf-8 -*-
"""
E2E test celého užívateľského toku na https://lexinova.fun.

Otvorí viditeľný Chromium prehliadač a preklikaním overí:

  1. Otvorí lexinova.fun, počká 4 s
  2. /register — vyplní e-mail + heslo + zopakuje heslo, vytvorí účet
  3. Po prihlásení sa odhlási, počká 4 s
  4. Znova sa prihlási, počká 4 s
  5. Vytvorí kategóriu „E2E Testovacia" a pridá 3 slovíčka ručne
  6. Importuje 3 slovíčka z TXT a 3 z Excelu (.xlsx)
  7. Spustí flashcard test (Všetky slovíčka) a odpovie na všetkých 9 kariet
  8. Prejde režim opakovania (flip + ďalšie slovo až po koniec)
  9. /profile → Zmazať účet → potvrdí (upratanie po sebe)
 10. Overí, že prihlásenie zmazaným účtom už neprejde

Rýchly variant bez kategórií/importu/testu/opakovania: `--quick`.

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
import re
import sys
import tempfile
import time
from pathlib import Path

# Windows konzola býva cp1252 — bez tohto padajú printy s diakritikou.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

BASE_URL = "https://lexinova.fun"
EMAIL = "Admin1@admin.com"
PASSWORD = "Admin1111"
PAUSE_S = 4
STEP_TIMEOUT_MS = 20_000

CATEGORY_NAME = "E2E Testovacia"
MANUAL_WORDS = [("dog", "pes"), ("cat", "mačka"), ("house", "dom")]
TXT_WORDS = [("bird", "vták"), ("tree", "strom"), ("water", "voda")]
XLSX_WORDS = [("sun", "slnko"), ("moon", "mesiac"), ("star", "hviezda")]
TOTAL_WORDS = len(MANUAL_WORDS) + len(TXT_WORDS) + len(XLSX_WORDS)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def pause(seconds: float = PAUSE_S) -> None:
    log(f"… čakám {seconds} s")
    time.sleep(seconds)


def login(page) -> None:
    """Prihlási sa a počká na presmerovanie na dashboard."""
    page.goto(f"{BASE_URL}/login")
    page.fill("#email", EMAIL)
    page.fill("#password", PASSWORD)
    page.click("#loginForm button[type=submit]")
    page.wait_for_url("**/dashboard", timeout=STEP_TIMEOUT_MS)


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


def main() -> int:
    parser = argparse.ArgumentParser(description="E2E test lexinova.fun")
    parser.add_argument("--quick", action="store_true",
                        help="len účtový tok (bez kategórií, importu, testu a opakovania)")
    args = parser.parse_args()
    total = 6 if args.quick else 10

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
            log(f"1/{total} Otváram {BASE_URL}")
            page.goto(BASE_URL)
            pause()

            log(f"2/{total} Registrácia {EMAIL}")
            if not register(page):
                log("   Registrácia neprešla — účet asi zostal z minulého behu, upratujem…")
                login(page)
                delete_account(page)
                log("   Starý účet zmazaný, skúšam registráciu znova")
                if not register(page):
                    raise RuntimeError("Registrácia zlyhala aj po upratovaní.")
            log("   Účet vytvorený, som na dashboarde")

            log(f"3/{total} Odhlasujem sa")
            logout(page)
            pause()

            log(f"4/{total} Prihlasujem sa znova ako {EMAIL}")
            login(page)
            pause()

            step = 5
            if not args.quick:
                log(f"5/{total} Vytváram kategóriu „{CATEGORY_NAME}“ a pridávam slovíčka ručne")
                category_id = create_category(page)
                add_words(page)
                pause()

                log(f"6/{total} Import slovíčok z TXT a Excelu")
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_dir = Path(tmp)
                    import_file(page, _make_txt(tmp_dir), TXT_WORDS)
                    import_file(page, _make_xlsx(tmp_dir), XLSX_WORDS)
                pause()

                log(f"7/{total} Flashcard test — Všetky slovíčka ({TOTAL_WORDS})")
                run_flashcard_test(page, category_id)
                pause()

                log(f"8/{total} Režim opakovania")
                run_repeat(page, category_id)
                pause()
                step = 9

            log(f"{step}/{total} Idem na /profile a mažem účet")
            delete_account(page)

            log(f"{step + 1}/{total} Kontrola: účet zmazaný — prihlásenie už nesmie prejsť")
            page.goto(f"{BASE_URL}/login")
            page.fill("#email", EMAIL)
            page.fill("#password", PASSWORD)
            page.click("#loginForm button[type=submit]")
            try:
                page.wait_for_url("**/dashboard", timeout=6_000)
                raise RuntimeError("Účet sa dá prihlásiť aj po zmazaní!")
            except PWTimeout:
                pass  # presne toto čakáme — login zlyhal

            log("✅ OK — celý tok prešiel" + (" (quick)" if args.quick else
                " (registrácia → kategória → slovíčka → import TXT+XLSX → test → opakovanie → zmazanie)"))
            return 0

        except Exception as exc:  # noqa: BLE001 — smoke test hlási čokoľvek
            shot = "e2e_smoke_fail.png"
            try:
                page.screenshot(path=shot)
                log(f"Screenshot zlyhania: {shot}")
            except Exception:
                pass
            log(f"❌ FAIL — {exc}")
            return 1

        finally:
            browser.close()


if __name__ == "__main__":
    sys.exit(main())
