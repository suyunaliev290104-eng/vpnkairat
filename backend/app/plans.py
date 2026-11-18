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
        Plan("m1", 30, 1, 159, 150, 2),
        Plan("m3", 90, 3, 399, 380, 5, "Популярный"),
        Plan("m6", 180, 6, 699, 660, 9),
        Plan("m12", 365, 12, 1190, 1080, 14, "Выгоднее всего"),
    )
}

BASE_MONTH_RUB = PLANS["m1"].rub


def per_month_rub(plan: Plan) -> int:
    return round(plan.rub / plan.months)


def discount_percent(plan: Plan) -> int:
    return round(100 - plan.rub * 100 / (BASE_MONTH_RUB * plan.months))
