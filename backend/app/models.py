from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(255))
    referrer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    subscription: Mapped["Subscription | None"] = relationship(back_populates="user", lazy="selectin")


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    uuid: Mapped[str] = mapped_column(String(36))
    sub_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_sync: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_3d: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_1d: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_expired: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship(back_populates="subscription")

    @property
    def expires(self) -> datetime | None:
        return aware(self.expires_at)

    @property
    def is_active(self) -> bool:
        return self.expires is not None and self.expires > utcnow()


class Server(Base):
    __tablename__ = "servers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    country: Mapped[str] = mapped_column(String(64), default="")
    flag: Mapped[str] = mapped_column(String(8), default="🌐")
    panel_url: Mapped[str] = mapped_column(String(255))
    username: Mapped[str] = mapped_column(String(128))
    password: Mapped[str] = mapped_column(String(128))
    inbound_id: Mapped[int] = mapped_column(Integer)
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=443)
    reality_pbk: Mapped[str] = mapped_column(String(128))
    reality_sni: Mapped[str] = mapped_column(String(255))
    reality_sid: Mapped[str] = mapped_column(String(32), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    provider_payment_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    plan_id: Mapped[str] = mapped_column(String(16))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(lazy="selectin")
