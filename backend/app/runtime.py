"""Starts bot polling, scheduler and VPN provider alongside the web app."""
import asyncio
from datetime import datetime
import logging

from aiogram.types import MenuButtonWebApp, WebAppInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.bot.setup import create_bot, create_dispatcher
from app.config import get_settings
from app.context import ctx
from app.db import init_db, setup_db
from app.scheduler import run_all, run_reset_bypass
from app.vpn.xui import XuiProvider

log = logging.getLogger(__name__)


async def start_runtime() -> list:
    st = get_settings()
    setup_db(st.database_url)
    await init_db()
    ctx.vpn = XuiProvider()
    ctx.bot = create_bot()
    dp = create_dispatcher()
    try:
        await ctx.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="VPN", web_app=WebAppInfo(url=st.webapp_url)))
    except Exception:
        log.warning("could not set menu button", exc_info=True)
    polling = asyncio.create_task(dp.start_polling(ctx.bot, handle_signals=False))
    sched = AsyncIOScheduler()
    sched.add_job(run_all, "interval", minutes=10, next_run_time=datetime.now())
    sched.add_job(run_reset_bypass, "cron", hour=0, minute=0, timezone="Europe/Moscow")
    sched.start()
    return [polling, sched, dp]


async def stop_runtime(items: list) -> None:
    polling, sched, dp = items
    sched.shutdown(wait=False)
    await dp.stop_polling()
    polling.cancel()
    await ctx.bot.session.close()
