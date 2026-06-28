# LexiNova – TODO

## 🔒 Bezpečnosť & GDPR — pred komerčnou propagáciou
> Audit 2026-06-26. Zoradené podľa závažnosti.

### 🔴 Kritické (bezpečnostné diery)
- [x] **Únik e-mailov** — `/api/v1/users` len pre admina, `/api/debug/users` + `/api/debug/categories` zmazané (commit 72a3a6e3, 2026-06-26)
- [x] **Server-side validácia registrácie** (`app/routers/auth.py`) — 2026-06-27
  - Email: `EmailStr` na `UserRegister` aj `UserLogin`
  - Heslo: `password_strength_error()` (8+/veľké/malé/číslica) cez Pydantic `field_validator` na registrácii aj resete
  - `/api/v1/reset-password` prepojený na `PasswordReset` model; reset frontend dostal rovnaké 4 pravidlá; `detailMsg()` v register/login/reset rieši 422 zoznam
- [x] **Rate limiting na zneužiteľné endpointy** — 2026-06-27
  - `POST /api/inquiry` → `@limiter.limit("5/hour")` (per IP)
  - `POST /api/v1/categories/ai-create` → `@limiter.limit("10/hour")` (chráni AI kredity)
  - Frontend (site-footer.js, ai_create_category.js) ošetruje 429 zrozumiteľnou hláškou

### 🟠 GDPR / právne (nutné pre komerciu)
- [x] **AI poskytovatelia v Privacy Policy** — 2026-06-27. Sekcia „Tretie strany" (SK+EN) doplnená o Groq/Gemini/Anthropic; uvedené, že sa posiela iba text promptu + jazyky (overené v ai_category_service.py)
- [x] **Obchodné podmienky (Terms of Service)** — 2026-06-27. Nová `terms.html` (SK+EN, 12 sekcií), route `/terms`, odkazy v registrácii + pätičke. Ceny/odstúpenie sú `[DOPLNIŤ]` placeholdery — doplniť po spustení Stripe.
- [x] **Identifikácia prevádzkovateľa + retention** v Privacy — 2026-06-27. Prevádzkovateľ: Miloš Lipničan (fyzická osoba, SK) + sekcia „Doba uchovávania" (SK+EN).
- [x] **Self-hostovať Google Fonts** — 2026-06-27. Inter v20 (variabilný, latin+latin-ext) v `app/static/fonts/`, `app/static/css/fonts.css`; nahradené v 12 šablónach; MIME `font/woff2` v main.py; sw.js precache v22. Žiadne volania na Google CDN.
- [x] Export dát + zmazanie účtu — funguje správne (ORM cascade maže aj kategórie aj slovíčka)

### 🟡 Stredné (bezpečnosť / produkcia)
- [x] **Security hlavičky** — 2026-06-27. `security_headers` middleware v main.py: CSP (unsafe-inline pre inline style/script), X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy, HSTS (len v prod/DEBUG=false)
- [x] **CORS zúžiť** — 2026-06-27. Origins podľa prostredia (localhost len v debug), voliteľná vlastná doména cez env `FRONTEND_ORIGIN`, explicitné metódy + hlavičky namiesto `*`
- [x] **Leak detailov chýb** — 2026-06-27. `register` aj `login` vracajú generickú hlášku; detail sa len loguje
- [ ] **Vlastná doména** — beží na `lexinova-...run.app`; pre dôveryhodnosť komerčnej služby treba vlastnú doménu (nie kód; CORS env `FRONTEND_ORIGIN` je pripravený)
- [x] `@app.on_event("startup")` → migrované na FastAPI lifespan (`asynccontextmanager`) — 2026-06-27

### ⚪ Upratovanie
- [x] Zmazané zbytočné súbory: `category_words copy.html`, `test.html`, starý `Readme` (WordKeeper), `procedure.txt` — 2026-06-27
- [x] **Automatické testy** — 2026-06-27. pytest + TestClient + SQLite (`tests/`, 20 testov: stránky, security hlavičky, fonty, validácia, login, rate limit). Spustenie: `python -m pytest`
- [x] **Monitoring** — 2026-06-27. Rotujúce logy `logs/lexinova.log` (3 dni/~72h retencia) + e-mail alerty pri ERROR (`ERROR_ALERT_EMAIL`, neblokujúco cez frontu) v `runtime.py`. Bez Sentry — self-hosted.

### ⚙️ Nasadenie
- [x] `ADMIN_EMAILS` nastavené na Cloud Run — overené 2026-06-27, admin prístup pod lipnicanmilos@gmail.com funguje

---

## Platobná brána — Lemon Squeezy (Merchant of Record)

