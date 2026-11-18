from app.bot.start import parse_ref
from app.bot.admin import parse_server_json


def test_parse_ref():
    assert parse_ref("ref_123") == 123
    assert parse_ref("") is None
    assert parse_ref(None) is None
    assert parse_ref("ref_abc") is None
    assert parse_ref("promo") is None


def test_parse_server_json():
    srv = parse_server_json('{"name":"DE","flag":"🇩🇪","panel_url":"https://p","username":"a","password":"b",'
                            '"inbound_id":1,"host":"de.ex","reality_pbk":"K","reality_sni":"s.com"}')
    assert srv.name == "DE" and srv.port == 443 and srv.enabled is True


def test_parse_server_json_missing_field():
    import pytest
    with pytest.raises(ValueError):
        parse_server_json('{"name":"DE"}')
