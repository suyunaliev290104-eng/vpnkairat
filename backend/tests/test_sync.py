from datetime import timedelta

from app.models import utcnow
from app.services.subscription import extend
from app.vpn.sync import sync_user


class FakeProvider:
    def __init__(self, fail_hosts=()):
        self.calls = []
        self.fail_hosts = set(fail_hosts)

    async def upsert_client(self, server, spec):
        if server.host in self.fail_hosts:
            raise RuntimeError("down")
        self.calls.append((server.host, spec))

    async def get_traffic(self, server, email):
        return (0, 0)


async def test_sync_upserts_on_all_enabled_servers(session, user_factory, server_factory):
    await server_factory(host="a")
    await server_factory(host="b")
    await server_factory(host="off", enabled=False)
    u = await user_factory(tg_id=42)
    sub = await extend(session, u, 30)
    p = FakeProvider()
    assert await sync_user(session, u, p) is True
    assert sorted(h for h, _ in p.calls) == ["a", "b"]
    spec = p.calls[0][1]
    assert spec.email == "tg42" and spec.uuid == sub.uuid and spec.enabled and spec.limit_ip == 3
    assert spec.sub_id == sub.sub_token
    assert abs(spec.expiry_ms - int(sub.expires.timestamp() * 1000)) < 1000
    assert sub.needs_sync is False


async def test_sync_marks_needs_sync_on_error(session, user_factory, server_factory):
    await server_factory(host="a")
    await server_factory(host="bad")
    u = await user_factory()
    sub = await extend(session, u, 30)
    assert await sync_user(session, u, FakeProvider(fail_hosts={"bad"})) is False
    assert sub.needs_sync is True


async def test_sync_expired_user_is_disabled(session, user_factory, server_factory):
    await server_factory(host="a")
    u = await user_factory()
    sub = await extend(session, u, 1)
    sub.expires_at = utcnow() - timedelta(days=1)
    await session.commit()
    p = FakeProvider()
    await sync_user(session, u, p)
    assert p.calls[0][1].enabled is False
