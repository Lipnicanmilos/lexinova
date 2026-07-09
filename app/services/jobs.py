"""Konkrétne denné joby aplikácie.

Import tohto modulu zaregistruje joby do lazy schedulera (app/services/scheduler.py).
Registruje ho `app/main.py` pri štarte. Nové denné joby pridávaj sem:

    def moj_job(db) -> None:
        ...            # idempotentná práca nad `db`
        db.commit()

    register_job("moj_job", moj_job, run_after_hour=3)
"""
from app.models.user import User
from app.services.runtime import logger
from app.services.scheduler import register_job
from app.utils import utcnow


def expire_subscriptions(db) -> None:
    """Vypne PLUS používateľom, ktorým predplatné expirovalo.

    Doteraz sa to dialo len pri prihlásení (`billing_service.expire_if_needed`),
    takže neaktívny používateľ so zmeškaným `subscription.canceled` webhookom
    mohol mať `is_plus=True` aj po expirácii (a skresľoval MRR). Tento job to
    dobehne aj bez prihlásenia. Idempotentný — spracuje aktuálne expirovaných."""
    now = utcnow()
    count = (
        db.query(User)
        .filter(
            User.is_plus.is_(True),
            User.plus_expires_at.isnot(None),
            User.plus_expires_at < now,
        )
        .update(
            {User.is_plus: False, User.plus_status: "expired"},
            synchronize_session=False,
        )
    )
    db.commit()
    if count:
        logger.info("expire_subscriptions: vypnutý PLUS %d používateľom", count)


register_job("expire_subscriptions", expire_subscriptions, run_after_hour=3)
