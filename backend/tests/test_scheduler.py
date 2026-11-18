from datetime import timedelta

from app.models import utcnow
from app.scheduler import expire, remind, resync
from app.services.subscription import extend, get_or_create_subscription


class FakeVpn:
    def __init__(self):
        self.specs = []

    async def upsert_client(self, server, spec):
        self.specs.append(spec)

    async def get_traffic(self, server, email):
        return (0, 0)


class Notes:
    def __init__(self):
        self.sent = []

    async def __call__(self, tg_id, text):
        self.sent.append((tg_id, text))


async def _sub_expiring_in(session, user, delta):
    sub = await get_or_create_subscription(session, user)
    sub.expires_at = utcnow() + delta
    await session.commit()
    return sub


async def test_remind_3d_sent_once(session, user_factory):
    u = await user_factory()
    await _sub_expiring_in(session, u, timedelta(days=2, hours=12))
    n = Notes()
    await remind(session, n)
    await remind(session, n)
    assert len(n.sent) == 1 and "3 дня" in n.sent[0][1]


async def test_remind_1d(session, user_factory):
    u = await user_factory()
    await _sub_expiring_in(session, u, timedelta(hours=20))
    n = Notes()
    await remind(session, n)
    await remind(session, n)
    assert len(n.sent) == 1 and "1 день" in n.sent[0][1]


async def test_no_remind_far_future(session, user_factory):
    u = await user_factory()
    await _sub_expiring_in(session, u, timedelta(days=10))
    n = Notes()
    await remind(session, n)
    assert n.sent == []


async def test_expire_disables_not_deletes(session, user_factory, server_factory):
    await server_factory()
    u = await user_factory()
    sub = await _sub_expiring_in(session, u, timedelta(minutes=-1))
    vpn, n = FakeVpn(), Notes()
    await expire(session, vpn, n)
    await expire(session, vpn, n)
    assert len(vpn.specs) == 1 and vpn.specs[0].enabled is False and vpn.specs[0].uuid == sub.uuid
    assert len(n.sent) == 1


async def test_expire_skips_users_without_subscription(session, user_factory, server_factory):
    await server_factory()
    u = await user_factory()
    await get_or_create_subscription(session, u)
    vpn, n = FakeVpn(), Notes()
    await expire(session, vpn, n)
    assert vpn.specs == [] and n.sent == []


async def test_resync_clears_flag(session, user_factory, server_factory):
    await server_factory()
    u = await user_factory()
    sub = await extend(session, u, 30)
    assert sub.needs_sync
    vpn = FakeVpn()
    await resync(session, vpn)
    assert sub.needs_sync is False and len(vpn.specs) == 1
