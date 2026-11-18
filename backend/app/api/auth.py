import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import User


class InvalidInitData(Exception):
    pass


def validate_init_data(init_data: str, bot_token: str, max_age: int = 86400) -> dict:
    params = dict(parse_qsl(init_data, keep_blank_values=True))
    received = params.pop("hash", None)
    if not received:
        raise InvalidInitData("no hash")
    dcs = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise InvalidInitData("bad signature")
    try:
        auth_date = int(params.get("auth_date", "0"))
    except ValueError:
        raise InvalidInitData("bad auth_date")
    if time.time() - auth_date > max_age:
        raise InvalidInitData("expired")
    if "user" in params:
        params["user"] = json.loads(params["user"])
    return params


async def get_session():
    from app.db import get_sessionmaker

    async with get_sessionmaker()() as s:
        yield s


async def current_user(
    authorization: str | None = Header(default=None),
    s: AsyncSession = Depends(get_session),
) -> User:
    from app.services.subscription import get_or_create_user

    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(401, "unauthorized")
    try:
        data = validate_init_data(authorization[4:], get_settings().bot_token)
    except InvalidInitData:
        raise HTTPException(401, "unauthorized")
    tg_user = data.get("user") or {}
    if "id" not in tg_user:
        raise HTTPException(401, "unauthorized")
    return await get_or_create_user(s, int(tg_user["id"]), tg_user.get("username"))
