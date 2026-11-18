"""Target SoC service — get/set battery charge target level."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode, encode

_LOGGER = logging.getLogger("custom_components.polestar.coordinator")
from ..models.charging import (
    ChargeTargetLevelSettingType,
    TargetSocResponse,
)
from ..models.common import (
    CHRONOS_SUCCESS_STATES,
    ChronosStatus,
    ResponseStatus,
    ResponseStatusCode,
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
        """Parse a GetTargetSoc response (targetSoc message at field 3)."""
        raw = decode(data)
        payload = raw.get(3)
        if isinstance(payload, bytes):
            # inner targetSoc: {1: batteryChargeTargetLevel, 2: settingType, ...}
            inner = decode(payload)
            try:
                setting_type = ChargeTargetLevelSettingType(inner.get(2, 0) or 0)
            except ValueError:
                setting_type = ChargeTargetLevelSettingType.UNSPECIFIED
            return TargetSocResponse(
                target_level=int(inner.get(1, 0) or 0),
                setting_type=setting_type,
            )
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
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{self._svc}/SetTargetSoc",
            wrap_chronos(self._vin, payload), metadata=metadata,
        )
        raw = decode(data)
        # SetTargetSocResponse is flat: {1: id, 2: vin, 3: status (chronos
        # delivery lifecycle), 4: message}. Field 3 is NOT our 4-value
        # ResponseStatusCode — it's the SENT/DELIVERED/SYNCED lifecycle.
        status_code = raw.get(3, 0)
        try:
            chronos_status = ChronosStatus(status_code)
        except ValueError:
            chronos_status = ChronosStatus.UNKNOWN_ERROR
        succeeded = chronos_status in CHRONOS_SUCCESS_STATES
        _LOGGER.debug(
            "SetTargetSoc response: status=%d (%s) -> %s",
            status_code, chronos_status.name, "ok" if succeeded else "failed",
        )
        return TargetSocResponse(
            response_status=ResponseStatus(
                status=ResponseStatusCode.SUCCESS if succeeded else ResponseStatusCode.ERROR,
                status_code=status_code,
            ),
        )
