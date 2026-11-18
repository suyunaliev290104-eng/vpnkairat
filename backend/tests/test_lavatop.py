import json

import httpx
import pytest
import respx
from starlette.requests import Request

from app.config import get_settings
from app.payments import registry
from app.payments.base import WebhookRejected
from app.payments.service import create_payment

OFFERS = {"m1": "off-1", "m3": "off-3", "m6": "off-6", "m12": "off-12"}


@pytest.fixture(autouse=True)
def cfg(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "lavatop_api_key", "KEY")
    monkeypatch.setattr(s, "lavatop_webhook_secret", "WHSECRET")
    monkeypatch.setattr(s, "lavatop_offers", OFFERS)
    registry.load_builtin()


def make_request(body: bytes, headers: dict) -> Request:
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    scope = {"type": "http", "method": "POST", "path": "/", "headers":
             [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
    return Request(scope, receive)


@respx.mock
async def test_create_invoice_uses_offer_and_email(session, user_factory):
    route = respx.post("https://gate.lava.top/api/v2/invoice").mock(return_value=httpx.Response(
        200, json={"id": "contract-1", "status": "in-progress", "paymentUrl": "https://pay.lava.top/x"}))
    u = await user_factory(email="a@b.ru")
    p, inv = await create_payment(session, u, "m3", "lavatop")
    req = route.calls.last.request
    assert req.headers["X-Api-Key"] == "KEY"
    body = json.loads(req.content)
    assert body == {"email": "a@b.ru", "offerId": "off-3", "currency": "RUB", "buyerLanguage": "RU"}
    assert p.provider_payment_id == "contract-1" and p.amount == 399 and p.currency == "RUB"
    assert inv.payment_url == "https://pay.lava.top/x"


async def test_no_email_raises(session, user_factory):
    u = await user_factory()
    with pytest.raises(ValueError, match="email_required"):
        await create_payment(session, u, "m1", "lavatop")


def test_disabled_without_offers(monkeypatch):
    monkeypatch.setattr(get_settings(), "lavatop_offers", {})
    assert registry.get("lavatop").enabled(get_settings()) is False


async def test_webhook_bad_key_rejected():
    body = json.dumps({"contractId": "c1", "status": "completed"}).encode()
    with pytest.raises(WebhookRejected):
        await registry.get("lavatop").parse_webhook(make_request(body, {"X-Api-Key": "wrong"}))


async def test_webhook_completed_paid():
    body = json.dumps({"eventType": "payment.success", "contractId": "c1", "status": "completed"}).encode()
    res = await registry.get("lavatop").parse_webhook(make_request(body, {"X-Api-Key": "WHSECRET"}))
    assert res.provider_payment_id == "c1" and res.paid is True


async def test_webhook_failed_not_paid():
    body = json.dumps({"eventType": "payment.failed", "contractId": "c1", "status": "failed"}).encode()
    res = await registry.get("lavatop").parse_webhook(make_request(body, {"X-Api-Key": "WHSECRET"}))
    assert res.paid is False
