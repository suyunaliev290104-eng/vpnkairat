"""3x-ui panel HTTP API (3.x). panel_url includes the panel's web base path.

3.x specifics: POST requests need an X-CSRF-Token header (GET /csrf-token, refreshed after
login), and clients are managed via /panel/api/clients/* keyed by email.
"""
import ssl
from contextlib import asynccontextmanager
from urllib.parse import quote

import httpx

from app.models import Server
from app.vpn.base import ClientSpec


class XuiError(Exception):
    pass


async def _csrf(c: httpx.AsyncClient) -> str:
    r = await c.get("/csrf-token")
    if r.status_code != 200:
        return ""
    return str(r.json().get("obj") or "")


class XuiProvider:
    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    @staticmethod
    def _verify(server: Server) -> ssl.SSLContext | bool:
        """Pin the panel's self-signed cert (panels are reached by IP, so no hostname check)."""
        if not server.panel_cert:
            return True
        ctx = ssl.create_default_context(cadata=server.panel_cert)
        ctx.check_hostname = False
        return ctx

    @asynccontextmanager
    async def _client(self, server: Server):
        async with httpx.AsyncClient(base_url=server.panel_url.rstrip("/"), timeout=self.timeout,
                                     verify=self._verify(server)) as c:
            r = await c.post("/login", data={"username": server.username, "password": server.password},
                             headers={"X-CSRF-Token": await _csrf(c)})
            if r.status_code != 200 or not r.json().get("success"):
                raise XuiError(f"login failed on {server.name} (HTTP {r.status_code})")
            # the session is rotated on login → fetch a fresh token for subsequent POSTs
            c.headers["X-CSRF-Token"] = await _csrf(c)
            yield c

    @staticmethod
    def _client_body(spec: ClientSpec) -> dict:
        return {
            "id": spec.uuid,
            "email": spec.email,
            "flow": "xtls-rprx-vision",
            "limitIp": spec.limit_ip,
            "expiryTime": spec.expiry_ms,
            "enable": spec.enabled,
            "subId": spec.sub_id,
            "totalGB": spec.total_bytes,  # bytes despite the name
            "tgId": 0,
        }

    @staticmethod
    def _check(r: httpx.Response, server: Server, what: str) -> None:
        ok = r.status_code == 200 and r.json().get("success")
        if not ok:
            msg = r.json().get("msg") if r.headers.get("content-type", "").startswith("application/json") else r.text[:200]
            raise XuiError(f"{server.name}: {what} failed: HTTP {r.status_code} {msg}")

    async def upsert_client(self, server: Server, spec: ClientSpec) -> None:
        body = self._client_body(spec)
        email = quote(spec.email, safe="")
        async with self._client(server) as c:
            existing = await c.get(f"/panel/api/clients/get/{email}")
            if existing.status_code == 200 and existing.json().get("success") and existing.json().get("obj"):
                r = await c.post(f"/panel/api/clients/update/{email}", json=body)
                self._check(r, server, "update client")
            else:
                r = await c.post("/panel/api/clients/add", json={"client": body, "inboundIds": [server.inbound_id]})
                self._check(r, server, "add client")

    async def reset_traffic(self, server: Server) -> None:
        """Zero every client's counters on this panel (bypass servers host only our clients)."""
        async with self._client(server) as c:
            self._check(await c.post("/panel/api/clients/resetAllTraffics"), server, "reset traffic")

    async def get_traffic(self, server: Server, email: str) -> tuple[int, int]:
        async with self._client(server) as c:
            r = await c.get(f"/panel/api/clients/traffic/{quote(email, safe='')}")
            obj = (r.json().get("obj") or {}) if r.status_code == 200 else {}
            return int(obj.get("up", 0)), int(obj.get("down", 0))
