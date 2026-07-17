import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.category import Category
from app.models.school_class import ClassCategory, ClassMember
from app.models.user import User
from app.models.word import Word
from app.routers.localization import get_language
from app.services.runtime import STATIC_DIR, templates
from app.services.stats_service import (
    get_category_word_summary,
    get_category_word_summary_overlay,
)

router = APIRouter(tags=["pages"])

# Kanonicka domena pre SEO (sitemap, robots, canonical/OG URL).
# Prepisatelna cez env, keby sa domena zmenila.
SITE_URL = os.getenv("SITE_URL", "https://lexinova.fun").rstrip("/")

# Verejne, indexovatelne stranky: (cesta, priorita, frekvencia zmien).
# Sukromne app stranky (dashboard/profile/test/...) sa zamerne vynechavaju.
PUBLIC_PAGES = [
    ("/", "1.0", "weekly"),
    ("/pricing", "0.9", "monthly"),
    ("/demo", "0.7", "monthly"),
    ("/register", "0.6", "monthly"),
    ("/login", "0.4", "yearly"),
    ("/terms", "0.3", "yearly"),
    ("/privacy", "0.3", "yearly"),
    ("/refunds", "0.3", "yearly"),
    ("/blog", "0.8", "weekly"),
]

# Blog clanky (SEO obsah). Novy clanok = novy zaznam tu + sablona v templates/blog/.
# (slug, sablona, titulok, popis, datum ISO) — datum sa zobrazuje aj ide do sitemapy.
BLOG_ARTICLES = [
    {
        "slug": "ako-sa-naucit-anglicke-slovicka",
        "template": "blog/ako-sa-naucit-anglicke-slovicka.html",
        "title": "Ako sa naučiť anglické slovíčka rýchlo a nezabudnúť ich",
        "description": (
            "7 overených techník na učenie anglických slovíčok: aktívne vybavovanie, "
            "rozložené opakovanie, učenie v kontexte a ako vám s tým pomôže AI."
        ),
        "date": "2026-07-16",
    },
]


def _get_session_user(request: Request):
    return request.session.get("user")


def _get_db_user_or_redirect(request: Request, db: Session):
    user_session = _get_session_user(request)
    if not user_session:
        return None, RedirectResponse(url="/login", status_code=303)

    user = db.query(User).filter(User.id == user_session["id"]).first()
    if not user:
        request.session.clear()
        return None, RedirectResponse(url="/login", status_code=303)
    return user, None


def _check_category_access(
    db: Session,
    user_id: int,
    category_id: int,
    is_plus_user: bool,
):
    """Vráti (category, is_owner, redirect).

    Vlastné kategórie: free lock „len najnovšia" ako doteraz. Sady triedy
    (cudzia kategória, člen triedy) sú prístupné vždy a lock ich neblokuje.
    """
    category = (
        db.query(Category)
        .filter(Category.id == category_id, Category.user_id == user_id)
        .first()
    )
    if not category:
        class_category = (
            db.query(Category)
            .join(ClassCategory, ClassCategory.category_id == Category.id)
            .join(ClassMember, ClassMember.class_id == ClassCategory.class_id)
            .filter(Category.id == category_id, ClassMember.user_id == user_id)
            .first()
        )
        if class_category:
            return class_category, False, None
        return None, False, RedirectResponse(url="/dashboard", status_code=303)

    if not is_plus_user:
        newest_category = (
            db.query(Category)
            .filter(Category.user_id == user_id)
            .order_by(Category.created_at.desc())
            .first()
        )
        if newest_category and newest_category.id != category_id:
            return None, False, RedirectResponse(url="/dashboard", status_code=303)

    return category, True, None


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(f"{STATIC_DIR}/favicon.ico")


@router.get("/apple-touch-icon.png", include_in_schema=False)
async def apple_touch_icon():
    return FileResponse(f"{STATIC_DIR}/apple-touch-icon.png")


@router.api_route("/robots.txt", methods=["GET", "HEAD"], include_in_schema=False)
async def robots_txt():
    # Vyhladavace: verejne stranky povolene, appka/API/auth zakazane.
    body = (
        "User-agent: *\n"
        "Allow: /$\n"
        "Disallow: /dashboard\n"
        "Disallow: /profile\n"
        "Disallow: /test\n"
        "Disallow: /repeat\n"
        "Disallow: /category/\n"
        "Disallow: /admin\n"
        "Disallow: /api/\n"
        "Disallow: /auth/\n"
        "Disallow: /reset-password\n"
        "Disallow: /forgot-password\n"
        "Disallow: /s/\n"
        "Disallow: /c/\n"
        "Disallow: /classes\n"
        f"\nSitemap: {SITE_URL}/sitemap.xml\n"
    )
    return Response(content=body, media_type="text/plain")


