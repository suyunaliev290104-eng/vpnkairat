import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Server, User
from app.services.subscription import get_or_create_subscription
from app.vpn.base import ClientSpec, VpnProvider

log = logging.getLogger(__name__)


def client_email(user: User) -> str:
    return f"tg{user.tg_id}"


async def enabled_servers(s: AsyncSession) -> list[Server]:
    return list(await s.scalars(select(Server).where(Server.enabled.is_(True)).order_by(Server.id)))


async def sync_user(s: AsyncSession, user: User, provider: VpnProvider) -> bool:
    """Push the user's current subscription state to every enabled server.

    Expired users are disabled (never deleted) so renewing reuses the same key.
    """
    sub = await get_or_create_subscription(s, user)
    spec = ClientSpec(
        uuid=sub.uuid,
        email=client_email(user),
        expiry_ms=int(sub.expires.timestamp() * 1000) if sub.expires else 0,
        enabled=sub.is_active,
        limit_ip=get_settings().device_limit,
        sub_id=sub.sub_token,
    )
    ok = True
    for server in await enabled_servers(s):
        try:
            await provider.upsert_client(server, spec)
        except Exception:
            log.exception("sync failed: user=%s server=%s", user.tg_id, server.name)
            ok = False
    sub.needs_sync = not ok
    await s.commit()
    return ok
