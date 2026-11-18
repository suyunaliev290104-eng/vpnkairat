import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import current_user, get_session
from app.config import get_settings
from app.context import ctx
from app.models import Server, Subscription, User, utcnow
from app.payments import registry
from app.payments.service import create_payment
from app.plans import PLANS, discount_percent, per_month_rub
from app.services.subscription import get_or_create_subscription, start_trial
from app.vpn.sync import client_email, enabled_servers, sync_user

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


async def _traffic(servers: list[Server], email: str) -> int:
    async def one(srv):
        try:
            up, down = await asyncio.wait_for(ctx.vpn.get_traffic(srv, email), 3)
            return up + down
        except Exception:
            return 0
    return sum(await asyncio.gather(*(one(s) for s in servers)))


def sub_url(sub: Subscription) -> str:
    return f"{get_settings().public_url.rstrip('/')}/sub/{sub.sub_token}"


async def me_payload(s: AsyncSession, user: User, with_traffic: bool = True) -> dict:
    sub = await get_or_create_subscription(s, user)
    servers = await enabled_servers(s)
    active = sub.is_active
    days_left = 0
    if active:
        days_left = max(0, -(-int((sub.expires - utcnow()).total_seconds()) // 86400))  # ceil
    traffic = await _traffic(servers, client_email(user)) if (with_traffic and sub.expires) else 0
    return {
        "user": {"tg_id": user.tg_id, "username": user.username, "email": user.email},
        "subscription": {
            "active": active,
            "expires_at": sub.expires.isoformat() if sub.expires else None,
            "days_left": days_left,
            "trial_available": not sub.trial_used and sub.expires is None,
            "sub_url": sub_url(sub),
            "traffic_used": traffic,
            "device_limit": get_settings().device_limit,
        },
        "servers": [{"name": x.name, "flag": x.flag, "country": x.country} for x in servers],
        "support_username": get_settings().support_username,
    }


@router.get("/me")
async def me(user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    return await me_payload(s, user)


@router.get("/plans")
async def plans(user: User = Depends(current_user)):
    providers = registry.available()
    return {
        "plans": [
            {
                "id": p.id, "days": p.days, "months": p.months, "badge": p.badge,
                "discount": discount_percent(p), "per_month_rub": per_month_rub(p),
                "prices": {pr.name: {"amount": pr.price(p), "currency": pr.currency} for pr in providers},
            }
            for p in PLANS.values()
        ],
        "providers": [
            {"name": p.name, "title": p.title, "currency": p.currency, "kind": p.kind,
             "needs_email": p.needs_email}
            for p in providers
        ],
    }


@router.post("/trial")
async def trial(user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    sub = await get_or_create_subscription(s, user)
    if sub.expires is not None:
        raise HTTPException(409, "trial_used")
    try:
        await start_trial(s, user)
    except ValueError as e:
        raise HTTPException(409, str(e))
    await sync_user(s, user, ctx.vpn)
    return await me_payload(s, user, with_traffic=False)


class PayIn(BaseModel):
    plan_id: str
    provider: str


@router.post("/pay")
async def pay(body: PayIn, user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    if body.provider not in {p.name for p in registry.available()}:
        raise HTTPException(400, "unknown_provider")
    try:
        payment, inv = await create_payment(s, user, body.plan_id, body.provider)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        log.exception("create_invoice failed")
        raise HTTPException(502, "payment_provider_error")
    return {"payment_id": payment.id, "payment_url": inv.payment_url, "kind": registry.get(body.provider).kind}


class EmailIn(BaseModel):
    email: EmailStr


@router.post("/email")
async def set_email(body: EmailIn, user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    user.email = str(body.email)
    await s.commit()
    return await me_payload(s, user, with_traffic=False)


@router.get("/referrals")
async def referrals(user: User = Depends(current_user), s: AsyncSession = Depends(get_session)):
    st = get_settings()
    invited = await s.scalar(select(func.count()).select_from(User).where(User.referrer_id == user.id))
    return {
        "link": f"https://t.me/{st.bot_username}?start=ref_{user.tg_id}",
        "invited": invited or 0,
        "bonus_days": st.referral_bonus_days,
    }
