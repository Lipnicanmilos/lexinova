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

## Ďalšie nápady / backlog
- [x] **Technické SEO — základ pre nájditeľnosť** ✅ 2026-07-13
  - `/robots.txt` (verejné stránky Allow, app/API/auth Disallow) + `/sitemap.xml` (8 verejných stránok, `SITE_URL` env-konfigurovateľné) — routy v `app/routers/pages.py`.
  - `index.html`: Open Graph + Twitter Card + `canonical` + JSON-LD `WebApplication` schéma (ceny €0/€4,99/€39,99) pre rich results.
  - Brandový **OG obrázok 1200×630** (`app/static/img/og-image.jpg`) — logo (vyrezaný badge bez svetlého pozadia) + názov + claim na navy pozadí; generátor `scratchpad/make_og.py`.
  - Nasadené a overené na produkcii (commity `aead6d8e`, `f8ac38f0`, `2fd22145`). Web už zaindexovaný v Google.
  - **Manuálne (užívateľ):** Google Search Console — property `lexinova.fun` overená, sitemap `sitemap.xml` odoslaná 2026-07-13 (čaká na spracovanie, „Nie je možné načítať" je dočasný stav). Overiť zajtra, že prešla na „Úspešné" (8 URL).
- [x] **Import poškodeného .xlsx vracia 400** ✅ 2026-07-13 (commit `8c150456`) — `pd.read_excel` parse chyba sa mapuje na 400 so zrozumiteľnou hláškou (detail do logu ako warning, nie ERROR → koniec falošných e-mail alertov). Testy `tests/test_word_import.py` (3) → spolu 103.
- [x] **Gemini 429: opravená textová aj fotková cesta** ✅ 2026-07-13 (commit `9b939ea9`)
  - `_post_gemini_generate_content` aj `..._from_image_gemini` pri 429 vyhodia `GeminiRateLimited` OKAMŽITE (žiadnych 8 odsúdených requestov) a router prepne na ďalšieho providera (Groq). 404 ďalej skúša modely (to je žiaduce).
  - Chyby modelov sa zbierajú všetky (predtým `last_error` prepisoval predošlé).
  - Vyčerpaná kvóta sa mapuje na HTTP **429** „skúste neskôr" (predtým generic 502) — konzistentné s video cestou.
- [x] **AI kvóta sa vracia, keď generovanie zlyhá** ✅ 2026-07-13 (commit `9b939ea9`)
  - `refund_ai_quota()` v `services/limits.py` — volá sa pri konečnom zlyhaní (502/429) v `ai-create`, `ai-create-from-image` aj `ai-create-from-video`.
  - Odpočet ostáva PRED volaním AI (paralelné requesty limit neobídu), refund je kompenzácia po zlyhaní.
  - Testy `tests/test_ai_stability.py` (7) → spolu 100 testov.
- [ ] **Overiť, prečo nenaskočil fallback na Groq** (2026-07-10) — 🔧 diagnostika nasadená 2026-07-13
  - `_provider_chain("gemini")` vracia `["gemini", "groq"]`, ale filtruje na providerov s nastaveným kľúčom. Používateľ dostal 502 → buď Groq tiež zlyhal, alebo appka `GROQ_API_KEY` nenašla.
  - 🔎 **Stopa (2026-07-10):** na Cloud Rune kľúč **je** nastavený (riadok 12, hodnota `gsk_...`) — **preveriť preklep v NÁZVE premennej**, appka by ju potom nenašla a Groq by z reťazca ticho vypadol. Viď go-live checklist krok 7.
  - ✅ **Nasadený startup log** `AI providers: claude=ON, gemini=ON, groq=OFF` (main.py lifespan, commit `9b939ea9`) — **ďalší krok: po deployi pozrieť Cloud Run log** (Logs Explorer alebo admin log viewer, hľadať „AI providers"). Ak `groq=OFF` → premenovať env premennú na presne `GROQ_API_KEY`.
- [ ] **AI kategória z YouTube videa** 🚧 kód hotový 2026-07-10 (backend + frontend) — **zostáva overiť naživo**
  - Podnet: používateľ vložil YouTube odkaz do bežného AI promptu → do modelu sa poslal len text URL (žiadne video), navyše Gemini vrátilo 429. Video appka dovtedy nepodporovala vôbec.
  - **Gemini-only, bez fallbacku.** YouTube URL vie spracovať jedine Gemini (`file_data.file_uri`, **len v1beta** — vo v1 to nefunguje). Groq ani Claude odkaz nestiahnu, takže `_provider_chain` sa tu nepoužíva.
  - **PLUS-only** (rozhodnuté 2026-07-10) — video je najdrahšia AI operácia a bez fallbacku; free tier Gemini má strop **8 h YouTube videa/deň na projekt**, takže pár dlhých videí od free účtov by vyžralo kvótu všetkým. Endpoint vracia 403 pre free účet.
  - **Strop dĺžky 20 min** (`youtube.VIDEO_MAX_SECONDS`). Dĺžku vie povedať len **YouTube Data API v3** → voliteľný env `YOUTUBE_API_KEY`. **Bez kľúča sa kontrola dĺžky preskočí** (video prejde) — ak chceme strop reálne vynucovať, kľúč treba nastaviť na Cloud Run.
  - Predkontrola cez **oEmbed** (bez kľúča): verejné video → 200 + názov, súkromné/zmazané/neexistujúce → 400. Beží PRED volaním Gemini, aby zlé video nespálilo kvótu. Cudzie domény sú odmietnuté (`file_uri` sa nesmie dať nasmerovať inam).
  - Nové: `app/services/youtube.py`, `generate_category_and_words_from_video_gemini()` + `GeminiRateLimited` v `ai_category_service.py`, `POST /api/v1/categories/ai-create-from-video` (`@limiter.limit("5/hour")`), schéma `AICategoryFromVideoRequest`. Max 40 slov/video.
  - 429 od Gemini sa mapuje na HTTP 429 („skús neskôr"), nie na 502 — a **neskúša ďalší model** (spoločná kvóta projektu, ďalší request je len ďalšia rana do limitu).
  - Testy `tests/test_ai_video.py` (18: parsovanie URL vrátane shorts/youtu.be/cudzej domény, PLUS gating, 400/429/500 mapovanie) → spolu 92 testov.
  - ⚠️ **Reálne volanie Gemini s videom zatiaľ neoverené** — lokálne nie je `GEMINI_API_KEY` a produkčný kľúč mal 2026-07-10 vyčerpanú kvótu (429). Tvar payloadu je z dokumentácie, nie z živého behu. **Prvý beh treba overiť na Cloud Run.**
  - [x] **Frontend** ✅ 2026-07-10 — tlačidlo „AI z videa" s odznakom PLUS + modál `aiVideoModal` (stepper Overujem → Pozerám → Ukladám) v `dashboard.html`. Klientská kontrola URL (`YT_URL_RE`) drží parity so serverom vrátane `youtube-nocookie.com`; PLUS gating v UI len šetrí request, autorita je server (403). `aiErrorMessage` doplnený o vetvu 403. SW cache **v32** (dashboard je precachovaný — bez bumpu by starí používatelia tlačidlo nevideli).
  - [ ] **Overiť naživo na Cloud Run** — nasadiť, pustiť jedno krátke verejné video, skontrolovať, že Gemini payload prejde a slovíčka sa uložia
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
