"""Health service — vehicle health status."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode
from ..models.battery import GetBatteryRequest
from ..models.health import Health

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_SVC = "/services.vehiclestates.health.HealthService"


class HealthServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def get_latest(self) -> Health:
        request = GetBatteryRequest(vin=self._vin)
        metadata = await self._connection.get_metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{_SVC}/GetHealth",
            request.to_bytes(),
            metadata=metadata,
        )
        raw = decode(data, {3: ("health", "message")})
        if raw.get("health"):
            return Health.from_bytes(raw["health"])
        return Health()
