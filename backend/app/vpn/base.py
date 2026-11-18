from dataclasses import dataclass
from typing import Protocol

from app.models import Server


@dataclass(frozen=True)
class ClientSpec:
    uuid: str
    email: str
    expiry_ms: int
    enabled: bool
    limit_ip: int
    sub_id: str
    total_bytes: int = 0  # 0 = unlimited; bypass servers get the daily cap


BYPASS = "bypass"


class VpnProvider(Protocol):
    async def upsert_client(self, server: Server, spec: ClientSpec) -> None: ...

    async def get_traffic(self, server: Server, email: str) -> tuple[int, int]: ...

    async def reset_traffic(self, server: Server) -> None: ...
