"""Jeden endpoint pre celú nástenku.

Nástenka potrebovala tri requesty (`/api/user`, `/api/user/stats`,
`/api/v1/categories`). Paralelne ich posielať nestačilo: merania na produkcii
2026-08-19 ukázali, že **tri súbežné requesty trvajú 2220 ms každý, kým
samostatný 1076 ms** — inštancia súbežnosť neutiahne. K tomu má každý request
vlastnú réžiu (~345 ms nameraných na triviálnom `/api/user`).

Jeden request vráti to isté a zaplatí réžiu raz. Pôvodné tri endpointy ostávajú
— používajú ich iné stránky aj offline cache.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.routers.categories import build_categories_payload
from app.routers.users import build_stats_payload, build_user_payload
from app.services.session_auth import get_authenticated_user

router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard")
async def get_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """Používateľ, štatistiky a kategórie naraz — jedna cesta namiesto troch."""
    return JSONResponse({
        "user": build_user_payload(request, current_user),
        "stats": build_stats_payload(db, current_user),
        # Pydantic modely treba previesť na čisté dáta, JSONResponse ich sám nezvládne.
        "categories": [c.model_dump(mode="json") for c in build_categories_payload(db, current_user)],
    })
