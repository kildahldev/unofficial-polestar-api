"""Weather service — temperature at car's location."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode, encode
from ..models.weather import WeatherReport

if TYPE_CHECKING:
    from ..connection import GrpcConnection

class WeatherServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.weather_svc

    async def get_report(self) -> WeatherReport | None:
        request = encode({"vin": (1, "string")}, {"vin": self._vin})
        metadata = await self._connection.get_metadata(self._vin)
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._svc}/GetWeatherReport",
            request,
            metadata=metadata,
        )
        raw = decode(data, {1: ("report", "message")})
        if raw.get("report"):
            return WeatherReport.from_bytes(raw["report"])
        return None
