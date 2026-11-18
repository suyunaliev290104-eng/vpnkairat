from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from app.config import get_settings
from app.db import get_sessionmaker
from app.services.subscription import get_or_create_user

router = Router()


def parse_ref(arg: str | None) -> int | None:
    if not arg or not arg.startswith("ref_"):
        return None
    tail = arg[4:]
    return int(tail) if tail.isdigit() else None


def open_app_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚀 Открыть VPN", web_app=WebAppInfo(url=get_settings().webapp_url))
    ]])


@router.message(CommandStart())
async def start(m: Message, command: CommandObject) -> None:
    async with get_sessionmaker()() as s:
        await get_or_create_user(s, m.from_user.id, m.from_user.username, parse_ref(command.args))
    st = get_settings()
    await m.answer(
        f"👋 Привет! Это <b>{st.brand_name}</b> — быстрый VPN, который работает там, где другие не могут.\n\n"
        f"• Пробный период {st.trial_days} дня бесплатно\n"
        "• Без лимита трафика, до 3 устройств\n"
        "• Оплата звёздами, картой, СБП или криптой\n\n"
        "Нажмите кнопку ниже, чтобы подключиться 👇",
        reply_markup=open_app_kb(),
        parse_mode="HTML",
    )
