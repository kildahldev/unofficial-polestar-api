"""Pre-cleaning status service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode
from ..models.precleaning import PreCleaningInfo

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_SVC = "/services.vehiclestates.precleaning.PreCleaningService"


class PreCleaningServiceClient:
    """Pre-cleaning air quality status (read-only)."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def get_latest(self) -> PreCleaningInfo:
        from ..models.battery import GetBatteryRequest
        request = GetBatteryRequest(vin=self._vin)
        metadata = await self._connection.get_metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{_SVC}/GetPreCleaning",
            request.to_bytes(),
            metadata=metadata,
        )
        raw = decode(data, {3: ("precleaning", "message")})
        if raw.get("precleaning"):
            return PreCleaningInfo.from_bytes(raw["precleaning"])
        return PreCleaningInfo()
