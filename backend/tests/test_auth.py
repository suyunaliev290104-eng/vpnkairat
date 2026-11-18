import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from app.api.auth import InvalidInitData, validate_init_data

TOKEN = "123:ABC"


def sign(params: dict, token: str = TOKEN) -> str:
    dcs = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    params = dict(params, hash=hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest())
    return urlencode(params)


def make(auth_date=None, user_id=42):
    return {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAA",
        "user": json.dumps({"id": user_id, "username": "bob"}),
    }


def test_valid_init_data():
    data = validate_init_data(sign(make()), TOKEN)
    assert data["user"]["id"] == 42


def test_tampered_rejected():
    raw = sign(make()).replace("bob", "eve")
    with pytest.raises(InvalidInitData):
        validate_init_data(raw, TOKEN)


def test_wrong_token_rejected():
    with pytest.raises(InvalidInitData):
        validate_init_data(sign(make(), "999:ZZZ"), TOKEN)


def test_old_rejected():
    with pytest.raises(InvalidInitData):
        validate_init_data(sign(make(auth_date=int(time.time()) - 90000)), TOKEN)


def test_missing_hash_rejected():
    with pytest.raises(InvalidInitData):
        validate_init_data(urlencode(make()), TOKEN)
