import asyncio
import json
from datetime import timedelta

from aiogram import F, Router
from aiogram.filters import Command, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.config import get_settings
from app.context import ctx
from app.db import get_sessionmaker
from app.models import Server, utcnow
from app.services.admin import all_user_ids, find_user, stats
from app.services.subscription import extend, get_or_create_subscription
from app.vpn.sync import sync_user

router = Router()

SERVER_REQUIRED = ("name", "panel_url", "username", "password", "inbound_id", "host", "reality_pbk", "reality_sni")


class IsAdmin(Filter):
    async def __call__(self, event) -> bool:
        return event.from_user.id in get_settings().admin_ids


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class AdminStates(StatesGroup):
    find = State()
    broadcast = State()
    confirm = State()


def parse_server_json(raw: str) -> Server:
    data = json.loads(raw)
    missing = [k for k in SERVER_REQUIRED if k not in data]
    if missing:
        raise ValueError("не хватает полей: " + ", ".join(missing))
    allowed = {c.name for c in Server.__table__.columns} - {"id"}
    return Server(**{"port": 443, "enabled": True, "reality_sid": "", "flag": "🌐", "country": "",
                     **{k: v for k, v in data.items() if k in allowed}})


def menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [b(text="📊 Статистика", callback_data="adm:stats"), b(text="🔎 Пользователь", callback_data="adm:find")],
        [b(text="📣 Рассылка", callback_data="adm:bc"), b(text="🖥 Серверы", callback_data="adm:srv")],
    ])


def fmt_money(d: dict) -> str:
    return ", ".join(f"{v} {k}" for k, v in d.items()) or "0"


@router.message(Command("admin"))
async def admin(m: Message, state: FSMContext) -> None:
    await state.clear()
    await m.answer("🛠 Админ-панель", reply_markup=menu_kb())


@router.callback_query(F.data == "adm:stats")
async def cb_stats(c: CallbackQuery) -> None:
    async with get_sessionmaker()() as s:
        st = await stats(s)
    await c.message.answer(
        f"👥 Пользователей: {st['users']} (сегодня +{st['new_today']})\n"
        f"✅ Активных подписок: {st['active']}\n"
        f"💰 Выручка сегодня: {fmt_money(st['revenue_today'])}\n"
        f"💰 За 30 дней: {fmt_money(st['revenue_30d'])}")
    await c.answer()


def user_kb(tg_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[[
        b(text="+7 дн.", callback_data=f"adm:add:{tg_id}:7"),
        b(text="+30 дн.", callback_data=f"adm:add:{tg_id}:30"),
        b(text="⛔️ Отключить", callback_data=f"adm:off:{tg_id}"),
    ]])


async def user_card(s, user) -> str:
    sub = await get_or_create_subscription(s, user)
    until = sub.expires.strftime("%d.%m.%Y %H:%M") if sub.expires else "—"
    state = "активна" if sub.is_active else "нет"
    return (f"👤 {user.tg_id} @{user.username or '—'}\n📧 {user.email or '—'}\n"
            f"Подписка: {state}, до {until}\nUUID: <code>{sub.uuid}</code>")


@router.callback_query(F.data == "adm:find")
async def cb_find(c: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.find)
    await c.message.answer("Пришлите Telegram ID или @username")
    await c.answer()


