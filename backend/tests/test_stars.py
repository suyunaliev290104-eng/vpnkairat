from app.bot.payments import check_pre_checkout, process_successful_payment
from app.context import ctx
from app.payments import registry
from app.payments.service import create_payment


class FakeBot:
    def __init__(self):
        self.kw = None

    async def create_invoice_link(self, **kw):
        self.kw = kw
        return "https://t.me/$invoice"


class FakeVpn:
    async def upsert_client(self, server, spec): pass
    async def get_traffic(self, server, email): return (0, 0)


async def _noop(tg_id, text): pass


async def test_stars_invoice(session, user_factory, monkeypatch):
    registry.load_builtin()
    bot = FakeBot()
    monkeypatch.setattr(ctx, "bot", bot)
    u = await user_factory()
    p, inv = await create_payment(session, u, "m12", "stars")
    assert inv.payment_url == "https://t.me/$invoice"
    assert p.provider_payment_id is None and p.amount == 1700 and p.currency == "XTR"
    assert bot.kw["currency"] == "XTR" and bot.kw["payload"] == f"pay:{p.id}"
    assert bot.kw["prices"][0].amount == 1700
    assert registry.get("stars").kind == "invoice"


async def test_pre_checkout_only_pending(session, user_factory, monkeypatch):
    registry.load_builtin()
    monkeypatch.setattr(ctx, "bot", FakeBot())
    u = await user_factory()
    p, _ = await create_payment(session, u, "m1", "stars")
    assert await check_pre_checkout(session, f"pay:{p.id}", 190) is True
    assert await check_pre_checkout(session, f"pay:{p.id}", 1) is False
    assert await check_pre_checkout(session, "pay:999999", 190) is False
    assert await check_pre_checkout(session, "garbage", 190) is False


async def test_successful_payment_marks_paid(session, user_factory, monkeypatch):
    registry.load_builtin()
    monkeypatch.setattr(ctx, "bot", FakeBot())
    u = await user_factory()
    p, _ = await create_payment(session, u, "m1", "stars")
    got = await process_successful_payment(session, f"pay:{p.id}", "charge-xyz", vpn=FakeVpn(), notifier=_noop)
    assert got.status == "paid" and got.provider_payment_id == "charge-xyz"
    again = await process_successful_payment(session, f"pay:{p.id}", "charge-xyz", vpn=FakeVpn(), notifier=_noop)
    assert again is None
