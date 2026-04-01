"""Exterior service — doors, windows, locks status."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..models.exterior import ExteriorStatus
from ..models.battery import GetBatteryRequest  # reuse same request shape (id + vin)

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_SVC = "/services.vehiclestates.exterior.ExteriorService"


class ExteriorServiceClient:
    """Exterior status service."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def get_latest(self) -> ExteriorStatus:
        request = GetBatteryRequest(vin=self._vin)
        metadata = await self._connection.get_metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{_SVC}/GetLatestExterior",
            request.to_bytes(),
            metadata=metadata,
        )
        # Response has same shape: id=1, vin=2, exterior=3
        from ..codec import decode
        raw = decode(data, {3: ("exterior", "message")})
        if raw.get("exterior"):
            return ExteriorStatus.from_bytes(raw["exterior"])
        return ExteriorStatus()
