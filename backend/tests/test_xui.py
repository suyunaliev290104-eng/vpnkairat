import json

import httpx
import pytest
import respx

from app.models import Server
from app.vpn.base import ClientSpec
from app.vpn.xui import XuiProvider

SRV = Server(name="NL", panel_url="https://p.example/base", username="a", password="b",
             inbound_id=7, host="h", port=443, reality_pbk="k", reality_sni="s", reality_sid="")
SPEC = ClientSpec(uuid="11111111-1111-1111-1111-111111111111", email="tg42",
                  expiry_ms=1_700_000_000_000, enabled=True, limit_ip=3, sub_id="tok")


@respx.mock
async def test_add_client_payload():
    respx.post("https://p.example/base/login").mock(return_value=httpx.Response(200, json={"success": True}))
    add = respx.post("https://p.example/base/panel/api/inbounds/addClient").mock(
        return_value=httpx.Response(200, json={"success": True}))
    await XuiProvider().upsert_client(SRV, SPEC)
    body = json.loads(add.calls.last.request.content)
    assert body["id"] == 7
    client = json.loads(body["settings"])["clients"][0]
    assert client["id"] == SPEC.uuid and client["email"] == "tg42"
    assert client["flow"] == "xtls-rprx-vision" and client["limitIp"] == 3
    assert client["expiryTime"] == 1_700_000_000_000 and client["enable"] is True
    assert client["subId"] == "tok" and client["totalGB"] == 0


@respx.mock
async def test_duplicate_falls_back_to_update():
    respx.post("https://p.example/base/login").mock(return_value=httpx.Response(200, json={"success": True}))
    respx.post("https://p.example/base/panel/api/inbounds/addClient").mock(
        return_value=httpx.Response(200, json={"success": False, "msg": "Duplicate email: tg42"}))
    upd = respx.post(f"https://p.example/base/panel/api/inbounds/updateClient/{SPEC.uuid}").mock(
        return_value=httpx.Response(200, json={"success": True}))
    await XuiProvider().upsert_client(SRV, SPEC)
    assert upd.called


@respx.mock
async def test_login_failure_raises():
    respx.post("https://p.example/base/login").mock(return_value=httpx.Response(200, json={"success": False}))
    with pytest.raises(Exception):
        await XuiProvider().upsert_client(SRV, SPEC)


@respx.mock
async def test_get_traffic():
    respx.post("https://p.example/base/login").mock(return_value=httpx.Response(200, json={"success": True}))
    respx.get("https://p.example/base/panel/api/inbounds/getClientTraffics/tg42").mock(
        return_value=httpx.Response(200, json={"success": True, "obj": {"up": 5, "down": 10}}))
    assert await XuiProvider().get_traffic(SRV, "tg42") == (5, 10)
