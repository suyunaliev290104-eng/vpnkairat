import base64

from app.models import Server
from app.vpn.links import build_subscription, build_vless

S1 = Server(name="Нидерланды", flag="🇳🇱", host="nl.example", port=443, reality_pbk="PBK",
            reality_sni="www.microsoft.com", reality_sid="ab12")


def test_build_vless_contains_reality_params():
    link = build_vless(S1, "uuid-1")
    assert link.startswith("vless://uuid-1@nl.example:443?")
    for part in ("type=tcp", "security=reality", "pbk=PBK", "fp=chrome", "sni=www.microsoft.com",
                 "sid=ab12", "flow=xtls-rprx-vision"):
        assert part in link
    assert "#" in link


def test_build_subscription_base64_all_servers():
    s2 = Server(name="DE", flag="🇩🇪", host="de.example", port=8443, reality_pbk="X",
                reality_sni="a.com", reality_sid="")
    decoded = base64.b64decode(build_subscription([S1, s2], "uuid-1")).decode()
    lines = decoded.split("\n")
    assert len(lines) == 2 and "de.example:8443" in lines[1]


def test_bypass_label():
    from urllib.parse import unquote
    s = Server(name="Москва", flag="🇷🇺", host="ru.example", port=443, reality_pbk="K",
               reality_sni="ya.ru", reality_sid="", kind="bypass")
    assert unquote(build_vless(s, "u").split("#", 1)[1]) == "🛡 Обход белых списков · Москва"
