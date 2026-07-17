import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.payment import Payment
from app.models.user import User
from app.services import billing_service
from app.services.runtime import logger
from app.services.session_auth import get_authenticated_user

router = APIRouter(tags=["billing"])


@router.get("/api/v1/billing/config")
async def billing_config(current_user: User = Depends(get_authenticated_user)):
    """Konfigurácia pre Paddle.js overlay na frontende (token je client-side)."""
    config = billing_service.client_config()
    # Pseudonymné žiacke konto nemá e-mail (faktúry, potvrdenia) — checkout preň nie je.
    if current_user.is_pseudonymous:
        config["billing_enabled"] = False
    return JSONResponse(config)


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


@router.post("/api/v1/billing/cancel")
async def cancel_my_subscription(
    current_user: User = Depends(get_authenticated_user),
    db: Session = Depends(get_db),
):
    if not current_user.paddle_subscription_id:
        raise HTTPException(status_code=404, detail="Žiadne aktívne predplatné.")
    try:
        data = await billing_service.cancel_subscription(current_user.paddle_subscription_id)
    except Exception as exc:
        logger.error(f"Cancel error: {exc}")
        raise HTTPException(status_code=502, detail="Nepodarilo sa zrušiť predplatné.")
    # Premietni výsledok hneď (webhook subscription.updated príde aj tak).
    billing_service.apply_subscription(current_user, data)
    db.commit()
    return JSONResponse(
        {
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
    if not current_user.paddle_customer_id:
        raise HTTPException(status_code=404, detail="Žiadne aktívne predplatné.")
    try:
        url = await billing_service.create_portal_session(
            current_user.paddle_customer_id, current_user.paddle_subscription_id
        )
    except Exception as exc:
        logger.error(f"Billing portal error: {exc}")
        raise HTTPException(status_code=502, detail="Nepodarilo sa otvoriť správu predplatného.")
    return JSONResponse({"url": url})


def _find_user(db: Session, custom: dict, data: dict):
    user_id = (custom or {}).get("user_id")
    if user_id:
        try:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                return user
        except (TypeError, ValueError):
            pass
    # subscription eventy majú id 'sub_...', transaction eventy majú subscription_id
    sub_ref = data.get("subscription_id")
    if not sub_ref and str(data.get("id", "")).startswith("sub_"):
        sub_ref = data.get("id")
    if sub_ref:
        user = db.query(User).filter(User.paddle_subscription_id == str(sub_ref)).first()
        if user:
            return user
    customer_id = data.get("customer_id")
    if customer_id:
        user = db.query(User).filter(User.paddle_customer_id == str(customer_id)).first()
        if user:
            return user
    return None


def _log_payment(db: Session, user: User, data: dict):
    txn_id = data.get("id")
    # Idempotencia — tú istú transakciu nelogujeme dvakrát.
    if txn_id and db.query(Payment).filter(
        Payment.provider_payment_id == str(txn_id)
    ).first():
        return
    totals = ((data.get("details") or {}).get("totals")) or {}
    grand_total = totals.get("grand_total")  # reťazec v najmenších jednotkách (centoch)
    try:
        amount = round(int(grand_total) / 100.0, 2)
    except (TypeError, ValueError):
        amount = 0.0
    db.add(
        Payment(
            user_id=user.id,
            email=user.email,
            provider="paddle",
            provider_payment_id=str(txn_id) if txn_id else None,
            provider_subscription_id=str(data.get("subscription_id") or user.paddle_subscription_id or ""),
            status="succeeded",
            amount=amount,
            currency=(totals.get("currency_code") or data.get("currency_code") or "EUR")[:10],
            description="LexiNova PLUS",
        )
    )


def _apply_adjustment(db: Session, data: dict, event_type: str):
    """Refund/chargeback z Paddle (adjustment.*) — premietne stav do platby."""
    action = data.get("action")
    if action not in ("refund", "chargeback"):
        return
    txn_id = data.get("transaction_id")
    payment = (
        db.query(Payment).filter(Payment.provider_payment_id == str(txn_id)).first()
        if txn_id else None
    )
    if not payment:
        logger.warning(f"Paddle {event_type}: platba {txn_id} nenájdená")
        return
    status = data.get("status")
    if status == "approved":
        payment.status = "refunded" if action == "refund" else "chargeback"
    elif status == "pending_approval":
        payment.status = "refund_pending"
    elif status in ("rejected", "reversed"):
        payment.status = "succeeded"  # refund neprešiel — platba ostáva uhradená
    logger.info(f"Paddle {event_type} ({action}/{status}): platba {txn_id} → {payment.status}")


@router.post("/api/webhooks/paddle")
async def paddle_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    signature = request.headers.get("Paddle-Signature", "")
    if not billing_service.verify_webhook_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid payload")

    event_type = event.get("event_type", "")
    data = event.get("data", {}) or {}
    custom = data.get("custom_data") or {}

    # Refundy/chargebacky sa viažu na platbu (nie používateľa) — riešime pred user lookupom.
    if event_type.startswith("adjustment."):
        _apply_adjustment(db, data, event_type)
        db.commit()
        return JSONResponse({"ok": True})

    user = _find_user(db, custom, data)
    if not user:
        # 200, aby Paddle neretryoval donekonečna (len zalogujeme).
        logger.warning(f"Paddle webhook '{event_type}': používateľ nenájdený")
        return JSONResponse({"ok": True})

    if event_type.startswith("subscription."):
        billing_service.apply_subscription(user, data)
        logger.info(
            f"Paddle {event_type}: user {user.id} → status={user.plus_status}, plus={user.is_plus}"
        )
    elif event_type in ("transaction.completed", "transaction.paid"):
        _log_payment(db, user, data)
    elif event_type == "transaction.payment_failed":
        user.plus_status = "past_due"
        logger.warning(f"Paddle payment failed: user {user.id}")

    db.commit()
    return JSONResponse({"ok": True})
