import hashlib
import hmac
import json

import httpx
import pytest
import respx
from starlette.requests import Request

from app.config import get_settings
from app.payments import registry
from app.payments.base import WebhookRejected
from app.payments.service import create_payment

TOKEN = "12345:AAtoken"


@pytest.fixture(autouse=True)
def cfg(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "cryptobot_token", TOKEN)
    monkeypatch.setattr(s, "cryptobot_testnet", False)
    registry.load_builtin()


def make_request(body: bytes, headers: dict) -> Request:
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    scope = {"type": "http", "method": "POST", "path": "/", "headers":
             [(k.lower().encode(), v.encode()) for k, v in headers.items()]}
    return Request(scope, receive)


def signed(body: bytes, token=TOKEN) -> str:
    return hmac.new(hashlib.sha256(token.encode()).digest(), body, hashlib.sha256).hexdigest()


@respx.mock
async def test_create_invoice(session, user_factory):
    route = respx.post("https://pay.crypt.bot/api/createInvoice").mock(return_value=httpx.Response(
        200, json={"ok": True, "result": {"invoice_id": 777, "bot_invoice_url": "https://t.me/CryptoBot?start=x",
                                          "mini_app_invoice_url": "https://t.me/CryptoBot/app?startapp=x"}}))
    u = await user_factory()
    p, inv = await create_payment(session, u, "m6", "cryptobot")
    req = route.calls.last.request
    assert req.headers["Crypto-Pay-API-Token"] == TOKEN
    body = json.loads(req.content)
    assert body["asset"] == "USDT" and body["amount"] == "9" and body["payload"] == str(p.id)
    assert p.provider_payment_id == "777" and p.currency == "USDT"
    assert inv.payment_url == "https://t.me/CryptoBot/app?startapp=x"


async def test_webhook_valid_signature_paid():
    body = json.dumps({"update_type": "invoice_paid", "payload": {"invoice_id": 777, "status": "paid"}}).encode()
    res = await registry.get("cryptobot").parse_webhook(make_request(body, {"crypto-pay-api-signature": signed(body)}))
    assert res.provider_payment_id == "777" and res.paid is True


async def test_webhook_bad_signature_rejected():
    body = b'{"update_type":"invoice_paid","payload":{"invoice_id":1}}'
    with pytest.raises(WebhookRejected):
        await registry.get("cryptobot").parse_webhook(
            make_request(body, {"crypto-pay-api-signature": signed(body, "other")}))


async def test_webhook_missing_signature_rejected():
    with pytest.raises(WebhookRejected):
        await registry.get("cryptobot").parse_webhook(make_request(b"{}", {}))
