import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import notify
from app.config import get_settings
from app.models import Payment, User, utcnow
from app.payments import registry
from app.payments.base import InvoiceResult
from app.plans import PLANS
from app.services.subscription import apply_referral_bonus, extend
from app.vpn.base import VpnProvider
from app.vpn.sync import sync_user

log = logging.getLogger(__name__)

Notifier = Callable[[int, str], Awaitable[None]]


async def create_payment(s: AsyncSession, user: User, plan_id: str, provider_name: str) -> tuple[Payment, InvoiceResult]:
    plan = PLANS.get(plan_id)
    if not plan:
        raise ValueError("unknown_plan")
    provider = registry.get(provider_name)
    payment = Payment(user_id=user.id, provider=provider.name, plan_id=plan.id,
                      amount=provider.price(plan), currency=provider.currency, status="pending")
    s.add(payment)
    await s.commit()
    invoice = await provider.create_invoice(payment, plan, user)
    if invoice.provider_payment_id:
        payment.provider_payment_id = invoice.provider_payment_id
        await s.commit()
    return payment, invoice


async def _safe_notify(notifier: Notifier, tg_id: int, text: str) -> None:
    try:
        await notifier(tg_id, text)
    except Exception:
        log.warning("notify failed for %s", tg_id, exc_info=True)


async def mark_paid(
    s: AsyncSession,
    provider_name: str,
    provider_payment_id: str | None,
    *,
    payment_id: int | None = None,
    vpn: VpnProvider,
    notifier: Notifier,
) -> Payment | None:
    """Idempotently mark a payment paid and grant the subscription.

    Returns the payment on the first successful transition, None if unknown or already processed.
    """
    if payment_id is not None:
        cond = (Payment.id == payment_id)
    elif provider_payment_id:
        cond = (Payment.provider_payment_id == provider_payment_id)
    else:
        return None
    values = {"status": "paid", "paid_at": utcnow()}
    if payment_id is not None and provider_payment_id:
        values["provider_payment_id"] = provider_payment_id
    res = await s.execute(
        update(Payment)
        .where(cond, Payment.provider == provider_name, Payment.status == "pending")
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    await s.commit()
    if res.rowcount != 1:
        return None

    payment = await s.scalar(select(Payment).where(cond).execution_options(populate_existing=True))
    user = await s.get(User, payment.user_id)
    plan = PLANS[payment.plan_id]
    sub = await extend(s, user, plan.days)
    await sync_user(s, user, vpn)
    await _safe_notify(notifier, user.tg_id, notify.paid(plan, sub.expires))

    referrer = await apply_referral_bonus(s, user)
    if referrer:
        await sync_user(s, referrer, vpn)
        await s.refresh(referrer, ["subscription"])
        await _safe_notify(notifier, referrer.tg_id,
                           notify.referral_bonus(get_settings().referral_bonus_days, referrer.subscription.expires))
    return payment
