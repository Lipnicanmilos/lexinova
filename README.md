# 📚 LexiNova

**LexiNova** je moderná webová aplikácia na učenie sa slovíčok s podporou flashcards, testov a pokročilých funkcií pre sledovanie pokroku.

## ✨ Funkcie

- 🔐 **Autentifikácia** - Registrácia/prihlásenie emailom alebo cez Google OAuth
- 📝 **Správa slovíčok** - Vytváranie, úprava a mazanie slovíčok
- 📂 **Kategórie** - Organizácia slovíčok do kategórií
- 🎯 **Testovanie** - Flashcard testy s rôznymi úrovňami znalostí
- 📊 **Štatistiky** - Sledovanie pokroku a úspešnosti
- 🌙 **Dark mode** - Prepínanie medzi svetlým a tmavým režimom
- 💎 **Plus verzia** - Rozšírené funkcie pre pokročilých používateľov
- 📱 **PWA podpora** - Inštalovateľná ako mobilná aplikácia
- 📧 **Email notifikácie** - Uvítacie emaily a reset hesla
- 📤 **Export dát** - Export všetkých dát do JSON formátu
- 🤖 **AI vytváranie kategórií** - Automatické generovanie kategórií a slovíčok pomocou AI (Groq / Gemini / Claude)

## 🛠️ Technológie

### Backend
- **FastAPI** 0.118.0 - Moderný Python web framework
- **SQLAlchemy** 2.0.43 - ORM pre prácu s databázou
- **PostgreSQL** - Databáza (Supabase)
- **Bcrypt** - Hashovanie hesiel
- **Python-JOSE** - JWT tokeny
- **FastAPI-Mail** - Email služba
- **Authlib** - Google OAuth integrácia
- **Anthropic** - Claude AI SDK
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

## 📋 Požiadavky

- Python 3.12+
- PostgreSQL databáza (Supabase)
- Gmail účet pre SMTP (email služba)
- Google Cloud projekt (pre OAuth)
- API kľúč pre AI (Groq odporúčaný — zadarmo na [console.groq.com](https://console.groq.com))

## 🚀 Inštalácia a spustenie

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

## 🗄️ Databázová štruktúra

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
- `category_id` - Foreign key na categories
- `user_id` - Foreign key na users
- `knowledge_level` - Úroveň znalosti (dont_know, learning, know)
- `times_tested` - Počet testovaní
- `times_correct` - Počet správnych odpovedí
- `last_tested` - Dátum posledného testu
- `created_at` - Dátum vytvorenia
- `updated_at` - Dátum aktualizácie

## 📁 Štruktúra projektu

```
LexiNova/
├── app/
│   ├── config/          # Konfiguračné súbory
│   ├── database/        # Databázové pripojenie
│   │   └── connection.py
│   ├── Http/            # HTTP utilities
│   ├── models/          # SQLAlchemy modely
│   │   ├── user.py
│   │   ├── category.py
│   │   └── word.py
│   ├── routers/         # API endpointy
│   │   ├── words.py
│   │   ├── users.py
│   │   ├── categories.py
│   │   ├── auth.py
│   │   └── localization.py
│   ├── schemas/         # Pydantic schémy
│   │   ├── user.py
│   │   ├── category.py
│   │   ├── word.py
│   │   └── ai_category.py
│   ├── services/        # Business logika
│   │   ├── auth_service.py
│   │   ├── email_service.py
│   │   └── ai_category_service.py
│   ├── static/          # Statické súbory (CSS, JS, ikony)
│   ├── templates/       # Jinja2 šablóny
│   └── main.py          # Hlavný súbor aplikácie
├── .env                 # Environment variables (nie v gite)
├── .gitignore
├── requirements.txt     # Python závislosti
├── runtime.txt          # Python verzia
└── README.md
```

## 🔑 API Endpointy

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
- `GET /api/user/export` - Exportovať dáta

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

## 🌐 Deployment (Google Cloud Run)

### 1. Príprava

```bash
# Vytvor Dockerfile (ak ešte neexistuje)
# Nastav secrets v Google Cloud Secret Manager
```

### 2. Build a deploy

```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/lexinova
gcloud run deploy lexinova --image gcr.io/PROJECT_ID/lexinova --platform managed
```

### 3. Nastavenie secrets

V Google Cloud Console nastav:
- `DATABASE_URL`
- `SECRET_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `GROQ_API_KEY` (alebo `GEMINI_API_KEY` / `ANTHROPIC_API_KEY`)

## 🔒 Bezpečnosť

- ✅ Heslá hashované pomocou bcrypt
- ✅ JWT tokeny pre autentifikáciu
- ✅ CORS konfigurácia
- ✅ Session middleware s HTTPS
- ✅ SQL injection ochrana (SQLAlchemy ORM)
- ✅ Environment variables pre citlivé dáta
- ✅ Rate limiting (odporúčané pridať)

## 🧪 Testovanie

```bash
# Spustenie testov (ak sú implementované)
pytest

# Test coverage
pytest --cov=app
```

## 📝 Licencia

MIT License - Voľne použiteľné pre osobné aj komerčné účely.

## 👨‍💻 Autor

**Miloš Lipničan**
- GitHub: [@Lipnicanmilos](https://github.com/Lipnicanmilos)
- Email: your-email@example.com

## 🤝 Prispievanie

Pull requesty sú vítané! Pre väčšie zmeny prosím najprv otvor issue.

## 📞 Podpora

Ak máš otázky alebo problémy, otvor issue na GitHube.

---

**Vyrobené s ❤️ pomocou FastAPI a Python**
