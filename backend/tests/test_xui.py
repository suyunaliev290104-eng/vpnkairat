import json

import httpx
import pytest
import respx

from app.models import Server
from app.vpn.base import ClientSpec
from app.vpn.xui import XuiProvider

B = "https://p.example/base"
SRV = Server(name="NL", panel_url=B, username="a", password="b",
             inbound_id=7, host="h", port=443, reality_pbk="k", reality_sni="s", reality_sid="")
SPEC = ClientSpec(uuid="11111111-1111-1111-1111-111111111111", email="tg42",
                  expiry_ms=1_700_000_000_000, enabled=True, limit_ip=3, sub_id="tok",
                  total_bytes=5 * 1024 ** 3)


def mock_auth():
    """3x-ui 3.x: CSRF token before and after login, sent as X-CSRF-Token on every POST."""
    tokens = iter(["csrf-pre", "csrf-post"])
    respx.get(f"{B}/csrf-token").mock(side_effect=lambda req: httpx.Response(
        200, json={"success": True, "obj": next(tokens)}))
    return respx.post(f"{B}/login").mock(return_value=httpx.Response(200, json={"success": True}))


@respx.mock
async def test_login_sends_csrf_and_api_calls_use_fresh_token():
    login = mock_auth()
    respx.get(f"{B}/panel/api/clients/get/tg42").mock(
        return_value=httpx.Response(200, json={"success": False, "obj": None}))
    add = respx.post(f"{B}/panel/api/clients/add").mock(return_value=httpx.Response(200, json={"success": True}))
    await XuiProvider().upsert_client(SRV, SPEC)
    assert login.calls.last.request.headers["X-CSRF-Token"] == "csrf-pre"
    assert add.calls.last.request.headers["X-CSRF-Token"] == "csrf-post"


@respx.mock
async def test_add_client_payload():
    mock_auth()
    respx.get(f"{B}/panel/api/clients/get/tg42").mock(
        return_value=httpx.Response(200, json={"success": False, "obj": None}))
    add = respx.post(f"{B}/panel/api/clients/add").mock(return_value=httpx.Response(200, json={"success": True}))
    await XuiProvider().upsert_client(SRV, SPEC)
    body = json.loads(add.calls.last.request.content)
    assert body["inboundIds"] == [7]
    client = body["client"]
    assert client["id"] == SPEC.uuid and client["email"] == "tg42"
    assert client["flow"] == "xtls-rprx-vision" and client["limitIp"] == 3
    assert client["expiryTime"] == 1_700_000_000_000 and client["enable"] is True
    assert client["subId"] == "tok" and client["totalGB"] == 5 * 1024 ** 3


@respx.mock
async def test_existing_client_is_updated():
    mock_auth()
    respx.get(f"{B}/panel/api/clients/get/tg42").mock(
        return_value=httpx.Response(200, json={"success": True, "obj": {"client": {"email": "tg42"}}}))
    upd = respx.post(f"{B}/panel/api/clients/update/tg42").mock(
        return_value=httpx.Response(200, json={"success": True}))
    await XuiProvider().upsert_client(SRV, SPEC)
    body = json.loads(upd.calls.last.request.content)
    assert body["email"] == "tg42" and body["enable"] is True and body["totalGB"] == 5 * 1024 ** 3


@respx.mock
async def test_add_failure_raises():
    mock_auth()
    respx.get(f"{B}/panel/api/clients/get/tg42").mock(
        return_value=httpx.Response(200, json={"success": False, "obj": None}))
    respx.post(f"{B}/panel/api/clients/add").mock(
        return_value=httpx.Response(200, json={"success": False, "msg": "boom"}))
    with pytest.raises(Exception, match="boom"):
        await XuiProvider().upsert_client(SRV, SPEC)


@respx.mock
async def test_login_failure_raises():
    respx.get(f"{B}/csrf-token").mock(return_value=httpx.Response(200, json={"success": True, "obj": "t"}))
    respx.post(f"{B}/login").mock(return_value=httpx.Response(200, json={"success": False}))
    with pytest.raises(Exception):
        await XuiProvider().upsert_client(SRV, SPEC)


@respx.mock
async def test_get_traffic():
    mock_auth()
    respx.get(f"{B}/panel/api/clients/traffic/tg42").mock(
        return_value=httpx.Response(200, json={"success": True, "obj": {"up": 5, "down": 10}}))
    assert await XuiProvider().get_traffic(SRV, "tg42") == (5, 10)


@respx.mock
async def test_reset_traffic_resets_all_clients():
    mock_auth()
    reset = respx.post(f"{B}/panel/api/clients/resetAllTraffics").mock(
        return_value=httpx.Response(200, json={"success": True}))
    await XuiProvider().reset_traffic(SRV)
    assert reset.called


# I-4: panel over HTTPS with a pinned self-signed certificate
def test_pinned_cert_builds_ssl_context():
    import ssl
    import subprocess
    import tempfile
    d = tempfile.mkdtemp()
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=x",
                    "-keyout", f"{d}/k", "-out", f"{d}/c"], check=True, capture_output=True)
    pem = open(f"{d}/c").read()
    srv = Server(name="NL", panel_url="https://1.2.3.4:2053/p", username="a", password="b", inbound_id=1,
                 host="h", port=443, reality_pbk="k", reality_sni="s", panel_cert=pem)
    ctx = XuiProvider._verify(srv)
    assert isinstance(ctx, ssl.SSLContext) and ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is False
    assert XuiProvider._verify(SRV) is True
