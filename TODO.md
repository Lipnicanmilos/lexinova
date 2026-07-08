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

## Platobná brána — Paddle (Merchant of Record)

**Rozhodnuté (2026-06-28):** Paddle (nezávislý pravý MoR, rieši EU DPH + faktúry — prevádzkovateľ je FO bez IČO).
⚠️ Pôvodne Lemon Squeezy, ale po akvizícii Stripom LS presmeruje nových používateľov do Stripe (nie čistý MoR) → prešli sme na Paddle. Backend prerobený commitom `8f352b69`.
Ceny: **PLUS Mesačne €4,99 · PLUS Ročne €39,99 · BEZ skúšobnej doby** (rozhodnuté 2026-07-08 — len free účet / PLUS mesačne / PLUS ročne).
✅ Živnosť/zdanenie overené s účtovníkom (2026-07-08) — go-live odblokovaný.

### Testovacie karty (Paddle sandbox)
| Účel | Číslo karty | Exp. | CVC |
|------|-------------|------|-----|
| Úspešná platba (Visa) | `4242 4242 4242 4242` | hocijaký budúci dátum | hocijaké 3 čísla |
| Mastercard (success) | `5555 5555 5555 4444` | -//- | -//- |
| Vyžaduje 3DS overenie | `4000 0038 0000 0002` | -//- | -//- |
| Zamietnutá platba | `4000 0000 0000 0002` | -//- | -//- |

### Fáza 0 — Paddle setup (manuálne, robí používateľ) ✅ (sandbox) — 2026-06-28
- [x] Sandbox účet (`sandbox-login.paddle.com`) + produkt „LexiNova PLUS" + 2 ceny (Monthly €4,99 / Annual €39,99), 7-day free trial, tax = Account default
- [x] Env (sandbox): `PADDLE_ENV=sandbox`, `PADDLE_API_KEY`, `PADDLE_CLIENT_TOKEN`, `PADDLE_WEBHOOK_SECRET`, `PADDLE_PRICE_MONTHLY`, `PADDLE_PRICE_ANNUAL` — v lokálnom `.env` aj na Cloud Run
- [x] Webhook destinácia → `https://lexinova-...run.app/api/webhooks/paddle` (subscription.* + transaction.completed + transaction.payment_failed)
- [x] **Checkout settings: Approved domain** + **Default payment link** (`/profile`) — inak `transaction_default_checkout_url_not_set`
- [ ] LIVE účet: zopakovať setup + revoke omylom zverejneného live API kľúča (`pdl_live_...`)

### Fáza 1 — DB migrácia (User) ✅ (kód) — 2026-06-28
- [x] Stĺpce v `User`: `plus_expires_at`, `plus_plan`, `plus_status`, `ls_customer_id`, `ls_subscription_id`, `plus_cancelled_at`
- [x] SQL migrácia pre Supabase: `migrations/2026-06-28_add_subscription_columns.sql`
- [ ] **TY: spustiť ten SQL na produkčnej Supabase DB** (create_all nepridá stĺpce do existujúcej tabuľky)
- [x] Payment model — transakcie logujeme s `provider='lemonsqueezy'`

### Fáza 2 — Backend služba + endpointy ✅ — 2026-06-28
- [x] `app/services/billing_service.py` — LS API klient (httpx) + HMAC-SHA256 verifikácia webhookov + mapovanie subscription→user
- [x] `POST /api/v1/checkout` (auth) — checkout pre plán, `custom={user_id}`, vráti URL (503 ak nenakonfigurované)
- [x] `GET /api/v1/subscription` (auth) — stav predplatného
- [x] `GET /api/v1/billing/portal` (auth) — URL na LS customer portal
- [x] `POST /api/webhooks/lemonsqueezy` — HMAC verifikácia; eventy created/updated/cancelled/expired/payment_success/payment_failed; idempotentné logovanie platby
- [x] Testy `test_billing.py` (7) — checkout auth/503/plán, subscription, webhook podpis + aktivácia + expirácia

### Fáza 3 — Aktivácia / expirácia ✅ (čiastočne) — 2026-06-28
- [x] `billing_service.expire_if_needed(user)` + kontrola pri logine (email aj OAuth)
- [ ] (voliteľné neskôr) Cloud Scheduler denný cron

### Fáza 4 — Frontend (profil) ✅ — 2026-06-28
- [x] Sekcia „Predplatné": stav (Standard / PLUS / trial) + dátum „aktívne do"
- [x] Tlačidlá „PLUS Mesačne / Ročne" → `/api/v1/checkout` → redirect
- [x] Tlačidlo „Spravovať predplatné" → `/api/v1/billing/portal` (otvára sa v novej karte)
- [x] Tlačidlo „Zrušiť predplatné" → `POST /api/v1/billing/cancel` (ku koncu obdobia, prístup ostáva do expirácie)
- [x] Checkout cez **Paddle.js overlay** (`Paddle.Checkout.open`) — nie server redirect
- [x] Návrat z checkoutu (`?upgraded=1`) → správa + reload stavu
- [x] **Odstránený fake user `togglePlus()` + endpoint `/api/user/plus`** (bezpečnostná diera — self-grant PLUS zadarmo). Admin override (`/api/admin/users`) zostáva.

