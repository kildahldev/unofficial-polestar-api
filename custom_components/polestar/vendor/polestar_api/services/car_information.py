"""Car information service — model name, model year, market and registration plate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode
from ..models.car_information import MyCar

if TYPE_CHECKING:
    from ..connection import GrpcConnection


class CarInformationServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.car_information_svc

    async def get_my_cars(self) -> list[MyCar]:
        """List the cars on the account (the request carries no VIN)."""
        metadata = await self._connection.get_metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._svc}/GetMyCars",
            b"",
            metadata=metadata,
        )
        raw = decode(data, {1: ("my_cars", "message")})
        cars = raw.get("my_cars")
        if cars is None:
            return []
        if not isinstance(cars, list):
            cars = [cars]
        return [MyCar.from_bytes(car) for car in cars]

    async def get_my_car(self) -> MyCar | None:
        """Return this vehicle's entry from the account's car list, or ``None`` if it is not there."""
        for my_car in await self.get_my_cars():
            if my_car.car is not None and my_car.car.vin == self._vin:
                return my_car
        return None
