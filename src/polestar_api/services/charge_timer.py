"""Charge timer service — get/set global battery charge timer."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import encode, encode_bool, encode_message
from ..models.charging import BatteryChargeTimer, ChargeTimerResponse
from .chronos import wrap_chronos

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_STREAM_TIMEOUT = 10.0


class ChargeTimerServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.charge_timer_svc

    async def get(self) -> ChargeTimerResponse:
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        data = None
        try:
            async with asyncio.timeout(_STREAM_TIMEOUT):
                async for data in grpc_call.unary_stream(
                    self._connection.channel,
                    f"{self._svc}/GetGlobalChargeTimerStream",
                    wrap_chronos(self._vin),
                    metadata=metadata,
                ):
                    break
        except TimeoutError:
            pass
        if data is None:
            return ChargeTimerResponse()
        return ChargeTimerResponse.from_bytes(data)

    async def set(self, timer: BatteryChargeTimer) -> ChargeTimerResponse:
        # APK: REQUEST=1 (ChronosRequest), CHARGE_TIMER=2, TIME_IS_UTC0=3
        payload = encode_message(2, timer.to_bytes()) + encode_bool(3, False)
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._svc}/SetGlobalChargeTimer",
            wrap_chronos(self._vin, payload),
            metadata=metadata,
        )
        return ChargeTimerResponse.from_bytes(data)
