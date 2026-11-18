import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_session
from app.context import ctx, notifier
from app.payments import registry
from app.payments.base import WebhookRejected
from app.payments.service import mark_paid

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhooks/{provider_name}")
async def webhook(provider_name: str, request: Request, s: AsyncSession = Depends(get_session)):
    try:
        provider = registry.get(provider_name)
    except ValueError:
        raise HTTPException(404)
    try:
        res = await provider.parse_webhook(request)
    except WebhookRejected:
        log.warning("rejected webhook for %s", provider_name)
        raise HTTPException(403)
    except NotImplementedError:
        raise HTTPException(404)
    if res.paid and res.provider_payment_id:
        await mark_paid(s, provider.name, res.provider_payment_id, vpn=ctx.vpn, notifier=notifier)
    return {"ok": True}
