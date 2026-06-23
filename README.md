# LexiNova

**LexiNova** je moderná webová aplikácia na učenie sa slovíčok s AI generovaním sád, flashcard testami a inteligentným opakovaním. Funguje aj offline ako PWA.

**Live demo:** [lexinova-1096007793591.us-central1.run.app](https://lexinova-1096007793591.us-central1.run.app)
**Vyskúšaj bez registrácie:** [/demo](https://lexinova-1096007793591.us-central1.run.app/demo)

## Funkcie

- **AI generovanie slovíčok** - Napíš tému, vyber jazyky — AI vytvorí celú sadu (Groq / Gemini / Claude)
- **Demo bez registrácie** - Vyskúšaj flashcard učenie hneď na `/demo`
- **Autentifikácia** - Email/heslo alebo Google OAuth
- **Správa slovíčok** - Vytváranie, úprava, mazanie
- **Kategórie** - Organizácia slovíčok do tematických sád
- **Flashcard testovanie** - Inteligentné opakovanie podľa úrovne znalosti (neviem / učím sa / viem)
- **Opakovanie** - Dedikovaný režim opakovania naučených slovíčok
- **Obojsmerné testovanie** - originál → preklad alebo preklad → originál
- **Štatistiky** - Sledovanie pokroku a úspešnosti
- **Dark mode** - Svetlý / tmavý režim
- **Plus verzia** - Rozšírené limity kategórií
- **PWA** - Inštalovateľná ako mobilná appka, funguje offline
- **Email notifikácie** - Uvítacie emaily, reset hesla, notifikácie o dotazoch
- **Kontaktný formulár** - Pätička s formulárom na zanechanie dotazu (bez prihlásenia)
- **Export dát** - JSON export, GDPR-friendly
- **Rate limiting** - Ochrana API endpointov (slowapi)
- **Admin panel** - Správa používateľov, platobný prehľad, správa dopytov

## Technológie

### Backend
- **FastAPI** 0.118.0 - Moderný Python web framework
- **SQLAlchemy** 2.0.43 - ORM pre prácu s databázou
- **PostgreSQL** - Databáza (Supabase)
- **Bcrypt** - Hashovanie hesiel
- **Python-JOSE** - JWT tokeny
- **FastAPI-Mail** - Email služba
- **Authlib** - Google OAuth integrácia
- **Anthropic** - Claude AI SDK
- **slowapi** - Rate limiting
- **httpx** - Async HTTP klient (Gemini REST API, Groq REST API)

### AI poskytovatelia
- **Groq** (predvolený) - `llama-3.3-70b-versatile`, free tier 14 400 req/deň
- **Google Gemini** - `gemini-2.0-flash`, free tier cez AI Studio
- **Anthropic Claude** - `claude-opus-4-8`, platený

### Frontend
- **Jinja2** - Template engine
- **Vanilla JavaScript** - Bez frameworkov
- **CSS3** - Moderný dizajn s dark mode
- **Service Worker** - PWA funkcionalita

## Požiadavky

- Python 3.12+
- PostgreSQL databáza (Supabase)
- Gmail účet pre SMTP (email služba)
- Google Cloud projekt (pre OAuth)
- API kľúč pre AI (Groq odporúčaný — zadarmo na [console.groq.com](https://console.groq.com))

## Inštalácia a spustenie

### 1. Klonovanie repozitára

```bash
git clone https://github.com/Lipnicanmilos/lexinova.git
cd lexinova
```

### 2. Vytvorenie virtuálneho prostredia

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Inštalácia závislostí

```bash
pip install -r requirements.txt
```

### 4. Konfigurácia environment variables

Vytvor `.env` súbor v root adresári projektu:

```env
# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Security
SECRET_KEY=your-super-secret-key-min-32-characters
SESSION_SECRET=your-session-secret-key

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Email (Gmail SMTP)
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-specific-password
MAIL_FROM=your-email@gmail.com

# Development
DEBUG=true

# AI poskytovatelia (stačí jeden)
GROQ_API_KEY=gsk_...          # Groq — zadarmo, odporúčané
GEMINI_API_KEY=AIzaSy...      # Google Gemini — zadarmo cez AI Studio
ANTHROPIC_API_KEY=sk-ant-...  # Claude — platený

# Admin (voliteľné)
ADMIN_EMAILS=admin@example.com,other@example.com  # Čiarkou oddelené emaily adminov
INQUIRY_TO=admin@example.com                       # Kam posielať notifikácie o dotazoch (default: lipnicanmilos@gmail.com)

# Databázová migrácia — spusti create_all len pri explicitnom požiadaní
# RUN_DB_CREATE_ALL=1

# Voliteľné — override modelu
# GROQ_MODEL=llama-3.3-70b-versatile
# GEMINI_MODEL=gemini-2.0-flash
# CLAUDE_MODEL=claude-opus-4-8
```

### 5. Spustenie aplikácie

```bash
# Development server
uvicorn app.main:app --reload --port 8000

# Alebo
python -m app.main
```

Aplikácia bude dostupná na: `http://localhost:8000`

## Databázová štruktúra

### Users
- `id` - Primárny kľúč
- `email` - Unikátny email
- `name` - Meno používateľa
- `password` - Hashované heslo (bcrypt)
- `is_plus` - Plus status
- `dark_mode` - Dark mode preferencia
- `created_at` - Dátum vytvorenia
- `last_login` - Posledné prihlásenie
- `reset_token` - Token pre reset hesla
- `reset_token_expires` - Expirácia tokenu

### Categories
- `id` - Primárny kľúč
- `name` - Názov kategórie
- `description` - Popis
- `user_id` - Foreign key na users
- `created_at` - Dátum vytvorenia
- `updated_at` - Dátum aktualizácie

### Words
- `id` - Primárny kľúč
- `original_word` - Pôvodné slovo
- `translation` - Preklad
- `language_from` - Jazyk pôvodného slova
- `language_to` - Jazyk prekladu
- `category_id` - Foreign key na categories (CASCADE delete)
- `user_id` - Foreign key na users
- `knowledge_level` - Úroveň znalosti (`dont_know` / `learning` / `know`)
- `times_tested` - Počet testovaní
- `times_correct` - Počet správnych odpovedí
- `last_tested` - Dátum posledného testu
- `created_at` - Dátum vytvorenia
- `updated_at` - Dátum aktualizácie

### Payments
- `id` - Primárny kľúč
- `user_id` - Foreign key na users (SET NULL pri zmazaní)
- `email` - Email (redundantný — zachová sa aj po zmazaní usera)
- `provider` - Poskytovateľ platby (`stripe` / `paddle` / `manual`)
- `provider_payment_id` - ID transakcie u poskytovateľa
- `provider_subscription_id` - ID predplatného
- `status` - Stav platby (`succeeded` / `pending` / `failed` / `refunded` / `canceled`)
- `amount` - Suma
- `currency` - ISO kód meny (default `EUR`)
- `description` - Popis platby
- `created_at` - Dátum vytvorenia

### Inquiries
- `id` - Primárny kľúč
- `name` - Meno odosielateľa (voliteľné)
- `email` - Email odosielateľa (voliteľné)
- `message` - Text dotazu
- `page` - Stránka, z ktorej bol dotaz odoslaný
- `user_agent` - User-Agent prehliadača
- `is_read` - Prečítané (admin)
- `created_at` - Dátum vytvorenia

## Štruktúra projektu

```
LexiNova/
├── app/
│   ├── config/          # Konfiguračné súbory
│   ├── database/        # Databázové pripojenie
│   │   └── connection.py
│   ├── models/          # SQLAlchemy modely
│   │   ├── user.py
│   │   ├── category.py
│   │   ├── word.py
│   │   ├── payment.py
│   │   └── inquiry.py
│   ├── routers/         # API endpointy a stránky
│   │   ├── pages.py     # HTML stránky
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── categories.py
│   │   ├── words.py
│   │   ├── admin.py     # Admin panel
│   │   └── inquiry.py   # Kontaktné dopyty
│   ├── schemas/         # Pydantic schémy
│   │   ├── user.py
│   │   ├── category.py
│   │   ├── word.py
│   │   └── ai_category.py
│   ├── services/        # Business logika
│   │   ├── auth_service.py
│   │   ├── email_service.py
│   │   ├── ai_category_service.py
│   │   ├── session_auth.py
│   │   ├── stats_service.py
│   │   └── runtime.py
│   ├── static/          # Statické súbory (CSS, JS, ikony)
│   │   └── js/
│   │       ├── ai_create_category.js
│   │       ├── offline-cache.js
│   │       └── site-footer.js  # Kontaktný formulár v pätičke
│   ├── templates/       # Jinja2 šablóny
│   └── main.py          # Hlavný súbor aplikácie
├── .env                 # Environment variables (nie v gite)
├── .gitignore
├── requirements.txt     # Python závislosti
├── runtime.txt          # Python verzia
└── README.md
```

## API Endpointy

### Autentifikácia
- `POST /api/v1/register` - Registrácia nového používateľa
- `POST /api/v1/login` - Prihlásenie
- `GET /api/v1/logout` - Odhlásenie
- `GET /auth/google` - Google OAuth prihlásenie
- `POST /api/v1/forgot-password` - Zabudnuté heslo
- `POST /api/v1/reset-password` - Reset hesla

### Používateľ
- `GET /api/user` - Získať aktuálneho používateľa
- `PATCH /api/user/plus` - Prepnúť Plus status
- `PATCH /api/user/dark-mode` - Prepnúť dark mode
- `DELETE /api/user` - Zmazať účet
- `GET /api/user/stats` - Získať štatistiky
- `GET /api/user/export` - Exportovať dáta (JSON)

### Kategórie
- `GET /api/v1/categories` - Zoznam kategórií
- `POST /api/v1/categories` - Vytvoriť kategóriu
- `GET /api/v1/categories/{id}` - Detail kategórie
- `PUT /api/v1/categories/{id}` - Aktualizovať kategóriu
- `DELETE /api/v1/categories/{id}` - Zmazať kategóriu
- `GET /api/v1/categories/{id}/stats` - Štatistiky kategórie
- `POST /api/v1/categories/ai-create` - AI generovanie kategórie so slovíčkami

#### Parametre AI vytvorenia
```json
{
  "prompt": "základné slovíčka pri cestovaní",
  "language_from": "en",
  "language_to": "sk",
  "count": 25,
  "ai_provider": "groq"
}
```
> `ai_provider`: `"groq"` (predvolený) | `"gemini"` | `"claude"`

### Slovíčka
- `GET /api/v1/words` - Zoznam slovíčok (s filtrami)
- `POST /api/v1/words` - Vytvoriť slovíčko
- `GET /api/v1/words/{id}` - Detail slovíčka
- `PUT /api/v1/words/{id}` - Aktualizovať slovíčko
- `DELETE /api/v1/words/{id}` - Zmazať slovíčko
- `PATCH /api/v1/words/{id}/knowledge` - Aktualizovať úroveň znalosti
- `POST /api/v1/words/test/start` - Začať test
- `POST /api/v1/words/test/submit` - Odoslať výsledky testu
- `POST /api/v1/words/import` - Import slovíčok (Excel/CSV)

### Kontaktný formulár (verejný)
- `POST /api/inquiry` - Odoslať dotaz (nevyžaduje prihlásenie)

### Admin (vyžaduje admin email v `ADMIN_EMAILS`)
- `GET /admin` - Admin panel (HTML)
- `GET /api/admin/users` - Zoznam používateľov so štatistikami (filter: `q`, `plus`)
- `PATCH /api/admin/users/{id}` - Upraviť používateľa (email, is_plus)
- `DELETE /api/admin/users/{id}` - Zmazať používateľa (vrátane jeho dát)
- `GET /api/admin/payments` - Prehľad platieb a príjmov
- `GET /api/admin/inquiries` - Zoznam dopytov
- `PATCH /api/admin/inquiries/{id}` - Prepnúť prečítané/neprečítané
- `DELETE /api/admin/inquiries/{id}` - Zmazať dopyt

## Deployment (Google Cloud Run)

### 1. Build a deploy

```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/lexinova
gcloud run deploy lexinova --image gcr.io/PROJECT_ID/lexinova --platform managed
```

### 2. Nastavenie secrets

V Google Cloud Console nastav:
- `DATABASE_URL`
- `SECRET_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `GROQ_API_KEY` (alebo `GEMINI_API_KEY` / `ANTHROPIC_API_KEY`)
- `ADMIN_EMAILS` - čiarkou oddelené emaily adminov
- `INQUIRY_TO` - email pre notifikácie o dotazoch

### 3. Prvotná migrácia databázy

Pre vytvorenie schémy pri prvom nasadení spusti s `RUN_DB_CREATE_ALL=1`:

```bash
gcloud run jobs execute lexinova --update-env-vars RUN_DB_CREATE_ALL=1
```

> Pri bežnom štarte sa `create_all` nespúšťa — zrýchľuje to cold start a šetrí pripojenia na Supabase.

## Bezpečnosť

- Heslá hashované pomocou bcrypt
- JWT tokeny pre autentifikáciu
- CORS konfigurácia
- Session middleware s HTTPS
- SQL injection ochrana (SQLAlchemy ORM)
- Environment variables pre citlivé dáta
- Rate limiting (slowapi)
- Admin endpointy chránené allow-listom emailov (`ADMIN_EMAILS`)

## Licencia

MIT License - Voľne použiteľné pre osobné aj komerčné účely.

## Autor

**Miloš Lipničan**
- GitHub: [@Lipnicanmilos](https://github.com/Lipnicanmilos)
- Email: lipnicanmilos@gmail.com

## Prispievanie

Pull requesty sú vítané! Pre väčšie zmeny prosím najprv otvor issue.
