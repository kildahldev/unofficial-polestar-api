"""Odometer service — current odometer reading."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, AsyncIterator

from .. import grpc as grpc_call
from ..codec import decode, encode
from ..models.odometer import OdometerStatus

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_RESPONSE_SCHEMA = {3: ("odometer", "message")}
_STREAM_TIMEOUT = 10.0


def _odometer_request(vin: str) -> bytes:
    """Encode an odometer request (VIN at field 2, per DT proto)."""
    return encode({"vin": (2, "string")}, {"vin": vin})


def _parse(data: bytes) -> OdometerStatus | None:
    raw = decode(data, _RESPONSE_SCHEMA)
    if raw.get("odometer"):
        return OdometerStatus.from_bytes(raw["odometer"])
    return None


class OdometerServiceClient:
    """Odometer service."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.odometer_svc

    async def get_latest(self) -> OdometerStatus | None:
        metadata = await self._connection.get_metadata(self._vin)
        data = None
        try:
            async with asyncio.timeout(_STREAM_TIMEOUT):
                async for data in grpc_call.unary_stream(
                    self._connection.channel,
                    f"{self._svc}/GetOdometer",
                    _odometer_request(self._vin),
                    metadata=metadata,
                ):
                    break
        except TimeoutError:
            pass
        if data is None:
            return None
        return _parse(data)

    async def stream(self) -> AsyncIterator[OdometerStatus]:
        """Stream odometer updates (long-lived subscription)."""
        metadata = await self._connection.get_metadata(self._vin)
        async for data in grpc_call.unary_stream(
            self._connection.channel,
            f"{self._svc}/GetOdometer",
            _odometer_request(self._vin),
            metadata=metadata,
        ):
            status = _parse(data)
            if status is not None:
                yield status
