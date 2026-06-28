import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.payment import Payment
from app.models.user import User
from app.services import billing_service
from app.services.runtime import limiter, logger
from app.services.session_auth import get_authenticated_user

router = APIRouter(tags=["billing"])

# Eventy, kde `data` predstavuje subscription objekt.
_SUBSCRIPTION_EVENTS = {
    "subscription_created",
    "subscription_updated",
    "subscription_resumed",
    "subscription_paused",
    "subscription_unpaused",
    "subscription_cancelled",
    "subscription_expired",
}


class CheckoutRequest(BaseModel):
    plan: str  # monthly | annual


@router.post("/api/v1/checkout")
@limiter.limit("10/hour")
async def create_checkout(
    request: Request,
    data: CheckoutRequest,
    current_user: User = Depends(get_authenticated_user),
):
    if data.plan not in ("monthly", "annual"):
        raise HTTPException(status_code=400, detail="Neplatný plán.")
    if not billing_service.is_configured():
        raise HTTPException(status_code=503, detail="Platby zatiaľ nie sú dostupné.")

    redirect_url = str(request.base_url).rstrip("/") + "/profile?upgraded=1"
    try:
        url = await billing_service.create_checkout(
            user_id=current_user.id,
            email=current_user.email,
            plan=data.plan,
            redirect_url=redirect_url,
        )
    except Exception as exc:
        logger.error(f"Checkout error: {exc}")
        raise HTTPException(status_code=502, detail="Nepodarilo sa vytvoriť platbu.")
    return JSONResponse({"url": url})


@router.get("/api/v1/subscription")
async def my_subscription(current_user: User = Depends(get_authenticated_user)):
    return JSONResponse(
        {
            "is_plus": bool(current_user.is_plus),
            "plan": current_user.plus_plan,
            "status": current_user.plus_status,
            "expires_at": current_user.plus_expires_at.isoformat()
            if current_user.plus_expires_at
            else None,
            "cancelled_at": current_user.plus_cancelled_at.isoformat()
            if current_user.plus_cancelled_at
            else None,
        }
    )


@router.get("/api/v1/billing/portal")
async def billing_portal(current_user: User = Depends(get_authenticated_user)):
    if not current_user.ls_subscription_id:
        raise HTTPException(status_code=404, detail="Žiadne aktívne predplatné.")
    try:
        sub = await billing_service.get_subscription(current_user.ls_subscription_id)
        url = sub["attributes"]["urls"]["customer_portal"]
    except Exception as exc:
        logger.error(f"Billing portal error: {exc}")
        raise HTTPException(status_code=502, detail="Nepodarilo sa otvoriť správu predplatného.")
    return JSONResponse({"url": url})


def _find_user(db: Session, custom: dict, subscription_id, customer_id, attrs: dict):
    user_id = custom.get("user_id")
    if user_id:
        try:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                return user
        except (TypeError, ValueError):
            pass
    # invoice eventy majú subscription_id v attrs
    sub_ref = subscription_id or attrs.get("subscription_id")
    if sub_ref:
        user = db.query(User).filter(User.ls_subscription_id == str(sub_ref)).first()
        if user:
            return user
    if customer_id:
        user = db.query(User).filter(User.ls_customer_id == str(customer_id)).first()
        if user:
            return user
    return None


def _log_payment(db: Session, user: User, invoice_id, attrs: dict):
    # Idempotencia — ten istý invoice nelogujeme dvakrát.
    if invoice_id and db.query(Payment).filter(
        Payment.provider_payment_id == str(invoice_id)
    ).first():
        return
    total = attrs.get("total")  # v centoch
    amount = round(total / 100.0, 2) if isinstance(total, (int, float)) else 0.0
    db.add(
        Payment(
            user_id=user.id,
            email=user.email,
            provider="lemonsqueezy",
            provider_payment_id=str(invoice_id) if invoice_id else None,
            provider_subscription_id=str(attrs.get("subscription_id") or user.ls_subscription_id or ""),
            status="succeeded",
            amount=amount,
            currency=(attrs.get("currency") or "EUR")[:10],
            description="LexiNova PLUS",
        )
    )


@router.post("/api/webhooks/lemonsqueezy")
async def lemonsqueezy_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    signature = request.headers.get("X-Signature", "")
    if not billing_service.verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid payload")

    meta = event.get("meta", {}) or {}
    event_name = meta.get("event_name")
    custom = meta.get("custom_data") or {}
    data = event.get("data", {}) or {}
    attrs = data.get("attributes", {}) or {}
    object_id = data.get("id")
    customer_id = attrs.get("customer_id")

    user = _find_user(db, custom, object_id, customer_id, attrs)
    if not user:
        # 200, aby Lemon Squeezy neretryoval donekonečna (len zalogujeme).
        logger.warning(f"LS webhook '{event_name}': používateľ nenájdený")
        return JSONResponse({"ok": True})

    if event_name in _SUBSCRIPTION_EVENTS:
        plan = billing_service.plan_for_variant(attrs.get("variant_id"))
        billing_service.apply_subscription(user, attrs, object_id, customer_id, plan)
        logger.info(f"LS {event_name}: user {user.id} → status={user.plus_status}, plus={user.is_plus}")
    elif event_name == "subscription_payment_success":
        _log_payment(db, user, object_id, attrs)
    elif event_name == "subscription_payment_failed":
        user.plus_status = "past_due"
        logger.warning(f"LS payment failed: user {user.id}")

    db.commit()
    return JSONResponse({"ok": True})
