from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import logging
import secrets
import json
from datetime import datetime, timedelta
from fastapi.responses import StreamingResponse
from passlib.hash import argon2
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from dotenv import load_dotenv  # Lokálne načíta .env, na Cloud Run sa ignoruje

# Importy z vašich modulov
from app.database.connection import get_db, SessionLocal, engine, Base
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse
from app.models.category import Category
from app.models.user import User
from app.models.word import Word
from app.routers import words
from app.models.word import KnowledgeLevel
from app.routers.localization import get_language
from sqlalchemy.orm import Session
from sqlalchemy import func

# Auth a Email services
from app.services.auth_service import hash_password, verify_password, create_access_token
from app.services.email_service import send_welcome_email

load_dotenv()

# Konfigurácia logovania
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cloud Run načíta secrets automaticky ako env variables
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

app = FastAPI()

# Statické súbory
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse("app/static/favicon.ico")

@app.get('/apple-touch-icon.png', include_in_schema=False)
async def apple_touch_icon():
    return FileResponse("app/static/apple-touch-icon.png")

@app.get('/manifest.json', include_in_schema=False)
async def get_manifest():
    return FileResponse(
        "app/static/manifest.json",
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

@app.get('/sw.js', include_in_schema=False)
async def get_sw():
    return FileResponse(
        "app/static/sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

# Words router
app.include_router(words.router)

# ✅ OPRAVA: Session middleware MUSÍ byť pridaný PRED CORSMiddleware
# Starlette spracováva middleware v opačnom poradí ako sú pridané
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY or os.getenv("SESSION_SECRET", "dev-secret-123"),
    https_only=os.getenv("DEBUG", "false").lower() != "true",  # ✅ False lokálne, True na Cloud Run
    same_site="lax",
    max_age=2592000,  # Session vydrží 30 dní (lepšie pre mobil/PWA)
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "https://wordkeeper-1096007793591.us-central1.run.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth configuration
config = Config('.env')
oauth = OAuth(config)

oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    authorize_url='https://accounts.google.com/o/oauth2/v2/auth',
    access_token_url='https://oauth2.googleapis.com/token',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    jwks_uri='https://www.googleapis.com/oauth2/v3/certs',
    client_kwargs={'scope': 'openid email profile'}
)

# Templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ============================================================
# HELPER FUNKCIE — optimalizované DB queries (1 query namiesto N+1)
# ============================================================

def _empty_level_counts() -> dict:
    return {level.value: 0 for level in KnowledgeLevel}


def get_category_word_summary(db: Session, user_id: int, category_ids: list) -> dict:
    """
    Vráti {category_id: {'total_words': int, 'level_counts': dict, 'level_percentages': dict}}
    pre VŠETKY kategórie naraz pomocou jedného GROUP BY query
    (namiesto 1 + 3 queries per kategória).
    """
    if not category_ids:
        return {}

    rows = db.query(
        Word.category_id,
        Word.knowledge_level,
        func.count(Word.id)
    ).filter(
        Word.user_id == user_id,
        Word.category_id.in_(category_ids)
    ).group_by(Word.category_id, Word.knowledge_level).all()

    summary = {cid: _empty_level_counts() for cid in category_ids}
    for cat_id, level, count in rows:
        level_value = level.value if hasattr(level, 'value') else level
        if cat_id in summary:
            summary[cat_id][level_value] = count

    result = {}
    for cid in category_ids:
        level_counts = summary[cid]
        total = sum(level_counts.values())
        if total > 0:
            level_percentages = {k: round(v / total * 100, 1) for k, v in level_counts.items()}
        else:
            level_percentages = _empty_level_counts_float()
        result[cid] = {
            'total_words': total,
            'level_counts': level_counts,
            'level_percentages': level_percentages
        }
    return result


def _empty_level_counts_float() -> dict:
    return {level.value: 0.0 for level in KnowledgeLevel}


def get_user_level_counts(db: Session, user_id: int) -> dict:
    """Vráti {level: count} pre všetky slovíčka usera, 1 query namiesto 3."""
    rows = db.query(
        Word.knowledge_level,
        func.count(Word.id)
    ).filter(
        Word.user_id == user_id
    ).group_by(Word.knowledge_level).all()

    level_counts = _empty_level_counts()
    for level, count in rows:
        level_value = level.value if hasattr(level, 'value') else level
        level_counts[level_value] = count
    return level_counts



mail_config = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True
)


