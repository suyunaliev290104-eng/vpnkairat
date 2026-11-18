import base64
from urllib.parse import quote, urlencode

from app.models import Server


def build_vless(server: Server, uuid: str) -> str:
    q = urlencode({
        "type": "tcp",
        "security": "reality",
        "pbk": server.reality_pbk,
        "fp": "chrome",
        "sni": server.reality_sni,
        "sid": server.reality_sid or "",
        "flow": "xtls-rprx-vision",
    })
    title = f"🛡 Обход белых списков · {server.name}" if server.kind == "bypass" else f"{server.flag} {server.name}"
    label = quote(title)
    return f"vless://{uuid}@{server.host}:{server.port}?{q}#{label}"


def build_subscription(servers: list[Server], uuid: str) -> str:
    text = "\n".join(build_vless(s, uuid) for s in servers)
    return base64.b64encode(text.encode()).decode()
