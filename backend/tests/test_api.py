import base64
import json
from datetime import timedelta

import httpx
import pytest

from app.config import get_settings
from app.context import ctx
from app.db import dispose_db, get_sessionmaker, init_db, setup_db
from app.main import create_app
from app.models import Payment, utcnow
from app.services.subscription import get_or_create_subscription, get_user_by_tg
from tests.test_auth import make, sign

TOKEN = "123:ABC"


class FakeVpn:
    def __init__(self):
        self.specs = []

    async def upsert_client(self, server, spec):
        self.specs.append(spec)

    async def get_traffic(self, server, email):
        return (100, 200) if server.kind != "bypass" else (1000, 2000)


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text))

    async def create_invoice_link(self, **kw):
        return "https://t.me/$inv"


@pytest.fixture
async def client(tmp_path, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "bot_token", TOKEN)
    monkeypatch.setattr(s, "bot_username", "my_vpn_bot")
    monkeypatch.setattr(s, "public_url", "https://vpn.example")
    monkeypatch.setattr(s, "lavatop_api_key", "KEY")
    monkeypatch.setattr(s, "lavatop_webhook_secret", "WH")
    monkeypatch.setattr(s, "lavatop_offers", {"m1": "o1", "m3": "o3", "m6": "o6", "m12": "o12"})
    monkeypatch.setattr(s, "cryptobot_token", "")
    monkeypatch.setattr(s, "stars_shop_url", "https://t.me/QuickStars_bot?start=628539345")
    setup_db(f"sqlite+aiosqlite:///{tmp_path}/t.db")
    await init_db()
    monkeypatch.setattr(ctx, "vpn", FakeVpn())
    monkeypatch.setattr(ctx, "bot", FakeBot())
    app = create_app(background=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c
    await dispose_db()


def auth(user_id=42):
    return {"Authorization": "tma " + sign(make(user_id=user_id), TOKEN)}


async def add_server(kind="direct", name="Нидерланды"):
    from app.models import Server
    async with get_sessionmaker()() as s:
        s.add(Server(name=name, flag="🇳🇱", country="NL", panel_url="https://p", username="a",
                     password="b", inbound_id=1, host="nl.example", port=443, reality_pbk="K",
                     reality_sni="sni.com", reality_sid="", kind=kind))
        await s.commit()


async def test_requires_auth(client):
    assert (await client.get("/api/me")).status_code == 401
    assert (await client.get("/api/me", headers={"Authorization": "tma bad"})).status_code == 401


async def test_me_new_user(client):
    await add_server()
    r = await client.get("/api/me", headers=auth())
    assert r.status_code == 200
    d = r.json()
    assert d["user"]["tg_id"] == 42
    assert d["subscription"]["active"] is False and d["subscription"]["trial_available"] is True
    assert d["subscription"]["sub_url"].startswith("https://vpn.example/sub/")
    assert d["servers"] == [{"name": "Нидерланды", "flag": "🇳🇱", "country": "NL", "kind": "direct"}]
    assert d["bypass"] == {"available": False, "used_today": 0, "limit": 5 * 1024 ** 3}
    assert d["support_username"] == ""


async def test_plans(client):
    d = (await client.get("/api/plans", headers=auth())).json()
    assert [p["id"] for p in d["plans"]] == ["m1", "m3", "m6", "m12"]
    m12 = d["plans"][3]
    assert m12["badge"] == "Выгоднее всего" and m12["discount"] == 25 and m12["per_month_rub"] == 149
    assert m12["prices"]["lavatop"] == {"amount": 1790, "currency": "RUB"}
    assert m12["prices"]["stars"] == {"amount": 1700, "currency": "XTR"}
    names = [p["name"] for p in d["providers"]]
    assert "stars" in names and "lavatop" in names and "cryptobot" not in names
    lava = next(p for p in d["providers"] if p["name"] == "lavatop")
    assert lava["needs_email"] is True and lava["kind"] == "link"
    assert d["stars_shop_url"] == "https://t.me/QuickStars_bot?start=628539345"


async def test_trial_once(client):
    r = await client.post("/api/trial", headers=auth())
    assert r.status_code == 200 and r.json()["subscription"]["active"] is True
    assert r.json()["subscription"]["days_left"] == 3
    r2 = await client.post("/api/trial", headers=auth())
    assert r2.status_code == 409 and r2.json()["detail"] == "trial_used"


async def test_pay_lavatop_requires_email(client):
    r = await client.post("/api/pay", headers=auth(), json={"plan_id": "m1", "provider": "lavatop"})
    assert r.status_code == 400 and r.json()["detail"] == "email_required"


async def test_pay_unknown_provider_or_plan(client):
    r = await client.post("/api/pay", headers=auth(), json={"plan_id": "m1", "provider": "nope"})
    assert r.status_code == 400
    r = await client.post("/api/pay", headers=auth(), json={"plan_id": "x", "provider": "stars"})
    assert r.status_code == 400


async def test_pay_disabled_provider_rejected(client):
    r = await client.post("/api/pay", headers=auth(), json={"plan_id": "m1", "provider": "cryptobot"})
    assert r.status_code == 400


async def test_pay_stars(client):
    r = await client.post("/api/pay", headers=auth(), json={"plan_id": "m1", "provider": "stars"})
    assert r.status_code == 200
    assert r.json()["payment_url"] == "https://t.me/$inv" and r.json()["kind"] == "invoice"


async def test_email_validation(client):
    assert (await client.post("/api/email", headers=auth(), json={"email": "bad"})).status_code == 422
    r = await client.post("/api/email", headers=auth(), json={"email": "a@b.ru"})
    assert r.status_code == 200 and r.json()["user"]["email"] == "a@b.ru"


async def _pending_lava_payment(cid="c-1"):
    async with get_sessionmaker()() as s:
        u = await get_user_by_tg(s, 42)
        s.add(Payment(user_id=u.id, provider="lavatop", provider_payment_id=cid, plan_id="m1",
                      amount=159, currency="RUB"))
        await s.commit()


async def test_webhook_repeat_extends_once(client):
    await add_server()
    await client.get("/api/me", headers=auth())
    await _pending_lava_payment()
    body = json.dumps({"contractId": "c-1", "status": "completed"})
    for _ in range(2):
        r = await client.post("/webhooks/lavatop", content=body, headers={"X-Api-Key": "WH"})
        assert r.status_code == 200
    d = (await client.get("/api/me", headers=auth())).json()
    assert d["subscription"]["days_left"] == 30
    assert len(ctx.bot.sent) == 1


async def test_webhook_bad_key_403(client):
    r = await client.post("/webhooks/lavatop", content="{}", headers={"X-Api-Key": "x"})
    assert r.status_code == 403


async def test_webhook_unknown_provider_404(client):
    assert (await client.post("/webhooks/nope", content="{}")).status_code == 404


async def test_sub_endpoint(client):
    await add_server()
    await client.post("/api/trial", headers=auth())
    url = (await client.get("/api/me", headers=auth())).json()["subscription"]["sub_url"]
    token = url.rsplit("/", 1)[1]
    r = await client.get(f"/sub/{token}")
    assert r.status_code == 200
    assert "nl.example:443" in base64.b64decode(r.text).decode()
    info = r.headers["subscription-userinfo"]
    assert "expire=" in info and "total=0" in info
    assert (await client.get("/sub/unknown")).status_code == 404


async def test_sub_endpoint_expired_is_empty(client):
    await add_server()
    await client.post("/api/trial", headers=auth())
    async with get_sessionmaker()() as s:
        u = await get_user_by_tg(s, 42)
        sub = await get_or_create_subscription(s, u)
        sub.expires_at = utcnow() - timedelta(days=1)
        token = sub.sub_token
        await s.commit()
    r = await client.get(f"/sub/{token}")
    assert r.status_code == 200 and base64.b64decode(r.text) == b""


async def test_referrals(client):
    d = (await client.get("/api/referrals", headers=auth())).json()
    assert d["link"] == "https://t.me/my_vpn_bot?start=ref_42"
    assert d["invited"] == 0 and d["bonus_days"] == 7


async def test_connect_redirect_page(client):
    await client.post("/api/trial", headers=auth())
    url = (await client.get("/api/me", headers=auth())).json()["subscription"]["sub_url"]
    token = url.rsplit("/", 1)[1]
    r = await client.get(f"/connect/{token}/happ")
    assert r.status_code == 200 and "happ://add/https://vpn.example/sub/" in r.text
    assert (await client.get(f"/connect/{token}/evil")).status_code == 404
    assert (await client.get("/connect/nope/happ")).status_code == 404


async def test_me_bypass_usage(client):
    await add_server()
    await add_server(kind="bypass", name="Москва")
    await client.post("/api/trial", headers=auth())
    d = (await client.get("/api/me", headers=auth())).json()
    assert d["bypass"] == {"available": True, "used_today": 3000, "limit": 5 * 1024 ** 3}
    assert d["subscription"]["traffic_used"] == 3300
    assert [s["kind"] for s in d["servers"]] == ["direct", "bypass"]
