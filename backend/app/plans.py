from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    id: str
    days: int
    months: int
    rub: int
    xtr: int
    usdt: int
    badge: str | None = None


PLANS: dict[str, Plan] = {
    p.id: p
    for p in (
        Plan("m1", 30, 1, 199, 190, 3),
        Plan("m3", 90, 3, 549, 520, 7, "Популярный"),
        Plan("m6", 180, 6, 999, 950, 13),
        Plan("m12", 365, 12, 1790, 1700, 22, "Выгоднее всего"),
    )
}

BASE_MONTH_RUB = PLANS["m1"].rub


def per_month_rub(plan: Plan) -> int:
    return int(plan.rub / plan.months + 0.5)  # half-up, not banker's rounding


def discount_percent(plan: Plan) -> int:
    return round(100 - plan.rub * 100 / (BASE_MONTH_RUB * plan.months))
