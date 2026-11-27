"""Main entry point for the Polestar API client."""

from __future__ import annotations

from .auth import AuthManager, FileTokenStore, TokenStore
from .connection import GrpcConnection
from .naming import model_from_slug
from .discovery import (
    VehicleInfo,
    discover_c3_endpoint,
    get_car_information_by_vins,
    get_internet_activation,
    get_order_specification,
    get_service_plan,
    get_vehicles,
)
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
        # Discovery can return only the VIN; the app's own car-information query has the plate.
        extra = await get_car_information_by_vins(token, [i.vin for i in infos])
        for info in infos:
            found = extra.get(info.vin)
            if found is None:
                continue
            info.registration_no = info.registration_no or found.registration_no
            info.model_year = info.model_year if info.model_year is not None else found.model_year
            info.slug = found.slug
            info.pno34 = found.pno34
            info.structure_week = found.structure_week
            info.is_primary_driver = found.is_primary_driver
            info.is_bst_edition = found.is_bst_edition
        self._vehicle_cache = infos
        vehicles = [
            Vehicle(
                vin=info.vin,
                connection=self._connection,
                internal_id=info.internal_id,
                registration_no=info.registration_no,
                model_year=info.model_year,
                model_name=info.model_name,
                slug=info.slug,
                pno34=info.pno34,
                structure_week=info.structure_week,
                is_primary_driver=info.is_primary_driver,
                is_bst_edition=info.is_bst_edition,
            )
            for info in infos
        ]
        for vehicle in vehicles:
            vehicle.internet_activation = await get_internet_activation(token, vehicle.vin)
            vehicle.order_specification = await get_order_specification(token, vehicle.vin)
            vehicle.service_plan = await get_service_plan(token, vehicle.vin)
        return vehicles

    async def async_enrich_vehicle(self, vehicle: Vehicle) -> None:
        """Add the app-backend details (plate, build week, activation, order) to a vehicle.

        ``get_vehicles`` does this only for cars in the account's own list. A guest or linked car is
        created directly from its VIN, so it needs this call. Every lookup fails soft.
        """
        token = await self._auth.ensure_valid_token()
        found = (await get_car_information_by_vins(token, [vehicle.vin])).get(vehicle.vin)
        if found is not None:
            vehicle.registration_no = vehicle.registration_no or found.registration_no
            if vehicle.model_year is None:
                vehicle.model_year = found.model_year
            vehicle.slug = vehicle.slug or found.slug
            vehicle.model_name = vehicle.model_name or model_from_slug(vehicle.slug)
            vehicle.pno34 = vehicle.pno34 or found.pno34
            vehicle.structure_week = vehicle.structure_week or found.structure_week
            vehicle.is_primary_driver = found.is_primary_driver
            vehicle.is_bst_edition = found.is_bst_edition
        vehicle.internet_activation = await get_internet_activation(token, vehicle.vin)
        vehicle.order_specification = await get_order_specification(token, vehicle.vin)
        vehicle.service_plan = await get_service_plan(token, vehicle.vin)

    async def async_refresh_service_plan(self, vehicle: Vehicle) -> None:
        """Read the car's service plan again (it changes rarely; Home Assistant asks every 3 days)."""
        token = await self._auth.ensure_valid_token()
        vehicle.service_plan = await get_service_plan(token, vehicle.vin)

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
