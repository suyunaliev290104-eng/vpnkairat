from aiogram import F, Router
from aiogram.types import Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.context import ctx, notifier
from app.db import get_sessionmaker
from app.models import Payment
from app.payments.service import Notifier, mark_paid
from app.payments.stars import parse_payload
from app.vpn.base import VpnProvider

router = Router()


async def check_pre_checkout(s: AsyncSession, payload: str, total_amount: int) -> bool:
    pid = parse_payload(payload)
    if pid is None:
        return False
    p = await s.get(Payment, pid)
    return bool(p and p.provider == "stars" and p.status == "pending" and int(p.amount) == total_amount)


async def process_successful_payment(s: AsyncSession, payload: str, charge_id: str, *,
                                     vpn: VpnProvider, notifier: Notifier) -> Payment | None:
    pid = parse_payload(payload)
    if pid is None:
        return None
    return await mark_paid(s, "stars", charge_id, payment_id=pid, vpn=vpn, notifier=notifier)


@router.pre_checkout_query()
async def on_pre_checkout(q: PreCheckoutQuery) -> None:
    async with get_sessionmaker()() as s:
        ok = await check_pre_checkout(s, q.invoice_payload, q.total_amount)
    await q.answer(ok=ok, error_message=None if ok else "Счёт устарел, создайте новый в приложении.")


@router.message(F.successful_payment)
async def on_successful_payment(m: Message) -> None:
    sp = m.successful_payment
    async with get_sessionmaker()() as s:
        await process_successful_payment(s, sp.invoice_payload, sp.telegram_payment_charge_id,
                                         vpn=ctx.vpn, notifier=notifier)
