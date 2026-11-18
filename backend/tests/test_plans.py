from app.plans import PLANS, discount_percent, per_month_rub


def test_prices():
    assert [(p.rub, p.xtr, p.usdt) for p in PLANS.values()] == [
        (159, 150, 2), (399, 380, 5), (699, 660, 9), (1190, 1080, 14)]


def test_discounts():
    assert [discount_percent(PLANS[k]) for k in ("m1", "m3", "m6", "m12")] == [0, 16, 27, 38]
    assert per_month_rub(PLANS["m12"]) == 99


def test_badges_and_days():
    assert PLANS["m3"].badge == "Популярный"
    assert PLANS["m12"].badge == "Выгоднее всего"
    assert [p.days for p in PLANS.values()] == [30, 90, 180, 365]
