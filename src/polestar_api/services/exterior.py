"""Exterior service — doors, windows, locks status."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode
from ..models.common import VehicleRequest
from ..models.exterior import (
    CentralLockStatus,
    DoorStatus,
    DoorsStatus,
    ExteriorStatus,
    HoodStatus,
    LockStatus,
    OpenStatus,
    SunroofStatus,
    TailgateStatus,
    TankLidStatus,
    WindowStatus,
    WindowsStatus,
)

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_RESPONSE_SCHEMA = {3: ("exterior", "message")}


class ExteriorServiceClient:
    """Exterior status service."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.exterior_svc

    @staticmethod
    def _lock(value: int | None) -> LockStatus:
        try:
            return LockStatus(value or 0)
        except ValueError:
            return LockStatus.UNSPECIFIED

    @staticmethod
    def _open(value: int | None) -> OpenStatus:
        try:
            return OpenStatus(value or 0)
        except ValueError:
            return OpenStatus.UNSPECIFIED

    @classmethod
    def _parse_digital_twin(cls, exterior_bytes: bytes) -> ExteriorStatus:
        raw = decode(exterior_bytes)
        return ExteriorStatus(
            central_lock=CentralLockStatus(lock_status=cls._lock(raw.get(2))),
            doors=DoorsStatus(
                front_left=DoorStatus(open_status=cls._open(raw.get(3))),
                front_right=DoorStatus(open_status=cls._open(raw.get(4))),
                rear_left=DoorStatus(open_status=cls._open(raw.get(5))),
                rear_right=DoorStatus(open_status=cls._open(raw.get(6))),
            ),
            windows=WindowsStatus(
                front_left=WindowStatus(open_status=cls._open(raw.get(7))),
                front_right=WindowStatus(open_status=cls._open(raw.get(8))),
                rear_left=WindowStatus(open_status=cls._open(raw.get(9))),
                rear_right=WindowStatus(open_status=cls._open(raw.get(10))),
            ),
            hood=HoodStatus(status=DoorStatus(open_status=cls._open(raw.get(11)))),
            tailgate=TailgateStatus(
                status=DoorStatus(
                    lock_status=cls._lock(raw.get(16)),
                    open_status=cls._open(raw.get(12)),
                )
            ),
            tank_lid=TankLidStatus(open_status=cls._open(raw.get(13))),
            sunroof=SunroofStatus(open_status=cls._open(raw.get(14))),
        )

    @classmethod
    def _is_digital_twin(cls, payload: dict) -> bool:
        """Detect Digital Twin flat-field format vs old nested-message format.

        DT uses flat ints for fields 2-16; old format uses nested messages (bytes).
        A partial stream update may omit any field, so check all known DT fields.
        """
        return any(isinstance(payload.get(f), int) for f in range(2, 17))

    @classmethod
    def _parse(cls, raw: dict) -> ExteriorStatus | None:
        exterior_bytes = raw.get("exterior")
        if not exterior_bytes:
            return None
        payload = decode(exterior_bytes)
        if cls._is_digital_twin(payload):
            status = cls._parse_digital_twin(exterior_bytes)
        else:
            status = ExteriorStatus.from_bytes(exterior_bytes)
        return status if status.has_data else None

    async def get_latest(self) -> ExteriorStatus | None:
        request = VehicleRequest(vin=self._vin)
        metadata = await self._connection.get_metadata(self._vin)
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._svc}/GetLatestExterior",
            request.to_bytes(),
            metadata=metadata,
        )
        return self._parse(decode(data, _RESPONSE_SCHEMA))

    async def stream(self) -> AsyncIterator[ExteriorStatus]:
        """Stream exterior status updates (server-push)."""
        request = VehicleRequest(vin=self._vin)
        metadata = await self._connection.get_metadata(self._vin)
        async for data in grpc_call.unary_stream(
            self._connection.channel,
            f"{self._svc}/GetExterior",
            request.to_bytes(),
            metadata=metadata,
        ):
            status = self._parse(decode(data, _RESPONSE_SCHEMA))
            if status is not None:
                yield status
