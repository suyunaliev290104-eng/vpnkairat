"""Process-wide singletons wired at startup (bot, VPN provider)."""
from dataclasses import dataclass
from typing import Any


@dataclass
class _Ctx:
    bot: Any = None
    vpn: Any = None


ctx = _Ctx()


async def notifier(tg_id: int, text: str) -> None:
    await ctx.bot.send_message(tg_id, text, parse_mode="HTML")