### Fáza 5 — PLUS benefity — HOTOVÉ (2026-06-29)
- [x] **Kategórie: PLUS = neobmedzene** (Free = 5) — categories.py create + ai-create (+ FE už neblokuje PLUS pri 5)
- [x] **AI generovanie: Free 3/deň, PLUS neobmedzene** — `services/limits.py:consume_ai_quota`, denný counter `User.ai_uses_date/ai_uses_count`, platí pre prompt aj fotku (429 pri prekročení). Migrácia `2026-06-29_ai_usage_columns.sql`.
- [x] **Limit slovíčok/kategória: Free 30, PLUS neobmedzene** — `services/limits.py:WORD_LIMIT_FREE`, vynútené v words.py (create + import) aj v AI ukladaní (`_persist_generated_category` word_limit)
- [x] **Rozšírené štatistiky (PLUS)** — `/api/user/stats` vracia `is_plus` + `plus_stats` (úspešnosť testov, zvládnuté slová, počet testov, top 5 najslabších slov); dashboard zobrazí PLUS sekciu
- [x] Testy `tests/test_plus_limits.py` (6) → spolu 43 testov
- [ ] Pozn.: gating používa `user.is_plus` (expire_if_needed pri logine ho drží aktuálny)

### Fáza 6 — Admin — HOTOVÉ (2026-06-30)
- [x] Stĺpce: stav predplatného, expirácia, plán (stĺpec „Predplatné" v admin tabuľke; `/api/admin/users` vracia plus_plan/status/expires_at/cancelled_at)
- [x] Manuálny grant PLUS o N dní — admin override (`POST /api/admin/users/{id}/grant-plus`, +/− dni, naväzuje na zostatok) + revoke (`POST .../revoke-plus`); tlačidlá 📅/✖ v admin UI
- [x] MRR / aktívne predplatné štatistika — `/api/admin/payments` počíta z User tabuľky (active subs, monthly/annual, MRR, ARR; trial mimo MRR); karty v záložke Platby

### Fáza 7 — Testy + go-live
- [x] Testy `test_billing.py` (8): config auth/nenakonfigurované, subscription, cancel auth/404, webhook podpis + aktivácia + zrušenie. Spolu 34 testov.
- [x] **E2E v sandbox test mode HOTOVÝ (2026-06-28):** migrácia na Supabase spustená, testovacia platba kartou `4242…` prešla, webhook aktivoval PLUS. ✅
- [x] Ceny v `terms.html` doplnené (SK+EN): PLUS Mesačne €4,99 / Ročne €39,99 vrátane DPH, Paddle ako MoR, postup refundácie (2026-06-30). ⚠️ Právne znenie refundácie odporúčam dať overiť právnikovi.
- [x] **Trial odstránený z kódu** (2026-07-08): `terms.html` SK+EN („skúšobná doba sa neposkytuje"), `profile.html` (popisok pod tlačidlami + badge „PLUS – skúšobné"), sw.js cache v29.
- [ ] Prepnúť na **live** Paddle účet — viď checklist nižšie.
- [ ] **Zrušiť testovacie predplatné (sandbox)** — vytvorené pri E2E teste platieb (2026-06-28) zrušiť v Paddle sandbox dashboarde

#### Go-live checklist (manuálne kroky v Paddle + Cloud Run):
1. [x] **Účtovník/živnosť** — potvrdené 2026-07-08.
2. [ ] **Paddle live účet** (`login.paddle.com`, nie sandbox): verifikácia účtu (môže pýtať doklady), website approval.
3. [ ] **Live produkt + ceny:** „LexiNova PLUS", Monthly €4,99 (`pri_01kw6mj3tvbyekxmh0xez2exk3`) + Annual €39,99 (`pri_01kw6mzcephazys90em9pjmjya`) — už vytvorené na live účte. **Trial nastaviť na „No trial"** (Paddle → Catalog → Prices → Trial period = none) a tax = Account default.
4. [ ] **Checkout settings (live):** Approved domain (produkčná doména/Cloud Run URL) + Default payment link (`/profile`) + Statement descriptor `LEXINOVA`.
5. [ ] **Live webhook** → `https://<prod-url>/api/webhooks/paddle`, rovnaké eventy (subscription.* + transaction.completed + transaction.payment_failed); skopírovať nový `PADDLE_WEBHOOK_SECRET`.
6. [ ] **Revoke** omylom zverejneného live API kľúča `pdl_live_apikey_01kw6n6m...` a vygenerovať nový `PADDLE_API_KEY`.
7. [ ] **Cloud Run env (live):** `PADDLE_ENV=production`, `BILLING_ENABLED=true`, `PADDLE_API_KEY` (nový live), `PADDLE_CLIENT_TOKEN` (live `live_...`), `PADDLE_WEBHOOK_SECRET` (live), `PADDLE_PRICE_MONTHLY`/`PADDLE_PRICE_ANNUAL` (live pri_...). Pozn.: zmena env NEnasadí nový kód — ak treba, push → nový build.
8. [ ] **E2E test na live** s reálnou kartou (malá suma) → checkout → webhook → PLUS → cancel; potom refund tej platby v Paddle.
9. [ ] (voliteľné) vlastná doména → pridať do CORS `FRONTEND_ORIGIN` + Paddle Approved domain.

---

## Ďalšie nápady / backlog
- [ ] **E2E test skript (Python + Playwright/Selenium):** spustí Chrome na `https://lexinova.fun` → signup (nový testovací účet) → prihlásenie → vytvorenie kategórií → testovanie slovíčok → opakovanie → zmazanie účtu (upratanie po sebe). Celý užívateľský flow proti produkcii.
- [ ] Pridať pätičku (site-footer.js) aj na dashboard, test, repeat stránky
- [ ] Import slovíčok (Excel/CSV) — overiť že funguje