@router.message(AdminStates.find)
async def do_find(m: Message, state: FSMContext) -> None:
    await state.clear()
    async with get_sessionmaker()() as s:
        user = await find_user(s, m.text or "")
        if not user:
            await m.answer("Не найден")
            return
        await m.answer(await user_card(s, user), reply_markup=user_kb(user.tg_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm:add:") | F.data.startswith("adm:off:"))
async def cb_user_action(c: CallbackQuery) -> None:
    parts = c.data.split(":")
    async with get_sessionmaker()() as s:
        user = await find_user(s, parts[2])
        if not user:
            await c.answer("Не найден", show_alert=True)
            return
        if parts[1] == "add":
            await extend(s, user, int(parts[3]))
        else:
            sub = await get_or_create_subscription(s, user)
            sub.expires_at = utcnow() - timedelta(seconds=1)
            sub.notified_expired = True
            await s.commit()
        ok = await sync_user(s, user, ctx.vpn)
        await c.message.edit_text(await user_card(s, user) + ("" if ok else "\n⚠️ Не все серверы обновлены"),
                                  reply_markup=user_kb(user.tg_id), parse_mode="HTML")
    await c.answer("Готово")


@router.callback_query(F.data == "adm:bc")
async def cb_broadcast(c: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.broadcast)
    await c.message.answer("Пришлите сообщение для рассылки (текст, фото с подписью — что угодно)")
    await c.answer()


@router.message(AdminStates.broadcast)
async def bc_preview(m: Message, state: FSMContext) -> None:
    await state.update_data(chat_id=m.chat.id, message_id=m.message_id)
    await state.set_state(AdminStates.confirm)
    b = InlineKeyboardButton
    await m.answer("Отправить всем?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
        b(text="✅ Отправить", callback_data="adm:bc_go"), b(text="✖️ Отмена", callback_data="adm:bc_no")]]))


@router.callback_query(F.data == "adm:bc_no")
async def bc_cancel(c: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await c.message.edit_text("Отменено")


@router.callback_query(F.data == "adm:bc_go", AdminStates.confirm)
async def bc_go(c: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    await c.message.edit_text("Рассылка запущена…")
    async with get_sessionmaker()() as s:
        ids = await all_user_ids(s)
    ok = fail = 0
    for uid in ids:
        try:
            await c.bot.copy_message(uid, data["chat_id"], data["message_id"])
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await c.message.answer(f"📣 Рассылка завершена: доставлено {ok}, ошибок {fail}")


def servers_kb(servers: list[Server]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{'🟢' if s.enabled else '⚪️'} {s.flag} {s.name}",
                                  callback_data=f"adm:srv_t:{s.id}")] for s in servers]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _servers(s) -> list[Server]:
    return list(await s.scalars(select(Server).order_by(Server.id)))


@router.callback_query(F.data == "adm:srv")
async def cb_servers(c: CallbackQuery) -> None:
    async with get_sessionmaker()() as s:
        servers = await _servers(s)
    await c.message.answer(
        "🖥 Серверы (нажмите, чтобы включить/выключить).\n"
        "Добавить: <code>/addserver {JSON}</code> — JSON печатает scripts/install_xui.sh",
        reply_markup=servers_kb(servers), parse_mode="HTML")
    await c.answer()


@router.callback_query(F.data.startswith("adm:srv_t:"))
async def cb_server_toggle(c: CallbackQuery) -> None:
    async with get_sessionmaker()() as s:
        srv = await s.get(Server, int(c.data.split(":")[2]))
        if srv:
            srv.enabled = not srv.enabled
            await s.commit()
        servers = await _servers(s)
    await c.message.edit_reply_markup(reply_markup=servers_kb(servers))
    await c.answer()


@router.message(Command("addserver"))
async def add_server(m: Message, command) -> None:
    try:
        srv = parse_server_json(command.args or "")
    except (ValueError, json.JSONDecodeError) as e:
        await m.answer(f"Ошибка: {e}")
        return
    async with get_sessionmaker()() as s:
        s.add(srv)
        await s.commit()
    await m.answer(f"✅ Сервер {srv.flag} {srv.name} добавлен. Существующие клиенты будут добавлены на него "
                   "при следующей синхронизации (/resync).")


@router.message(Command("resync"))
async def resync_all(m: Message) -> None:
    from app.models import Subscription
    async with get_sessionmaker()() as s:
        subs = list(await s.scalars(select(Subscription).where(Subscription.expires_at > utcnow())))
        for sub in subs:
            sub.needs_sync = True
        await s.commit()
    await m.answer(f"🔄 {len(subs)} активных подписок поставлено в очередь синхронизации (до 10 минут).")
