from datetime import timedelta

from app.models import Payment, utcnow
from app.services.admin import find_user, stats
from app.services.subscription import extend


async def test_admin_stats_counts(session, user_factory):
    a = await user_factory(tg_id=1, username="alice")
    b = await user_factory(tg_id=2, username="bob")
    await extend(session, a, 30)
    session.add_all([
        Payment(user_id=a.id, provider="lavatop", plan_id="m1", amount=159, currency="RUB", status="paid",
                paid_at=utcnow()),
        Payment(user_id=b.id, provider="stars", plan_id="m1", amount=150, currency="XTR", status="paid",
                paid_at=utcnow() - timedelta(days=10)),
        Payment(user_id=b.id, provider="stars", plan_id="m1", amount=150, currency="XTR", status="pending"),
    ])
    await session.commit()
    st = await stats(session)
    assert st["users"] == 2 and st["active"] == 1 and st["new_today"] == 2
    assert st["revenue_today"] == {"RUB": 159}
    assert st["revenue_30d"] == {"RUB": 159, "XTR": 150}


async def test_find_user(session, user_factory):
    await user_factory(tg_id=77, username="Carol")
    assert (await find_user(session, "77")).tg_id == 77
    assert (await find_user(session, "@carol")).tg_id == 77
    assert await find_user(session, "@nobody") is None


async def test_queue_resync_all_marks_only_active(session, user_factory):
    from app.services.admin import queue_resync_all
    from app.services.subscription import get_or_create_subscription
    a = await user_factory()
    b = await user_factory()
    sa = await extend(session, a, 30)
    sa.needs_sync = False
    sb = await get_or_create_subscription(session, b)
    await session.commit()
    assert await queue_resync_all(session) == 1
    assert sa.needs_sync is True and sb.needs_sync is False
