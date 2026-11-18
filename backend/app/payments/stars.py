from aiogram.types import LabeledPrice
from fastapi import Request

from app.config import Settings
from app.context import ctx
from app.models import Payment, User
from app.payments.base import InvoiceResult, PaymentProvider, WebhookResult
from app.payments.registry import register
from app.plans import Plan


def payload_for(payment: Payment) -> str:
    return f"pay:{payment.id}"


def parse_payload(payload: str) -> int | None:
    prefix, _, pid = payload.partition(":")
    if prefix != "pay" or not pid.isdigit():
        return None
    return int(pid)


@register
class StarsProvider(PaymentProvider):
    name = "stars"
    title = "Telegram Stars"
    currency = "XTR"
    kind = "invoice"

    def price(self, plan: Plan) -> int:
        return plan.xtr

    def enabled(self, settings: Settings) -> bool:
        return bool(settings.bot_token)

    async def create_invoice(self, payment: Payment, plan: Plan, user: User) -> InvoiceResult:
        url = await ctx.bot.create_invoice_link(
            title=f"VPN на {plan.months} мес.",
            description=f"Подписка на {plan.days} дней, без лимита трафика",
            payload=payload_for(payment),
            currency="XTR",
            prices=[LabeledPrice(label=f"{plan.months} мес.", amount=plan.xtr)],
        )
        return InvoiceResult(payment_url=url)

    async def parse_webhook(self, request: Request) -> WebhookResult:
        raise NotImplementedError("Stars payments arrive via the bot, not a webhook")
