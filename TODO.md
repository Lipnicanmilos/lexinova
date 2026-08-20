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
- [x] **Vlastná doména** — `lexinova.fun` kúpená a namapovaná na Cloud Run (2026-07-04), OAuth aj Paddle na nej fungujú
- [x] `@app.on_event("startup")` → migrované na FastAPI lifespan (`asynccontextmanager`) — 2026-06-27

### ⚪ Upratovanie
- [x] **Audit logovania** ✅ 2026-07-10 — infra OK (konzola + rotujúci súbor 48h + e-mail alerty + admin viewer). Opravené: zmazaný debug spam `Session keys in dashboard` (pages.py, logoval sa pri KAŽDOM načítaní dashboard/profile/test/repeat), e-maily používateľov v OAuth logoch nahradené user_id (GDPR — Cloud Logging drží ~30 dní). Testovací user `test123` sa vytvára len pri `DEBUG=true` — na produkcii nie, overené. AI payload warning (500 znakov) ponechaný — užitočný na ladenie.
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
✅ **Doména `lexinova.fun` schválená Paddlom (2026-07-10)** — website review vybavený.
🟢 **ÚČET JE LIVE (2026-07-10)** — e-mail „Your account is live — you can now take payments": doména `lexinova.fun` schválená, KYC prešlo, **checkout je na live povolený**.
🏁 **GO-LIVE KOMPLETNÝ (2026-07-10 večer)** — live konfigurácia nasadená a **E2E s reálnou kartou prešiel** (platba → webhook → PLUS → cancel → refund, viď krok 8). Predaj PLUS je ostrý. ✅ **Payout verification aj zrušenie test subscription overené 2026-07-13 — Paddle časť je tým kompletne uzavretá.** (7b rotácia kľúčov — vynechané na žiadosť užívateľa 2026-07-13.)

### Testovacie karty (Paddle sandbox)
| Účel | Číslo karty | Exp. | CVC |
|------|-------------|------|-----|
| Úspešná platba (Visa) | `4242 4242 4242 4242` | hocijaký budúci dátum | hocijaké 3 čísla |
| Mastercard (success) | `5555 5555 5555 4444` | -//- | -//- |
| Vyžaduje 3DS overenie | `4000 0038 0000 0002` | -//- | -//- |
| Zamietnutá platba | `4000 0000 0000 0002` | -//- | -//- |

### Fáza 0 — Paddle setup (manuálne, robí používateľ) ✅ (sandbox) — 2026-06-28
- [x] Sandbox účet (`sandbox-login.paddle.com`) + produkt „LexiNova PLUS" + 2 ceny (Monthly €4,99 / Annual €39,99), tax = Account default. Pôvodné trialy (7d Monthly / 1d Yearly) zrušené 2026-07-08 — sandbox zosúladený s live (bez trialu).
- [x] Env (sandbox): `PADDLE_ENV=sandbox`, `PADDLE_API_KEY`, `PADDLE_CLIENT_TOKEN`, `PADDLE_WEBHOOK_SECRET`, `PADDLE_PRICE_MONTHLY`, `PADDLE_PRICE_ANNUAL` — v lokálnom `.env` aj na Cloud Run
- [x] Webhook destinácia → `https://lexinova-...run.app/api/webhooks/paddle` (subscription.* + transaction.completed + transaction.payment_failed)
- [x] **Checkout settings: Approved domain** + **Default payment link** (`/profile`) — inak `transaction_default_checkout_url_not_set`
- [x] LIVE účet: zopakovať setup ✅ 2026-07-10 (produkt + ceny + checkout settings + webhook + env)

### Fáza 1 — DB migrácia (User) ✅ (kód) — 2026-06-28
- [x] Stĺpce v `User`: `plus_expires_at`, `plus_plan`, `plus_status`, `ls_customer_id`, `ls_subscription_id`, `plus_cancelled_at`
- [x] SQL migrácia pre Supabase: `migrations/2026-06-28_add_subscription_columns.sql`
- [x] **SQL migrácia spustená na produkčnej Supabase DB** (2026-06-28, vrátane rename ls_→paddle_)
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

### Fáza 4 — Frontend (profil) ✅ — 2026-06-28 (modál zrušenia 2026-07-10)
- [x] Sekcia „Predplatné": stav (Standard / PLUS / trial) + dátum „aktívne do"
- [x] Tlačidlá „PLUS Mesačne / Ročne" → `/api/v1/checkout` → redirect
- [x] Tlačidlo „Spravovať predplatné" → `/api/v1/billing/portal` (otvára sa v novej karte)
- [x] Tlačidlo „Zrušiť predplatné" → `POST /api/v1/billing/cancel` (ku koncu obdobia, prístup ostáva do expirácie)
- [x] Natívny `confirm()` pri zrušení nahradený štýlovaným modálom (`cancelSubModal`, SK/EN, tlačidlá „Ponechať PLUS" / „Zrušiť predplatné") — 2026-07-10, sw.js cache **v33** (profil je precachovaný)
- [x] Checkout cez **Paddle.js overlay** (`Paddle.Checkout.open`) — nie server redirect
- [x] Návrat z checkoutu (`?upgraded=1`) → správa + reload stavu
- [x] **Odstránený fake user `togglePlus()` + endpoint `/api/user/plus`** (bezpečnostná diera — self-grant PLUS zadarmo). Admin override (`/api/admin/users`) zostáva.

### Fáza 5 — PLUS benefity — HOTOVÉ (2026-06-29)
- [x] **Kategórie: PLUS = neobmedzene** (Free = 5) — categories.py create + ai-create (+ FE už neblokuje PLUS pri 5)
- [x] **AI generovanie: Free 3/deň, PLUS neobmedzene** — `services/limits.py:consume_ai_quota`, denný counter `User.ai_uses_date/ai_uses_count`, platí pre prompt aj fotku (429 pri prekročení). Migrácia `2026-06-29_ai_usage_columns.sql`.
- [x] **Limit slovíčok/kategória: Free 30, PLUS neobmedzene** — `services/limits.py:WORD_LIMIT_FREE`, vynútené v words.py (create + import) aj v AI ukladaní (`_persist_generated_category` word_limit)
- [x] **Rozšírené štatistiky (PLUS)** — `/api/user/stats` vracia `is_plus` + `plus_stats` (úspešnosť testov, zvládnuté slová, počet testov, top 5 najslabších slov); dashboard zobrazí PLUS sekciu
- [x] Testy `tests/test_plus_limits.py` (6) → spolu 43 testov
- Pozn.: gating používa `user.is_plus` (expire_if_needed pri logine ho drží aktuálny)

