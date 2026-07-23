import os
import re
import secrets
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi_mail import FastMail, MessageSchema
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from passlib.hash import argon2
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.utils import utcnow
from app.services import billing_service
from app.services.auth_service import hash_password, verify_password
from app.services.email_service import send_welcome_email
from app.services.runtime import (
    SECRET_KEY,
    is_debug_mode,
    limiter,
    logger,
    mail_config,
    oauth,
)

_signer = URLSafeTimedSerializer(SECRET_KEY, salt="oauth-finalize")
_state_signer = URLSafeTimedSerializer(SECRET_KEY, salt="oauth-state")
_next_signer = URLSafeTimedSerializer(SECRET_KEY, salt="oauth-next")

router = APIRouter(tags=["authentication"])

# Sila hesla – musí sedieť s frontend validáciou v register.html
# (aspoň 8 znakov, veľké písmeno, malé písmeno, číslica).
PASSWORD_MIN_LENGTH = 8

# Jednotná hláška pre zlý e-mail AJ zlé heslo — nezrádzame, či e-mail existuje.
INVALID_CREDENTIALS = "Nesprávny e-mail alebo heslo."
# Dummy hash na vyrovnanie času odpovede, keď e-mail neexistuje (timing attack).
_TIMING_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")


def password_strength_error(password: str) -> Optional[str]:
    """Vráti chybovú hlášku ak heslo nespĺňa požiadavky, inak None."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Heslo musí mať aspoň {PASSWORD_MIN_LENGTH} znakov."
    if not re.search(r"[A-Z]", password):
        return "Heslo musí obsahovať veľké písmeno."
    if not re.search(r"[a-z]", password):
        return "Heslo musí obsahovať malé písmeno."
    if not re.search(r"[0-9]", password):
        return "Heslo musí obsahovať číslicu."
    return None


def _validate_password_field(value: str) -> str:
    error = password_strength_error(value)
    if error:
        raise ValueError(error)
    return value


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None

    _check_password = field_validator("password")(_validate_password_field)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class PasswordReset(BaseModel):
    token: str
    password: str

    _check_password = field_validator("password")(_validate_password_field)


@router.post("/api/v1/register")
@limiter.limit("5/hour")
async def register(
    request: Request,
    user_data: UserRegister,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        email = user_data.email
        password = user_data.password
        name = user_data.name or email.split("@")[0]

        if not (email and password):
            raise HTTPException(status_code=400, detail="Email and password required")

        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="User with this email already exists")

        new_user = User(
            email=email,
            name=name,
            is_plus=False,
            password=hash_password(password),
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        background_tasks.add_task(send_welcome_email, new_user.email, new_user.name)

        session_user = {
            "id": new_user.id,
            "email": new_user.email,
            "name": new_user.name,
            "is_plus": new_user.is_plus,
            "dark_mode": new_user.dark_mode,
        }
        request.session["user"] = session_user

        return JSONResponse({"message": "Registration successful", "user": session_user})
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Registration error: {exc}")
        raise HTTPException(status_code=400, detail="Registration failed. Please try again.")


@router.post("/api/v1/login")
@limiter.limit("10/minute")
async def login(request: Request, user_data: UserLogin, db: Session = Depends(get_db)):
    try:
        email = user_data.email
        password = user_data.password

        if not (email and password):
            raise HTTPException(status_code=400, detail="Email and password required")

        user = db.query(User).filter(User.email == email).first()
        if not user:
            verify_password(password, _TIMING_DUMMY_HASH)
            raise HTTPException(status_code=400, detail=INVALID_CREDENTIALS)

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
            raise HTTPException(status_code=400, detail=INVALID_CREDENTIALS)

        user.last_login = utcnow()
        billing_service.expire_if_needed(user)  # ak PLUS expiroval, vypni ho
        db.commit()

        session_user = {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "is_plus": user.is_plus,
            "dark_mode": user.dark_mode,
        }
        request.session["user"] = session_user

        return JSONResponse({"message": "Login successful", "user": session_user})
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Login error: {exc}")
        raise HTTPException(status_code=400, detail="Login failed. Please try again.")


@router.post("/api/v1/logout")
async def logout(request: Request):
    request.session.clear()
    return {"message": "Logged out successfully"}


# OAuth callback musí ostať na hoste, kde sa login začal (session cookie
# so state je viazaná na doménu). Každá z týchto redirect URI musí byť
# schválená v Google Cloud konzole (Authorized redirect URIs).
GOOGLE_CALLBACK_HOSTS = {
    "lexinova.fun",
    "www.lexinova.fun",
    "lexinova-1096007793591.us-central1.run.app",
}

# Authlib ukladá CSRF state do session cookie. Tá sa ale prepisuje pri KAŽDEJ
# odpovedi zo snapshotu, ktorý si SessionMiddleware načítal na začiatku daného
# requestu — takže hociktorá súbežná požiadavka (napr. predcache service workera)
# vie state z cookie vyhodiť skôr, než sa vrátime z Google. Výsledok bol
# "mismatching_state: CSRF Warning!" na prvý pokus. State preto zrkadlíme do
# vlastnej cookie, do ktorej nikto iný nesiaha, a v callbacku ho obnovíme.
OAUTH_STATE_COOKIE = "oauth_state"
# Rovnaká životnosť, akú dáva state aj samotný authlib (exp = +1 h). Kratšie TTL
# (pôvodne 10 min) zhodilo login každému, kto na Google obrazovke strávil dlhšie
# — výber účtu + heslo + 2FA sa cez 10 minút prehupne ľahko.
OAUTH_STATE_TTL = 3600

# Kam pokračovať po prihlásení (?next= zo zdieľacieho linku /s/{kód} alebo /c/{kód}).
# Google flow prechádza cez Google a späť, takže cieľ musí niekde prežiť — rovnako
# ako state ho držíme v session aj vo vlastnej cookie.
OAUTH_NEXT_COOKIE = "oauth_next"


def _safe_next(value: Optional[str]) -> Optional[str]:
    """Povolí len internú cestu — inak by sa cez ?next= dal spraviť open redirect.

    Rovnaké pravidlá ako `safeNextUrl()` v login.html a register.html.
    """
    if not value or not value.startswith("/") or value.startswith("//"):
        return None
    if "\\" in value or "\n" in value or "\r" in value:
        return None
    return value


def _restore_next(request: Request) -> Optional[str]:
    """Cieľ uložený pri štarte flow; cookie je poistka, ak session neprežije."""
    target = _safe_next(request.session.pop("oauth_next", None))
    if target:
        return target
    raw = request.cookies.get(OAUTH_NEXT_COOKIE)
    if not raw:
        return None
    try:
        return _safe_next(_next_signer.loads(raw, max_age=OAUTH_STATE_TTL))
    except (BadSignature, SignatureExpired):
        logger.warning("OAuth next cookie neplatná alebo expirovaná")
        return None


@router.get("/auth/google")
async def google_login(request: Request):
    host = request.url.hostname
    if host in GOOGLE_CALLBACK_HOSTS:
        redirect_uri = f"https://{host}/auth/google/callback"
    else:
        # lokálny vývoj a neznáme hosty — env, inak produkčný default
        redirect_uri = os.getenv(
            "GOOGLE_REDIRECT_URI",
            "https://lexinova.fun/auth/google/callback",
        )

    keys_before = set(request.session)
    response = await oauth.google.authorize_redirect(request, redirect_uri)

    # State, ktorý práve pribudol do session (vrátane nonce/PKCE dát), odložíme
    # aj do samostatnej cookie viazanej na /auth.
    new_state = {
        key: value
        for key, value in request.session.items()
        if key.startswith("_state_google_") and key not in keys_before
    }
    if new_state:
        response.set_cookie(
            OAUTH_STATE_COOKIE,
            _state_signer.dumps(new_state),
            max_age=OAUTH_STATE_TTL,
            httponly=True,
            secure=not is_debug_mode(),
            samesite="lax",
            path="/auth",
        )
    else:
        logger.warning("OAuth start: authlib nevrátil žiadny nový state")

    next_path = _safe_next(request.query_params.get("next"))
    if next_path:
        request.session["oauth_next"] = next_path
        response.set_cookie(
            OAUTH_NEXT_COOKIE,
            _next_signer.dumps(next_path),
            max_age=OAUTH_STATE_TTL,
            httponly=True,
            secure=not is_debug_mode(),
            samesite="lax",
            path="/auth",
        )
    else:
        # Bez tohto by cieľ z predošlého (opusteného) pokusu presmeroval
        # používateľa na sadu, ktorú tentokrát vôbec neotváral.
        request.session.pop("oauth_next", None)
        response.delete_cookie(OAUTH_NEXT_COOKIE, path="/auth")
    return response


def _restore_oauth_state(request: Request) -> str:
    """Vráti do session state uložený pri štarte flow (viď OAUTH_STATE_COOKIE).

    Návratová hodnota je iba diagnostika do logu — odkiaľ sa state vzal:
    session / cookie / expired / invalid / missing.
    """
    callback_state = request.query_params.get("state") or ""
    in_session = bool(callback_state) and f"_state_google_{callback_state}" in request.session

    raw = request.cookies.get(OAUTH_STATE_COOKIE)
    if not raw:
        return "session" if in_session else "missing"
    try:
        stored = _state_signer.loads(raw, max_age=OAUTH_STATE_TTL)
    except SignatureExpired:
        logger.warning("OAuth state cookie expired")
        return "expired"
    except BadSignature:
        logger.warning("OAuth state cookie invalid")
        return "invalid"
    for key, value in stored.items():
        # Session má prednosť — obsah je rovnaký, len ju už nemusíme prepisovať.
        request.session.setdefault(key, value)
    return "session" if in_session else "cookie"


@router.get("/auth/google/callback", name="google_callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    logger.info("Google callback started")
    state_source = _restore_oauth_state(request)
    next_path = _restore_next(request)
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = await oauth.google.userinfo(token=token)
        logger.info("User info received from Google")

        if not user_info or not user_info.get("email"):
            raise HTTPException(status_code=400, detail="Failed to get user info from Google")

        email = user_info["email"]
        name = user_info.get("name", email.split("@")[0])
        picture = user_info.get("picture", "")

        user = db.query(User).filter(User.email == email).first()
        new_user = False

        if not user:
            # Náhodné heslo, ktoré nikto nepozná — Google užívateľ sa prihlasuje
            # cez OAuth; lokálne heslo si vie nastaviť cez forgot-password.
            # (Konštantné dummy heslo by umožnilo login cez /api/v1/login komukoľvek.)
            user = User(
                email=email,
                name=name,
                password=hash_password(secrets.token_urlsafe(32)),
                is_plus=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            new_user = True
            logger.info(f"New user created: id={user.id}")

            try:
                message = MessageSchema(
                    subject="Vitajte v LexiNova! 🎉",
                    recipients=[email],
                    body=f"""Ahoj {name},

