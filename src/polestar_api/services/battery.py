"""Battery service client."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from ..models.battery import Battery, GetBatteryResponse
from ..models.common import VehicleRequest
from .. import grpc as grpc_call

if TYPE_CHECKING:
    from ..connection import GrpcConnection

METHOD_GET_LATEST = "/services.vehiclestates.battery.BatteryService/GetLatestBattery"
METHOD_STREAM = "/services.vehiclestates.battery.BatteryService/GetBattery"


class BatteryServiceClient:
    """Battery service wrapper."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def get_latest(self) -> Battery:
        """Get the latest battery status."""
        request = VehicleRequest(vin=self._vin)
        metadata = await self._connection.get_metadata(self._vin)

        response_data = await grpc_call.unary_unary(
            self._connection.channel,
            METHOD_GET_LATEST,
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
            METHOD_STREAM,
            request.to_bytes(),
            metadata=metadata,
        ):
            response = GetBatteryResponse.from_bytes(response_data)
            if response.battery:
                yield response.battery
