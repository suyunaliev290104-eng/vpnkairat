import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import notify
from app.models import Subscription, User, utcnow
from app.payments.service import Notifier, _safe_notify
from app.vpn.base import VpnProvider
from app.vpn.sync import sync_user

log = logging.getLogger(__name__)


async def remind(s: AsyncSession, notifier: Notifier) -> None:
    now = utcnow()
    subs = await s.scalars(select(Subscription).where(
        Subscription.expires_at > now,
        Subscription.expires_at <= now + timedelta(days=3),
        Subscription.notified_1d.is_(False),
    ))
    for sub in list(subs):
        user = await s.get(User, sub.user_id)
        if sub.expires - now <= timedelta(days=1):
            sub.notified_1d = sub.notified_3d = True
            await _safe_notify(notifier, user.tg_id, notify.expires_soon(1))
        elif not sub.notified_3d:
            sub.notified_3d = True
            await _safe_notify(notifier, user.tg_id, notify.expires_soon(3))
        await s.commit()


async def expire(s: AsyncSession, vpn: VpnProvider, notifier: Notifier) -> None:
    subs = await s.scalars(select(Subscription).where(
        Subscription.expires_at <= utcnow(),
        Subscription.notified_expired.is_(False),
    ))
    for sub in list(subs):
        user = await s.get(User, sub.user_id)
        await sync_user(s, user, vpn)
        sub.notified_expired = True
        await s.commit()
        await _safe_notify(notifier, user.tg_id, notify.expired())


async def resync(s: AsyncSession, vpn: VpnProvider) -> None:
    subs = await s.scalars(select(Subscription).where(Subscription.needs_sync.is_(True)))
    for sub in list(subs):
        await sync_user(s, await s.get(User, sub.user_id), vpn)


async def run_all() -> None:
    """Periodic job entry point (every 10 minutes)."""
    from app.context import ctx, notifier
    from app.db import get_sessionmaker

    for job in (lambda s: remind(s, notifier), lambda s: expire(s, ctx.vpn, notifier),
                lambda s: resync(s, ctx.vpn)):
        try:
            async with get_sessionmaker()() as s:
                await job(s)
        except Exception:
            log.exception("scheduler job failed")
