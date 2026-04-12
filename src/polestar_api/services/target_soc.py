"""Target SoC service — get/set battery charge target level."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode, encode
from ..models.charging import (
    ChargeTargetLevelSettingType,
    TargetSocResponse,
)
from .chronos import wrap_chronos

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_STREAM_TIMEOUT = 10.0  # seconds to wait for first message from subscription


class TargetSocServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.target_soc_svc

    @staticmethod
    def _parse(data: bytes) -> TargetSocResponse:
        raw = decode(data)
        target_soc = raw.get(3)
        if isinstance(target_soc, bytes):
            target_raw = decode(target_soc)
            return TargetSocResponse(target_level=int(target_raw.get(1, 0) or 0))
        return TargetSocResponse.from_bytes(data)

    async def get(self) -> TargetSocResponse:
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        data = None
        try:
            async with asyncio.timeout(_STREAM_TIMEOUT):
                async for data in grpc_call.unary_stream(
                    self._connection.channel, f"{self._svc}/GetTargetSoc",
                    wrap_chronos(self._vin), metadata=metadata,
                ):
                    break  # take first message from subscription
        except TimeoutError:
            pass
        if data is None:
            return TargetSocResponse()
        return self._parse(data)

    async def set(
        self,
        level: int,
        setting_type: ChargeTargetLevelSettingType = ChargeTargetLevelSettingType.DAILY,
    ) -> TargetSocResponse:
        # APK: REQUEST=1 (ChronosRequest), BATTERY_CHARGE_TARGET_LEVEL=2, SETTING_TYPE=3
        payload = encode(
            {"level": (2, "int32"), "setting_type": (3, "int32")},
            {"level": level, "setting_type": int(setting_type)},
        )
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        data = None
        try:
            async with asyncio.timeout(_STREAM_TIMEOUT):
                async for data in grpc_call.unary_stream(
                    self._connection.channel, f"{self._svc}/SetTargetSoc",
                    wrap_chronos(self._vin, payload), metadata=metadata,
                ):
                    break  # take first message from subscription
        except TimeoutError:
            pass
        if data is None:
            return TargetSocResponse()
        return self._parse(data)