@router.api_route("/sitemap.xml", methods=["GET", "HEAD"], include_in_schema=False)
async def sitemap_xml():
    urls = "".join(
        f"  <url>\n"
        f"    <loc>{SITE_URL}{path}</loc>\n"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        f"  </url>\n"
        for path, priority, changefreq in PUBLIC_PAGES
    )
    urls += "".join(
        f"  <url>\n"
        f"    <loc>{SITE_URL}/blog/{a['slug']}</loc>\n"
        f"    <lastmod>{a['date']}</lastmod>\n"
        f"    <changefreq>yearly</changefreq>\n"
        f"    <priority>0.7</priority>\n"
        f"  </url>\n"
        for a in BLOG_ARTICLES
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}"
        "</urlset>\n"
    )
    return Response(content=body, media_type="application/xml")


@router.get("/manifest.json", include_in_schema=False)
async def get_manifest():
    return FileResponse(
        f"{STATIC_DIR}/manifest.json",
        media_type="application/manifest+json",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@router.get("/sw.js", include_in_schema=False)
async def get_sw():
    return FileResponse(
        f"{STATIC_DIR}/sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@router.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"lang": get_language(request)},
    )


@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html")


@router.get("/dashboard")
async def dashboard_page(request: Request, db: Session = Depends(get_db)):
    db_user, redirect = _get_db_user_or_redirect(request, db)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "email": db_user.email or db_user.name or "",
            "is_plus": db_user.is_plus,
            "dark_mode": db_user.dark_mode,
        },
    )


@router.get("/classes")
async def classes_page(request: Request, db: Session = Depends(get_db)):
    """Učiteľská správa tried (Fáza 2 učiteľského kanála).

    Dostupná každému prihlásenému — zakladanie tried a prehľad žiakov si PLUS
    vynucuje backend, učiteľ s vypršaným PLUS tu ďalej spravuje existujúce triedy."""
    db_user, redirect = _get_db_user_or_redirect(request, db)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        request,
        "classes.html",
        {
            "email": db_user.email or db_user.name or "",
            "is_plus": db_user.is_plus,
            "dark_mode": db_user.dark_mode,
        },
    )


@router.get("/profile")
async def profile_page(request: Request, db: Session = Depends(get_db)):
    db_user, redirect = _get_db_user_or_redirect(request, db)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        request,
        "profile.html",
        {"email": db_user.email or db_user.name or "", "user": db_user},
    )


@router.get("/category/{category_id}/words")
async def category_words_page(request: Request, category_id: int, db: Session = Depends(get_db)):
    user_session = _get_session_user(request)
    if not user_session:
        return RedirectResponse(url="/login", status_code=303)

    db_user = db.query(User).filter(User.id == user_session["id"]).first()
    if not db_user:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)

    category, is_owner, redirect = _check_category_access(db, db_user.id, category_id, db_user.is_plus)
    if redirect:
        return redirect

    if is_owner:
        summary = get_category_word_summary(db, db_user.id, [category.id])[category.id]
    else:
        summary = get_category_word_summary_overlay(db, db_user.id, [category.id])[category.id]
    category_data = {
        "id": category.id,
        "name": category.name,
        "description": category.description,
        "level_percentages": summary["level_percentages"],
    }

    return templates.TemplateResponse(
        request,
        "category_words.html",
        {
            "email": user_session.get("email") or user_session.get("name") or "",
            "category": category_data,
            "dark_mode": db_user.dark_mode,
            # Sada triedy: žiak slová nepridáva/needituje (patria učiteľovi)
            "readonly": not is_owner,
        },
    )


@router.get("/test")
async def test_page(
    request: Request,
    category: int = None,
    level: str = None,
    db: Session = Depends(get_db),
):
    user_session = _get_session_user(request)
    if not user_session:
        return RedirectResponse(url="/login", status_code=303)

    db_user = db.query(User).filter(User.id == user_session["id"]).first()
    if not db_user:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)

    category_data = None
    if category:
        category_data, _is_owner, redirect = _check_category_access(db, db_user.id, category, db_user.is_plus)
        if redirect:
            return redirect

    return templates.TemplateResponse(
        request,
        "flashcard_test.html",
        {
            "email": user_session.get("email") or user_session.get("name") or "",
            "category": category_data,
            "level": level,
        },
    )


