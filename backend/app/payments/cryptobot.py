import hashlib
import hmac
import json

import httpx
from fastapi import Request

from app.config import Settings, get_settings
from app.models import Payment, User
from app.payments.base import InvoiceResult, PaymentProvider, WebhookRejected, WebhookResult
from app.payments.registry import register
from app.plans import Plan


@register
class CryptoBotProvider(PaymentProvider):
    """Crypto Pay API (@CryptoBot). Webhook URL: https://<domain>/webhooks/cryptobot"""

    name = "cryptobot"
    title = "Криптовалюта (CryptoBot)"
    currency = "USDT"

    def price(self, plan: Plan) -> int:
        return plan.usdt

    def enabled(self, settings: Settings) -> bool:
        return bool(settings.cryptobot_token)

    @staticmethod
    def _base() -> str:
        s = get_settings()
        return "https://testnet-pay.crypt.bot/api" if s.cryptobot_testnet else "https://pay.crypt.bot/api"

    async def create_invoice(self, payment: Payment, plan: Plan, user: User) -> InvoiceResult:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                f"{self._base()}/createInvoice",
                headers={"Crypto-Pay-API-Token": get_settings().cryptobot_token},
                json={
                    "asset": "USDT",
                    "amount": str(plan.usdt),
                    "description": f"VPN на {plan.months} мес.",
                    "payload": str(payment.id),
                    "expires_in": 3600,
                },
            )
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"cryptobot: {data.get('error')}")
        res = data["result"]
        url = res.get("mini_app_invoice_url") or res.get("bot_invoice_url") or res.get("pay_url")
        return InvoiceResult(payment_url=url, provider_payment_id=str(res["invoice_id"]))

    async def parse_webhook(self, request: Request) -> WebhookResult:
        body = await request.body()
        sig = request.headers.get("crypto-pay-api-signature", "")
        secret = hashlib.sha256(get_settings().cryptobot_token.encode()).digest()
        expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
        if not sig or not hmac.compare_digest(sig, expected):
            raise WebhookRejected("bad signature")
        data = json.loads(body)
        inv = data.get("payload") or {}
        return WebhookResult(
            provider_payment_id=str(inv.get("invoice_id", "")),
            paid=data.get("update_type") == "invoice_paid",
        )
