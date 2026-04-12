"""Dashboard service — odometer, trip meters, tire pressure, warnings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode
from ..models.common import VehicleRequest
from ..models.connectivity import ConnectivityInfo
from ..models.dashboard import DashboardStatus

if TYPE_CHECKING:
    from ..connection import GrpcConnection

class DashboardServiceClient:
    """Dashboard status service."""

    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.dashboard_svc

    async def get_latest(self) -> DashboardStatus | None:
        request = VehicleRequest(vin=self._vin)
        metadata = await self._connection.get_metadata(self._vin)
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._svc}/GetLatestDashboard",
            request.to_bytes(),
            metadata=metadata,
        )
        # Response: field 1 = ResponseStatus, field 2 = DashboardStatus, field 3 = ConnectivityInfo
        raw = decode(data, {2: ("dashboard", "message")})
        if raw.get("dashboard"):
            return DashboardStatus.from_bytes(raw["dashboard"])
        return None

    async def get_connectivity(self) -> ConnectivityInfo | None:
        request = VehicleRequest(vin=self._vin)
        metadata = await self._connection.get_metadata(self._vin)
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._svc}/GetLatestDashboard",
            request.to_bytes(),
            metadata=metadata,
        )
        raw = decode(data, {3: ("connectivity", "message")})
        if raw.get("connectivity"):
            return ConnectivityInfo.from_bytes(raw["connectivity"])
        return None
