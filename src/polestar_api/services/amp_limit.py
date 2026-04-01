"""Amp limit service — get/set battery charge amperage limit."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..models.charging import AmpLimitResponse, SetAmpLimitRequest

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_SVC = "/chronos.services.v1.AmpLimitService"


class AmpLimitServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def get(self) -> AmpLimitResponse:
        metadata = await self._connection.get_metadata()
        metadata["vin"] = self._vin
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{_SVC}/GetAmpLimit", b"", metadata=metadata,
        )
        return AmpLimitResponse.from_bytes(data)

    async def set(self, amperage: int) -> AmpLimitResponse:
        req = SetAmpLimitRequest(amperage_limit=amperage)
        metadata = await self._connection.get_metadata()
        metadata["vin"] = self._vin
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{_SVC}/SetAmpLimit", req.to_bytes(), metadata=metadata,
        )
        return AmpLimitResponse.from_bytes(data)
