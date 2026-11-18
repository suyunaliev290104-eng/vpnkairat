from datetime import datetime

from app.plans import Plan


def fmt_date(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y")


def paid(plan: Plan, expires: datetime) -> str:
    return (f"✅ Оплата прошла! Подписка на {plan.months} мес. активна до <b>{fmt_date(expires)}</b>.\n"
            "Откройте приложение, чтобы подключиться.")


def referral_bonus(days: int, expires: datetime) -> str:
    return f"🎁 Ваш друг оплатил подписку — вам +{days} дней! Подписка до <b>{fmt_date(expires)}</b>."


def expires_soon(days: int) -> str:
    word = "день" if days == 1 else "дня"
    return f"⏳ Подписка закончится через {days} {word}. Продлите, чтобы VPN не отключился."


def expired() -> str:
    return "⛔️ Подписка закончилась, VPN отключён. Продлите её в приложении — ключ останется прежним."
