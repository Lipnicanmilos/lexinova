# -*- coding: utf-8 -*-
"""
E2E smoke test — registrácia → odhlásenie → prihlásenie → zmazanie účtu.

Manuálne spúšťaný skript proti produkcii (https://lexinova.fun). Otvorí
viditeľný Chromium prehliadač a preklikaním overí základný účtový tok:

  1. Otvorí lexinova.fun, počká 4 s
  2. /register — vyplní e-mail + heslo + zopakuje heslo, vytvorí účet
  3. Po prihlásení sa odhlási, počká 4 s
  4. Znova sa prihlási, počká 4 s
  5. /profile → Zmazať účet → potvrdí (upratanie po sebe)

Ak testovací účet z minulého (spadnutého) behu ešte existuje, skript sa
ním najprv prihlási, zmaže ho a registráciu zopakuje.

Spustenie (jednorazová príprava):
    venv\\Scripts\\python.exe -m pip install playwright
    venv\\Scripts\\python.exe -m playwright install chromium
Potom:
    venv\\Scripts\\python.exe scripts\\e2e_smoke.py
"""

import sys
import time

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


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def pause() -> None:
    log(f"… čakám {PAUSE_S} s")
    time.sleep(PAUSE_S)


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


def main() -> int:
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
            log(f"1/6 Otváram {BASE_URL}")
            page.goto(BASE_URL)
            pause()

            log(f"2/6 Registrácia {EMAIL}")
            if not register(page):
                log("   Registrácia neprešla — účet asi zostal z minulého behu, upratujem…")
                login(page)
                delete_account(page)
                log("   Starý účet zmazaný, skúšam registráciu znova")
                if not register(page):
                    raise RuntimeError("Registrácia zlyhala aj po upratovaní.")
            log("   Účet vytvorený, som na dashboarde")

            log("3/6 Odhlasujem sa")
            logout(page)
            pause()

            log(f"4/6 Prihlasujem sa znova ako {EMAIL}")
            login(page)
            pause()

            log("5/6 Idem na /profile a mažem účet")
            delete_account(page)

            log("6/6 Kontrola: účet zmazaný — prihlásenie už nesmie prejsť")
            page.goto(f"{BASE_URL}/login")
            page.fill("#email", EMAIL)
            page.fill("#password", PASSWORD)
            page.click("#loginForm button[type=submit]")
            try:
                page.wait_for_url("**/dashboard", timeout=6_000)
                raise RuntimeError("Účet sa dá prihlásiť aj po zmazaní!")
            except PWTimeout:
                pass  # presne toto čakáme — login zlyhal

            log("✅ OK — celý tok (registrácia → odhlásenie → prihlásenie → zmazanie) prešiel")
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
