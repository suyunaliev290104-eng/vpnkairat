from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Payment, Subscription, User, utcnow


async def _revenue(s: AsyncSession, since) -> dict[str, float]:
    rows = await s.execute(
        select(Payment.currency, func.sum(Payment.amount))
        .where(Payment.status == "paid", Payment.paid_at >= since)
        .group_by(Payment.currency)
    )
    out: dict[str, float] = defaultdict(float)
    for cur, total in rows:
        out[cur] = int(total) if float(total).is_integer() else float(total)
    return dict(out)


async def stats(s: AsyncSession) -> dict:
    now = utcnow()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "users": await s.scalar(select(func.count()).select_from(User)),
        "active": await s.scalar(select(func.count()).select_from(Subscription)
                                 .where(Subscription.expires_at > now)),
        "new_today": await s.scalar(select(func.count()).select_from(User).where(User.created_at >= day_start)),
        "revenue_today": await _revenue(s, day_start),
        "revenue_30d": await _revenue(s, now - timedelta(days=30)),
    }


async def find_user(s: AsyncSession, query: str) -> User | None:
    q = query.strip()
    if q.lstrip("-").isdigit():
        return await s.scalar(select(User).where(User.tg_id == int(q)))
    name = q.lstrip("@").lower()
    return await s.scalar(select(User).where(func.lower(User.username) == name))


async def queue_resync_all(s: AsyncSession) -> int:
    """Mark every active subscription for re-sync (e.g. after adding a server). Returns count."""
    subs = list(await s.scalars(select(Subscription).where(Subscription.expires_at > utcnow())))
    for sub in subs:
        sub.needs_sync = True
    await s.commit()
    return len(subs)


async def all_user_ids(s: AsyncSession) -> list[int]:
    return list(await s.scalars(select(User.tg_id)))
