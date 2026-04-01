"""Parking climatization service — climate status."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..models.climate import ClimatizationInfo

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_SVC = "/services.vehiclestates.parkingclimatization.ParkingClimatizationService"


class ClimateServiceClient:
    """Parking climatization status service."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def get_latest(self) -> ClimatizationInfo:
        from ..models.battery import GetBatteryRequest
        from ..codec import decode
        request = GetBatteryRequest(vin=self._vin)
        metadata = await self._connection.get_metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{_SVC}/GetLatestParkingClimatization",
            request.to_bytes(),
            metadata=metadata,
        )
        raw = decode(data, {3: ("climate", "message")})
        if raw.get("climate"):
            return ClimatizationInfo.from_bytes(raw["climate"])
        return ClimatizationInfo()