**Rozhodnuté (2026-06-27):** Lemon Squeezy (MoR, rieši DPH za nás — prevádzkovateľ je FO bez IČO).
Ceny: **PLUS Mesačne €4,99 · PLUS Ročne €39,99 · 7-dňový trial**.
⚠️ Pred OSTRÝM spustením (live) overiť s účtovníkom živnosť/zdanenie príjmu. Celý vývoj prebehne v **test mode** (žiadne reálne peniaze, netreba živnosť).

### Fáza 0 — Lemon Squeezy setup (manuálne, robí používateľ)
- [ ] Vytvoriť LS účet + Store (test mode)
- [ ] Produkt „LexiNova PLUS" s 2 variantmi (Monthly €4,99, Annual €39,99), oba subscription + 7-day free trial
- [ ] API key, Store ID, Webhook signing secret, Variant IDs (monthly/annual)
- [ ] Env: `LEMONSQUEEZY_API_KEY`, `LEMONSQUEEZY_STORE_ID`, `LEMONSQUEEZY_WEBHOOK_SECRET`, `LEMONSQUEEZY_VARIANT_MONTHLY`, `LEMONSQUEEZY_VARIANT_ANNUAL`

### Fáza 1 — DB migrácia (User)
- [ ] Stĺpce: `plus_expires_at` (DateTime), `plus_plan` (String monthly/annual), `plus_status` (String: on_trial/active/past_due/cancelled/expired), `ls_customer_id` (String), `ls_subscription_id` (String), `plus_cancelled_at` (DateTime)
- [ ] Spustiť `RUN_DB_CREATE_ALL=1` (alebo ALTER TABLE)
- [ ] Payment model už existuje — logovať doň transakcie (provider='lemonsqueezy')

### Fáza 2 — Backend služba + endpointy
- [ ] `app/services/billing_service.py` — LS API klient (httpx) + HMAC verifikácia webhookov
- [ ] `POST /api/v1/checkout` (auth) — vytvorí LS checkout pre zvolený plán, `custom={user_id}`, vráti URL
- [ ] `GET /api/v1/subscription` (auth) — stav predplatného prihláseného usera
- [ ] `GET /api/v1/billing/portal` (auth) — URL na LS customer portal (zmena/zrušenie)
- [ ] `POST /api/webhooks/lemonsqueezy` — **HMAC-SHA256 podpisová verifikácia**; eventy:
  - `subscription_created` / `subscription_updated` → set is_plus, plus_status, plus_expires_at, ls_* podľa `custom.user_id`
  - `subscription_payment_success` → predĺž `plus_expires_at`
  - `subscription_payment_failed` → e-mail notifikácia
  - `subscription_cancelled` / `subscription_expired` → po expirácii deaktivuj
- [ ] Rate limit + idempotencia webhookov

### Fáza 3 — Aktivácia / expirácia
- [ ] Helper `user_has_active_plus(user)` — is_plus AND (plus_expires_at None alebo > now)
- [ ] Kontrola pri logine: ak `plus_expires_at < now()` → is_plus=False (webhooky sú primárny zdroj)
- [ ] (voliteľné neskôr) Cloud Scheduler denný cron

### Fáza 4 — Frontend (profil)
- [ ] Sekcia „Predplatné": stav (Free / PLUS do DD.MM.YYYY / trial do…)
- [ ] Tlačidlá „Upgradovať na PLUS" (mesačne/ročne) → `/checkout` → redirect
- [ ] Tlačidlo „Spravovať predplatné" → portal
- [ ] Banner pri expirácii / zlyhanej platbe
- [ ] Odstrániť fake user `togglePlus()` (nechať len admin override)

### Fáza 5 — PLUS benefity (treba doplniť hodnotu)
- [ ] Definovať čo PLUS dáva navyše (teraz len 20 vs 5 kategórií) — napr. viac AI generovaní, viac slovíčok/kat., rozšírené štatistiky
- [ ] Vynútiť limity na backende podľa `user_has_active_plus`

### Fáza 6 — Admin
- [ ] Stĺpce: stav predplatného, expirácia, plán
- [ ] Manuálny grant PLUS s dátumom (+30 dní) — admin override
- [ ] MRR / aktívne predplatné štatistika (Payment model + LS)

### Fáza 7 — Testy + go-live
- [ ] Testy: checkout vytvorí URL, webhook (validný/nevalidný podpis), aktivácia/expirácia, gating
- [ ] E2E v test mode (testovacia karta)
- [ ] Prepnúť LS na live + reálne env premenné (až po vyriešení živnosti)

---

## Ďalšie nápady / backlog
- [ ] Pridať pätičku (site-footer.js) aj na dashboard, test, repeat stránky
- [ ] Import slovíčok (Excel/CSV) — overiť že funguje