# ============================================================
# PAGE ROUTES
# ============================================================

@app.get("/")
async def read_root(request: Request):
    lang = get_language(request)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "lang": lang
    })

@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/dashboard")
async def dashboard_page(request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session:
        return RedirectResponse(url='/login', status_code=303)
    # ✅ OPRAVA: is_plus a dark_mode vždy z DB
    db_user = db.query(User).filter(User.id == user_session['id']).first()
    if not db_user:
        request.session.clear()
        return RedirectResponse(url='/login', status_code=303)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "email": db_user.email,
        "is_plus": db_user.is_plus,
        "dark_mode": db_user.dark_mode
    })

@app.get("/profile")
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session:
        return RedirectResponse(url='/login', status_code=303)
    # ✅ Vždy načítavaj user dáta z DB, nie len zo session
    user = db.query(User).filter(User.id == user_session['id']).first()
    if not user:
        request.session.clear()
        return RedirectResponse(url='/login', status_code=303)
    context = {"request": request, "email": user.email, "user": user}
    return templates.TemplateResponse("profile.html", context)

@app.get("/category/{category_id}/words")
async def category_words_page(request: Request, category_id: int, db: Session = Depends(get_db)):
    user = request.session.get('user')
    if not user:
        return RedirectResponse(url='/login', status_code=303)

    user_id = user['id']

    # ✅ is_plus vždy čítaj z DB, nie zo session
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        request.session.clear()
        return RedirectResponse(url='/login', status_code=303)
    is_plus_user = db_user.is_plus

    category = db.query(Category).filter(Category.id == category_id, Category.user_id == user_id).first()
    if not category:
        return RedirectResponse(url='/dashboard', status_code=303)

    if not is_plus_user:
        newest_category = db.query(Category)\
            .filter(Category.user_id == user_id)\
            .order_by(Category.created_at.desc())\
            .first()
        if newest_category and newest_category.id != category_id:
            return RedirectResponse(url='/dashboard', status_code=303)

    summary = get_category_word_summary(db, user_id, [category.id])[category.id]

    category_data = {
        "id": category.id,
        "name": category.name,
        "description": category.description,
        "level_percentages": summary['level_percentages']
    }

    return templates.TemplateResponse("category_words.html", {
        "request": request,
        "email": user.get('email', ''),
        "category": category_data,
        "dark_mode": db_user.dark_mode  # ✅ dark_mode vždy z DB
    })

@app.get("/test")
async def test_page(request: Request, category: int = None, level: str = None, db: Session = Depends(get_db)):
    user = request.session.get('user')
    if not user:
        return RedirectResponse(url='/login', status_code=303)

    user_id = user['id']

    # ✅ is_plus z DB
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        request.session.clear()
        return RedirectResponse(url='/login', status_code=303)
    is_plus_user = db_user.is_plus

    category_data = None
    if category:
        category_data = db.query(Category).filter(Category.id == category, Category.user_id == user_id).first()
        if not category_data:
            return RedirectResponse(url='/dashboard', status_code=303)

        if not is_plus_user:
            newest_category = db.query(Category)\
                .filter(Category.user_id == user_id)\
                .order_by(Category.created_at.desc())\
                .first()
            if newest_category and newest_category.id != category:
                return RedirectResponse(url='/dashboard', status_code=303)

    return templates.TemplateResponse("flashcard_test.html", {
        "request": request,
        "email": user.get('email', ''),
        "category": category_data,
        "level": level
    })

@app.get("/repeat")
async def repeat_page(request: Request, category: int = None, level: str = None, db: Session = Depends(get_db)):
    user = request.session.get('user')
    if not user:
        return RedirectResponse(url='/login', status_code=303)

    user_id = user['id']

    # ✅ is_plus z DB
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        request.session.clear()
        return RedirectResponse(url='/login', status_code=303)
    is_plus_user = db_user.is_plus

    category_data = None
    if category:
        category_data = db.query(Category).filter(Category.id == category, Category.user_id == user_id).first()
        if not category_data:
            return RedirectResponse(url='/dashboard', status_code=303)

        if not is_plus_user:
            newest_category = db.query(Category)\
                .filter(Category.user_id == user_id)\
                .order_by(Category.created_at.desc())\
                .first()
            if newest_category and newest_category.id != category:
                return RedirectResponse(url='/dashboard', status_code=303)

    return templates.TemplateResponse("repeat.html", {
        "request": request,
        "email": user.get('email', ''),
        "category": category_data,
        "level": level
    })


