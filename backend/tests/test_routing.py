import base64
import json

from app.vpn.routing import HAPP_PREFIX, build_happ_routing


def decode(link: str) -> dict:
    assert link.startswith(HAPP_PREFIX)
    return json.loads(base64.b64decode(link[len(HAPP_PREFIX):]))


def test_happ_routing_sends_russia_direct():
    r = decode(build_happ_routing("Kairat"))
    assert r["Name"] == "Kairat" and r["GlobalProxy"] == "true"
    assert "geoip:ru" in r["DirectIp"] and "geoip:private" in r["DirectIp"]
    assert "geosite:category-ru" in r["DirectSites"]
    assert "geosite:ru-available-only-inside" in r["DirectSites"]
    assert r["Geoipurl"].endswith("geoip.dat") and r["Geositeurl"].endswith("geosite.dat")
    assert r["DomainStrategy"] == "IPIfNonMatch"
