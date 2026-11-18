import json
import ssl
from contextlib import asynccontextmanager

import httpx

from app.models import Server
from app.vpn.base import ClientSpec


class XuiError(Exception):
    pass


class XuiProvider:
    """3x-ui panel HTTP API. panel_url includes the panel's web base path."""

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
            r = await c.post("/login", data={"username": server.username, "password": server.password})
            if r.status_code != 200 or not r.json().get("success"):
                raise XuiError(f"login failed on {server.name}")
            yield c

    @staticmethod
    def _body(server: Server, spec: ClientSpec) -> dict:
        client = {
            "id": spec.uuid,
            "email": spec.email,
            "flow": "xtls-rprx-vision",
            "limitIp": spec.limit_ip,
            "expiryTime": spec.expiry_ms,
            "enable": spec.enabled,
            "subId": spec.sub_id,
            "totalGB": spec.total_bytes,  # 3x-ui stores bytes despite the name
            "tgId": "",
            "reset": 0,
        }
        return {"id": server.inbound_id, "settings": json.dumps({"clients": [client]})}

    async def upsert_client(self, server: Server, spec: ClientSpec) -> None:
        body = self._body(server, spec)
        async with self._client(server) as c:
            r = await c.post("/panel/api/inbounds/addClient", json=body)
            data = r.json()
            if data.get("success"):
                return
            if "duplicate" in str(data.get("msg", "")).lower():
                r = await c.post(f"/panel/api/inbounds/updateClient/{spec.uuid}", json=body)
                if r.json().get("success"):
                    return
            raise XuiError(f"{server.name}: {r.json().get('msg')}")

    async def reset_traffic(self, server: Server) -> None:
        async with self._client(server) as c:
            r = await c.post(f"/panel/api/inbounds/resetAllClientTraffics/{server.inbound_id}")
            if not r.json().get("success"):
                raise XuiError(f"{server.name}: reset failed: {r.json().get('msg')}")

    async def get_traffic(self, server: Server, email: str) -> tuple[int, int]:
        async with self._client(server) as c:
            r = await c.get(f"/panel/api/inbounds/getClientTraffics/{email}")
            obj = r.json().get("obj") or {}
            return int(obj.get("up", 0)), int(obj.get("down", 0))
