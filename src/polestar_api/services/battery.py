"""Battery service client."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from ..models.battery import Battery, GetBatteryResponse
from ..models.common import VehicleRequest
from .. import grpc as grpc_call

if TYPE_CHECKING:
    from ..connection import GrpcConnection

class BatteryServiceClient:
    """Battery service wrapper."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.battery_svc

    async def get_latest(self) -> Battery | None:
        """Get the latest battery status, or ``None`` if the backend omits it."""
        request = VehicleRequest(vin=self._vin)
        metadata = await self._connection.get_metadata(self._vin)

        response_data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._svc}/GetLatestBattery",
            request.to_bytes(),
            metadata=metadata,
        )
        response = GetBatteryResponse.from_bytes(response_data)
        return response.battery

    async def stream(self) -> AsyncIterator[Battery]:
        """Stream battery status updates."""
        request = VehicleRequest(vin=self._vin)
        metadata = await self._connection.get_metadata(self._vin)

        async for response_data in grpc_call.unary_stream(
            self._connection.channel,
            f"{self._svc}/GetBattery",
            request.to_bytes(),
            metadata=metadata,
        ):
            response = GetBatteryResponse.from_bytes(response_data)
            if response.battery:
                yield response.battery
