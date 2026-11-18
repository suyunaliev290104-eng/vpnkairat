from datetime import timedelta

import pytest

from app.models import Payment, utcnow
from app.payments import registry
from app.payments.base import InvoiceResult, PaymentProvider
from app.payments.service import create_payment, mark_paid
from app.services.subscription import get_or_create_subscription, get_or_create_user


class FakeVpn:
    def __init__(self, fail=False):
        self.fail = fail
        self.synced = []

    async def upsert_client(self, server, spec):
        if self.fail:
            raise RuntimeError("down")
        self.synced.append(spec)

    async def get_traffic(self, server, email):
        return (0, 0)


class Notes:
    def __init__(self):
        self.sent = []

    async def __call__(self, tg_id, text):
        self.sent.append((tg_id, text))


class DummyProvider(PaymentProvider):
    name = "dummy"
    title = "Dummy"
    currency = "RUB"

    def price(self, plan):
        return plan.rub

    def enabled(self, settings):
        return True

    async def create_invoice(self, payment, plan, user):
        return InvoiceResult(payment_url="https://pay/x", provider_payment_id=f"inv-{payment.id}")

    async def parse_webhook(self, request):
        raise NotImplementedError


@pytest.fixture(autouse=True)
def dummy():
    registry.register(DummyProvider)
    yield
    registry.unregister("dummy")


def close(a, b):
    return abs((a - b).total_seconds()) < 5


async def test_create_payment_stores_pending(session, user_factory):
    u = await user_factory()
    p, inv = await create_payment(session, u, "m3", "dummy")
    assert p.status == "pending" and p.amount == 549 and p.currency == "RUB" and p.plan_id == "m3"
    assert p.provider_payment_id == f"inv-{p.id}" and inv.payment_url == "https://pay/x"


async def test_create_payment_unknown_plan(session, user_factory):
    u = await user_factory()
    with pytest.raises(ValueError, match="unknown_plan"):
        await create_payment(session, u, "m99", "dummy")


async def test_mark_paid_extends_once(session, user_factory, server_factory):
    await server_factory()
    u = await user_factory()
    p, _ = await create_payment(session, u, "m1", "dummy")
    vpn, notes = FakeVpn(), Notes()
    first = await mark_paid(session, "dummy", p.provider_payment_id, vpn=vpn, notifier=notes)
    second = await mark_paid(session, "dummy", p.provider_payment_id, vpn=vpn, notifier=notes)
    assert first is not None and first.status == "paid" and second is None
    sub = await get_or_create_subscription(session, u)
    assert close(sub.expires, utcnow() + timedelta(days=30))
    assert len(vpn.synced) == 1 and len(notes.sent) == 1


async def test_mark_paid_unknown_id_returns_none(session):
    assert await mark_paid(session, "dummy", "nope", vpn=FakeVpn(), notifier=Notes()) is None


async def test_mark_paid_wrong_provider_returns_none(session, user_factory):
    u = await user_factory()
    p, _ = await create_payment(session, u, "m1", "dummy")
    assert await mark_paid(session, "other", p.provider_payment_id, vpn=FakeVpn(), notifier=Notes()) is None


async def test_mark_paid_by_payment_id_sets_provider_id(session, user_factory):
    u = await user_factory()
    p, _ = await create_payment(session, u, "m1", "dummy")
    got = await mark_paid(session, "dummy", "charge-1", payment_id=p.id, vpn=FakeVpn(), notifier=Notes())
    assert got.provider_payment_id == "charge-1"


async def test_mark_paid_when_vpn_down_still_paid(session, user_factory, server_factory):
    await server_factory()
    u = await user_factory()
    p, _ = await create_payment(session, u, "m1", "dummy")
    got = await mark_paid(session, "dummy", p.provider_payment_id, vpn=FakeVpn(fail=True), notifier=Notes())
    assert got.status == "paid"
    sub = await get_or_create_subscription(session, u)
    assert sub.is_active and sub.needs_sync is True


async def test_referral_bonus_on_paid(session):
    ref = await get_or_create_user(session, 501, "ref")
    payer = await get_or_create_user(session, 502, "payer", ref_tg_id=501)
    p, _ = await create_payment(session, payer, "m1", "dummy")
    notes = Notes()
    await mark_paid(session, "dummy", p.provider_payment_id, vpn=FakeVpn(), notifier=notes)
    sub = await get_or_create_subscription(session, ref)
    assert close(sub.expires, utcnow() + timedelta(days=7))
    assert {t for t, _ in notes.sent} == {501, 502}


async def test_failed_notifier_does_not_break_payment(session, user_factory):
    u = await user_factory()
    p, _ = await create_payment(session, u, "m1", "dummy")

    async def boom(tg_id, text):
        raise RuntimeError("blocked by user")

    got = await mark_paid(session, "dummy", p.provider_payment_id, vpn=FakeVpn(), notifier=boom)
    assert got.status == "paid"
    assert (await session.get(Payment, p.id)).status == "paid"
