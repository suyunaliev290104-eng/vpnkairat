import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import notify
from app.models import Subscription, User, utcnow
from app.payments.service import Notifier, _safe_notify
from app.vpn.base import VpnProvider
from app.vpn.base import BYPASS
from app.vpn.sync import enabled_servers, sync_user

log = logging.getLogger(__name__)


async def remind(s: AsyncSession, notifier: Notifier) -> None:
    now = utcnow()
    subs = await s.scalars(select(Subscription).where(
        Subscription.expires_at > now,
        Subscription.expires_at <= now + timedelta(days=3),
        Subscription.notified_1d.is_(False),
    ))
    for sub in list(subs):
        await s.refresh(sub)  # may have been renewed since the query ran
        if sub.notified_1d or not sub.expires or not (now < sub.expires <= now + timedelta(days=3)):
            continue
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
        await s.refresh(sub)
        if sub.notified_expired or sub.is_active:
            continue
        user = await s.get(User, sub.user_id)
        await sync_user(s, user, vpn)
        sub.notified_expired = True
        await s.commit()
        await _safe_notify(notifier, user.tg_id, notify.expired())


async def resync(s: AsyncSession, vpn: VpnProvider) -> None:
    subs = await s.scalars(select(Subscription).where(Subscription.needs_sync.is_(True)))
    for sub in list(subs):
        await sync_user(s, await s.get(User, sub.user_id), vpn)


async def reset_bypass(s: AsyncSession, vpn: VpnProvider) -> None:
    """Daily (00:00 MSK): reset per-client traffic on bypass servers → new 5 GB/day allowance."""
    for server in await enabled_servers(s):
        if server.kind != BYPASS:
            continue
        try:
            await vpn.reset_traffic(server)
        except Exception:
            log.exception("bypass traffic reset failed on %s", server.name)


async def run_reset_bypass() -> None:
    from app.context import ctx
    from app.db import get_sessionmaker

    async with get_sessionmaker()() as s:
        await reset_bypass(s, ctx.vpn)


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
