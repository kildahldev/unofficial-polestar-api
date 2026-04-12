"""Pre-cleaning status service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import asyncio

from .. import grpc as grpc_call
from ..codec import decode, encode
from ..models.precleaning import PreCleaningInfo

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_SVC = "/services.vehiclestates.precleaning.PreCleaningService"
_RESPONSE_SCHEMA = {3: ("precleaning", "message")}


def _precleaning_request(vin: str) -> bytes:
    """Encode a pre-cleaning request (VIN at field 2, per DT proto)."""
    return encode({"vin": (2, "string")}, {"vin": vin})


class PreCleaningServiceClient:
    """Pre-cleaning air quality status (read-only)."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    async def get_latest(self) -> PreCleaningInfo | None:
        metadata = await self._connection.get_metadata(self._vin)
        async with asyncio.timeout(15):
            async for data in grpc_call.unary_stream(
                self._connection.channel,
                f"{_SVC}/GetPreCleaning",
                _precleaning_request(self._vin),
                metadata=metadata,
            ):
                raw = decode(data, _RESPONSE_SCHEMA)
                if raw.get("precleaning"):
                    return PreCleaningInfo.from_bytes(raw["precleaning"])
                return None
        return None
