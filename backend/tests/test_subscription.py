from datetime import timedelta

import pytest

from app.models import utcnow
from app.services.subscription import (
    apply_referral_bonus, extend, get_or_create_subscription, get_or_create_user, start_trial,
)


def close(a, b):
    return abs((a - b).total_seconds()) < 5


async def test_trial_gives_3_days_once(session, user_factory):
    u = await user_factory()
    sub = await start_trial(session, u)
    assert close(sub.expires, utcnow() + timedelta(days=3))
    with pytest.raises(ValueError, match="trial_used"):
        await start_trial(session, u)


async def test_extend_active_adds_to_expiry(session, user_factory):
    u = await user_factory()
    sub = await get_or_create_subscription(session, u)
    sub.expires_at = utcnow() + timedelta(days=10)
    await session.commit()
    sub = await extend(session, u, 30)
    assert close(sub.expires, utcnow() + timedelta(days=40))
    assert sub.needs_sync is True


async def test_extend_expired_starts_from_now(session, user_factory):
    u = await user_factory()
    sub = await get_or_create_subscription(session, u)
    sub.expires_at = utcnow() - timedelta(days=7)
    sub.notified_expired = True
    await session.commit()
    sub = await extend(session, u, 30)
    assert close(sub.expires, utcnow() + timedelta(days=30))
    assert sub.notified_expired is False


async def test_subscription_has_uuid_and_token(session, user_factory):
    u = await user_factory()
    sub = await get_or_create_subscription(session, u)
    assert len(sub.uuid) == 36 and len(sub.sub_token) >= 16
    assert (await get_or_create_subscription(session, u)).id == sub.id


async def test_referrer_set_only_on_create(session):
    ref = await get_or_create_user(session, 1, "ref", None)
    other = await get_or_create_user(session, 2, "other", None)
    u = await get_or_create_user(session, 3, "new", ref_tg_id=1)
    assert u.referrer_id == ref.id
    again = await get_or_create_user(session, 3, "new", ref_tg_id=2)
    assert again.referrer_id == ref.id
    assert other.referrer_id is None


async def test_self_referral_ignored(session):
    u = await get_or_create_user(session, 5, "me", ref_tg_id=5)
    assert u.referrer_id is None


async def test_unknown_referrer_ignored(session):
    u = await get_or_create_user(session, 6, "x", ref_tg_id=999999)
    assert u.referrer_id is None


async def test_referral_bonus_7_days(session):
    ref = await get_or_create_user(session, 10, "ref", None)
    payer = await get_or_create_user(session, 11, "payer", ref_tg_id=10)
    got = await apply_referral_bonus(session, payer)
    assert got.id == ref.id
    sub = await get_or_create_subscription(session, ref)
    assert close(sub.expires, utcnow() + timedelta(days=7))


async def test_no_referrer_no_bonus(session, user_factory):
    u = await user_factory()
    assert await apply_referral_bonus(session, u) is None
