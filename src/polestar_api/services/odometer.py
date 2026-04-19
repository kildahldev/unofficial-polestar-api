"""Odometer service — current odometer reading."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode, encode
from ..models.odometer import OdometerStatus

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_RESPONSE_SCHEMA = {3: ("odometer", "message")}


def _odometer_request(vin: str) -> bytes:
    """Encode an odometer request (VIN at field 2, per DT proto)."""
    return encode({"vin": (2, "string")}, {"vin": vin})


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
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._svc}/GetOdometer",
            _odometer_request(self._vin),
            metadata=metadata,
        )
        raw = decode(data, _RESPONSE_SCHEMA)
        if raw.get("odometer"):
            return OdometerStatus.from_bytes(raw["odometer"])
        return None
