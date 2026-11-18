"""Main entry point for the Polestar API client."""

from __future__ import annotations

from .auth import AuthManager, FileTokenStore, TokenStore
from .connection import GrpcConnection
from .discovery import VehicleInfo, discover_c3_endpoint, get_vehicles
from .vehicle import Vehicle


class PolestarApi:
    """Async client for the Polestar vehicle API.

    Usage::

        async with PolestarApi(email="...", password="...") as api:
            vehicles = await api.get_vehicles()
            battery = await vehicles[0].get_battery()
            if battery is not None:
                print(battery.charge_level)
    """

    def __init__(
        self,
        email: str,
        password: str,
        *,
        token_store: TokenStore | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._auth = AuthManager(token_store=token_store)
        self._connection: GrpcConnection | None = None
        self._vehicle_cache: list[VehicleInfo] | None = None

    async def async_init(self) -> None:
        """Authenticate and discover endpoints. Must be called before use."""
        await self._auth.authenticate(self._email, self._password)
        token = await self._auth.ensure_valid_token()
        endpoint = await discover_c3_endpoint(token)
        self._connection = GrpcConnection(
            host=endpoint.host,
            port=endpoint.port,
            auth=self._auth,
        )

    async def get_vehicles(self) -> list[Vehicle]:
        """Fetch the user's vehicles."""
        token = await self._auth.ensure_valid_token()
        infos = await get_vehicles(token)
        self._vehicle_cache = infos
        return [
            Vehicle(
                vin=info.vin,
                connection=self._connection,
                internal_id=info.internal_id,
                registration_no=info.registration_no,
                model_year=info.model_year,
                model_name=info.model_name,
            )
            for info in infos
        ]

    async def get_vehicle(self, vin: str) -> Vehicle:
        """Get a specific vehicle by VIN."""
        vehicles = await self.get_vehicles()
        for v in vehicles:
            if v.vin == vin:
                return v
        raise ValueError(f"Vehicle not found: {vin}")

    async def close(self) -> None:
        """Close all connections."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def __aenter__(self) -> PolestarApi:
        await self.async_init()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
