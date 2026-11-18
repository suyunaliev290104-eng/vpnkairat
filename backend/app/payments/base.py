from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal

from fastapi import Request

from app.config import Settings
from app.models import Payment, User
from app.plans import Plan


@dataclass
class InvoiceResult:
    payment_url: str | None
    provider_payment_id: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class WebhookResult:
    provider_payment_id: str
    paid: bool


class WebhookRejected(Exception):
    pass


class PaymentProvider(ABC):
    """One payment method. To add a new one: subclass, implement, register in registry.py."""

    name: str  # used in URLs (/webhooks/<name>) and DB
    title: str  # shown to users
    currency: str
    kind: str = "link"  # "link" → openLink, "invoice" → Telegram openInvoice

    @abstractmethod
    def price(self, plan: Plan) -> int | Decimal: ...

    @abstractmethod
    def enabled(self, settings: Settings) -> bool: ...

    @abstractmethod
    async def create_invoice(self, payment: Payment, plan: Plan, user: User) -> InvoiceResult: ...

    @abstractmethod
    async def parse_webhook(self, request: Request) -> WebhookResult: ...
