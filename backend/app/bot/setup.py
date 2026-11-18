from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from app.bot import admin, payments, start
from app.config import get_settings


def create_bot() -> Bot:
    return Bot(get_settings().bot_token, default=DefaultBotProperties(parse_mode="HTML"))


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_routers(admin.router, payments.router, start.router)
    return dp
