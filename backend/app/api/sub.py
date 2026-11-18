import base64
import html

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_session
from app.config import get_settings
from app.models import Subscription
from app.vpn.links import build_subscription
from app.vpn.routing import build_happ_routing
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
    if st.split_routing:
        headers["routing"] = build_happ_routing(st.brand_name)
    if st.support_username:
        headers["support-url"] = f"https://t.me/{st.support_username}"
    return PlainTextResponse(body, headers=headers)


DEEPLINKS = {
    "happ": "happ://add/{url}",
    "v2raytun": "v2raytun://import/{url}",
    "hiddify": "hiddify://import/{url}",
    "streisand": "streisand://import/{url}",
}


@router.get("/connect/{token}/{client_app}")
async def connect(token: str, client_app: str, s: AsyncSession = Depends(get_session)):
    """Telegram can't open custom URL schemes; this page bounces the user into the VPN client."""
    tpl = DEEPLINKS.get(client_app)
    sub = await s.scalar(select(Subscription).where(Subscription.sub_token == token))
    if not tpl or not sub:
        raise HTTPException(404)
    url = f"{get_settings().public_url.rstrip('/')}/sub/{sub.sub_token}"
    link = html.escape(tpl.format(url=url), quote=True)
    page = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Подключение</title>
<style>body{{font-family:system-ui,sans-serif;display:flex;min-height:100vh;align-items:center;
justify-content:center;margin:0;background:#0f1115;color:#fff;text-align:center}}
a{{display:inline-block;margin-top:16px;padding:14px 22px;border-radius:14px;background:#3d7bfd;
color:#fff;text-decoration:none;font-weight:600}}</style></head>
<body><div><h2>Открываем приложение…</h2>
<p>Если ничего не произошло — нажмите кнопку.<br>Приложение должно быть установлено.</p>
<a href="{link}">Добавить подписку</a></div>
<script>setTimeout(function(){{location.href="{link}"}},150)</script></body></html>"""
    return HTMLResponse(page)
