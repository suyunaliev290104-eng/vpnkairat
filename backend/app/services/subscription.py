import secrets
import uuid as uuidlib
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Subscription, User, utcnow


async def get_user_by_tg(s: AsyncSession, tg_id: int) -> User | None:
    return await s.scalar(select(User).where(User.tg_id == tg_id))


async def get_or_create_user(
    s: AsyncSession, tg_id: int, username: str | None, ref_tg_id: int | None = None
) -> User:
    user = await get_user_by_tg(s, tg_id)
    if user:
        if username and user.username != username:
            user.username = username
            await s.commit()
        return user
    referrer = None
    if ref_tg_id and ref_tg_id != tg_id:
        referrer = await get_user_by_tg(s, ref_tg_id)
    user = User(
        tg_id=tg_id,
        username=username,
        referrer_id=referrer.id if referrer else None,
        is_admin=tg_id in get_settings().admin_ids,
    )
    s.add(user)
    await s.commit()
    return user


async def get_or_create_subscription(s: AsyncSession, user: User, *, lock: bool = False) -> Subscription:
    """Always returns the row as it is in the DB now (never a stale identity-map copy).

    lock=True takes a row lock (SELECT ... FOR UPDATE; no-op on SQLite) for read-modify-write.
    """
    q = select(Subscription).where(Subscription.user_id == user.id).execution_options(populate_existing=True)
    if lock:
        q = q.with_for_update()
    sub = await s.scalar(q)
    if sub:
        return sub
    sub = Subscription(user_id=user.id, uuid=str(uuidlib.uuid4()), sub_token=secrets.token_urlsafe(16))
    s.add(sub)
    await s.commit()
    return sub


async def _add_days(s: AsyncSession, sub: Subscription, days: int, commit: bool = True) -> Subscription:
    now = utcnow()
    start = sub.expires if sub.expires and sub.expires > now else now
    sub.expires_at = start + timedelta(days=days)
    left = sub.expires_at - now
    # Don't warn "N days left" about a term that was that short from the start (e.g. a 3-day trial).
    sub.notified_1d = left <= timedelta(days=1)
    sub.notified_3d = left <= timedelta(days=3)
    sub.notified_expired = False
    sub.needs_sync = True
    if commit:
        await s.commit()
    return sub


async def start_trial(s: AsyncSession, user: User) -> Subscription:
    sub = await get_or_create_subscription(s, user, lock=True)
    if sub.trial_used:
        raise ValueError("trial_used")
    sub.trial_used = True
    return await _add_days(s, sub, get_settings().trial_days)


async def extend(s: AsyncSession, user: User, days: int, *, commit: bool = True) -> Subscription:
    sub = await get_or_create_subscription(s, user, lock=True)
    return await _add_days(s, sub, days, commit=commit)


async def apply_referral_bonus(s: AsyncSession, payer: User) -> User | None:
    if not payer.referrer_id:
        return None
    referrer = await s.get(User, payer.referrer_id)
    if not referrer:
        return None
    await extend(s, referrer, get_settings().referral_bonus_days)
    return referrer