vitajte v LexiNova! Sme radi, že ste sa k nám pridali cez Google.

Začnite učiť nové slovíčka ešte dnes:
https://lexinova.fun/dashboard

S pozdravom,
Tím LexiNova
""",
                    subtype="plain",
                )
                fm = FastMail(mail_config)
                await fm.send_message(message)
            except Exception as exc:
                logger.error(f"Welcome email error: {exc}")
        else:
            if not user.name and name:
                user.name = name
            user.last_login = utcnow()
            billing_service.expire_if_needed(user)  # ak PLUS expiroval, vypni ho
            db.commit()

        session_user = {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "picture": picture,
            "is_plus": user.is_plus,
            "dark_mode": user.dark_mode,
        }
        logger.info(f"OAuth success for user_id: {session_user['id']}, redirecting to finalize")

        # Podpísaný URL token (60s TTL) — session nastavíme až v /auth/finalize,
        # nie tu, aby sme obišli Cloud Run bug kde Set-Cookie z callback response
        # sa stratí pred tým, než browser pošle /dashboard request.
        token = _signer.dumps({"user": session_user, "next": next_path})
        response = RedirectResponse(url=f"/auth/finalize?t={token}", status_code=303)
        response.delete_cookie(OAUTH_STATE_COOKIE, path="/auth")
        response.delete_cookie(OAUTH_NEXT_COOKIE, path="/auth")
        return response
    except Exception as exc:
        # Callback zopakovaný cez back/refresh (state je už spotrebovaný), ale
        # používateľ je medzitým prihlásený — nie je to chyba, pošli ho ďalej.
        if state_source == "missing" and request.session.get("user"):
            logger.info("Google callback replay for logged-in user — redirecting to dashboard")
            return RedirectResponse(url="/dashboard", status_code=303)
        # Kontext k chybe: bez neho sa "mismatching_state" nedá odlíšiť od
        # expirovanej cookie, iného hosta či zopakovaného callbacku.
        logger.error(
            "Google auth error: %s (state_source=%s, host=%s, cookie=%s, google_error=%s)",
            exc,
            state_source,
            request.url.hostname,
            "yes" if request.cookies.get(OAUTH_STATE_COOKIE) else "no",
            request.query_params.get("error") or "-",
        )
        response = RedirectResponse(url="/login?error=google_auth_failed")
        response.delete_cookie(OAUTH_STATE_COOKIE, path="/auth")
        response.delete_cookie(OAUTH_NEXT_COOKIE, path="/auth")
        return response


@router.get("/auth/finalize")
async def google_finalize(request: Request, t: str):
    try:
        payload = _signer.loads(t, max_age=60)
    except SignatureExpired:
        logger.warning("OAuth finalize: token expired")
        return RedirectResponse(url="/login?error=session_expired")
    except BadSignature:
        logger.warning("OAuth finalize: invalid token")
        return RedirectResponse(url="/login?error=google_auth_failed")

    # Počas deployu môže doraziť token starého tvaru (holý user dict bez "next").
    session_user = payload.get("user", payload)
    target = _safe_next(payload.get("next")) or "/dashboard"

    request.session["user"] = session_user
    logger.info(f"Session finalized for user_id: {session_user['id']}, next: {target}")
    return RedirectResponse(url=target, status_code=303)


@router.post("/api/v1/forgot-password")
@limiter.limit("3/hour")
async def forgot_password(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    email = data.get("email")

    # Bez guardu by {"email": null} matchlo pseudonymné žiacke účty (email IS NULL).
    if not email or not isinstance(email, str):
        return JSONResponse({"message": "Ak email existuje, poslali sme odkaz."})

    user = db.query(User).filter(User.email == email).first()
    if not user:
        return JSONResponse({"message": "Ak email existuje, poslali sme odkaz."})

    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expires = utcnow() + timedelta(hours=1)
    db.commit()

    reset_url = f"{request.base_url}reset-password?token={token}"
    message = MessageSchema(
        subject="Reset hesla – LexiNova",
        recipients=[email],
        body=f"Klikni na odkaz pre reset hesla:\n\n{reset_url}\n\nOdkaz je platný 1 hodinu.",
        subtype="plain",
    )
    fm = FastMail(mail_config)
    await fm.send_message(message)

    return JSONResponse({"message": "Ak email existuje, poslali sme odkaz."})


@router.post("/api/v1/reset-password")
@limiter.limit("5/hour")
async def reset_password(
    request: Request, data: PasswordReset, db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.reset_token == data.token).first()
    if not user or user.reset_token_expires < utcnow():
        raise HTTPException(status_code=400, detail="Token je neplatný alebo vypršal.")

    user.password = hash_password(data.password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()

    return JSONResponse({"message": "Heslo bolo zmenené."})
