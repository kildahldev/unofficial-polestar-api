"""Availability service — check if car is reachable."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode
from ..models.availability import Availability
from ..models.battery import GetBatteryRequest

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_SVC = "/services.vehiclestates.availability.AvailabilityService"


class AvailabilityServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def get_latest(self) -> Availability:
        request = GetBatteryRequest(vin=self._vin)
        metadata = await self._connection.get_metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{_SVC}/GetLatestAvailability",
            request.to_bytes(),
            metadata=metadata,
        )
        raw = decode(data, {3: ("availability", "message")})
        if raw.get("availability"):
            return Availability.from_bytes(raw["availability"])
        return Availability()
