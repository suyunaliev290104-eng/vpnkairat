"""Split tunneling for the Happ client: Russian sites/IPs go direct, everything else via VPN.

Sent as the `routing` header of the subscription response. `onadd` means Happ applies the
profile when the subscription is added and doesn't override the user's later changes.
Geo files: runetfreedom/russia-v2ray-rules-dat (v2fly categories + Russia-specific lists,
incl. `ru-available-only-inside` — sites that refuse foreign IPs: banks, gov, marketplaces).
"""
import base64
import json

HAPP_PREFIX = "happ://routing/onadd/"
GEO = "https://github.com/runetfreedom/russia-v2ray-rules-dat/releases/latest/download"


def build_happ_routing(name: str) -> str:
    profile = {
        "Name": name,
        "GlobalProxy": "true",
        "RemoteDNSType": "DoH",
        "RemoteDNSDomain": "https://cloudflare-dns.com/dns-query",
        "RemoteDNSIP": "1.1.1.1",
        "DomesticDNSType": "DoU",
        "DomesticDNSDomain": "",
        "DomesticDNSIP": "77.88.8.8",
        "Geoipurl": f"{GEO}/geoip.dat",
        "Geositeurl": f"{GEO}/geosite.dat",
        "LastUpdated": "",
        "DnsHosts": {},
        "DirectSites": ["geosite:category-ru", "geosite:ru-available-only-inside", "geosite:private"],
        "DirectIp": ["geoip:ru", "geoip:private"],
        "ProxySites": [],
        "ProxyIp": [],
        "BlockSites": [],
        "BlockIp": [],
        "DomainStrategy": "IPIfNonMatch",
        "FakeDNS": "false",
    }
    raw = json.dumps(profile, ensure_ascii=False, separators=(",", ":")).encode()
    return HAPP_PREFIX + base64.b64encode(raw).decode()
