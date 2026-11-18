from app.plans import PLANS, discount_percent, per_month_rub


def test_prices():
    assert [(p.rub, p.xtr, p.usdt) for p in PLANS.values()] == [
        (199, 190, 3), (549, 520, 7), (999, 950, 13), (1790, 1700, 22)]


def test_discounts():
    assert [discount_percent(PLANS[k]) for k in ("m1", "m3", "m6", "m12")] == [0, 8, 16, 25]
    assert [per_month_rub(PLANS[k]) for k in ("m1", "m3", "m6", "m12")] == [199, 183, 167, 149]


def test_badges_and_days():
    assert PLANS["m3"].badge == "Популярный"
    assert PLANS["m12"].badge == "Выгоднее всего"
    assert [p.days for p in PLANS.values()] == [30, 90, 180, 365]
