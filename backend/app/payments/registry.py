from app.config import Settings, get_settings
from app.payments.base import PaymentProvider

_providers: dict[str, PaymentProvider] = {}


def register(cls: type[PaymentProvider]) -> type[PaymentProvider]:
    _providers[cls.name] = cls()
    return cls


def unregister(name: str) -> None:
    _providers.pop(name, None)


def get(name: str) -> PaymentProvider:
    try:
        return _providers[name]
    except KeyError:
        raise ValueError("unknown_provider")


def available(settings: Settings | None = None) -> list[PaymentProvider]:
    settings = settings or get_settings()
    return [p for p in _providers.values() if p.enabled(settings)]


def load_builtin() -> None:
    """Import built-in providers so their @register decorators run."""
    from app.payments import cryptobot, stars  # noqa: F401
