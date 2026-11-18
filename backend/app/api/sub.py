import base64

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_session
from app.config import get_settings
from app.models import Subscription
from app.vpn.links import build_subscription
from app.vpn.sync import enabled_servers

router = APIRouter()


@router.get("/sub/{token}")
async def subscription(token: str, s: AsyncSession = Depends(get_session)):
    sub = await s.scalar(select(Subscription).where(Subscription.sub_token == token))
    if not sub:
        raise HTTPException(404)
    st = get_settings()
    body = build_subscription(await enabled_servers(s), sub.uuid) if sub.is_active else ""
    expire = int(sub.expires.timestamp()) if sub.expires else 0
    headers = {
        "profile-title": "base64:" + base64.b64encode(st.brand_name.encode()).decode(),
        "profile-update-interval": "12",
        "subscription-userinfo": f"upload=0; download=0; total=0; expire={expire}",
    }
    if st.support_username:
        headers["support-url"] = f"https://t.me/{st.support_username}"
    return PlainTextResponse(body, headers=headers)
