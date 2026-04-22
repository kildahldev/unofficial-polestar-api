"""Target SoC service — get/set battery charge target level."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode, encode

_LOGGER = logging.getLogger(__name__)
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
        """Unwrap chronos envelope and parse the target SoC payload."""
        raw = decode(data)
        payload = raw.get(3)
        if isinstance(payload, bytes):
            inner = decode(payload)
            return TargetSocResponse(target_level=int(inner.get(1, 0) or 0))
        return TargetSocResponse()

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
        # SetTargetSoc is unary on the server; streaming hangs until timeout.
        payload = encode(
            {"level": (2, "int32"), "setting_type": (3, "int32")},
            {"level": level, "setting_type": int(setting_type)},
        )
        request_data = wrap_chronos(self._vin, payload)
        _LOGGER.info("SetTargetSoc request: level=%d, setting_type=%d, payload=%s", level, int(setting_type), request_data.hex())
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{self._svc}/SetTargetSoc",
            request_data, metadata=metadata,
        )
        _LOGGER.info("SetTargetSoc raw response (%d bytes): %s", len(data), data.hex())
        raw = decode(data)
        _LOGGER.info("SetTargetSoc decoded fields: %s", {k: v.hex() if isinstance(v, bytes) else v for k, v in raw.items()})
        result = self._parse(data)
        _LOGGER.info("SetTargetSoc parsed result: %s", result)
        return result