@router.get("/repeat")
async def repeat_page(
    request: Request,
    category: int = None,
    level: str = None,
    db: Session = Depends(get_db),
):
    user_session = _get_session_user(request)
    if not user_session:
        return RedirectResponse(url="/login", status_code=303)

    db_user = db.query(User).filter(User.id == user_session["id"]).first()
    if not db_user:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)

    category_data = None
    if category:
        category_data, _is_owner, redirect = _check_category_access(db, db_user.id, category, db_user.is_plus)
        if redirect:
            return redirect

    return templates.TemplateResponse(
        request,
        "repeat.html",
        {
            "email": user_session.get("email") or user_session.get("name") or "",
            "category": category_data,
            "level": level,
        },
    )


@router.get("/demo")
async def demo_page(request: Request):
    return templates.TemplateResponse(request, "demo.html")


@router.get("/auth/callback")
async def auth_callback(request: Request):
    return templates.TemplateResponse(request, "auth-callback.html")


@router.get("/privacy")
async def privacy_page(request: Request):
    return templates.TemplateResponse(request, "privacy.html")


@router.get("/terms")
async def terms_page(request: Request):
    return templates.TemplateResponse(request, "terms.html")


@router.get("/pricing")
async def pricing_page(request: Request):
    return templates.TemplateResponse(request, "pricing.html")


@router.get("/refunds")
async def refunds_page(request: Request):
    return templates.TemplateResponse(request, "refunds.html")


@router.get("/blog")
async def blog_index(request: Request):
    return templates.TemplateResponse(
        request,
        "blog.html",
        {"articles": BLOG_ARTICLES, "site_url": SITE_URL},
    )


@router.get("/blog/{slug}")
async def blog_article(request: Request, slug: str):
    article = next((a for a in BLOG_ARTICLES if a["slug"] == slug), None)
    if not article:
        return templates.TemplateResponse(request, "404.html", status_code=404)
    return templates.TemplateResponse(
        request,
        article["template"],
        {"article": article, "site_url": SITE_URL},
    )


@router.get("/s/{share_code}")
async def shared_category_page(request: Request, share_code: str, db: Session = Depends(get_db)):
    """Verejná landing stránka zdieľanej sady (Fáza 1 učiteľského kanála).

    Neprihlásený návštevník vidí náhľad + CTA na prihlásenie/registráciu
    (s ?next= späť na túto stránku), prihlásený importuje jedným klikom."""
    code = share_code.strip().upper()
    category = db.query(Category).filter(Category.share_code == code).first()

    preview = None
    if category:
        total_words = (
            db.query(func.count(Word.id)).filter(Word.category_id == category.id).scalar() or 0
        )
        first_word = db.query(Word).filter(Word.category_id == category.id).first()
        preview = {
            "name": category.name,
            "description": category.description,
            "total_words": total_words,
            "language_from": first_word.language_from if first_word else None,
            "language_to": first_word.language_to if first_word else None,
        }

    return templates.TemplateResponse(
        request,
        "share.html",
        {
            "preview": preview,
            "share_code": code,
            "logged_in": bool(_get_session_user(request)),
        },
        status_code=200 if preview else 404,
    )


@router.get("/c/{class_code}")
async def class_join_page(request: Request, class_code: str, db: Session = Depends(get_db)):
    """Verejná landing stránka triedy (Fáza 2 učiteľského kanála).

    Neprihlásený sa pridá pseudonymne (prezývka + heslo, bez e-mailu) alebo
    cez login/register s ?next= späť; prihlásený jedným klikom."""
    from app.models.school_class import SchoolClass

    code = class_code.strip().upper()
    school_class = db.query(SchoolClass).filter(SchoolClass.join_code == code).first()

    preview = None
    if school_class:
        teacher = db.query(User).filter(User.id == school_class.teacher_id).first()
        member_count = (
            db.query(func.count(ClassMember.id))
            .filter(ClassMember.class_id == school_class.id)
            .scalar()
            or 0
        )
        preview = {
            "name": school_class.name,
            "teacher_name": teacher.name if teacher else None,
            "member_count": member_count,
        }

    return templates.TemplateResponse(
        request,
        "class_join.html",
        {
            "preview": preview,
            "class_code": code,
            "logged_in": bool(_get_session_user(request)),
        },
        status_code=200 if preview else 404,
    )


@router.get("/forgot-password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(request, "forgot_password.html")


@router.get("/reset-password")
async def reset_password_page(request: Request, token: str):
    return templates.TemplateResponse(request, "reset_password.html", {"token": token})
