"""Odometer service — current odometer reading."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..models.battery import GetBatteryRequest
from ..models.odometer import OdometerStatus

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_SVC = "/services.vehiclestates.odometer.OdometerService"


class OdometerServiceClient:
    """Odometer service."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def get_latest(self) -> OdometerStatus:
        from ..codec import decode
        request = GetBatteryRequest(vin=self._vin)
        metadata = await self._connection.get_metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{_SVC}/GetOdometer",
            request.to_bytes(),
            metadata=metadata,
        )
        raw = decode(data, {3: ("odometer", "message")})
        if raw.get("odometer"):
            return OdometerStatus.from_bytes(raw["odometer"])
        return OdometerStatus()
