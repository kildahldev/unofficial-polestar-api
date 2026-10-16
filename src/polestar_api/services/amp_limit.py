"""Amp limit service — get/set battery charge amperage limit."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode, encode
from ..models.charging import AmpLimitResponse
from ..models.common import (
    CHRONOS_SUCCESS_STATES,
    ChronosStatus,
    ResponseStatus,
    ResponseStatusCode,
)
from .chronos import wrap_chronos

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_STREAM_TIMEOUT = 10.0


class AmpLimitServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.amp_limit_svc

    @staticmethod
    def _parse(data: bytes) -> AmpLimitResponse:
        """Unwrap chronos envelope and parse the amp limit payload."""
        raw = decode(data)
        payload = raw.get(3)
        if isinstance(payload, bytes):
            inner = decode(payload)
            return AmpLimitResponse(amperage_limit=int(inner.get(1, 0) or 0))
        return AmpLimitResponse()

    async def get(self) -> AmpLimitResponse:
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        data = None
        try:
            async with asyncio.timeout(_STREAM_TIMEOUT):
                async for data in grpc_call.unary_stream(
                    self._connection.channel, f"{self._svc}/GetAmpLimit",
                    wrap_chronos(self._vin), metadata=metadata,
                ):
                    break
        except TimeoutError:
            pass
        if data is None:
            return AmpLimitResponse()
        return self._parse(data)

    async def set(self, amperage: int) -> AmpLimitResponse:
        # APK: REQUEST=1 (ChronosRequest), AMP_LIMIT=2
        payload = encode({"amp_limit": (2, "int32")}, {"amp_limit": amperage})
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        data = await grpc_call.unary_unary(
            self._connection.channel, f"{self._svc}/SetAmpLimit",
            wrap_chronos(self._vin, payload), metadata=metadata,
        )
        # SetAmpLimit returns a flat delivery acknowledgement, unlike GetAmpLimit's
        # nested amperage payload. Preserve the lifecycle code for callers.
        status_code = decode(data).get(3, 0)
        if not isinstance(status_code, int):
            status_code = 0
        try:
            chronos_status = ChronosStatus(status_code)
        except ValueError:
            chronos_status = ChronosStatus.UNKNOWN_ERROR
        return AmpLimitResponse(
            response_status=ResponseStatus(
                status=(
                    ResponseStatusCode.SUCCESS
                    if chronos_status in CHRONOS_SUCCESS_STATES
                    else ResponseStatusCode.ERROR
                ),
                status_code=status_code,
            ),
        )
