"""Health service — vehicle health status."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode, encode
from ..models.health import Health

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_RESPONSE_SCHEMA = {3: ("health", "message")}
_STREAM_TIMEOUT = 10.0


def _health_request(vin: str) -> bytes:
    """Encode a health request (VIN at field 2, per DT proto)."""
    return encode({"vin": (2, "string")}, {"vin": vin})


class HealthServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.health_svc

    async def get_latest(self) -> Health | None:
        metadata = await self._connection.get_metadata(self._vin)
        data = None
        try:
            async with asyncio.timeout(_STREAM_TIMEOUT):
                async for data in grpc_call.unary_stream(
                    self._connection.channel,
                    f"{self._svc}/GetHealth",
                    _health_request(self._vin),
                    metadata=metadata,
                ):
                    break
        except TimeoutError:
            pass
        if data is None:
            return None
        raw = decode(data, _RESPONSE_SCHEMA)
        if raw.get("health"):
            return Health.from_bytes(raw["health"])
        return None
