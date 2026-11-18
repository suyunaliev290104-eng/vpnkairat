"""lava.top payments (cards RU/foreign, SBP).

Setup in the lava.top cabinet:
  1. Create a product with 4 offers (one per plan) priced as in app/plans.py; put their ids
     into LAVATOP_OFFERS, e.g. {"m1":"<id>","m3":"<id>","m6":"<id>","m12":"<id>"}.
  2. API key → LAVATOP_API_KEY.
  3. Webhook URL https://<domain>/webhooks/lavatop, auth type "API key" with your own secret
     → LAVATOP_WEBHOOK_SECRET (lava.top sends it in the X-Api-Key header).

NOTE: field names follow lava.top public API v2 as known at implementation time;
the docs host (gate.lava.top) was unreachable from the build environment — verify
against https://gate.lava.top/docs before going live.
"""
import hmac
import json

import httpx
from fastapi import Request

from app.config import Settings, get_settings
from app.models import Payment, User
from app.payments.base import InvoiceResult, PaymentProvider, WebhookRejected, WebhookResult
from app.payments.registry import register
from app.plans import PLANS, Plan

API = "https://gate.lava.top"
PAID_STATUSES = {"completed", "subscription-active"}


@register
class LavaTopProvider(PaymentProvider):
    name = "lavatop"
    title = "Карта / СБП"
    currency = "RUB"
    needs_email = True

    def price(self, plan: Plan) -> int:
        return plan.rub

    def enabled(self, settings: Settings) -> bool:
        offers = settings.lavatop_offers
        return bool(settings.lavatop_api_key) and all(offers.get(pid) for pid in PLANS)

    async def create_invoice(self, payment: Payment, plan: Plan, user: User) -> InvoiceResult:
        if not user.email:
            raise ValueError("email_required")
        s = get_settings()
        offer = s.lavatop_offers.get(plan.id)
        if not offer:
            raise ValueError("lavatop_offer_missing")
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                f"{API}/api/v2/invoice",
                headers={"X-Api-Key": s.lavatop_api_key},
                json={"email": user.email, "offerId": offer, "currency": "RUB", "buyerLanguage": "RU"},
            )
        if r.status_code >= 400:
            raise RuntimeError(f"lavatop {r.status_code}: {r.text[:200]}")
        data = r.json()
        return InvoiceResult(payment_url=data["paymentUrl"], provider_payment_id=str(data["id"]))

    async def parse_webhook(self, request: Request) -> WebhookResult:
        secret = get_settings().lavatop_webhook_secret
        got = request.headers.get("x-api-key", "")
        if not secret or not hmac.compare_digest(got, secret):
            raise WebhookRejected("bad api key")
        data = json.loads(await request.body())
        return WebhookResult(
            provider_payment_id=str(data.get("contractId", "")),
            paid=data.get("status") in PAID_STATUSES,
        )