### Fáza 6 — Admin — HOTOVÉ (2026-06-30)
- [x] Stĺpce: stav predplatného, expirácia, plán (stĺpec „Predplatné" v admin tabuľke; `/api/admin/users` vracia plus_plan/status/expires_at/cancelled_at)
- [x] Manuálny grant PLUS o N dní — admin override (`POST /api/admin/users/{id}/grant-plus`, +/− dni, naväzuje na zostatok) + revoke (`POST .../revoke-plus`); tlačidlá 📅/✖ v admin UI
- [x] MRR / aktívne predplatné štatistika — `/api/admin/payments` počíta z User tabuľky (active subs, monthly/annual, MRR, ARR; trial mimo MRR); karty v záložke Platby
- [x] **Refundy v admin Platbách** ✅ 2026-07-10 — webhook spracúva `adjustment.created/updated` (refund/chargeback → `Payment.status` refunded/refund_pending/chargeback; rejected/reversed vráti succeeded), refundované platby vypadnú z tržieb, nová karta „Refundy" + pill „Refundované/Refund čaká/Chargeback" v tabuľke. Test `test_webhook_refund_marks_payment`.
  - ⚠️ **Manuálny krok: v Paddle destinácii doškrtnúť eventy `adjustment.created` + `adjustment.updated`** (Developer tools → Notifications → Edit destination) — bez toho refund eventy nechodia.
  - Pozn.: dnešný refund (pred nasadením) v DB zostane ako „Uhradené" — event už Paddle znova nepošle; prípadne opraviť ručne v DB.

### Fáza 7 — Testy + go-live
- [x] Testy `test_billing.py` (8): config auth/nenakonfigurované, subscription, cancel auth/404, webhook podpis + aktivácia + zrušenie. Spolu 34 testov.
- [x] **E2E v sandbox test mode HOTOVÝ (2026-06-28):** migrácia na Supabase spustená, testovacia platba kartou `4242…` prešla, webhook aktivoval PLUS. ✅
- [x] Ceny v `terms.html` doplnené (SK+EN): PLUS Mesačne €4,99 / Ročne €39,99 vrátane DPH, Paddle ako MoR, postup refundácie (2026-06-30). ⚠️ Právne znenie refundácie odporúčam dať overiť právnikovi.
- [x] **Trial odstránený z kódu** (2026-07-08): `terms.html` SK+EN („skúšobná doba sa neposkytuje"), `profile.html` (popisok pod tlačidlami + badge „PLUS – skúšobné"), sw.js cache v29.
- [x] Prepnúť na **live** Paddle účet ✅ 2026-07-10 — viď checklist nižšie.
- [x] **Zrušiť testovacie predplatné (sandbox)** ✅ 2026-07-08 — predplatné lipnicanova.dominika@gmail.com (z E2E testu 2026-06-28) zrušené immediately v sandbox dashboarde

#### Go-live checklist (manuálne kroky v Paddle + Cloud Run):
1. [x] **Účtovník/živnosť** — potvrdené 2026-07-08.
2. [x] **Paddle live účet — doména SCHVÁLENÁ** ✅ **2026-07-10**: Website approval → Domain approval → `lexinova.fun` = **Approved**. Website review už nie je blokátor.
   - 💡 **Poučenie:** rozhodol **resubmit formulár** (`vendors.paddle.com/request-domain-approval`), nie odpovede na e-mail — tie reviewer podľa všetkého nikdy nevidel. Web bol compliant celý čas; slepé úpravy už compliant stránky by boli stratou času. Pripravený Gmail draft (`r2148115676784477999`) je **neaktuálny, neposielať**.
   - Historický priebeh (ponechané pre kontext):
   - ⏳ **2026-07-08: 1. re-review domény.** Prvá recenzia zamietnutá (chýbal verejný cenník) → `/pricing` + `/refunds` nasadené, odpoveď na e-mail odoslaná, **Resubmit domain for review** kliknutý.
   - ❌ **2026-07-09 15:07: DRUHÉ zamietnutie** (sellers@paddle.com, tá istá generická šablóna „Action needed: confirm pricing on lexinova.fun" — nepomenúva konkrétny dôvod). Prišlo ~1 h po druhej e-mail odpovedi.
   - 🔎 **Diagnostika (2026-07-09) — web bol preukázateľne compliant na všetky 4 body:**
     - Verejný cenník `https://lexinova.fun/pricing` → **HTTP 200**, dostupný bez loginu, názov produktu + čo obsahuje + presné ceny €4,99/mes · €39,99/rok. ✅
     - Konzistentná cena: **testovacia faktúra z 5.7. potvrdzuje tax-INCLUSIVE** — kupujúci zaplatil presne **€4,99 (inc. tax)** = subtotal €4,06 + VAT €0,93. Web „vrátane DPH" tak **sedí** s checkoutom. ✅
     - Daňová transparentnosť: „Ceny sú vrátane DPH / VAT included" je pravdivé (daň zahrnutá, nie pridaná navrch) — vetu „taxes calculated at checkout" NEtreba (protirečila by tax-inclusive realite). ✅
     - Trial: všade „bez skúšobnej doby / no free trial". ✅
   - ~~Gmail draft odpovede pre sellers@paddle.com (`r2148115676784477999`)~~ — **neaktuálny, neposielať** (doména schválená 2026-07-10).
   - Doména: `lexinova.fun`
   - Cenová stránka: `https://lexinova.fun/pricing` ✅ (2026-07-08)
   - Terms of service: `https://lexinova.fun/terms` ✅
   - Privacy policy: `https://lexinova.fun/privacy` ✅
   - Refund policy: `https://lexinova.fun/refunds` ✅ (2026-07-08)
   - Všetky štyri sú odkazované z pätičky a `/pricing` je aj v hlavnej navigácii.
2b. [x] **Overenie účtu / KYC** ✅ **2026-07-10** — identity check cez overovacieho partnera Paddlu prešiel. Paddle potvrdil: „You can now start collecting payments with Paddle as soon as you are ready."

2c. [x] **Payout verification** ✅ **2026-07-13** — platba/payout na Paddle overená. Účet je plne funkčný vrátane výplat.

3. [x] **Live produkt + ceny:** „LexiNova PLUS", Monthly €4,99 (`pri_01kw6mj3tvbyekxmh0xez2exk3`, custom ID `plus-monthly`) + Annual €39,99 (`pri_01kw6mzcephazys90em9pjmjya`, custom ID `plus-annual`) — vytvorené na live účte, **Trial = žiadny overené v dashboarde 2026-07-08** ✅. (Tax category = SaaS; tax = Account default over pri kroku 4.)
4. [x] **Checkout settings (live)** ✅ 2026-07-10 — Approved domain + Default payment link (`/profile`) + Statement descriptor `LEXINOVA`; overené úspešným live checkoutom.
5. [x] **Live webhook** ✅ 2026-07-10 → `https://lexinova.fun/api/webhooks/paddle`, eventy `subscription.*` + `transaction.completed` + `transaction.payment_failed`.
   - ⚠️ **Stalo sa presne varované:** prvý nasadený secret nesedel → Paddle dostával **401** a PLUS sa po platbe neaktivoval. Oprava: skopírovať **celý** Secret key z destinácie → Cloud Run → Deploy → v Notification logu **Retry** zaseknutých eventov (v poradí `payment_failed` → `completed` → `created` → `activated`, aby `past_due` neprepísal aktívny stav).
6. ~~Revoke live API kľúča~~ — vynechané na žiadosť užívateľa (2026-07-08), existujúci live kľúč sa použije.
   - ⚠️ Pozn. (2026-07-10): Paddle ukáže hodnotu API kľúča **len raz, pri vytvorení**. Ak nie je nikde uložená, treba spraviť **Create API key** (permissions aspoň `transactions`, `subscriptions`, `customers` — kód volá portal session aj cancel) a starý revokovať.

7. [x] **Cloud Run env (live)** ✅ 2026-07-10 — všetky `PADDLE_*` prepnuté na live hodnoty, `BILLING_ENABLED=true`, duplicitný `PADDLE_CLIENT_TOKEN` (riadok 25) zmazaný. Webhook secret bolo treba raz opraviť (viď krok 5).
   - Ponaučenia (platia aj nabudúce): vloženie `.env` bloku do konzoly **pridáva riadky, neprepisuje** rovnomenné → vznikajú duplicity s neurčitým poradím. `gcloud`: použiť `--update-env-vars`, **nikdy `--set-env-vars`**. `PADDLE_API_BASE` nesmie existovať (prebil by `PADDLE_ENV`). `DEBUG` netreba — default je `false` (`runtime.py:133`). Zmena env vytvorí novú revíziu, ale NEnasadí nový kód (na to treba push do `main` → `cloudbuild.yaml`).
   - 🔎 `GEMINI_API_KEY` má netypický formát `AQ.Ab8...` (nie `AIzaSy...`) — funguje (AI generovanie prešlo E2E 2026-07-10), netreba riešiť.

7b. ~~🔐 **Rotovať Groq a Anthropic API kľúče**~~ — **VYNECHANÉ na žiadosť užívateľa (2026-07-13).** Hodnoty sa 2026-07-10 objavili len na screenshotoch v tomto chate (nie verejne, nie v git histórii), Anthropic účet je na Evaluation (free) pláne s „Last used: Never" → reálne riziko vyhodnotené ako nízke. Pôvodný postup pre prípad zmeny rozhodnutia: nový kľúč v konzole providera → nahradiť na Cloud Run → starý revoke.
   - ⚙️ (voliteľné, nesúvisí s bezpečnosťou) na Cloud Rune je `ANTHROPIC_API_KEY` **duplicitne na riadku 22** s rôznymi hodnotami — pri najbližšej úprave env stojí za 30 s zmazať duplicitu.
8. [x] **E2E test na live s reálnou kartou** ✅ 2026-07-10 — účet `lipnicanova.dominika@gmail.com`: 1. pokus o platbu zamietnutý kartou (`payment_failed` — dobrý test dunning eventu), 2. pokus €4,99 prešiel (txn `txn_01kx6r8t20ve8t6r1csg3t14e2`, faktúra 40610-10001), webhooky po oprave secretu doručené, PLUS aktivovaný, zrušenie cez /profile, **full refund Complete**. Ekonomika transakcie: €4,99 = €0,93 DPH + €0,69 Paddle fee → **netto ~€3,37**.
   - [x] ✅ **2026-07-13 — testovacia subscription zrušená a overená v Paddle → Subscriptions.** Žiadna ďalšia platba sa nestrhne.
9. [ ] (voliteľné) vlastná doména → pridať do CORS `FRONTEND_ORIGIN` + Paddle Approved domain.

---

## 💰 Komerčné hodnotenie (2026-07-10, po go-live)

**Verdikt: technicky aj procesne pripravená zarábať (predaj PLUS je ostrý), ale bez distribúcie to bude hobby-príjem. Cesta k peniazom = úzke zacielenie SK/CZ + učiteľský kanál + SEO, nie súboj s Duolingom.** Prvý míľnik: **50 platiacich = ~€170/mes netto** + 1 marketingová aktivita týždenne.

**Silné stránky:** prevádzková zrelosť (testy, E2E, monitoring, admin, GDPR, Grafana) nadpriemer; ekonomika zdravá — náklady ~0, z €4,99 zostáva ~€3,37 netto, break-even pri nule; Paddle MoR rieši EÚ DPH; diferenciátor = AI z vlastných materiálov (fotka učebnice, YouTube video).

**Riziká:** (1) **AI spoľahlivosť je najslabší článok a zároveň jadro platenej hodnoty** — free tiery, 429 kaskády, nefunkčný Groq fallback, Anthropic eval plán; platiaci PLUS s 502 z „neobmedzeného AI" zruší predplatné → AI backlog položky sú priorita č. 1 pred propagáciou. (2) Trh brutálne konkurenčný — globálne nevyhráme, lokálne (SK/CZ) áno. (3) Distribúcia zatiaľ neexistuje.

**Odporúčania podľa dopadu:**
1. Stabilita AI reťazca (backlog nižšie) + zvážiť malý platený Gemini budget — zaplatí sa z jednej mesačnej platby
2. **Kanál učiteľ → trieda (B2B2C):** učiteľ zdieľa sadu žiakom kódom/linkom; 1 učiteľ = ~25 účtov; v SK školstve prázdny priestor — najväčšia páka na rast
3. **SEO obsah:** predgenerované verejné stránky „slovíčka na tému X" s CTA na registráciu (generátor už existuje)
4. **Spaced repetition (SRS):** nadstavba nad `knowledge_level`, drží retenciu; môže byť PLUS-only
5. **Merať aktivačný funnel:** registrácia → 1. kategória → 1. test → návrat 7. deň (Grafana ukazuje MRR, nie kde ľudia odpadávajú)
6. Ľahká gamifikácia (streak, denný cieľ)

---

## 🔜 Kde pokračovať (stav k 2026-08-19 večer)

> Z auditu 19. 8. (24 bodov) je hotových 22. Všetko nižšie je otvorené.
> Posledný nasadený stav: **v1.0.414**. Duplicity v dátach vyčistené skriptom
> (7 skupín, 8 riadkov) — ⚠️ heslo k Supabase bolo v histórii shellu, **rotovať**.

**Najbližší krok — overiť produkciu po nasadení.** Testy nekontrolujú vzhľad ani JS,
a v poslednej vlne šlo veľa vizuálnych zmien (spoločná hlavička, presun CSS/JS do
súborov, admin, osemsmerovka). Prejsť: nástenka → kategória → test → opakovanie →
osemsmerovka → triedy → profil → admin. Konkrétne pozrieť:
- či po dokončení testu sedia čísla na nástenke **na prvý pokus** (oprava zápisu 36 → 16 príkazov),
- `Server-Timing` na `/api/user/stats` (koľko z toho je `db` a koľko `app`),
- či sa v osemsmerovke dá slovo označiť dvoma ťuknutiami aj klávesnicou.

**Výkon (P2)**
- [ ] Statika bez CDN (153 ms). Súvisí s regiónom, riešiť spolu s ním.

**Rozloženie a obsah (P2/P3)**
- [ ] Landing nemá žiadny dôkaz, že to funguje — chýbajú screenshoty appky (miesto na ne je pripravené na `/pre-ucitelov`, čaká na obrázky).
- [ ] Limit 30 slov na kategóriu — zmerať, koľko Free účtov naň naráža.
- [ ] Slovíčko je len dvojica — chýba príkladová veta a slovný druh (AI ich vie dať v tom istom volaní).
- [ ] Jeden režim testovania — najlacnejší prírastok je výber zo štyroch možností.

**Odložené rozhodnutím**
- [ ] Presun Cloud Runu do EU regiónu (~112 ms na dotaz). Detaily v [Infraštruktúra] nižšie v tomto súbore.

**Zvyšky**
- [ ] Náhľad pred uložením má len textová cesta; **fotka a video** ukladajú rovno.
- [ ] Mobil nikto neoveril na skutočnom telefóne — kritické sú graf aktivity s 30 popiskami a mriežka osemsmerovky na 360 px.

---

## Ďalšie nápady / backlog
- [x] **Overovanie spojenia už nestojí round-trip na každom requeste** ✅ 2026-08-20
  - `pool_pre_ping=True` posielal `SELECT 1` pred **každým** vypožičaním spojenia. Nad vzdialenou databázou (~112 ms na cestu) sa tá daň platila aj vtedy, keď to isté spojenie odišlo pred sekundou.
  - Ping ostáva, ale beží len keď spojenie **ležalo dlhšie než 30 s** (`checkin` si zapamätá čas, `checkout` sa rozhodne). Pri mŕtvom spojení sa vyhodí `DisconnectionError`, SQLAlchemy ho zahodí a operáciu zopakuje — presne ako pôvodný pre-ping, len bez ceny v horúcej ceste.
  - Spojenia neumierajú medzi dvoma requestami za sebou, ale keď Cloud Run uspí inštanciu alebo Supabase zavrie nečinné spojenie — a to hranica 30 s pokrýva.
  - Testy `tests/test_connection_ping.py` (3): že `pool_pre_ping` sa nevrátil, že hranica je v rozumnom rozsahu a že čerstvé spojenie sa neoveruje druhýkrát.
- [x] **Počet kategórií ako poddotaz** ✅ 2026-08-20 — bol to samostatný dotaz, teraz ide v tom istom SELECTe nad slovami (korelovaný poddotaz databázu nestojí nič navyše). Štatistiky: **6 dotazov**, kategórie 3, celá nástenka jedným requestom **~9 vrátane prihlásenia** — pred touto vlnou to bolo 12 dotazov, tri requesty a tri pingy.
  - **Čo vo výkone ostáva:** studený štart Cloud Runu (`min-instances`, stojí peniaze) a presun do EU regiónu. Všetko ostatné v kóde je vyčerpané — ďalšie zrýchlenie je už len o vzdialenosti k databáze.
- [x] **Nástenka jedným requestom namiesto troch** ✅ 2026-08-20
  - Paralelizácia z 19. 8. narazila na strop: merania na produkcii ukázali, že **tri súbežné requesty trvajú 2220 ms každý, kým samostatný 1076 ms** — inštancia súbežnosť neutiahne. K tomu má každý request vlastnú réžiu (~345 ms nameraných na triviálnom `/api/user`), takže sa platila trikrát.
  - Nový **`GET /api/dashboard`** vráti používateľa, štatistiky aj kategórie naraz. Telá pôvodných endpointov sú vytiahnuté do `build_user_payload`, `build_stats_payload` a `build_categories_payload`, takže obe cesty vracajú **to isté z toho istého kódu** — test to porovnáva pole po poli, aby sa nemohli rozísť.
  - **Pôvodné tri endpointy ostávajú** — používajú ich iné stránky, offline cache aj čiastočné obnovenie po vytvorení či zmazaní sady.
  - Offline vetva sa zjednodušila: keď zlyhá jeden request, vykreslí sa všetko z `localStorage` naraz (predtým tri samostatné `catch` bloky).
  - Overené v prehliadači: nástenka pošle **jediné** volanie `/api/dashboard`, vykreslí čísla, kategórie aj identitu; pri zlyhaní naskočí offline banner a dáta z cache. Testy `tests/test_dashboard_endpoint.py` (4) → spolu **458**.
  - **Čo z výkonu ostáva:** `pool_pre_ping` (jeden round-trip navyše na request), 7 dotazov v štatistikách (dá sa na 3–4), studený štart Cloud Runu, a presun do EU regiónu — ten je stále najväčší.
- [x] **Kanál pre učiteľov: prvá trieda zadarmo + vlastná stránka** ✅ 2026-08-20 (P3 z auditu)
  - **Rozhodnutie 2026-08-20:** triedy boli celé za PLUS, takže učiteľ musel zaplatiť skôr, než zistil, či mu appka sadne — a pritom práve on privedie 25 používateľov naraz. **Jedna trieda je odteraz aj na Standard pláne** (`CLASS_LIMIT_FREE`), ďalšie vyžadujú PLUS.
  - **Prehľad pokroku (`/overview`) prestal byť PLUS-only** — bezplatná trieda bez neho by nedávala zmysel, učiteľ by videl len kód a zoznam mien.
  - Nástenka ukazuje odkaz na Triedy každému okrem žiackych (pseudonymných) kont; stránka Triedy má namiesto cedule „Triedy sú PLUS funkcia" vetu o tom, že prvá je zadarmo.
  - **Nová stránka `/pre-ucitelov`** (a `/en/pre-ucitelov`): tri kroky (založ · rozdaj kód · priraď a sleduj), čo z toho učiteľ má, koľko to stojí, dve CTA. V sitemape, s canonical aj hreflang. Na hlavnej stránke pribudol blok, ktorý na ňu vedie, a odkaz v pätičke.
  - **Žiadne vymyslené dôkazy.** Používateľ potvrdil, že appku zatiaľ v triede nikto nepoužíva, takže text nesľubuje referencie ani čísla — hovorí len o tom, čo appka vie. Miesto na screenshot triedy je pripravené s rámom a popisom; čaká na obrázok.
  - Testy `tests/test_for_teachers.py` (6) — vrátane toho, že **text a kód si neodporujú**: keď stránka tvrdí „prvá trieda zadarmo", `CLASS_LIMIT_FREE` musí byť 1. Testy tried prepísané na novú politiku. Spolu **454**.
- [x] **Cenník: prepínač Mesačne / Ročne** ✅ 2026-08-20 (P3 z auditu)
  - Ročná cena (39,99 = úspora 33 %) bola len v drobnom texte pod mesačnou, hoci je to plán, ktorý chceme predať. Teraz je nad kartami prepínač a **ročné je predvolené**; voľba sa pamätá, aby sa cena nevracala na mesačnú pri každom otvorení.
  - Pri ročnom sa ukazuje aj mesačný ekvivalent („vychádza to na €3,33 mesačne") — číslo, ktoré si človek porovnáva.
  - **„Bez skúšobnej doby" povedané raz a vecne.** Bolo trikrát, vždy negatívne, na najcitlivejšom mieste stránky. Podnadpis teraz hovorí, čo platí: „Standard je zadarmo navždy — vyskúšaj ho bez karty."
  - Prepínač je v oboch jazykových verziách a overený v prehliadači (SK aj EN, prepnutie tam aj späť, uložená voľba).
- [x] **AI pomenúva kategórie v jazyku používateľa** ✅ 2026-08-20 (P3 z auditu)
  - Slovenský prompt vracal „Airport Verbs" s anglickým popisom, takže v zozname stáli vedľa seba „Talianske slovíčka na dovolenku" a „Vocabulary for a Holiday".
  - Prompt teraz výslovne žiada názov aj popis v jazyku, **do ktorého sa prekladá** — to je jazyk používateľa. Cesty z fotky a z videa to už mali, len to nebolo vidieť z textu promptu; doplnená poznámka, aby to bolo jednoznačné.
  - Náhľad pred uložením už názov aj tak dovoľuje prepísať, takže ide o pohodlie, nie o poistku.
- [x] **História aktivity sa agreguje v databáze** ✅ 2026-08-20
  - `get_history_stats` načítavalo **všetky** riadky `test_sessions` používateľa a spočítalo ich v Pythone — objem rástol s používaním appky, hoci graf potrebuje 30 dní.
  - Teraz jeden `GROUP BY` po dňoch v okne **400 dní** (dosť aj na ročnú sériu) plus samostatný `COUNT` na celkový počet testov — ten je „za celý čas", takže do okna nepatrí. Dva dotazy bez ohľadu na to, koľko testov používateľ absolvoval.
  - Testy `tests/test_history_window.py` (4) — strážia **počet dotazov**, sériu dní naprieč agregáciou aj to, že opakovanie sa ráta do aktivity, ale nie do úspešnosti.
- [x] **Rozloženie nástenky** ✅ 2026-08-20 (P2 z auditu)
  - Bolo to „rad 2 dlaždice, potom 4, potom osamelá 1". Príčinou bol pruh rozloženia znalosti (`grid-column: 1 / -1`) uprostred mriežky — lámal riadky. Presunutý za dlaždice; z dvoch mriežok za sebou je jedna, riadky sú **4 + 3** a pruh je celý pod nimi.
  - **Kategórie sú vyššie:** sekcia „Tvoje kategórie" bola až za slabými kategóriami, grafom aj odznakmi. Teraz idú hneď za súhrnnými dlaždicami a podrobné štatistiky sú pod nimi. Na 1280 px sa nadpis posunul z 643 px na 513 px.
- [x] **FontAwesome 271 kB → 9 kB** ✅ 2026-08-20 (P2 z auditu)
  - Appka používa **51 ikon**, ťahala kvôli nim celý balík: CSS 100 kB + solid 147 kB + regular 24 kB.
  - `scripts/build_icon_subset.py` prejde šablóny aj skripty, nájde použité názvy, vytiahne k nim kódy z pôvodného CSS a vygeneruje `app/static/css/icons.css` (3,7 kB) plus dva orezané fonty (4,8 + 0,7 kB). **Spolu 9,1 kB — úspora 261 kB.** Triedy `fa-solid fa-trash` ostávajú, v šablónach sa nič neprepisovalo.
  - **Subsetuje sa z `.ttf`, nie z `.woff2`** — woff2 má transformovanú tabuľku `glyf` a fontTools ju odmieta („not enough 'glyf' table data"). Výstup je woff2.
  - Pôvodný FontAwesome ostáva vo `vendor/` ako zdroj pre generovanie, ale nič ho už neservíruje.
  - **Tiché riziko:** nová ikona v šablóne sa bez opätovného spustenia skriptu jednoducho nevykreslí — nič nespadne, v konzole nič nie je. Preto `tests/test_icon_subset.py` (4 testy) kontroluje, že každá použitá ikona je v podmnožine, že fonty sú malé a že žiadna šablóna neťahá celý balík.
  - `fonttools` je vývojová závislosť (`requirements-dev.txt`), import je v skripte lokálny, aby testy prešli aj bez nej. SW cache **v58 → v59**.
- [x] **Zoznam slovíčok: hľadanie a stránkovanie** ✅ 2026-08-20 (P2 z auditu)
  - Kategória so 139 slovami vykreslila 139 riadkov naraz a nájsť v nich jedno slovo sa dalo len očami.
  - **Hľadanie ignoruje diakritiku aj veľkosť písmen** („cerven" nájde „červený") a hľadá v origináli aj preklade. Diakritika sa zahadzuje len pri porovnaní, v dátach ostáva.
  - **Vykresľuje sa po 50** s pätičkou „Zobrazených 50 zo 139" a tlačidlom na ďalšiu dávku. Slová sa aj tak načítajú všetky jedným dotazom, takže hľadanie beží v prehliadači a funguje offline — žiadna cesta do databázy navyše.
  - **„Vybrať všetko" znamená všetko, čo prešlo filtrom**, nie len prvú stránku: skryté riadky sa najprv dokreslia. Pri tom sa ukázala chyba, ktorú by testy nechytili — dokreslenie volá `updateBulkUI()`, ktorá `selectAll.checked` prepíše na false, takže zámer treba zapamätať pred prekreslením.
  - Zároveň opravené, že **prepnutie EN/SK neprekreslilo riadky** (skladajú sa v JS). Jazyk drží premenná, nie `localStorage` — prepínač volá `setActiveLanguage()` ešte pred zápisom voľby, takže z `localStorage` by sa čítal predchádzajúci jazyk.
- [x] **Chart.js sa načíta až keď treba** ✅ 2026-08-20 (P2 z auditu)
  - 204 kB sa sťahovalo pri každom načítaní nástenky, aj keď graf aktivity je hlboko pod ohybom. Knižnica sa teraz vloží až keď sa prvý graf priblíži na 200 px k oknu (`IntersectionObserver`); bez podpory observera sa kreslí rovno.
  - Chyba pri načítaní ide do konzoly ako warning — pôvodne som ju tichým `catch` zamlčal, čo ma pri overovaní stálo pol hodiny.
  - **Overené inak než zvyšok:** panel prehliadača v tomto prostredí nekompozituje snímky, takže `IntersectionObserver` v ňom callback nikdy nespustí. Overený je teda vlastný kód (načítanie na požiadanie + vykreslenie) s podstrčeným observerom; samotné spúšťanie pri scrollovaní treba pozrieť na produkcii.
  - V precache service workera knižnica ostáva — sťahuje sa raz na pozadí pri inštalácii, nie pri každom načítaní stránky, a offline režim ju potrebuje.
- [x] **Osemsmerovka sa dá hrať bez myši** ✅ 2026-08-19 (P1 prístupnosť z auditu)
  - Druhá cesta k tomu istému: **dve ťuknutia** — prvé písmeno a posledné. Potvrdzovacie tlačidlo netreba, čiara medzi dvoma bodmi je jednoznačná (slová ležia len v priamych smeroch). Ťuknutie na to isté písmeno výber zruší, mimo priamky začne nový.
  - **Klávesnica robí to isté:** šípky posúvajú po mriežke, Enter označí začiatok aj koniec, Escape ruší; počas výberu je vidieť, kam by slovo siahalo. Mriežka má `role="grid"` a **roving tabindex** — tabulátor ju preskočí jedným krokom namiesto ~200.
  - Ťah myšou aj prstom ostal nedotknutý; klik bez pohybu sa rozpozná ako ťuknutie, takže obe cesty žijú vedľa seba bez ďalšieho poslucháča udalostí.
  - Overené v prehliadači na všetkých troch cestách (dvojťuk, klávesnica, ťah).
- [x] **Skript na zlúčenie duplicít padal pri zápise** ✅ 2026-08-19
  - `NoReferencedTableError` a potom `InvalidRequestError: expression 'User' failed to locate a name`. Skript si importoval len `Word`, ale SQLAlchemy si pri zápise **zoraďuje tabuľky podľa cudzích kľúčov** a vzťahy rozlúšťa **podľa názvu triedy** — s neúplnou sadou modelov to padne. Zákerné na tom je, že **čítanie prejde** a chyba príde až na commite, takže nasucho vyzeralo všetko v poriadku.
  - Nový `app/models/registry.py` načíta všetky modely naraz; skripty si ho importujú namiesto ťahania celého FastAPI. Nič sa odtiaľ neimportuje späť, takže nevzniká cyklus.
  - Overené naostro proti dočasnej databáze: 5 slov → 3, `subject` má `predmet, tema` a spočítanú históriu.
  - ⚠️ **Na produkcii sa pri prvom (padnutom) behu nič nezmenilo** — transakcia spadla pred commitom.
- [x] **Po teste sa čísla na nástenke aktualizovali až po viacerých obnoveniach** ✅ 2026-08-19 (nález používateľa)
  - **Príčina:** `POST /words/test/submit` načítaval **každé slovo vlastným dotazom** a SQLAlchemy ho potom zapisovala **vlastným UPDATE-om**. Pri teste na 21 kartičiek to bolo vyše 40 ciest do databázy; pri nameraných ~112 ms na cestu vyše dvoch sekúnd. Odchod na nástenku čaká na uloženie **najviac 5 s** a potom odíde tak či tak — dashboard sa teda stihol načítať skôr, než zápis dobehol, a ukazoval stav spred testu.
  - **Oprava:** slová aj `word_progress` sa načítajú jedným dotazom (`id.in_(…)`) a zapíšu jedným hromadným príkazom (`db.execute(update(Word), rows)`). **Zmerané: 36 → 16 príkazov, z toho UPDATE 21 → 1.**
  - **Pozor na `expire_all()`** — pri hromadnom zápise treba expirovať **cielene** len zapísané slová. `expire_all()` by zahodilo aj neuložené zmeny `WordProgress` (pokrok pri sadách triedy), takže by sa žiakom prestal ukladať pokrok.
  - **`executemany_mode="values_plus_batch"` na engine** (len pre Postgres, SQLite v testoch ten parameter nepozná): jeden `executemany` ešte neznamená jednu cestu — psycopg2 predvolene posiela riadky po jednom. S `execute_batch` odíde dávka naraz.
  - Testy `tests/test_submit_batching.py` (2) — strážia **počet príkazov**, nie čas: čas závisí od siete, počet ciest od kódu. Spolu **436**.
- [x] **Detail triedy sa nedal nájsť** ✅ 2026-08-19 (P1 z auditu — inak, než audit tvrdil)
  - Audit hlásil, že detail chýba („nedá sa ňou preklikať, nie je odkiaľ priradiť sadu ani vidieť žiaka"). **V skutočnosti existuje** — klik na kartu otvorí zoznam žiakov, priraďovanie sád aj prehľad pokroku, a backend má na to kompletné endpointy. Karta to len nijako nenaznačovala.
  - Doplnená výzva „Otvoriť žiakov a sady →" priamo na karte a **automatické otvorenie, keď je trieda jediná**. Keď recenzent funkciu nenájde, pre používateľa neexistuje — takže to bola chyba, len na inom mieste.
- [x] **Zvyšné inline CSS/JS von zo šablón** ✅ 2026-08-19 — `flashcard_test` a `category_words` mali v skriptoch šablónové výrazy, takže sa najprv oddelili serverové dáta do malého inline bloku `PAGE_DATA` a zvyšok (78,6 kB) šiel do `page-*.css` / `page-*.js`. SW cache **v57 → v58**. Testy `test_flashcard_leave_guard.py` kontrolujú poistky proti odchodu z testu — po presune čítajú obsah `page-*.js`, nie HTML.
- [x] **Admin, presun inline CSS/JS a funkčné medzery kartičiek** ✅ 2026-08-19 (dokončenie P0 dizajnu + P1 z auditu)
  - **Admin bol piaty variant** — nenačítaval ani `design-system.css`, farby mal natvrdo v hexoch a tmavý režim sa nemal ako zapnúť (pravidlá `[data-theme="dark"]` tam boli, ale atribút nikto nenastavil). Teraz má spoločnú hlavičku, farby z tokenov a boot tmavého režimu ako zvyšok appky.
  - **Inline CSS/JS von zo šablón: 169 kB.** Päť stránok (nástenka, opakovanie, admin, profil, triedy) nemalo v skriptoch **ani jeden** šablónový výraz, takže presun bol mechanický: `page-*.css` a `page-*.js` so `?v={{ app_version }}`. Poradie spustenia ostalo — súbor sa linkuje presne tam, kde bol inline blok. **Krátke skripty ostávajú inline zámerne:** boot tmavej témy musí bežať skôr, než sa vykreslia prvé pixely, inak stránka blikne nabielo.
    - Zostáva ~100 kB CSS a ~148 kB JS v ostatných šablónach; `flashcard_test` a `category_words` majú v skriptoch Jinja (`{{ category.id }}`), takže potrebujú najprv oddeliť serverové dáta do malého inline bloku.
    - SW cache **v56 → v57** + desať nových súborov do precache. Bez toho by offline režim ukázal stránky bez štýlov a bez JS — HTML by z cache prišlo, ale odkazy by nemali odkiaľ.
  - **Kartičky sa dajú ohodnotiť klávesnicou** — `1` = Neviem, `2` = Viem, obe až po odkrytí prekladu (inak by sa dalo odpovedať naslepo). **Šípka doprava ostáva „Neviem"** — rozhodnuté používateľom 2026-08-19, audit navrhoval opak.
  - **Výsledok už neklame.** Po ukončení testu po jednej kartičke z 21 hlásil „100 % · Výborné!". Pri predčasnom ukončení sa teraz ukáže **počet („2/3 z balíka")**, nie percento — z jednej kartičky sa percento poctivo spočítať nedá. Pribudol **zoznam slov, ktoré používateľ nevedel**, aj s prekladom a tlačidlom „Precvičiť len tieto" (vedie na test neznámych slov kategórie — tie slová sú po teste presne na tejto úrovni, takže netreba nový endpoint).
  - **„1 žiakov" → „1 žiak".** Slovenčina má tri tvary (1 žiak, 2–4 žiaci, 5+ žiakov), angličtina dva.
  - **Natívne „Choose File / No file chosen"** píše prehliadač podľa jazyka systému a preložiť sa nedá. Pole ostáva v DOM (formulár aj klávesnica ho potrebujú), ale je odsunuté z dohľadu a klikáme naň cez `<label>`; názov súboru dopĺňa JS. Fokus je vidieť na tlačidle (`:focus-visible + .file-btn`).
  - **Stav len farbou** — preverené, neplatí to: pruh rozloženia aj koláčiky na kartách majú pri farbe aj text („Neviem 😕", „Viem ✅") a číslo. Nechané tak.
  - Overené v prehliadači na kópiách siedmich stránok: externé `page-*` súbory sa načítajú, funkcie z nich sú definované, admin číta dátumy po slovensky, klávesy 1/2 zapisujú odpoveď a predčasný výsledok ukáže „2/3 z balíka" so zoznamom chybných slov. Testy 434.
- [x] **Jedna hlavička a jedny komponenty naprieč appkou** ✅ 2026-08-19 (P0 z auditu 19. 8., prvá vlna)
  - **Nález:** „štyri rôzne dizajny v jednej aplikácii". Nástenka mala tmavý panel s logom, detail kategórie obrovský gradientový nadpis a žiadnu navigáciu, test kartičiek vlastnú lištu vnútri karty, Opakovanie systémový `<select>` a oranžové tlačidlo, ktoré sa inde nevyskytovalo.
  - **Príčina:** hlavičku malo každé z tých miest zapísanú vo vlastnom `<style>`. Kópie boli takmer rovnaké — a preto sa nenápadne rozišli: šírka 1000 / 1100 / 1200 px, medzera .4 vs .75 rem, iné zaoblenie tlačidiel.
  - **Nový `app/static/css/app-shell.css`** drží hlavičku, logo, `.icon-btn`, `.lang-btn`, mobilné menu a polia (`.app-input`, `.app-select`). Šírku obsahu si stránka nastaví premennou `--shell-width`, nie kópiou pravidla. Farby a tiene ostávajú v `design-system.css` — shell je len o prvkoch, ktoré sa opakujú.
  - **Odstránených 54 duplicitných CSS pravidiel** zo štyroch šablón (nástenka, opakovanie, triedy, profil). Odstraňovali sa **len pravidlá na najvyššej úrovni** — tie isté selektory sa používajú aj vnútri `@media` (napr. `.menu-toggle { display: block; }` pre mobil) a tie musia zostať.
  - **Detail kategórie** dostal rovnakú hlavičku ako zvyšok appky namiesto gradientového nadpisu s e-mailom pod ním.
  - **Test kartičiek** zámerne **nemá plnú navigáciu** — je to sústredená obrazovka a odchod uprostred testu stráži potvrdzovací modál. Dostal však logo a rovnaké tlačidlá, takže už nevyzerá ako iný produkt; odchod cez logo ide tiež cez `goDashboard`, teda cez ten istý modál.
  - **Opakovanie:** natívne `<select>` nahradil zdieľaný `.app-select`, oranžový gradient tlačidla „Automaticky" značkový (`var(--grad)`) — bola to jediná taká farba v celej appke.
  - SW cache **v55 → v56** + `app-shell.css` do precache, inak by ho offline režim nemal odkiaľ vziať.
  - Overené v prehliadači na kópiách štyroch stránok: hlavička 64 px a rovnaké tlačidlá všade, popisky sa prepínajú EN/SK vrátane názvov pre čítačky obrazovky. Testy 434.
  - **Zostáva z tohto bodu:** admin je piaty variant a zatiaľ sa neriešil; inline CSS/JS (~79 kB na stránku) ostáva v šablónach — presun do súborov je samostatná úloha, tu išlo o vizuálnu jednotu.
- [x] **Jazyk, tón a drobnosti naprieč appkou** ✅ 2026-08-19 (P1 + P2 z auditu 19. 8.)
  - **Anglické zvyšky v slovenskom rozhraní.** „Tested: 3x / Success: 0%" pri každom slovíčku, „Original:" a „Translation:" v Opakovaní, „All words" v nadpise testu aj v hláške po prehratí. Všetko sa skladá v JS, takže `data-en/data-sk` na ne nesiahli — texty musia byť v kóde. V `repeat.html` na to pribudol `uiLang()`, ktorý číta jazyk **v momente použitia**, nie pri načítaní (inak by prepnutie EN/SK na tie texty nezabralo).
  - **Jednotné tykanie.** Landing a nástenka tykali, prihlásenie a profil vykali. Zjednotené na tykanie vrátane chybových hlášok zo servera. **Právne stránky ostávajú vo vykaní zámerne** — tak sa právne texty píšu. Pozor na rod: slovenský minulý čas je rodovo príznakový, takže „Dosiahol si maximum" by oslovilo len mužov → všade prítomný čas („Máš maximum {N} kategórií").
  - **Jeden názov pre návrat.** Bolo to „← Dashboard" (test), „← Nástenka" (triedy), „Späť" (kategória) a „Dashboard" (profil) — štyri názvy pre jedno miesto. Teraz SK „Nástenka" / EN „Dashboard" všade.
  - **Tituly stránok** zjednotené na `{Stránka} – LexiNova` (kolísalo to medzi pomlčkou, zvislítkom a bodkou); štyri stránky appky mali anglický titul aj v slovenčine.
  - **E-mail zmizol z premietaných obrazoviek.** Detail kategórie aj hlavička testu ukazovali `lipnicanmilos@gmail.com` — presne to učiteľ premieta triede. Server teraz posiela meno a e-mail je len záloha, keď meno chýba.
  - **Prístupnosť:** `aria-label` + bublina na ikonové tlačidlá (zdieľať/premenovať/zmazať sadu, upraviť/zmazať slovíčko, zmazať triedu, odobrať žiaka, zvonček). Prekladajú sa spolu s rozhraním — na dashboarde cez nový `data-en-label`/`data-sk-label`, lebo ikonové tlačidlo nemá text, ktorý by sa dal prepísať.
  - **AI okná už nepýtajú ISO kódy.** Šesť textových polí s `en`/`sk` nahradili rozbaľovacie zoznamy s názvami jazykov (13 jazykov). **Bez vlajok zámerne** — emoji vlajku Windows vykresľuje ako prázdny štvorček, rovnaký problém už raz riešili kartičky.
  - **Drobnosti:** posledný `console.log` z produkcie preč · admin vypisuje dátumy `sk-SK` (bolo `10/11/2025, 11:32:47 PM` v slovenskom rozhraní) · séria „Opakovania" sa v grafe ukáže, len keď v okne naozaj niečo je (legenda inak ukazovala stĺpec, ktorý nikde nebol) · akčné ikonky na karte kategórie majú vyhradené miesto, takže pri prejdení myšou už neprekryjú názov.
  - Testy: 434 (bez zmeny — ide o texty a CSS). Overené v prehliadači na kópii dashboardu: popisky sa prepínajú EN/SK aj na ikonových tlačidlách, jazykové zoznamy posielajú správne kódy, náhľad AI sady funguje s nimi.
  - **Otvorené z auditu:** zjednotenie dizajnu (P0), klávesnica pre Viem/Neviem a zoznam chybných slov vo výsledkoch, detail triedy so žiakmi, presun inline CSS/JS do súborov, FontAwesome a Chart.js, vyhľadávanie a stránkovanie v zozname slovíčok.
- [x] **Náhľad pred uložením AI sady** ✅ 2026-08-19 (dokončenie P0 „AI duplicity")
  - **Prečo:** vygenerované slová padali rovno do účtu. Používateľ nemal kde vyhodiť, čo nechce, ani premenovať kategóriu — a názvy AI vymýšľala v jazyku promptu, takže vedľa seba stáli „Talianske slovíčka na dovolenku" a „Vocabulary for a Holiday".
  - **Dva kroky namiesto jedného.** `/ai-preview` vygeneruje a **nič neuloží**, `/ai-save` uloží výber. AI kvóta sa odpočíta pri náhľade — tam vzniká náklad; uloženie je zadarmo a AI nevolá. Limit kategórií sa kontroluje na oboch miestach (medzi náhľadom a uložením mohol používateľ v inej karte založiť sadu).
  - **V náhľade:** zoznam s odškrtávaním (všetko zaškrtnuté), počítadlo „Uloží sa 3 z 5", hromadné označiť/odškrtnúť, pole na názov kategórie. Odškrtnuté slovo ostáva čitateľné, len prečiarknuté a stlmené — nie zmiznuté. Tlačidlo „Zahodiť" nezanechá v účte nič.
  - **Duplicity sa zlučujú už v náhľade** — v zozname na odsúhlasenie nemá svietiť to isté slovo dvakrát s iným prekladom.
  - Spoločná logika volania AI je v `_generate_words()`, takže `/ai-create` (pôvodná cesta, ukladá rovno) a `/ai-preview` sa nerozchádzajú. `/ai-create` ostáva funkčné pre prípadných klientov mimo dashboardu.
  - **Zatiaľ len textová cesta.** „AI z fotky" a „AI z videa" ukladajú rovno ako doteraz — náhľad pre ne je rovnaká práca na frontende, spraviť sa dá kedykoľvek.
  - Testy `tests/test_ai_preview.py` (5) → spolu **434**. Front-end overený v prehliadači na kópii dashboardu: odškrtnutie dvoch slov a premenovanie kategórie pošle na server presne dve slová s novým názvom.
- [x] **AI duplicity: jedna kartička s viacerými prekladmi** ✅ 2026-08-19 (P0 z auditu 19. 8.)
  - **Nález:** v kategórii vznikli `subject → téma` **aj** `subject → predmet` ako dve kartičky. Používateľ dostal to isté slovo dvakrát s iným „správnym" prekladom, druhý výskyt označil ako neznámy — odtiaľ „Success: 0 %" pri slovách, ktoré vie. Tichý zabijak retencie: vyzerá to, akoby sa neučil.
  - **Príčina:** kontrola existujúceho slova je dotaz do DB, ale session má **`autoflush=False`**, takže slovo pridané o riadok vyššie v tej istej dávke dotaz nevidel. Druhý výskyt sa preto uložil ako nový riadok. Navyše sa porovnávalo presne na znak, takže `border` a `Border` boli dve slová.
  - **Oprava pri ukladaní:** heslá kategórie sa načítajú **jedným dotazom** do mapy kľúčovanej bez ohľadu na veľkosť písmen (predtým 25 dotazov pri 25 slovách) a do tej istej mapy pribúdajú aj slová z práve spracúvanej dávky. Rovnaké heslo s iným prekladom sa **zlúči** — `téma, predmet` — namiesto prepísania alebo duplikátu. Platí to aj pre druhé generovanie do tej istej kategórie.
  - **Diakritika sa nezahadzuje.** „šport" a „sport" sú dve rôzne slová; kľúč rozlišuje len veľkosť písmen a medzery. Zlúčený preklad sa nepridá, ak by prekročil `VARCHAR(100)`.
  - **Prompt** teraz výslovne zakazuje opakované heslo s iným prekladom aj odvodené tvary vedľa základného (`border`/`borders`, `regular`/`regularly`) — to je jazyková úloha, patrí do promptu, nie do kódu (stemming by rozbil dvojice, ktoré sa učia zámerne).
  - **Staré dáta:** `scripts/merge_duplicate_words.py` — nasucho vypíše, čo by spravil, s `--apply` zlúči. Prežije riadok s bohatšou históriou, počty testov sa spočítajú (zlúčenie nesmie vyzerať ako reset pokroku).
  - Testy `tests/test_word_dedupe.py` (10) → spolu **429**.
  - **Nespravené z návrhu auditu:** obrazovka s náhľadom pred uložením (odškrtať slová, premenovať kategóriu). Je to samostatná UI práca a duplicitám už bráni ukladanie.
- [x] **Demo generuje naozaj — AI bez registrácie** ✅ 2026-08-19 (P0 z auditu 19. 8.)
  - **Nález:** landing sľubuje „napíš tému a AI pripraví sadu", demo ukazovalo 12 natvrdo zapísaných španielskych slov a k tomu vždy v svetlej téme. Jediná obrazovka, kde sa návštevník rozhoduje o registrácii, nepredvádzala to, na čom stojí produkt.
  - **Ako to beží:** `/demo` začína zadaním témy (klikacie štítky ako príklady), potom kroky „Čítam tému → Generujem → Pripravujem kartičky" a päť kartičiek. Nič sa neukladá k účtu, žiadna kategória nevzniká — sada žije len v prehliadači.
  - **Tri poistky proti spáleniu kvóty** (rozhodnuté 2026-08-19): rate limit 5/h na IP · **cache podľa témy** (`demo_generations`, normalizovaný kľúč bez diakritiky a veľkých písmen — rovnaká téma sa negeneruje druhýkrát) · **denný strop naprieč všetkými** (`DEMO_AI_DAILY_LIMIT`, default 60). Riadok v tabuľke vzniká len pri skutočnom AI volaní, takže „koľko riadkov pribudlo dnes" **je** dnešná spotreba — samostatné počítadlo netreba.
  - **Nikdy nie chyba namiesto slovíčok.** Vyčerpaný strop aj zlyhanie providera vracajú pripravenú sadu (najžiadanejšiu z cache, inak zabudovanú) a `source` to poctivo pomenuje v UI — „dnešný limit je vyčerpaný, toto je pripravená sada". Claude sa v ukážke nepoužíva (platený), len Gemini → Groq.
  - Migrácia `2026-08-19_demo_generations.sql` **spustená na Supabase 2026-08-19** ✅. (Bez nej ukážka funguje, ale nemeria spotrebu, takže AI nevolá vôbec a podáva zabudované sady.)
  - Doplnené aj: tmavá téma podľa `localStorage` (rovnaký boot ako landing) + prepínač, čítanie nahlas podľa skutočných jazykov sady (predtým natvrdo `es-ES`/`en-US`), „Skúsiť znova" vracia na zadanie témy. Testy `tests/test_demo_generate.py` (9).
- [x] **Dashboard po nasadení: čo zabralo a čo nie** ✅ 2026-08-19 (merania používateľa na v1.0.402)
  - **Zabralo:** dashboard naplnený **4,7–6,9 s → 2,55 s**. Tri volania štartujú v tej istej milisekunde, skeleton drží až po dáta.
  - **Nezabralo tak, ako malo:** `/api/user/stats` samostatne 1,9 s → **1,05 s**, ale *počas načítania dashboardu* stále **1,82 s**. Príčina je súbežnosť, nie počet dotazov: tri requesty naraz trvajú 2220 ms každý oproti 1076 ms samostatne. Inštancia súbežnosť neutiahne (1 vCPU / nízka concurrency).
  - **`Server-Timing` na každej odpovedi** (`db;dur=… ;desc="N queries", app;dur=…, total;dur=…`) — bez neho sa zvonku nedá rozhodnúť, či endpoint počíta, alebo čaká na databázu. `app/services/timing.py` meria cez `before/after_cursor_execute`; počítadlo je meniteľný slovník v `ContextVar`, lebo synchrónne endpointy bežia vo vlákne z poolu (prepísaná premenná by sa k middleware nedostala, zápis do spoločného slovníka áno). Testy `tests/test_server_timing.py` (3).
  - **Prefetch prestal súťažiť o CPU:** jeden request na kategóriu namiesto dvoch (server vracia `knowledge_level`, rozdelenie do dvoch cache kľúčov zvládne prehliadač), len **3 najnovšie kategórie** namiesto všetkých, `MAX_CONCURRENCY` 3 → **1** a spustenie až po `load` v nečinnosti (timeout 4 s → 15 s). `/api/v1/words/test/start` bral 2,5 s na volanie a končil v 4,44 s — bola to najdlhšia vec na dashboarde.
  - **Hypotéza na overenie po deployi:** appka beží v `us-central1` (`cloudbuild.yaml`), takže ak je Supabase v EU, každý dotaz platí transatlantický round-trip ~110 ms — päť dotazov ≈ 550 ms, presne tá „vlastná práca" nad podlahou. `Server-Timing` to rozsúdi: vysoké `db` = vzdialená databáza (rieši sa regiónom, nie kódom). Pozor, `pool_pre_ping` posiela pred každým vypožičaním spojenia `SELECT 1`, ktorý **obchádza** event listenery — prejaví sa v `app`, nie v `db`.
- [x] **Dashboard: koniec so 4–7 sekundami núl** ✅ 2026-08-19 (P0 z auditu 19. 8.)
  - **Nález:** po prihlásení svietili na dashboarde samé nuly 4–7 s. Merania z auditu: `/api/user/stats` 1897 a 1855 ms pri 4 kB odpovede, `/api/v1/categories` ~0,9 s, `/api/user` 590 ms.
  - **Príčina 1 — zbytočné čakanie na `/api/user`.** `pageshow` mal `await loadUserData()` a až potom púšťal štatistiky a kategórie, hoci ani jedno z neho nič nepotrebuje. Teraz idú **všetky tri requesty naraz** (`Promise.all`); `loadCategories` si počká na používateľa len tesne pred vykreslením — zámok pre free účty sa riadi `currentUserIsPlus`, inak by PLUS účet na moment videl zámky.
  - **Príčina 2 — 12 round-tripov na jedno zobrazenie.** Endpoint posielal na Supabase tucet samostatných dotazov (počet slov, dva sumy, počty podľa úrovne, netestované, dávno netestované, priemer opakovaní, kategórie, história, 2× naučené, slabé kategórie). Nad vzdialenou databázou sa neplatí za výpočet, ale za počet ciest tam a späť. Nový `get_word_aggregates()` spraví **sedem dotazov nad `words` jedným prechodom** (podmienené `COUNT`/`SUM`/`AVG`) a `get_learned_counts` zvládne obe okná naraz cez `COUNT(DISTINCT CASE …)`. **Zmerané: 12 → 5 dotazov.**
  - **Príčina 3 — chýbajúce indexy.** `words.user_id` nemal index vôbec a nad cudzím kľúčom `words.category_id` si ho Postgres sám nevytvorí, takže každý dotaz štatistík išiel seq scanom cez celú tabuľku. Migrácia `2026-08-19_words_indexes.sql` **spustená na Supabase 2026-08-19** ✅ + `index=True` v modeli, aby nové prostredia vznikli rovnaké. Overené cez `EXPLAIN ANALYZE SELECT count(*) FROM words WHERE user_id = 1` — `Index Only Scan`, `Heap Fetches: 0`, 0,120 ms. (`CONCURRENTLY` v Supabase SQL Editore neprejde — obaľuje príkazy do transakcie, chyba `25001` — a pri tejto veľkosti tabuľky ho netreba.)
    - Poznámka: plánovač si na dotazy filtrujúce len `user_id` berie zložený `ix_words_user_tested` (vedúci stĺpec sedí), takže samostatný `ix_words_user_id` je fakticky nadbytočný. Nechaný zámerne — stojí len zápisy, nie čítania; ak by sa upratovalo, `DROP INDEX ix_words_user_id;` je bezpečný.
  - **Skeleton namiesto núl.** `stats-loading` je priamo v `<body>` (nie až v JS, inak by medzi prvým vykreslením a `pageshow` blikli nuly), dole ide v `finally` — takže ani zlyhané načítanie nenechá pruhy navždy. Nula je odpoveď („nemáš nič"), pruh je čakanie.
  - **Prefetch bežal trikrát** — `loadCategories()` sa volá aj po vytvorení a zmazaní sady a zakaždým plánoval sťahovanie všetkých slovíčok. Teraz raz za načítanie stránky; predohrev offline stránok (`/profile`, `/test`, `/repeat`) sa presunul až za dáta, aby o linku nesúťažil práve počas čakania na štatistiky.
  - Overené v prehliadači na kópii dashboardu s podstrčenými odpoveďami: všetky tri volania štartujú v tej istej milisekunde, skeleton drží od prvého vykreslenia po dáta. Testy: `test_stats.py` +2 (agregáty proti počítaniu po riadkoch, prázdny účet) → spolu **407**.
  - **Zámerne nespravené:** predpočítaná tabuľka štatistík ani cache, ktoré audit navrhoval ako prvé — päť dotazov nad indexovanou tabuľkou by malo stačiť. Ak by nie, ďalší krok je 60 s cache na `/api/user/stats`.
- [x] **Odchod z bežiaceho testu kartičiek tlačidlom späť** ✅ 2026-08-11
  - **Nález (používateľ):** spustený test + tlačidlo späť = odchod bez pýtania a **bez uloženia odpovedí**. Modál „Ukončiť test?" existoval len na odkaze „← Dashboard" (`goDashboard`), `popstate` ani `beforeunload` neriešil nič.
  - **Riešenie v `flashcard_test.html`:** strážna položka v histórii (`armHistoryGuard` → `history.pushState`) — späť ju vyberie, hneď ju vrátime a namiesto odchodu ukážeme **ten istý modál** ako odkaz (funguje aj pre hardvérové späť na mobile). Po dokončení testu (obrazovka výsledkov) späť odchádza normálne, jedným stlačením.
  - `beforeunload` (natívny dialóg prehliadača) pri zavretí karty/reloade s nezapísanými odpoveďami + **`pagehide` beacon** ako posledná poistka — odpovede sa uložia, aj keď stránka zanikne.
  - Proti dvojitému zápisu: `pendingFrom` — `submitResults()` posiela len `answers.slice(pendingFrom)` (inak by modál + beacon započítali karty do `times_tested` dvakrát).
  - Overené lokálne v prehliadači (SQLite): späť → modál → „Zostať" ostane v teste · „Ukončiť" uloží presne zodpovedané karty (2 z 5) a odíde na dashboard · tvrdý odchod uloží beaconom bez duplicity. Testy `tests/test_flashcard_leave_guard.py` (2) → spolu **193**. SW cache **v49 → v50** (stránka testu je precachovaná).
- [x] **Zdieľané čítanie slovíčok — `static/js/speech.js`** ✅ 2026-08-11 (úroveň 1 z posúdenia kvality reči)
  - **Podnet:** reč mala tri kópie a rozchádzali sa. `repeat.html` (po oprave z 3. 8.) mapoval jazyk na locale a vyberal konkrétny hlas; `flashcard_test.html` a `demo.html` posielali holé `u.lang = "sk"` bez hlasu → prehliadač čítal slovenčinu **anglickým hlasom**, alebo mlčal.
  - Nový modul `app/static/js/speech.js` (`window.LexiSpeech`) — jediný zdroj pravdy, rovnaký princíp ako `design-system.css`: `LOCALE_BY_CODE`/`toLocale` (24 jazykov), cache hlasov + `voiceschanged`, `pickVoice` (presná zhoda → rovnaký jazyk → nič), `speak` (jednorazové, ruší predošlú reč) a `speakAsync` (promise na `onend` + poistný timeout, pre auto-play).
  - **Chýbajúci systémový hlas** sa už nezamlčí — nenápadný toast (SK/EN, raz za jazyk a reláciu). Hlási sa len keď je zoznam hlasov naozaj načítaný (prázdny = „ešte neviem", nie „nie je hlas").
  - **Tempo reči je spoločné** — kartičky aj demo čítajú `rate` z nastavení Opakovania (`wk_repeat_play_settings`), takže používateľ ho nastavuje na jednom mieste. Žiadne nové UI.
  - Opravený aj Chrome bug „prvé ťuknutie na 🔊 nespraví nič" — `cancel()` a `speak()` v tom istom ticku sa už nevolajú za sebou.
  - Overené lokálne v prehliadači: kartičky čítajú `en-US` hlasom *Microsoft David* a `sk-SK` hlasom *Microsoft Filip* (predtým holé `en`/`sk` bez hlasu), tempo 1,25 z nastavení sa prenieslo, auto-play v Opakovaní beží nezmenene, demo správne hlási chýbajúci španielsky hlas. Testy `tests/test_speech_module.py` (3) → spolu **197**. `speech.js` doplnený do SW precache (v50).
  - Ďalší krok (nerobené, rozhodnutie odložené): serverové neurónové TTS s cache MP3 — konzistentná kvalita naprieč zariadeniami, ~$16/1M znakov, ale nová infra + latencia + offline režim + doplnenie providera do Privacy.
- [x] **Grafy „Viem/Neviem" sa po teste neaktualizovali (návrat tlačidlom späť)** ✅ 2026-08-11
  - **Zistenie:** server aj API sú v poriadku — po odoslaní testu vracia `/api/v1/categories`, `/api/v1/categories/{id}` aj `/api/user/stats` **okamžite nové čísla** (overené lokálne). Dashboard je tiež v poriadku: celý jeho init visí na `pageshow`, takže sa prekreslí aj po návrate z bfcache.
  - **Príčina:** `category_words.html` mal init len na `DOMContentLoaded`. Návrat **tlačidlom späť** obnoví stránku z bfcache, kde `DOMContentLoaded` už nebeží → percentá „😕 Neviem (x%) / ✅ Viem (y%)" na testovacích tlačidlách aj úrovne slovíčok ostali v stave spred testu. Test kartičiek odkazom vracia na `/dashboard`, takže zo stránky sady je späť jediná cesta naspäť — preto to bilo do očí práve tam.
  - **Oprava:** `window.addEventListener('pageshow', e => { if (e.persisted) { loadCategory(); loadWords(); } })` — bežné načítanie ďalej rieši `DOMContentLoaded`, obnova beží len pri návrate z bfcache. Overené lokálne (dáta zmenené na pozadí → po `pageshow` sa 100 % Neviem preklopilo na 100 % Viem). Test v `tests/test_flashcard_leave_guard.py` → spolu **194**.
- [x] **Redizajn aplikácie + zdieľaný design system** ✅ 2026-07-21 (merge `363ccd4b`, nasadené a overené na produkcii)
  - **Podnet:** audit šablón ukázal, že tokeny (`--primary`, `--bg`…) boli duplikované v 25 súboroch → každá zmena znamenala 25 editov a vznikal drift.
  - **Základ:** nový `app/static/css/design-system.css` — jediný zdroj pravdy (tokeny, dark mode cez `data-theme`, komponenty `btn`/`card`/`pill`/`icon-tile`/`ds-nav`/`theme-toggle`/`field`/`reveal`). **Šablóny už nesmú definovať vlastné `:root` bloky.**
  - **Space Grotesk** self-hostovaný (latin + latin-ext, OFL) ako display font — CSP povoľuje len `font-src 'self'`, takže Google CDN nie je možnosť.
  - **Fáza 1 (plný redizajn verejných stránok):** landing (asymetrický hero, bento grid, **SVG ikony namiesto emoji**), login + register (split-screen s brand panelom), pricing, blog.
  - **Fáza 2 (migrácia internej appky):** dashboard, profile, classes, repeat, flashcard_test, category_words, demo, share, class_join, terms, privacy, refunds, 404, 500, blog článok, forgot/reset password. Zámerne **migrácia, nie prepis** — napojenie zdieľaného CSS + zmazanie duplicitných token blokov, funkčný markup a JS zachovaný 1:1 (prepisovanie 1500-riadkového dashboardu by bolo zbytočné riziko).
  - Kompatibilné aliasy v design-systeme (`--card`, `--card-bg`, `--input-bg`, `--bg-color`, `--text-main/-color/-muted`, `--primary-light`, `--primary-gradient`, `--shadow`) umožnili migrovať staré šablóny bez zásahu do markupu — tým sa zjednotil aj `category_words`, ktorý mal vlastnú nekonzistentnú sadu názvov.
  - **Vyriešené:** duplicita tokenov (**−600 riadkov CSS**, celkovo merge −841), chýbajúci dark mode na verejných a auth stránkach, nekonzistentné dark surfaces a radiusy.
  - `sw.js` cache **v45 → v46** + `design-system.css` a fonty do precache (bez toho by PWA používatelia dostali staré CSS).
  - **Vynechané zámerne:** `admin.html` (nepoužíva žiadne CSS premenné, vlastné natvrdo písané štýly — interný nástroj), redirect obrazovky `google-login.html` / `auth-callback.html`.
  - ✅ **Overené 2026-07-23** — prihlásená časť appky (dashboard, category_words, profile, classes, repeat, flashcard_test) preklikaná na produkcii používateľom, bez nálezov.
  - Známa kozmetika: farebné pruhy úrovní v `category_words` („Don't Know"/„Know") sú natvrdo svetlé → v dark mode pôsobia cudzo (pôvodné správanie, nie regresia).
- [ ] **Učiteľské účty (kanál učiteľ → trieda)** 💡 návrh 2026-07-17 — rozpracovanie odporúčania č. 2 z komerčného hodnotenia; 3 fázy, každá samostatne nasaditeľná:
  - [x] **Fáza 1 HOTOVÁ a overená na produkcii** ✅ 2026-07-17 — `share_code` na kategórii (migrácia `2026-07-17_category_share.sql` spustená na Supabase), endpointy share/unshare/preview/import-shared, landing `/s/{kód}` (`share.html`, noindex + robots Disallow), `?next=` redirect v login/register, share tlačidlo + modál v dashboarde (sw **v36**). Kód 8 znakov bez O/0/I/1/L (diktovateľný v triede). Testy `tests/test_share.py` (17) → spolu **124**. Nasadené (commit `3e863744`) a overené naživo. ~~Známe obmedzenie: Google OAuth login ignoruje `?next=`~~ ✅ **opravené 2026-07-23** — `?next=` sa posiela do `/auth/google`, prežije cestu cez Google (session + podpísaná cookie `oauth_next`, rovnaká poistka ako pri OAuth state) a `/auth/finalize` presmeruje na cieľ. Cesta sa validuje na oboch koncoch (`_safe_next` — len interná cesta, žiadny open redirect), aj keď príde z podpísaného tokenu. Testy `tests/test_oauth_next.py` (13). **Overené na produkcii 2026-07-23** — `login?next=/pricing` → Google → používateľ skončí na `/pricing`.
  - **Fáza 1 — Zdieľanie sady kódom/linkom (bez rolí, najmenší krok):**
    - Vlastník kategórie vygeneruje zdieľací kód/link (napr. `/s/ABC123`); prijímateľ sa prihlási (alebo zaregistruje — každý link je akvizičný kanál) a sada sa mu **skopíruje** do účtu (copy-on-import, žiadne zdieľané vlastníctvo — jednoduchý model, žiadne permissions).
    - Limity: kópia príde **celá aj nad 30 slov** (`WORD_LIMIT_FREE` platí pre vlastnú tvorbu, nie pre import — rovnaká logika ako XLSX import), ale **počíta sa do `CATEGORY_LIMIT_FREE`** (inak by si free účty preposielaním sád obišli limit kategórií).
    - **PLUS: nie.** Zdieľanie aj prijatie je free pre všetkých — viralita je celý zmysel fázy 1, paywall by zabil rast. Monetizácia je nepriama: tvorca sád naráža na AI limity (3/deň free, video PLUS), prijímatelia na limit 5 kategórií.
  - [x] **Fáza 2 HOTOVÁ v kóde (2026-07-17)**, migrácia `migrations/2026-07-17_teacher_classes.sql` ✅ **spustená na Supabase (2026-07-17)** — zostáva deploy na Cloud Run + overenie na prode.
    - DB: `classes`, `class_members`, `class_categories`, `word_progress` (overlay pokrok žiaka na cudzích slovách — sady triedy sú live odkaz, učiteľove `words` sa žiakom nemenia); `users.email` nullable + `users.is_pseudonymous`.
    - Rozhodnutia: **hybrid žiacke účty** (pseudonymné bez e-mailu à la Kahoot + existujúce e-mailové), **login žiaka = kód triedy + prezývka + heslo** (učiteľ heslo resetuje, nečíta), kód triedy 6 znakov (rovnaká abeceda ako share), po vypršaní PLUS „frozen-management, live-learning" (žiaci sa učia ďalej, 403 len na create + overview).
    - Backend: `app/routers/classes.py` (CRUD, regenerate-code, members, reset-password len pre pseudonymné, assign/unassign, overview, join/join-new/login/leave, preview), `class_access.py`, overlay v `words.py` (test/start, get_words, submit → `word_progress`), `get_categories` vracia sady tried s `from_class`+`class_name` (nepočítajú sa do limitu 5), `_check_category_access` pustí člena triedy (readonly).
    - FE: `/classes` (učiteľ: triedy, žiaci, sady checkboxom, prehľad pokroku), `/c/{kód}` landing (join-new bez e-mailu / login / register s ?next=), žiacky mód na `/login`, badge „Trieda" na dashboarde, readonly detail sady. SW **v37**. Privacy: sekcia o žiackych kontách (SK+EN).
    - Hardening None-email: `forgot_password` guard na `{"email": null}`, billing config vypne checkout pre žiacke kontá, template fallbacky na meno.
    - Testy: `test_classes.py` (18) + `test_class_progress.py` (10) → spolu **154**. E2E overené lokálne Playwrightom (20 kontrol: učiteľ → trieda → sada → žiak join-new → test → word_progress → prehľad → žiacky login).
    - Po nasadení overiť na prode: založenie triedy, join žiaka cez `/c/{kód}`, test žiaka, prehľad.
  - **Fáza 2 — Učiteľská rola + trieda (tu vzniká platená hodnota):**
    - Učiteľ založí triedu, žiaci sa pridajú kódom triedy. Sady priradené triede žiaci vidia **live** (odkaz, nie kópia — oprava preklepu sa prejaví všetkým) a **nepočítajú sa do žiackych limitov** (nie sú ich vlastníctvom).
    - Prehľad triedy: kto testoval, úspešnosť, posledná aktivita — dáta už existujú v štatistikách, treba len agregáciu per-trieda.
    - **PLUS: platí učiteľ.** Triedy + prehľad pokroku = PLUS funkcia (žiadny nový tier, existujúci billing). Žiak je free: sady triedy má zadarmo a bez limitov, vlastná tvorba nad limit = vlastný PLUS. Ekonomika: 1 učiteľ €4,99/mes privedie ~25 free účtov (leads, časť sa časom konvertuje sama).
    - ⚠️ **GDPR blocker pred spustením:** žiaci sú často pod 16 (čl. 8 GDPR — súhlas rodiča) a pokrok žiaka viditeľný učiteľovi je nové spracovanie osobných údajov → update privacy policy; zvážiť **pseudonymné žiacke účty bez e-mailu** (vzor Kahoot — žiak sa pridá kódom + prezývkou), čím väčšina problému odpadne.
  - **Fáza 3 — Školská licencia (B2B, až keď fáza 2 má trakciu):**
    - Multi-učiteľ pod jednou školou, ročná faktúra, per-učiteľ cena cez Paddle (quantity na existujúcom ročnom price ID alebo samostatný price). Rieši aj to, že učitelia neradi platia kartou z vlastného vrecka — platí škola.
  - **Kedy je potrebný PLUS (súhrn):** zdieľanie/prijatie linkom **free** · založenie triedy a prehľad žiakov **PLUS (učiteľ)** · žiak v triede **free vrátane sád triedy** · AI tvorba podľa existujúcich pravidiel (3/deň free, video PLUS).
- [x] **Zviditeľnenie webu — analytika + obsahový SEO kanál** ✅ nasadené 2026-08-18 (ďalšia etapa nižšie: „SEO druhá vlna")
  - **Východisko:** technické SEO bolo hotové, ale chýbalo meranie (nulová analytika) a indexovateľný obsah (15 URL, z toho 3 články). Google nemal čo rankovať.
  - **1. Cookieless analytika (Plausible).** Nový partial `app/templates/partials/analytics.html` vložený do `<head>` 24 šablón (mimo `admin.html` a redirect obrazoviek `auth-callback`/`google-login`). Konfigurácia cez env `ANALYTICS_DOMAIN` + `ANALYTICS_SRC` v `runtime.py` ako Jinja globals — **bez `ANALYTICS_DOMAIN` sa skript nevykreslí vôbec**, takže lokál ani testy neposielajú dáta.
    - **CSP:** `_analytics_origin()` v `main.py` odvodí origin z `ANALYTICS_SRC` a doplní ho do `script-src` aj `connect-src`. Bez toho by CSP skript zablokovala. Podporuje aj self-hostovanú inštanciu; relatívna URL sa ticho vynechá (radšej bez analytiky než nevalidná CSP).
    - **Ciele funnelu** cez wrapper `window.lexiTrack(name, props)` (no-op pri vypnutej analytike): `Registracia` (register.html), `Sada vytvorena` s `zdroj` = ai-text/ai-foto/ai-video/rucne (dashboard.html), `Test dokonceny` v `showResults()` — zámerne až na obrazovke výsledkov, aby predčasný odchod modálom ani poistný beacon nerátali dokončenie. `CTA registracia` na tématických stránkach.
    - ⚠️ **Google registrácia sa nemeria** — ide cez `/auth/google` a na klientovi ju nevieme odlíšiť od prihlásenia. Ak bude treba, musí sa označiť serverovo pri prvom vytvorení používateľa.
    - **Privacy + cookie lišta doplnené** (SK aj EN): nová sekcia „Návštevnosť webu" (čo sa zbiera/nezbiera, právny základ čl. 6 ods. 1 písm. f). Text lišty „žiadne sledovanie" prepísaný na „návštevnosť meriame anonymne — bez cookies, profilovania a reklám", aby tvrdenie ostalo pravdivé.
  - **2. Tematické stránky „slovíčka na tému X"** (odporúčanie č. 3 z komerčného hodnotenia). Dáta v `app/services/seo_topics.py`, šablóny `topics.html` (rozcestník) + `topic.html` (detail), routy `/slovicka` a `/slovicka/{slug}`. **12 tém × 20 slovíčok**, každé s prekladom a **príkladovou vetou** (nie holý zoznam — proti thin content), plus sekcia „na čo si dať pozor" a interné prelinkovanie na príbuzné témy. Výslovnosť cez zdieľaný `LexiSpeech`. Sitemap sa napĺňa automaticky (15 → 28 URL). Sitewide odkaz doplnený do `site-footer.js`.
    - Štruktúrované dáta: `BreadcrumbList` + `LearningResource` na detaile, `CollectionPage` na rozcestníku.
    - **Rozšírenie o novú tému = jeden záznam v `TOPICS`**, nič iné.
  - **3. Nový článok pre učiteľov** — `ako-ucit-slovicka-v-triede` (SK + EN), zámerne mierený na učiteľský kanál: je to zároveň obsah, ktorý sa dá zdieľať v učiteľských komunitách (odporúčanie č. 2).
  - Testy: `test_analytics.py` (8) + `test_seo_topics.py` (18, vrátane integrity dát — mŕtve `related` odkazy, dĺžka meta description, duplicitné slová) + rozšírený `test_blog.py` (parametrizovaný cez všetky články v SK aj EN, kontrola existencie šablóny) → spolu **275** (predtým 197). SW cache **v50 → v51** (`site-footer.js` a `cookie-notice.js` sú precachované).
  - **Zostáva urobiť (mimo kódu):**
    - [ ] Založiť Plausible účet a nastaviť `ANALYTICS_DOMAIN=lexinova.fun` na Cloud Run (bez toho analytika nebeží).
    - [x] Sitemap odoslaná v Search Console ✅ 2026-08-18 — property overená, sitemap podaná. Overené proti produkcii: `/sitemap.xml` vracia Googlebotovi 200 za 0,26 s, platné XML, správny content-type. Stav „Nie je možné načítať" s prázdnym „Posledné načítanie" = Google ju ešte nečítal, nie chyba servera.
    - [ ] Off-page distribúcia (SK/CZ učiteľské skupiny, katalógy AI/edu nástrojov) — zatiaľ nerobené.
- [ ] **Publikovanie do obchodov (Microsoft Store, Google Play)** 🚧 príprava hotová 2026-08-18
  - **Prečo to ide:** appka je PWA, takže z nej **PWABuilder** (nástroj Microsoftu) vygeneruje hotový balík — pre Windows `.msixbundle`, pre Android balík typu TWA. Balík netreba podpisovať, Microsoft ho pri certifikácii podpíše sám. Review býva 24–48 h. **Registrácia vývojára je od mája 2026 zadarmo** aj pre firmy.
  - **Čo je hotové v kóde:** manifest má `id`, `name`, `short_name`, `description`, `start_url`, `scope`, `display: standalone`, ikony 192 + 512 (vrátane `maskable`), farby, kategórie aj jazyk. Doplnené **`shortcuts`** (Test, Opakovanie, Osemsmerovka) — vo Windowse a Androide sa ukážu po kliknutí pravým na ikonu appky. HTTPS aj service worker s offline režimom sú dávno na mieste.
  - **Čo treba spraviť ručne (nedá sa za teba):**
    - [ ] Účet v **Partner Center** (osobný Microsoft účet, nie pracovný ani školský), rezervovať názov appky.
    - [ ] Na [pwabuilder.com](https://www.pwabuilder.com) zadať `https://lexinova.fun`, stiahnuť Windows balík a nahrať ho v Partner Center. Package ID, Publisher ID a Publisher display name vypíše Partner Center — musia sedieť s tým, čo sa zadá v PWABuilderi.
    - [ ] **Screenshoty do listingu** — nahrávajú sa priamo v Partner Center, nemusia byť v manifeste. Stačia 3–4: dashboard so štatistikami, test kartičiek, osemsmerovka, stránka kategórie.
    - [ ] **Testovací účet pre recenzenta.** `start_url` je `/dashboard`, takže neprihlásený recenzent skončí na logine a submit bez prihlasovacích údajov v poznámkach pre certifikáciu spadne.
    - [ ] Vekové hodnotenie (IARC dotazník), odkaz na Ochranu súkromia (`/privacy` — už existuje) a kontakt na podporu.
  - **Platby:** pre nehry na PC povoľuje Microsoft policy 10.8.1 buď svoje IAP API, **alebo** „secure third-party purchase API" — Paddle by mal prejsť. Podmienky si prečítať pred submitom, nie po ňom.
  - **Poradie:** pre appku na učenie je mobil hlavný kanál, takže **Google Play (TWA) má väčší zmysel než Windows Store**. PWABuilder vygeneruje oboje z tej istej PWA; Play navyše vyžaduje `assetlinks.json` na doméne (digitálne overenie vlastníctva), Windows nie.
- [ ] **Osemsmerovka s tajničkou** 💡 návrh 2026-08-18 — odložené („zatiaľ nechajme takto")
  - **Zámer:** písmená, ktoré po vyškrtaní všetkých slov zostanú, sa čítajú po riadkoch a dajú vetu; po vylúštení sa zobrazí veta aj jej preklad. Dnes sa voľné bunky dopĺňajú náhodnými písmenami, takže ide o zámenu výplne za písmená tajničky.
  - **Jediná skutočná prekážka: počet voľných buniek sa musí presne rovnať počtu písmen tajničky.** Poradie generovania sa preto otočí — najprv veta, potom sa dopočíta veľkosť mriežky a počet umiestnených slov tak, aby to sedelo na písmeno presne. Pomôže nečtvorcová mriežka (rows × cols dáva jemnejšie krokovanie než size²) a možnosť vynechať najkratšie slovo.
  - **Odkiaľ veta** — nerozhodnuté, tri cesty: (a) AI podľa témy kategórie, jedno volanie vráti vetu aj preklad — najlepšie sadne k obsahu, ale míňa denný AI limit a bez internetu hra spadne na verziu bez tajničky; (b) poskladať z prekladov slovíčok kategórie — zadarmo a offline, ale je to skôr zoznam než veta; (c) vlastná veta uložená ku kategórii (nové pole v DB) — pod kontrolou, ale treba ju vyplniť pri každej kategórii.
  - Dĺžku vety netreba riešiť na strane AI (modely presný počet písmen nedodržia) — rieši ju mriežka.

- [x] **Hra: osemsmerovka zo slovíčok kategórie** ✅ 2026-08-18 — prvá verzia hotová (`/hra?category={id}`, vstup zo stránky kategórie). Mriežka sa skladá v prehliadači, bez AI a bez nového endpointu; ťahom myši aj prstom, nájdené slovo ostáva v mriežke prečiarknuté a v zozname sa odkryje preklad. **Do štatistík sa hra zámerne nezapočítava** (rozhodnuté 2026-08-18) — nájdenie slova v mriežke nie je odpoveď na otázku, takže by skresľovala aj úspešnosť aj sériu dní. Otvorené z pôvodného návrhu ostáva: distraktory cez AI a voľba, ktorá strana ide do mriežky.
  - **Zámer:** z kategórie sa vygeneruje mriežka písmen, v nej sú poskryté slovíčka. Používateľ ťahom myši (na mobile prstom) označí nájdené slovo; ak sedí, ostane zvýraznené a **mimo tabuľky sa ukáže jeho preklad**. Učenie bez testovacieho tlaku — iný spôsob kontaktu s tou istou slovnou zásobou než kartičky.
  - **Terminológia:** ide o **osemsmerovku** (word search), nie klasickú krížovku. V krížovke sa písmená píšu podľa legendy; tu sa hotové slovo označuje ťahom, čo je presne to, čo bolo zadané. Ak by sme neskôr chceli aj klasickú krížovku s legendou (definícia = preklad, dopĺňajú sa písmená), je to samostatná úloha — iné generovanie aj iné ovládanie.
  - **Generovanie mriežky nepotrebuje AI.** Umiestnenie slov do mriežky je deterministický algoritmus (skús náhodnú pozíciu a smer, over kolízie, opakuj; zvyšok doplň náhodnými písmenami) — pár desiatok riadkov, beží okamžite, zadarmo a funguje aj offline. AI by sem priniesla latenciu, náklady, limity a nedeterminizmus bez pridanej hodnoty.
    - **Kde AI zmysel má:** doplniť do mriežky *distraktory* — slová, ktoré vyzerajú podobne ako tie správne (typické zámeny), aby hráč naozaj čítal. To je jazyková úloha, na tú je AI vhodná. Nechať ako druhú fázu, prvá verzia bez nej.
  - **Otvorené rozhodnutia pred implementáciou:**
    - Ktorá strana ide do mriežky — originál, preklad, alebo náhodne? (Ak je v mriežke originál a mimo sa ukáže preklad, hra trénuje rozpoznávanie; opačne produkciu.)
    - Diakritika a viacslovné výrazy: „hlavné jedlo" alebo „naťahovať sa" sa do mriežky nezmestia rozumne — buď vynechať slová s medzerou, alebo ich skladať bez medzier. Rovnako sa treba rozhodnúť, či mriežka bude s diakritikou (slovenská strana) alebo bez.
    - Veľkosť mriežky podľa počtu slov (napr. 10×10 pre 8 slov, 15×15 pre 15) a maximálny počet slov na hru.
  - **Rozsah prvej verzie:** nová stránka `/hra?category={id}` (alebo `/osemsmerovka`), generovanie na klientovi z už načítaných slovíčok kategórie (žiadny nový endpoint), označovanie ťahom, zoznam nájdených s prekladmi vedľa mriežky, tlačidlo „nová hra". Backend netreba meniť, kým hru nechceme počítať do štatistík.
- [x] **Rýchlosť prepnutia jazyka + preklad Chromu** ✅ 2026-08-18
  - **Podnet:** po otvorení dashboardu či kategórie trvalo 0,5–1 s, kým sa prepol nastavený jazyk.
  - **Príčina 1 — neskoré vykreslenie:** dashboard prekladal texty až v handleri `pageshow` (teda po načítaní chart.js, fontawesome a fontov), ostatné šablóny v skripte na konci `<body>`. Nový `partials/lang_boot.html` je inline skript v `<head>`, ktorý preklad aplikuje **počas parsovania HTML** cez `MutationObserver`. Element prekladá až keď parser prejde ďalej — prepis `textContent` ešte otvoreného elementu by sa zduplikoval s tým, čo parser dopíše za ním. Bez uloženej voľby nerobí nič.
  - **Príčina 2 — Chrome:** stránku po načítaní ešte raz prekladal Google Translate (`translated-ltr`, 1341 uzlov `font`). Prepisoval texty („Admin" → „Administrátor") aj popisku tlačidla „EN" na „SK", takže v headeri boli dve tlačidlá „SK". Na stránky s vlastným EN/SK prepínačom pridané `<meta name="google" content="notranslate">`; marketingové stránky ostávajú preložiteľné pre návštevníkov, ktorí nevedia ani po slovensky, ani po anglicky.
- [x] **SEO druhá vlna — technické opravy, dvojjazyčné URL, obsah** ✅ 2026-08-18
  - **Audit produkcie** (10 stránok, sitemap, robots, štruktúrované dáta, prelinkovanie) našiel osem vecí; všetky opravené.
  - **A) Technické opravy.** `/demo` malo prázdny H1, žiadny popis a ~10 slov textu (thin content v sitemape). `/register` a `/login` bez meta description; `/pricing`, `/demo`, `/register`, `/login`, blog a články bez OG/Twitter tagov. `/pricing` malo **dva H1** (SK aj skrytá EN verzia). FAQ na cenníku Google nevidel strojovo → `FAQPage` JSON-LD (test kontroluje, že otázky aj odpovede sedia s viditeľným textom, inak ich Google zahodí). `/slovicka` doplnený `ItemList`. `/login` von zo sitemapy.
    - **Najpodstatnejšie:** pätičku vykresľoval až `site-footer.js`, takže jediný interný odkaz na `/slovicka` a `/blog` vznikal po spustení JS. Odkazy sú teraz v HTML (`partials/seo_footer_links.html`) a `site-footer.js` ich len presunie do svojej pätičky. SW cache **v51 → v52** — bez bumpu by vracajúci sa používatelia mali starý `site-footer.js` a videli odkazy dvakrát.
  - **B) Jazyk na serveri.** Homepage sa Googlu ukazovala po anglicky (`<html lang="en">`, anglický title aj H1) a slovenčina sa doplnila až JS z `localStorage`, ktorý crawler nemá — pri SK/CZ trhu nebolo na slovenské dopyty čo indexovať okrem `/slovicka` a blogu. Osem verejných stránok má teraz obe verzie na vlastnej URL (`/` a `/en`, `/pricing` a `/en/pricing`, …), prepis rieši `app/services/i18n_html.py` nad hotovým HTML (netreba prepisovať každý reťazec v šablónach). Cenník a právne stránky mali v DOM oba jazyky naraz (druhý skrytý cez `display:none`) — teda celý text dvakrát a dva H1; teraz sa do HTML dostane len blok patriaci k URL. Prepínač EN/SK preklikne na druhú URL a voľbu si zapamätá pre appku; `lang_boot` sa na týchto stránkach nespúšťa.
    - ⚠️ **Vedľajší efekt:** návštevník s uloženou angličtinou, ktorý príde na slovenskú URL (napr. z Google.sk), uvidí slovenčinu a appka sa mu prepne na SK. Jedným klikom na EN je späť. Automatické presmerovanie podľa uloženej voľby zámerne **nie je** — Googlebot nemá `localStorage`, takže by videl niečo iné než používateľ.
  - **C) Obsah.** Tematické stránky **12 → 26** (šport, doprava, bývanie, počítač a internet, peniaze, práca, oblečenie, zvieratá, príroda, voľný čas, čas a dátumy, emócie, telefonovanie a e-maily, farby a tvary). Každá 18 slov s príkladovou vetou, vlastný úvod (žiadna duplicita textu), tri poznámky k častým chybám a rozdielom UK/US, prelinkovanie na príbuzné témy. Spolu 492 slovíčok; sitemap **29 → 50 URL**.
  - Testy: `test_seo_meta.py` (30) + `test_i18n_pages.py` (37).
  - **Zostáva:** obsah homepage (~200 slov je na hlavnú vstupnú stránku málo), po dátach z GSC pridať témy podľa reálnych dopytov.
- [x] **Lepšie štatistiky + história úrovní** ✅ 2026-08-18
  - **Zrušené** „Najslabšie slová" a „Najsilnejšie slová" (na žiadosť) — backend kvôli piatim riadkom načítaval celú tabuľku otestovaných slov, teraz stačí `COUNT`. Payload `plus_stats` už nič neniesol, PLUS sekciu riadi príznak `is_plus`.
  - **Opravené klamlivé metriky:** „Absolvované testy" ukazovalo `SUM(times_tested)`, čiže počet zodpovedaných kariet (u autora 681 namiesto 65 testov) — teraz skutočný počet riadkov v `test_sessions`. Duplicitné „Zvládnuté slová" (to isté číslo je v hlavnej mriežke aj v mastery krúžku) nahradil priemer opakovaní na zvládnuté slovo.
  - **Rozloženie znalosti ako jeden pruh** namiesto dvoch holých čísel. Úrovne sú len dve — stredná „Učím sa" sa už nikde nenastavuje (v dátach autora 0 riadkov), ostala len vo filtri a hromadnej zmene na stránke kategórie → odstránená; filter „Neviem" zachytí aj staršie riadky s `learning`.
  - **Nový panel „Kde ti to nejde"** — 3 kategórie s najnižšou úspešnosťou (min. 5 zodpovedaných kariet, inak by rebríčku kraľovalo slovo skúšané raz a zle), každá s tlačidlom rovno do testu neznámych slov. Náhrada za zrušený zoznam najslabších slov — na úrovni, kde sa dá konať.
  - **Nová tabuľka `word_level_events`** (migrácia `2026-08-18_word_level_events.sql`, spustená na Supabase ✅) — zapisuje len **skutočné zmeny** úrovne, nie každé opakovanie karty, takže rastie s učením, nie s používaním. Z nej nová dlaždica „Naučené (7 dní)". Zápis aj čítanie sú best effort, appka beží aj pred migráciou.
  - Testy: `test_level_history.py` (4) + rozšírený `test_stats.py`.
- [x] **Opakovanie sa ráta do aktivity** ✅ 2026-08-18 — migrácia `2026-08-18_test_sessions_kind.sql` spustená na Supabase ✅
  - Auto-play v Opakovaní si slovíčka len načítal cez `test/start` a späť neposielal nič: používateľ mohol prejsť sto kartičiek a na dashboarde sa nestalo nič — žiadna séria dní, žiadny stĺpec v grafe. Čas strávený učením appka vôbec neodmeňovala.
  - Zapisuje sa ako `test_sessions` s `kind='review'`: ráta sa do série dní aj grafu aktivity (vlastný stĺpec vedľa testov), ale **nikdy do úspešnosti** — pri prehrávaní sa neodpovedá, `correct=0` by priemer strhlo na nulu.
  - Zápis pri zastavení aj pri odchode zo stránky (`sendBeacon`), počítadlo sa hneď nuluje (žiadne dvojité započítanie). Cudzie `category_id` sa zahodí.
  - Testy: `test_review_sessions.py` (4).
- [x] **Kartičky — ovládanie a ukončenie** ✅ 2026-08-18
  - **Predčasné ukončenie:** test sa dal opustiť len nenápadným odkazom „← Dashboard" v rohu. Pod odpoveďovými tlačidlami je výrazné „Ukončiť a uložiť" (gradient ako hlavné CTA; emoji vlajku Windows vykresľoval ako prázdny štvorček, nahradil ju inline SVG). Potvrdenie existujúcim modálom, potom výsledková obrazovka — **úspešnosť sa počíta zo zodpovedaných kartičiek**, nie z celého balíka, aby predčasný koniec nevyzeral ako prepadnutie. Funnel udalosť „Test dokončený" sa pritom nezapočíta.
  - **Klávesnica** zjednotená s Opakovaním: medzerník prehrá zobrazené slovíčko, ↑ odkryje preklad, ↓ ho skryje, ← sa vráti bez zápisu, → posunie ďalej a kartičku označí ako **„Neviem"** (preskočené = nevedel som ho, nech sa vracia). „Viem" ostáva zámerne len na tlačidle — omylom stlačená klávesa by slovíčko označila za zvládnuté. Predtým → hneď označilo „Viem" a ← „Neviem", takže každý posun menil úroveň slovíčka, a raz odkrytý preklad sa nedal schovať.
  - Návrat na už zodpovedanú kartičku ju nezapočíta druhýkrát.
- [x] **Priebeh pri hromadných akciách v kategórii** ✅ 2026-08-18 — pri mazaní viacerých slovíčok nebolo vidno, že akcia beží. Potvrdzovacie tlačidlo dostalo spinner, modál sa zamkne a v texte beží priebeh „Mazanie slovíčok… 3/12". Requesty idú po štyroch (výber 200 slov neotvorí 200 spojení naraz), neúspešné kusy sa spočítajú a nahlásia — predtým sa chyby ticho ignorovali. Rovnaký spinner dostalo aj „Použiť" pri hromadnej zmene úrovne.
- [x] **Technické SEO — základ pre nájditeľnosť** ✅ 2026-07-13
  - `/robots.txt` (verejné stránky Allow, app/API/auth Disallow) + `/sitemap.xml` (8 verejných stránok, `SITE_URL` env-konfigurovateľné) — routy v `app/routers/pages.py`.
  - `index.html`: Open Graph + Twitter Card + `canonical` + JSON-LD `WebApplication` schéma (ceny €0/€4,99/€39,99) pre rich results.
  - Brandový **OG obrázok 1200×630** (`app/static/img/og-image.jpg`) — logo (vyrezaný badge bez svetlého pozadia) + názov + claim na navy pozadí; generátor `scratchpad/make_og.py`.
  - Nasadené a overené na produkcii (commity `aead6d8e`, `f8ac38f0`, `2fd22145`). Web už zaindexovaný v Google.
  - **Kánonická doména + canonical tagy** ✅ 2026-07-23 — GSC hlásila „Duplikovať bez kánonickej adresy vybranej používateľom". Príčina: `www.lexinova.fun` aj apex sú namapované na to isté Cloud Run a **www vracalo 200 namiesto presmerovania** → web bežal na dvoch adresách. Pridaný middleware `canonical_host_redirect` (301 www → apex, zachováva cestu aj query). **Výnimka `/auth/`** — OAuth state cookie je viazaná na host, presmerovanie callbacku by login zhodilo. Zároveň doplnený `<link rel="canonical">` na 7 stránok zo sitemapy, ktoré ho nemali (pricing, demo, register, login, terms, privacy, refunds — predtým len index, blog a článok). Testy v `tests/test_pages.py`.
  - **Sitemap „Nie je možné načítať" (2026-07-23):** overené proti produkcii — `/sitemap.xml` vracia 200, `application/xml`, funguje HEAD aj GET, aj pod Googlebot user-agentom. Na strane servera niet čo opraviť; ostáva vyžiadať znovunačítanie v GSC. Ak by zlyhávalo ďalej, podozrenie padá na timeout pri studenom štarte Cloud Run (scale-to-zero).
  - **Search Console (2026-07-13):** property overená, sitemap odoslaná, **homepage INDEXOVANÁ** („Webová adresa je na Googli", HTTPS ✅, indexovanie vyžiadané). Sitemap status „Nie je možné načítať" bol spôsobený chýbajúcou HEAD podporou (opravené `1be5db32`) — po oprave živý test Googlebotom prešiel; status v konzole sa preklopí sám (skontrolovať o pár dní). „Iná chyba" pri 3 assetoch (fonty, obrázok) v render reporte je neškodná — Googlebot bežne preskakuje časť zdrojov.
- [x] **Import poškodeného .xlsx vracia 400** ✅ 2026-07-13 (commit `8c150456`) — `pd.read_excel` parse chyba sa mapuje na 400 so zrozumiteľnou hláškou (detail do logu ako warning, nie ERROR → koniec falošných e-mail alertov). Testy `tests/test_word_import.py` (3) → spolu 103.
- [x] **Gemini 429: opravená textová aj fotková cesta** ✅ 2026-07-13 (commit `9b939ea9`)
  - `_post_gemini_generate_content` aj `..._from_image_gemini` pri 429 vyhodia `GeminiRateLimited` OKAMŽITE (žiadnych 8 odsúdených requestov) a router prepne na ďalšieho providera (Groq). 404 ďalej skúša modely (to je žiaduce).
  - Chyby modelov sa zbierajú všetky (predtým `last_error` prepisoval predošlé).
  - Vyčerpaná kvóta sa mapuje na HTTP **429** „skúste neskôr" (predtým generic 502) — konzistentné s video cestou.
- [x] **AI kvóta sa vracia, keď generovanie zlyhá** ✅ 2026-07-13 (commit `9b939ea9`)
  - `refund_ai_quota()` v `services/limits.py` — volá sa pri konečnom zlyhaní (502/429) v `ai-create`, `ai-create-from-image` aj `ai-create-from-video`.
  - Odpočet ostáva PRED volaním AI (paralelné requesty limit neobídu), refund je kompenzácia po zlyhaní.
  - Testy `tests/test_ai_stability.py` (7) → spolu 100 testov.
- [x] **Groq fallback — vyriešené** ✅ 2026-07-13 — startup log (commit `9b939ea9`) na Cloud Run ukázal **`AI providers: claude=ON, gemini=ON, groq=ON`** → kľúč je správne nastavený, žiadny preklep. Záver: 10.7. fallback prebehol, ale **Groq zlyhal tiež** (starý kód logoval len poslednú chybu, preto to nebolo vidno). Odteraz sa logujú chyby všetkých pokusov — pri ďalšom výskyte bude presný dôvod v logu.
- [x] **AI kategória z YouTube videa** ✅ hotové — kód 2026-07-10, **overené naživo na produkcii 2026-07-17** (limit medzitým zvýšený na 100 slov)
  - Podnet: používateľ vložil YouTube odkaz do bežného AI promptu → do modelu sa poslal len text URL (žiadne video), navyše Gemini vrátilo 429. Video appka dovtedy nepodporovala vôbec.
  - **Gemini-only, bez fallbacku.** YouTube URL vie spracovať jedine Gemini (`file_data.file_uri`, **len v1beta** — vo v1 to nefunguje). Groq ani Claude odkaz nestiahnu, takže `_provider_chain` sa tu nepoužíva.
  - **PLUS-only** (rozhodnuté 2026-07-10) — video je najdrahšia AI operácia a bez fallbacku; free tier Gemini má strop **8 h YouTube videa/deň na projekt**, takže pár dlhých videí od free účtov by vyžralo kvótu všetkým. Endpoint vracia 403 pre free účet.
  - **Strop dĺžky 20 min** (`youtube.VIDEO_MAX_SECONDS`). Dĺžku vie povedať len **YouTube Data API v3** → voliteľný env `YOUTUBE_API_KEY`. **Bez kľúča sa kontrola dĺžky preskočí** (video prejde) — ak chceme strop reálne vynucovať, kľúč treba nastaviť na Cloud Run.
  - Predkontrola cez **oEmbed** (bez kľúča): verejné video → 200 + názov, súkromné/zmazané/neexistujúce → 400. Beží PRED volaním Gemini, aby zlé video nespálilo kvótu. Cudzie domény sú odmietnuté (`file_uri` sa nesmie dať nasmerovať inam).
  - Nové: `app/services/youtube.py`, `generate_category_and_words_from_video_gemini()` + `GeminiRateLimited` v `ai_category_service.py`, `POST /api/v1/categories/ai-create-from-video` (`@limiter.limit("5/hour")`), schéma `AICategoryFromVideoRequest`. Max 100 slov/video (`VIDEO_MAX_WORDS`, pôvodne 40, zvýšené 2026-07-17).
  - 429 od Gemini sa mapuje na HTTP 429 („skús neskôr"), nie na 502 — a **neskúša ďalší model** (spoločná kvóta projektu, ďalší request je len ďalšia rana do limitu).
  - Testy `tests/test_ai_video.py` (18: parsovanie URL vrátane shorts/youtu.be/cudzej domény, PLUS gating, 400/429/500 mapovanie) → spolu 92 testov.
  - ⚠️ **Reálne volanie Gemini s videom zatiaľ neoverené** — lokálne nie je `GEMINI_API_KEY` a produkčný kľúč mal 2026-07-10 vyčerpanú kvótu (429). Tvar payloadu je z dokumentácie, nie z živého behu. **Prvý beh treba overiť na Cloud Run.**
  - [x] **Frontend** ✅ 2026-07-10 — tlačidlo „AI z videa" s odznakom PLUS + modál `aiVideoModal` (stepper Overujem → Pozerám → Ukladám) v `dashboard.html`. Klientská kontrola URL (`YT_URL_RE`) drží parity so serverom vrátane `youtube-nocookie.com`; PLUS gating v UI len šetrí request, autorita je server (403). `aiErrorMessage` doplnený o vetvu 403. SW cache **v32** (dashboard je precachovaný — bez bumpu by starí používatelia tlačidlo nevideli).
  - [x] **Hint v modáli o limitoch** ✅ 2026-07-17 — text upozorňuje na max 20 min a max 100 slovíčok (SK aj EN), SW cache bump na **v35**.
  - [x] **Overiť naživo na Cloud Run** ✅ 2026-07-17 — používateľ otestoval generovanie z videa na produkcii, slovíčka sa uložili
  - [ ] (voliteľné) `YOUTUBE_API_KEY` na Cloud Run, aby strop 20 min naozaj platil
- [x] **Denné joby v aplikácii (lazy scheduler, anacron vzor)** ✅ 2026-07-09 — riešenie pre Cloud Run (scale-to-zero → in-process APScheduler nefunguje):
  - Tabuľka `job_runs (job_name PK, last_run_date, last_run_at, last_status, last_error)` — model `app/models/job_run.py`, migrácia `migrations/2026-07-09_job_runs.sql` **spustená na Supabase 2026-07-09** ✅.
  - Jadro `app/services/scheduler.py`: `register_job(name, func, run_after_hour=3)` + `run_due_jobs()`; joby v `app/services/jobs.py` (import registruje).
  - **Kontrola pri zobudení:** middleware `lazy_scheduler_trigger` v main.py — fire-and-forget task po odoslaní odpovede, throttlované max. 1× za 5 min/inštanciu (`maybe_run_due_jobs`), DB práca v threadpoole.
  - **Ochrana pred duplicitou:** atomický `UPDATE job_runs ... WHERE last_run_date < today` — beh vykoná len inštancia, ktorej UPDATE zmenil riadok. Claim ostáva aj po chybe (žiadne retry stormy) — idempotentný job dobehne ďalší deň.
  - Chyba jobu: rollback + `last_status='error'` + `last_error`, loguje sa ako ERROR (→ existujúci e-mail alert), request nikdy nezhodí.
  - **Prvý job: `expire_subscriptions`** — vypne PLUS používateľom s `plus_expires_at < now` (doteraz len pri logine cez `expire_if_needed`).
  - MRR oprava v `/api/admin/payments` — expirovaní (ktorých job ešte nevypol) sa nerátajú do MRR/aktívnych ✅.
  - Testy `tests/test_scheduler.py` (6) → spolu 70 testov.
  - Obmedzenie vzoru (akceptované): ak celý deň nepríde žiadny request, job dobehne až s prvou návštevou nasledujúci deň.
- [x] **Admin záložka „Joby"** ✅ 2026-07-09 — nová záložka v admin paneli (`/admin`) so zoznamom všetkých registrovaných denných jobov:
  - Tabuľka: názov + popis (1. riadok docstringu), cieľová hodina (default/override), posledný beh, stav (`ok`/`error`/`running`), posledná chyba.
  - **Manuálne spustenie** ▶ — `POST /api/admin/jobs/{name}/run` (`scheduler.force_run`): beží hneď v threadpoole, claim na dnešok si nastaví (auto-beh dnes už nenaskočí), história s `triggered_by='manual'`.
  - **Prestavenie hodiny** 🕐 — `PATCH /api/admin/jobs/{name}` → `job_runs.run_after_hour` (0–23 UTC, null = default z kódu); override má prednosť v `run_due_jobs`.
  - **História behov** 🕘 — tabuľka `job_run_history` (started/finished/status/error/triggered_by), `GET /api/admin/jobs/{name}/history`, rozbaľovací riadok v UI (posledných 20).
  - Migrácia `migrations/2026-07-09_job_runs_admin.sql` — **spustená na Supabase 2026-07-09** ✅. Testy: +4 → spolu 74.
  - Prestavenie hodiny cez **modál s mriežkou hodín** (00:00–23:00, aktuálna zvýraznená, default prerušovaný okraj; klik rovno uloží, tlačidlo Default vráti na default z kódu, Esc/klik mimo zavrie) — 2026-07-09.
- [x] **E2E smoke test skript — účet (Playwright, manuálne spúšťaný)** ✅ 2026-07-08 — `scripts/e2e_smoke.py`, spustenie `venv\Scripts\python.exe scripts\e2e_smoke.py` (jednorazovo: `pip install playwright` + `playwright install chromium`). Viditeľný prehliadač (headless=false), beží proti produkcii:
  1. Otvorí `https://lexinova.fun` → počká 4 s
  2. Prejde na `https://lexinova.fun/register` → vyplní e-mail `Admin1@admin.com`, heslo `Admin1111`, zopakuje heslo `Admin1111` → vytvorí účet
  3. Po prihlásení sa odhlási → počká 4 s
  4. Znova sa prihlási (`Admin1@admin.com` / `Admin1111`) → počká 4 s
  5. Prejde na `https://lexinova.fun/profile` → Delete account → potvrdí zmazanie (upratanie po sebe)
- [x] **E2E test skript — celý flow** ✅ 2026-07-08 — zlúčené do `scripts/e2e_smoke.py`: signup → logout → login → kategória „E2E Testovacia" + 3 slovíčka ručne → import 3 z TXT + 3 z XLSX → flashcard test (9 kariet, striedavo viem/neviem) → opakovanie → zmazanie účtu. Celý flow je default, `--quick` spustí len účtový tok. Oba varianty odskúšané proti produkcii.
- [x] Pridať pätičku (site-footer.js) aj na dashboard, test, repeat stránky ✅ 2026-07-08 (+ SW precache, cache v31)
- [x] Import slovíčok (Excel/TXT) — overené E2E skriptom na produkcii ✅ 2026-07-08. TXT („originál, preklad" na riadok) parsuje prehliadač po slovách cez POST /api/v1/words; .xlsx/.xls spracúva server (`/api/v1/words/import`, pandas — 1. riadok = hlavička). Import je teraz súčasť `scripts/e2e_smoke.py` (krok 6, TXT aj XLSX).
