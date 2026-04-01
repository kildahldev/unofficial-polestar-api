"""Charge timer service — get/set global battery charge timer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..models.charging import (
    BatteryChargeTimer,
    ChargeTimerResponse,
    SetChargeTimerRequest,
)

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_SVC = "/chronos.services.v2.GlobalChargeTimerService"


class ChargeTimerServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def get(self) -> ChargeTimerResponse:
        metadata = await self._connection.get_metadata()
        metadata["vin"] = self._vin
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{_SVC}/GetGlobalChargeTimerStream",
            b"",
            metadata=metadata,
        )
        return ChargeTimerResponse.from_bytes(data)

    async def set(self, timer: BatteryChargeTimer) -> ChargeTimerResponse:
        req = SetChargeTimerRequest(timer=timer)
        metadata = await self._connection.get_metadata()
        metadata["vin"] = self._vin
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{_SVC}/SetGlobalChargeTimer",
            req.to_bytes(),
            metadata=metadata,
        )
        return ChargeTimerResponse.from_bytes(data)