# ============================================================
# AUTH API ENDPOINTS
# ============================================================

class UserRegister(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

@app.post("/api/v1/register")
async def register(request: Request, user_data: UserRegister, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        email = user_data.email
        password = user_data.password
        name = user_data.name or email.split('@')[0]

        if email and password:
            existing_user = db.query(User).filter(User.email == email).first()
            if existing_user:
                raise HTTPException(status_code=400, detail="User with this email already exists")

            hashed_password = hash_password(password)

            new_user = User(
                email=email,
                name=name,
                is_plus=False,
                password=hashed_password
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)

            # Uvítací email cez BackgroundTasks — nezabrzdí odozvu
            background_tasks.add_task(send_welcome_email, new_user.email, new_user.name)

            session_user = {
                "id": new_user.id,
                "email": new_user.email,
                "name": new_user.name,
                "is_plus": new_user.is_plus,
                "dark_mode": new_user.dark_mode
            }
            request.session['user'] = session_user

            return JSONResponse({
                "message": "Registration successful",
                "user": session_user
            })
        else:
            raise HTTPException(status_code=400, detail="Email and password required")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/login")
async def login(request: Request, user_data: UserLogin, db: Session = Depends(get_db)):
    try:
        email = user_data.email
        password = user_data.password

        if email and password:
            user = db.query(User).filter(User.email == email).first()

            if not user:
                raise HTTPException(status_code=400, detail="User not found. Please register first.")

            # Overenie hesla — bcrypt alebo argon2 s migráciou na bcrypt
            verified = False
            try:
                if verify_password(password, user.password):
                    verified = True
            except ValueError:
                if argon2.verify(password, user.password):
                    user.password = hash_password(password)
                    db.commit()
                    verified = True

            if not verified:
                raise HTTPException(status_code=400, detail="Incorrect password")

            user.last_login = datetime.utcnow()
            db.commit()

            session_user = {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "is_plus": user.is_plus,
                "dark_mode": user.dark_mode
            }
            request.session['user'] = session_user

            return JSONResponse({
                "message": "Login successful",
                "user": session_user
            })
        else:
            raise HTTPException(status_code=400, detail="Email and password required")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/logout")
async def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out successfully"}


# ============================================================
# GOOGLE OAUTH
# ============================================================

@app.get('/auth/google')
async def google_login(request: Request):
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "https://wordkeeper-1096007793591.us-central1.run.app/auth/google/callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get('/auth/google/callback', name='google_callback')
async def google_callback(request: Request, db: Session = Depends(get_db)):
    logger.info("Google callback started")
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = await oauth.google.userinfo(token=token)
        logger.info(f"User info received for: {user_info.get('email')}")

        if not user_info or not user_info.get('email'):
            raise HTTPException(status_code=400, detail="Failed to get user info from Google")

        email = user_info['email']
        name = user_info.get('name', email.split('@')[0])
        picture = user_info.get('picture', '')

        user = db.query(User).filter(User.email == email).first()
        new_user = False

        if not user:
            hashed_password = hash_password("google_auth_dummy_password")
            user = User(
                email=email,
                name=name,
                password=hashed_password,
                is_plus=False
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            new_user = True
            logger.info(f"New user created: {user.email}")

            # Uvítací email pre nového Google užívateľa
            try:
                message = MessageSchema(
                    subject="Vitajte v WordKeeper! 🎉",
                    recipients=[email],
                    body=f"""Ahoj {name},

vitajte v WordKeeper! Sme radi, že ste sa k nám pridali cez Google.

Začnite učiť nové slovíčka ešte dnes:
https://wordkeeper-1096007793591.us-central1.run.app/dashboard

S pozdravom,
Tím WordKeeper
""",
                    subtype="plain"
                )
                fm = FastMail(mail_config)
                await fm.send_message(message)
            except Exception as e:
                logger.error(f"Welcome email error: {e}")
        else:
            if not user.name and name:
                user.name = name
            user.last_login = datetime.utcnow()
            db.commit()

        session_user = {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "picture": picture,
            "is_plus": user.is_plus,
            "dark_mode": user.dark_mode
        }
        request.session['user'] = session_user

        jwt_token = create_access_token(data={"sub": user.email})
        callback_url = f"{request.base_url}auth/callback?token={jwt_token}&new_user={'1' if new_user else '0'}&email={email}&name={name}"
        return RedirectResponse(url=callback_url)

    except Exception as e:
        logger.error(f"Google auth error: {e}")
        return RedirectResponse(url='/login?error=google_auth_failed')


@app.get("/auth/callback")
async def auth_callback(request: Request):
    return templates.TemplateResponse("auth-callback.html", {"request": request})


# ============================================================
# USER API ENDPOINTS
# ============================================================

@app.get("/api/user")
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.id == user_session['id']).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return JSONResponse({
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "picture": user_session.get('picture', ''),
        "is_plus": user.is_plus,
        "dark_mode": user.dark_mode,
        "created_at": user.created_at.isoformat() if user.created_at else None
    })


@app.patch("/api/user/plus")
async def toggle_user_plus(request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.id == user_session['id']).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_plus = not user.is_plus
    db.commit()
    db.refresh(user)

    user_session['is_plus'] = user.is_plus
    request.session['user'] = user_session

    return JSONResponse({
        "message": "Plus status updated successfully",
        "is_plus": user.is_plus
    })


@app.patch("/api/user/dark-mode")
async def toggle_user_dark_mode(request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.id == user_session['id']).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.dark_mode = not user.dark_mode
    db.commit()
    db.refresh(user)

    user_session['dark_mode'] = user.dark_mode
    request.session['user'] = user_session

    return JSONResponse({
        "message": "Dark mode status updated successfully",
        "dark_mode": user.dark_mode
    })


@app.delete("/api/user")
async def delete_user(request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.id == user_session['id']).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    request.session.clear()

    return JSONResponse({
        "message": "User account and associated data deleted successfully"
    })


@app.get("/api/user/stats")
async def get_user_stats(request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user_session['id']

    words_count = db.query(func.count(Word.id)).filter(Word.user_id == user_id).scalar() or 0
    categories_count = db.query(func.count(Category.id)).filter(Category.user_id == user_id).scalar() or 0
    tests_taken = db.query(func.coalesce(func.sum(Word.times_tested), 0)).filter(Word.user_id == user_id).scalar() or 0
    times_correct = db.query(func.coalesce(func.sum(Word.times_correct), 0)).filter(Word.user_id == user_id).scalar() or 0

    success_rate = 0
    if tests_taken > 0:
        success_rate = round((times_correct / tests_taken) * 100, 2)

    level_counts = get_user_level_counts(db, user_id)

    return JSONResponse({
        "total_words": words_count,
        "total_categories": categories_count,
        "tests_taken": tests_taken,
        "success_rate": success_rate,
        "words_by_level": level_counts
    })


@app.get("/api/user/export")
async def export_user_data(request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user_session['id']

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    categories = db.query(Category).filter(Category.user_id == user_id).all()
    words = db.query(Word).filter(Word.user_id == user_id).all()

    export_data = {
        "export_info": {
            "exported_at": datetime.utcnow().isoformat(),
            "user_id": user.id,
            "user_email": user.email,
            "user_name": user.name,
            "is_plus": user.is_plus
        },
        "categories": [
            {
                "id": cat.id,
                "name": cat.name,
                "description": cat.description,
                "created_at": cat.created_at.isoformat() if cat.created_at else None
            }
            for cat in categories
        ],
        "words": [
            {
                "id": word.id,
                "original_word": word.original_word,
                "translation": word.translation,
                "category_id": word.category_id,
                "knowledge_level": word.knowledge_level.value if word.knowledge_level else None,
                "times_tested": word.times_tested,
                "times_correct": word.times_correct,
                "last_tested": word.last_tested.isoformat() if word.last_tested else None,
                "created_at": word.created_at.isoformat() if word.created_at else None
            }
            for word in words
        ]
    }

    def generate():
        yield json.dumps(export_data, indent=2, ensure_ascii=False)

    filename = f"wordkeeper_data_{user.email}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    return StreamingResponse(
        generate(),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ============================================================
# CATEGORIES API ENDPOINTS
# ============================================================

@app.get("/api/v1/categories", response_model=list[CategoryResponse])
async def get_categories(request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user_session['id']
    categories = db.query(Category).filter(Category.user_id == user_id).all()

    # ✅ Jeden GROUP BY query pre všetky kategórie naraz (namiesto 1 + 3*N queries)
    summaries = get_category_word_summary(db, user_id, [c.id for c in categories])

    result = []
    for category in categories:
        summary = summaries.get(category.id, {
            'total_words': 0,
            'level_counts': _empty_level_counts(),
            'level_percentages': _empty_level_counts_float()
        })

        result.append(CategoryResponse(
            id=category.id,
            name=category.name,
            description=category.description,
            user_id=category.user_id,
            created_at=category.created_at,
            total_words=summary['total_words'],
            level_counts=summary['level_counts'],
            level_percentages=summary['level_percentages']
        ))

    return result


@app.post("/api/v1/categories", response_model=CategoryResponse)
async def create_category(category_data: CategoryCreate, request: Request, db: Session = Depends(get_db)):
    # ✅ OPRAVA: user_id MUSÍ prísť zo session, nie z request body
    # (inak by ktokoľvek mohol vytvoriť kategóriu pre cudzie user_id)
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user_session['id']

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    category_count = db.query(Category).filter(Category.user_id == user_id).count()
    if category_count >= 5:
        raise HTTPException(status_code=400, detail="Maximum limit of 5 categories reached")

    existing_category = db.query(Category).filter(
        Category.name == category_data.name,
        Category.user_id == user_id
    ).first()
    if existing_category:
        raise HTTPException(status_code=400, detail="Category with this name already exists")

    new_category = Category(
        name=category_data.name,
        description=category_data.description,
        user_id=user_id
    )
    db.add(new_category)
    db.commit()
    db.refresh(new_category)

    logger.info(f"Category saved to database with ID: {new_category.id}")
    return new_category


@app.put("/api/v1/categories/{category_id}", response_model=CategoryResponse)
async def update_category(category_id: int, category_update: CategoryUpdate, request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user_session['id']
    category = db.query(Category).filter(Category.id == category_id, Category.user_id == user_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    for field, value in category_update.dict(exclude_unset=True).items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)

    summary = get_category_word_summary(db, user_id, [category.id])[category.id]
    total_words = summary['total_words']
    level_counts = summary['level_counts']
    level_percentages = summary['level_percentages']

    return CategoryResponse(
        id=category.id,
        name=category.name,
        description=category.description,
        created_at=category.created_at,
        user_id=category.user_id,
        total_words=total_words,
        level_counts=level_counts,
        level_percentages=level_percentages
    )


@app.delete("/api/v1/categories/{category_id}")
async def delete_category(category_id: int, request: Request, db: Session = Depends(get_db)):
    # ✅ OPRAVA: Pridaná autentifikácia + kontrola vlastníctva
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    category = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == user_session['id']
    ).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    db.delete(category)
    db.commit()

    return {"message": "Category deleted successfully"}


@app.get("/api/v1/categories/{category_id}", response_model=CategoryResponse)
async def get_category_detail(category_id: int, request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user_session['id']
    category = db.query(Category).filter(Category.id == category_id, Category.user_id == user_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    summary = get_category_word_summary(db, user_id, [category.id])[category.id]
    total_words = summary['total_words']
    level_counts = summary['level_counts']
    level_percentages = summary['level_percentages']

    return CategoryResponse(
        id=category.id,
        name=category.name,
        description=category.description,
        user_id=category.user_id,
        created_at=category.created_at,
        total_words=total_words,
        level_counts=level_counts,
        level_percentages=level_percentages
    )


@app.get("/api/v1/categories/{category_id}/stats")
async def get_category_stats(category_id: int, request: Request, db: Session = Depends(get_db)):
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    category = db.query(Category).filter(Category.id == category_id, Category.user_id == user_session['id']).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    summary = get_category_word_summary(db, user_session['id'], [category_id])[category_id]
    total_words = summary['total_words']
    level_counts = summary['level_counts']

    stats = {
        "total_words": total_words,
        "dont_know_percentage": round((level_counts.get('dont_know', 0) / total_words * 100), 1) if total_words > 0 else 0,
        "learning_percentage": round((level_counts.get('learning', 0) / total_words * 100), 1) if total_words > 0 else 0,
        "know_percentage": round((level_counts.get('know', 0) / total_words * 100), 1) if total_words > 0 else 0
    }

    return JSONResponse(stats)


# ============================================================
# MISC API ENDPOINTS
# ============================================================

@app.get("/api/v1/users")
async def get_users(request: Request, db: Session = Depends(get_db)):
    # ✅ OPRAVA: Chránený endpoint
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    users = db.query(User).all()
    return [
        {"id": user.id, "email": user.email, "name": user.name}
        for user in users
    ]


@app.get("/api/debug/categories")
async def debug_categories(request: Request, db: Session = Depends(get_db)):
    # ✅ OPRAVA: Chránený endpoint — vracia len kategórie prihláseného usera
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    categories = db.query(Category).filter(Category.user_id == user_session['id']).all()
    return {
        "total_categories": len(categories),
        "categories": [
            {"id": cat.id, "name": cat.name, "description": cat.description, "user_id": cat.user_id}
            for cat in categories
        ]
    }


@app.get("/api/debug/users")
async def debug_users(request: Request, db: Session = Depends(get_db)):
    # ✅ OPRAVA: Chránený endpoint
    user_session = request.session.get('user')
    if not user_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    users = db.query(User).all()
    return {
        "total_users": len(users),
        "users": [
            {"id": user.id, "email": user.email, "name": user.name}
            for user in users
        ]
    }


# ============================================================
# STARTUP EVENT
# ============================================================

@app.on_event("startup")
async def startup_event():
    Base.metadata.create_all(bind=engine)
    logger.info("Application starting up...")
    # ✅ OPRAVA: Test user len v development mode
    if os.getenv("DEBUG", "false").lower() == "true":
        db = SessionLocal()
        try:
            test_user = db.query(User).filter(User.email == "test@example.com").first()
            hashed_password = hash_password("test123")
            if not test_user:
                test_user = User(email="test@example.com", name="Test User", is_plus=False, password=hashed_password)
                db.add(test_user)
                logger.info("Test user created with password 'test123'")
            else:
                if not verify_password("test123", test_user.password):
                    test_user.password = hashed_password
                    db.commit()
                    logger.info("Test user password updated to bcrypt hash")
                else:
                    logger.info("Test user already exists with correct password")
            db.commit()
        except Exception as e:
            logger.error(f"Error creating/updating test user: {e}")
        finally:
            db.close()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)


# ============================================================
# EMAIL / PASSWORD RESET ENDPOINTS
# ============================================================

@app.get("/forgot-password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})


@app.post("/api/v1/forgot-password")
async def forgot_password(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    email = data.get("email")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        return JSONResponse({"message": "Ak email existuje, poslali sme odkaz."})

    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    db.commit()

    reset_url = f"{request.base_url}reset-password?token={token}"
    message = MessageSchema(
        subject="Reset hesla – WordKeeper",
        recipients=[email],
        body=f"Klikni na odkaz pre reset hesla:\n\n{reset_url}\n\nOdkaz je platný 1 hodinu.",
        subtype="plain"
    )
    fm = FastMail(mail_config)
    await fm.send_message(message)

    return JSONResponse({"message": "Ak email existuje, poslali sme odkaz."})


@app.get("/reset-password")
async def reset_password_page(request: Request, token: str):
    return templates.TemplateResponse("reset_password.html", {"request": request, "token": token})


@app.post("/api/v1/reset-password")
async def reset_password(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    token = data.get("token")
    new_password = data.get("password")

    user = db.query(User).filter(User.reset_token == token).first()

    if not user or user.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token je neplatný alebo vypršal.")

    user.password = hash_password(new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()

    return JSONResponse({"message": "Heslo bolo zmenené."})