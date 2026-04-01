"""Service discovery for Polestar gRPC endpoints and vehicle listing."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from .exceptions import ApiError

C3_DISCOVERY_URL = "https://cnepmob.volvocars.com/"
C3_ACCEPT_HEADER = "application/volvo.cloud.cnepmob.v1+json"

MYSTAR_V2_URL = "https://pc-api.polestar.com/eu-north-1/mystar-v2/"

GET_VEHICLES_QUERY = """
query GetConsumerCarsV2 {
    getConsumerCarsV2 {
        vin
        internalVehicleIdentifier
        registrationNo
        modelYear
        content { model { name } }
    }
}
"""


@dataclass
class GrpcEndpoint:
    host: str
    port: int
    keep_alive_time: int | None = None


@dataclass
class VehicleInfo:
    vin: str
    internal_id: str | None = None
    registration_no: str | None = None
    model_year: int | None = None
    model_name: str | None = None


async def discover_c3_endpoint(access_token: str) -> GrpcEndpoint:
    """Discover the C3 gRPC endpoint via the Volvo Cloud discovery service."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            C3_DISCOVERY_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": C3_ACCEPT_HEADER,
            },
        )
        if r.status_code != 200:
            raise ApiError(f"C3 discovery failed: {r.status_code}", r.status_code)

        data = r.json()

    # The response contains c3 and c3Lbs environments
    c3 = data.get("c3", {})
    host = c3.get("grpcHost")
    port = c3.get("grpcPort", 443)
    keep_alive = c3.get("grpcKeepAliveTime")

    if not host:
        raise ApiError("C3 discovery response missing grpcHost")

    return GrpcEndpoint(host=host, port=int(port), keep_alive_time=keep_alive)


async def get_vehicles(access_token: str) -> list[VehicleInfo]:
    """Fetch the user's vehicles via MyStarV2 GraphQL."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            MYSTAR_V2_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"query": GET_VEHICLES_QUERY},
        )
        if r.status_code != 200:
            raise ApiError(f"Vehicle list failed: {r.status_code}", r.status_code)

        data = r.json()

    cars = data.get("data", {}).get("getConsumerCarsV2", [])
    vehicles = []
    for car in cars:
        content = car.get("content") or {}
        model = content.get("model") or {}
        vehicles.append(
            VehicleInfo(
                vin=car["vin"],
                internal_id=car.get("internalVehicleIdentifier"),
                registration_no=car.get("registrationNo"),
                model_year=car.get("modelYear"),
                model_name=model.get("name"),
            )
        )

    return vehicles
