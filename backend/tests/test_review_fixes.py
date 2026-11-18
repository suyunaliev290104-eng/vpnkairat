"""Regression tests for findings of the final review."""
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import Payment, Subscription, utcnow
from app.payments import registry, service
from app.payments.service import create_payment, mark_paid
from app.scheduler import expire, remind, resync
from app.services.subscription import extend, get_or_create_subscription, start_trial
from app.vpn.sync import sync_user
from tests.test_payment_service import DummyProvider, FakeVpn, Notes


@pytest.fixture(autouse=True)
def dummy():
    registry.register(DummyProvider)
    yield
    registry.unregister("dummy")


async def _stale_expired_sub(sessionmaker, session, user_factory):
    """Session A holds an expired sub in its identity map; session B renews it."""
    u = await user_factory()
    sub = await get_or_create_subscription(session, u)
    sub.expires_at = utcnow() - timedelta(days=1)
    sub.needs_sync = True
    await session.commit()
    _ = sub.expires_at  # loaded in session A
    async with sessionmaker() as b:
        ub = await b.get(type(u), u.id)
        await extend(b, ub, 30)
    return u, sub


# I-1: stale identity map must not push old state
async def test_sync_user_uses_fresh_db_state(sessionmaker, session, user_factory, server_factory):
    await server_factory()
    u, _ = await _stale_expired_sub(sessionmaker, session, user_factory)
    vpn = FakeVpn()
    await sync_user(session, u, vpn)
    assert vpn.synced[-1].enabled is True


async def test_resync_does_not_disable_freshly_paid(sessionmaker, session, user_factory, server_factory):
    await server_factory()
    await _stale_expired_sub(sessionmaker, session, user_factory)
    subs = list(await session.scalars(select(Subscription)))  # job-start snapshot
    assert subs
    vpn = FakeVpn()
    await resync(session, vpn)
    assert all(spec.enabled for spec in vpn.synced)


async def test_expire_skips_freshly_renewed(sessionmaker, session, user_factory, server_factory):
    await server_factory()
    await _stale_expired_sub(sessionmaker, session, user_factory)
    vpn, notes = FakeVpn(), Notes()
    await expire(session, vpn, notes)
    assert notes.sent == [] and all(s.enabled for s in vpn.synced)


# I-2: paid status and granted days commit together
async def test_mark_paid_rolls_back_if_extend_fails(sessionmaker, session, user_factory, monkeypatch):
    u = await user_factory()
    p, _ = await create_payment(session, u, "m1", "dummy")
    pid, ppid = p.id, p.provider_payment_id

    async def boom(*a, **kw):
        raise RuntimeError("db died")

    monkeypatch.setattr(service, "extend", boom)
    with pytest.raises(RuntimeError):
        await mark_paid(session, "dummy", ppid, vpn=FakeVpn(), notifier=Notes())
    async with sessionmaker() as fresh:
        assert (await fresh.get(Payment, pid)).status == "pending"


# I-3: extend must read the current expiry, not a stale one
async def test_extend_reads_fresh_expiry(sessionmaker, session, user_factory):
    u = await user_factory()
    sub = await extend(session, u, 30)
    async with sessionmaker() as b:
        await extend(b, await b.get(type(u), u.id), 30)
    sub = await extend(session, u, 30)
    assert abs((sub.expires - (utcnow() + timedelta(days=90))).total_seconds()) < 10


# M-1 (re-graded): no "3 days left" reminder right after a 3-day trial
async def test_no_reminder_right_after_trial(session, user_factory):
    u = await user_factory()
    await start_trial(session, u)
    notes = Notes()
    await remind(session, notes)
    assert notes.sent == []


async def test_reminder_after_renewal_still_sent(session, user_factory):
    u = await user_factory()
    sub = await extend(session, u, 30)
    sub.expires_at = utcnow() + timedelta(days=2)
    await session.commit()
    notes = Notes()
    await remind(session, notes)
    assert len(notes.sent) == 1


# M-4 (re-graded): empty CryptoBot token must reject every webhook
async def test_cryptobot_empty_token_rejects(monkeypatch):
    import hashlib, hmac
    from app.payments.base import WebhookRejected
    from tests.test_cryptobot import make_request
    monkeypatch.setattr(get_settings(), "cryptobot_token", "")
    registry.load_builtin()
    body = b'{"update_type":"invoice_paid","payload":{"invoice_id":1}}'
    sig = hmac.new(hashlib.sha256(b"").digest(), body, hashlib.sha256).hexdigest()
    with pytest.raises(WebhookRejected):
        await registry.get("cryptobot").parse_webhook(make_request(body, {"crypto-pay-api-signature": sig}))


# M-5 (re-graded): lava.top hidden until every plan has an offer id
def test_lavatop_disabled_with_blank_offers(monkeypatch):
    registry.load_builtin()
    s = get_settings()
    monkeypatch.setattr(s, "lavatop_api_key", "k")
    monkeypatch.setattr(s, "lavatop_offers", {"m1": "", "m3": "", "m6": "", "m12": ""})
    assert registry.get("lavatop").enabled(s) is False
    monkeypatch.setattr(s, "lavatop_offers", {"m1": "a", "m3": "b", "m6": "c"})
    assert registry.get("lavatop").enabled(s) is False
