"""Lemon Squeezy (Merchant of Record) — checkout, subscription, webhook verifikácia.

Konfigurácia cez env premenné (môžu chýbať — appka funguje, platby sú len neaktívne):
  LEMONSQUEEZY_API_KEY, LEMONSQUEEZY_STORE_ID, LEMONSQUEEZY_WEBHOOK_SECRET,
  LEMONSQUEEZY_VARIANT_MONTHLY, LEMONSQUEEZY_VARIANT_ANNUAL
"""
import hashlib
import hmac
import os
from datetime import datetime
from typing import Optional

import httpx

from app.utils import utcnow

LS_API_BASE = "https://api.lemonsqueezy.com/v1"
_JSON_API = {
    "Accept": "application/vnd.api+json",
    "Content-Type": "application/vnd.api+json",
}

# stavy, pri ktorých má používateľ ešte PLUS prístup (cancelled = beží do konca obdobia)
ACTIVE_STATUSES = {"on_trial", "active", "past_due", "cancelled"}


def is_configured() -> bool:
    return bool(os.getenv("LEMONSQUEEZY_API_KEY") and os.getenv("LEMONSQUEEZY_STORE_ID"))


def _auth_headers() -> dict:
    return {**_JSON_API, "Authorization": f"Bearer {os.getenv('LEMONSQUEEZY_API_KEY', '')}"}


def variant_id_for_plan(plan: str) -> Optional[str]:
    return {
        "monthly": os.getenv("LEMONSQUEEZY_VARIANT_MONTHLY"),
        "annual": os.getenv("LEMONSQUEEZY_VARIANT_ANNUAL"),
    }.get(plan)


def plan_for_variant(variant_id) -> Optional[str]:
    vid = str(variant_id)
    if vid and vid == os.getenv("LEMONSQUEEZY_VARIANT_MONTHLY"):
        return "monthly"
    if vid and vid == os.getenv("LEMONSQUEEZY_VARIANT_ANNUAL"):
        return "annual"
    return None


async def create_checkout(*, user_id: int, email: str, plan: str, redirect_url: str) -> str:
    """Vytvorí Lemon Squeezy checkout a vráti URL, na ktorú presmerujeme používateľa."""
    store_id = os.getenv("LEMONSQUEEZY_STORE_ID")
    variant_id = variant_id_for_plan(plan)
    if not (store_id and variant_id):
        raise RuntimeError("Lemon Squeezy nie je nakonfigurované (store/variant chýba)")

    body = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "checkout_data": {
                    "email": email,
                    "custom": {"user_id": str(user_id)},  # vráti sa vo webhooku
                },
                "product_options": {"redirect_url": redirect_url},
            },
            "relationships": {
                "store": {"data": {"type": "stores", "id": str(store_id)}},
                "variant": {"data": {"type": "variants", "id": str(variant_id)}},
            },
        }
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{LS_API_BASE}/checkouts", json=body, headers=_auth_headers())
        resp.raise_for_status()
        return resp.json()["data"]["attributes"]["url"]


async def get_subscription(subscription_id: str) -> dict:
    """Načíta subscription z LS (napr. kvôli URL na customer portal)."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{LS_API_BASE}/subscriptions/{subscription_id}", headers=_auth_headers()
        )
        resp.raise_for_status()
        return resp.json()["data"]


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Overí HMAC-SHA256 podpis webhooku (hlavička X-Signature)."""
    secret = os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET", "")
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        # LS dáva ISO 8601 (napr. 2026-07-28T10:00:00.000000Z) — ako naive UTC
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def apply_subscription(user, attrs: dict, subscription_id, customer_id, plan: Optional[str]) -> None:
    """Premietne stav subscription (z webhooku) do používateľa."""
    status = attrs.get("status")
    user.plus_status = status
    if subscription_id:
        user.ls_subscription_id = str(subscription_id)
    if customer_id:
        user.ls_customer_id = str(customer_id)
    if plan:
        user.plus_plan = plan

    # Expirácia: ends_at (po zrušení), inak renews_at, inak koniec trialu
    user.plus_expires_at = _parse_dt(
        attrs.get("ends_at") or attrs.get("renews_at") or attrs.get("trial_ends_at")
    )

    if status == "cancelled" and not user.plus_cancelled_at:
        user.plus_cancelled_at = utcnow()
    elif status in ("active", "on_trial"):
        user.plus_cancelled_at = None

    user.is_plus = status in ACTIVE_STATUSES


def expire_if_needed(user) -> bool:
    """Ak PLUS expiroval (napr. zmeškaný webhook), vypni ho. Vráti True ak sa zmenilo."""
    if user.is_plus and user.plus_expires_at and user.plus_expires_at < utcnow():
        user.is_plus = False
        user.plus_status = "expired"
        return True
    return False
