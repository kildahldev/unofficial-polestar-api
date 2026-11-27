"""Service discovery for Polestar gRPC endpoints and vehicle listing."""

from __future__ import annotations

import ssl
import uuid
from dataclasses import dataclass
from typing import Any

import logging

import httpx

from .exceptions import ApiError

_LOGGER = logging.getLogger(__name__)

_SSL_CONTEXT = ssl.create_default_context()

C3_DISCOVERY_URL = "https://cnepmob.volvocars.com/"
C3_ACCEPT_HEADER = "application/volvo.cloud.cnepmob.v1+json"

APP_BACKEND_GRAPHQL_URL = "https://pc-api.polestar.com/eu-north-1/app-backend/api/graphql"
APP_BACKEND_ACCEPT_HEADER = "multipart/mixed;deferSpec=20220824, application/graphql-response+json, application/json"
APP_BACKEND_OPERATION_NAME = "GetVDMSCars"
APP_BACKEND_CLIENT_LIBRARY = {"name": "apollo-kotlin", "version": "4.4.1"}
APP_FORCE_UPDATE_VERSION = "5.15.1"
APP_LOCALE = "SE"
APP_USER_AGENT = "PolestarApp/5.15.1b9417 Android/14"

APP_BACKEND_GET_VEHICLES_QUERY = """
query GetVDMSCars {
    vdms {
        getVehiclesInformation {
            vin
            internalVehicleIdentifier
            registrationNo
            modelYear
            content { model { name } }
        }
    }
}
"""

APP_BACKEND_CAR_INFO_OPERATION_NAME = "CarInformationByVins"
APP_BACKEND_CAR_INFO_QUERY = (
    "query CarInformationByVins($input: CarInformationByVinsInput) { cars { "
    "carInformationByVins(input: $input) { isBstEdition isPrimaryDriver modelYear pno34 "
    "registrationNumber slug structureWeek vin } } }"
)
APP_BACKEND_INTERNET_ACTIVATION_QUERY = (
    "query InternetActivationStatus($vin: String!) { internetActivation { "
    "status(vin: $vin) { mnoStatus timestamp } } }"
)
# Order details (no prices, postcode or order id) matched to a car by its VIN.
# The car's service plan (prepaid service contract), as the Polestar app's Service screen reads it. Empty for
# many accounts (an Australian fleet order, Nov 2026); a UK-market account returned a plan with three products.
APP_BACKEND_SERVICE_PLAN_QUERY = (
    "query PolestarServicePlansForVin($vin: String!) { servicePlan { getServicePlan(vin: $vin) { "
    "name mileageUnit status productStatus products { name startDate endDate mileage } } } }"
)
APP_BACKEND_ORDERS_QUERY = (
    "query GetOrdersV2 { poms { getOrders { data { car { edition engine exterior interior model "
    "modelYear vin wheels } orderV2 { configuration { specifications { label value } "
    "features { displayType title } } } } } } }"
)


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
    slug: str | None = None
    pno34: str | None = None
    structure_week: str | None = None
    is_primary_driver: bool | None = None
    is_bst_edition: bool | None = None


async def discover_c3_endpoint(access_token: str) -> GrpcEndpoint:
    """Discover the C3 gRPC endpoint via the Volvo Cloud discovery service."""
    async with httpx.AsyncClient(verify=_SSL_CONTEXT, timeout=30) as client:
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
    """Fetch the user's vehicles.

    The current mobile app uses the app-backend GraphQL endpoint with the
    X-PolestarId-Authorization header and Apollo-style request metadata.
    """
    async with httpx.AsyncClient(verify=_SSL_CONTEXT, timeout=30) as client:
        response = await client.post(
            APP_BACKEND_GRAPHQL_URL,
            headers={
                **_app_backend_headers(access_token),
                "Accept": APP_BACKEND_ACCEPT_HEADER,
                "Content-Type": "application/json",
            },
            json=_app_backend_payload(),
        )
        if response.status_code != 200:
            raise ApiError(f"Vehicle list failed (app-backend: {_http_failure(response)})", response.status_code)

        data = response.json()
        graphql_error = _graphql_error_text(data.get("errors"))
        if graphql_error:
            raise ApiError(f"Vehicle list failed (app-backend: {graphql_error})")

        return _extract_app_backend_vehicles(data)


async def get_car_information_by_vins(access_token: str, vins: list[str]) -> dict[str, VehicleInfo]:
    """Look up the registration plate and model year for ``vins``.

    This is the query the mobile app uses for its Specifications screen. Account discovery
    (``GetVDMSCars``) can return only the VIN for secondary or guest accounts, and the C3
    car-information service has no plate, but this query does. Any failure returns ``{}``.
    """
    if not vins:
        return {}
    headers = {
        **_app_backend_headers(access_token),
        "X-APOLLO-OPERATION-NAME": APP_BACKEND_CAR_INFO_OPERATION_NAME,
        "Accept": APP_BACKEND_ACCEPT_HEADER,
        "Content-Type": "application/json",
    }
    payload = {
        "operationName": APP_BACKEND_CAR_INFO_OPERATION_NAME,
        "variables": {"input": {"vins": vins}},
        "query": APP_BACKEND_CAR_INFO_QUERY,
        "extensions": {"clientLibrary": APP_BACKEND_CLIENT_LIBRARY},
    }
    try:
        async with httpx.AsyncClient(verify=_SSL_CONTEXT, timeout=30) as client:
            response = await client.post(APP_BACKEND_GRAPHQL_URL, headers=headers, json=payload)
        if response.status_code != 200:
            _log_app_backend_failure(APP_BACKEND_CAR_INFO_OPERATION_NAME, response.status_code)
            return {}
        data = response.json()
    except (httpx.HTTPError, ValueError) as err:
        _log_app_backend_failure(APP_BACKEND_CAR_INFO_OPERATION_NAME, None, error=err)
        return {}
    if not isinstance(data, dict) or data.get("errors"):
        _log_app_backend_failure(APP_BACKEND_CAR_INFO_OPERATION_NAME, 200, (data or {}).get("errors") if isinstance(data, dict) else None)
        return {}
    return _extract_car_information_by_vins(data)



def _log_app_backend_failure(operation: str, status: int | None, errors: Any = None, error: Exception | None = None) -> None:
    """One warning when an app-backend query fails (no tokens or personal data in the message)."""
    if error is not None:
        detail = type(error).__name__
    elif status is not None and status != 200:
        detail = f"HTTP {status}"
    else:
        messages = [e.get("message") for e in errors if isinstance(e, dict)] if isinstance(errors, list) else []
        detail = f"GraphQL errors: {messages[:2]}"
    _LOGGER.warning("Polestar app-backend query %s failed (%s); its details (plate, build week, ...) will be missing", operation, detail)


def _extract_car_information_by_vins(data: dict[str, Any]) -> dict[str, VehicleInfo]:
    cars = (((data.get("data") or {}).get("cars") or {}).get("carInformationByVins")) or []
    result: dict[str, VehicleInfo] = {}
    for car in cars:
        if not isinstance(car, dict):
            continue
        vin = car.get("vin")
        if not isinstance(vin, str) or not vin:
            continue
        result[vin] = VehicleInfo(
            vin=vin,
            registration_no=_string_or_none(car.get("registrationNumber")),
            model_year=_parse_model_year(car.get("modelYear")),
            slug=_string_or_none(car.get("slug")),
            pno34=_string_or_none(car.get("pno34")),
            structure_week=_string_or_none(car.get("structureWeek")),
            is_primary_driver=car.get("isPrimaryDriver") if isinstance(car.get("isPrimaryDriver"), bool) else None,
            is_bst_edition=car.get("isBstEdition") if isinstance(car.get("isBstEdition"), bool) else None,
        )
    return result


async def _app_backend_query(
    access_token: str, operation: str, query: str, variables: dict[str, Any]
) -> dict[str, Any] | None:
    """Run a read-only app-backend GraphQL query. Returns the ``data`` object, or ``None`` on any failure."""
    headers = {
        **_app_backend_headers(access_token),
        "X-APOLLO-OPERATION-NAME": operation,
        "Accept": APP_BACKEND_ACCEPT_HEADER,
        "Content-Type": "application/json",
    }
    payload = {
        "operationName": operation,
        "variables": variables,
        "query": query,
        "extensions": {"clientLibrary": APP_BACKEND_CLIENT_LIBRARY},
    }
    try:
        async with httpx.AsyncClient(verify=_SSL_CONTEXT, timeout=30) as client:
            response = await client.post(APP_BACKEND_GRAPHQL_URL, headers=headers, json=payload)
        if response.status_code != 200:
            _log_app_backend_failure(operation, response.status_code)
            return None
        data = response.json()
    except (httpx.HTTPError, ValueError) as err:
        _log_app_backend_failure(operation, None, error=err)
        return None
    if not isinstance(data, dict) or data.get("errors"):
        _log_app_backend_failure(operation, 200, data.get("errors") if isinstance(data, dict) else None)
        return None
    result = data.get("data")
    return result if isinstance(result, dict) else None


async def get_internet_activation(access_token: str, vin: str) -> dict[str, str | None] | None:
    """The car's mobile-network activation status: ``{"status": ..., "timestamp": ...}``, or ``None``."""
    data = await _app_backend_query(
        access_token, "InternetActivationStatus", APP_BACKEND_INTERNET_ACTIVATION_QUERY, {"vin": vin}
    )
    status = (((data or {}).get("internetActivation") or {}).get("status")) or None
    if not isinstance(status, dict):
        return None
    return {"status": _string_or_none(status.get("mnoStatus")), "timestamp": _string_or_none(status.get("timestamp"))}


async def get_order_specification(access_token: str, vin: str) -> dict[str, Any] | None:
    """The order details (engine, colour, interior, wheels, specifications) of the car with ``vin``."""
    data = await _app_backend_query(access_token, "GetOrdersV2", APP_BACKEND_ORDERS_QUERY, {})
    orders = ((((data or {}).get("poms") or {}).get("getOrders") or {}).get("data")) or []
    for order in orders:
        car = (order or {}).get("car") if isinstance(order, dict) else None
        if not isinstance(car, dict) or car.get("vin") != vin:
            continue
        config = ((order.get("orderV2") or {}).get("configuration")) or {}
        return {
            "edition": car.get("edition"),
            "engine": car.get("engine"),
            "exterior": car.get("exterior"),
            "interior": car.get("interior"),
            "wheels": car.get("wheels"),
            "specifications": {
                str(i.get("label")): i.get("value") for i in config.get("specifications") or [] if isinstance(i, dict)
            },
            "features": [i.get("title") for i in config.get("features") or [] if isinstance(i, dict)],
        }
    return None


def _extract_app_backend_vehicles(data: dict[str, Any]) -> list[VehicleInfo]:
    """Parse vehicles from the app-backend GraphQL response."""
    cars = ((data.get("data") or {}).get("vdms") or {}).get("getVehiclesInformation") or []
    return _build_vehicle_list(cars)


def _app_backend_headers(access_token: str) -> dict[str, str]:
    """Return the headers the mobile app adds around GraphQL calls."""
    return {
        "User-Agent": APP_USER_AGENT,
        "X-Polestar-Force-Update-Version": APP_FORCE_UPDATE_VERSION,
        "X-Polestar-Locale": APP_LOCALE,
        "X-PolestarId-Authorization": f"Bearer {access_token}",
        "X-APOLLO-OPERATION-NAME": APP_BACKEND_OPERATION_NAME,
        "X-APOLLO-REQUEST-UUID": str(uuid.uuid4()),
    }


def _app_backend_payload() -> dict[str, Any]:
    """Return the POST body Apollo sends for the vehicle discovery query."""
    return {
        "operationName": APP_BACKEND_OPERATION_NAME,
        "variables": {},
        "query": APP_BACKEND_GET_VEHICLES_QUERY,
        "extensions": {"clientLibrary": APP_BACKEND_CLIENT_LIBRARY},
    }


def _build_vehicle_list(cars: list[Any]) -> list[VehicleInfo]:
    """Normalize GraphQL vehicle records into VehicleInfo objects."""
    vehicles: list[VehicleInfo] = []
    for car in cars:
        if not isinstance(car, dict):
            continue
        vin = car.get("vin")
        if not isinstance(vin, str) or not vin:
            continue

        content = car.get("content") or {}
        model = content.get("model") if isinstance(content, dict) else {}
        model_name = model.get("name") if isinstance(model, dict) else None
        vehicles.append(
            VehicleInfo(
                vin=vin,
                internal_id=_string_or_none(car.get("internalVehicleIdentifier")),
                registration_no=_string_or_none(car.get("registrationNo")),
                model_year=_parse_model_year(car.get("modelYear")),
                model_name=_string_or_none(model_name),
            )
        )
    return vehicles


def _graphql_error_text(errors: object) -> str | None:
    """Return a compact GraphQL error summary."""
    if not isinstance(errors, list) or not errors:
        return None

    messages = []
    for error in errors:
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                messages.append(message)

    if messages:
        return "; ".join(messages)
    return "graphql error"


def _http_failure(response: httpx.Response) -> str:
    """Return a compact HTTP failure summary including body message when present."""
    detail: str | None = None
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        if text:
            detail = text.replace("\n", " ")[:200]
    else:
        if isinstance(payload, dict):
            detail = _graphql_error_text(payload.get("errors"))
            if detail is None:
                for key in ("message", "error", "detail"):
                    value = payload.get(key)
                    if isinstance(value, str) and value:
                        detail = value
                        break

    if detail:
        return f"{response.status_code} ({detail})"
    return str(response.status_code)


def _parse_model_year(value: object) -> int | None:
    """Normalize model year strings to integers when possible."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _string_or_none(value: object) -> str | None:
    """Return strings unchanged and coerce everything else to None."""
    return value if isinstance(value, str) and value else None


def _date_only(value: Any) -> str | None:
    """``2030-10-28T00:00:00+00:00`` -> ``2030-10-28`` (the plan's dates are whole days)."""
    text = _string_or_none(value)
    return text[:10] if text else None


async def get_service_plan(access_token: str, vin: str) -> dict[str, Any] | None:
    """The car's service plan: name, status, mileage unit and products, or ``None`` when there is none.

    Only the first plan is returned in full; ``other_plans`` names any others. No ids or VIN are kept.
    """
    data = await _app_backend_query(access_token, "PolestarServicePlansForVin", APP_BACKEND_SERVICE_PLAN_QUERY, {"vin": vin})
    plans = [p for p in (((data or {}).get("servicePlan") or {}).get("getServicePlan") or []) if isinstance(p, dict)]
    if not plans:
        return None
    plan = plans[0]
    products = [
        {
            "name": _string_or_none(p.get("name")),
            "start": _date_only(p.get("startDate")),
            "end": _date_only(p.get("endDate")),
            "mileage": p.get("mileage") if isinstance(p.get("mileage"), (int, float)) else None,
        }
        for p in plan.get("products") or []
        if isinstance(p, dict)
    ]
    return {
        "name": _string_or_none(plan.get("name")),
        "status": _string_or_none(plan.get("status")),
        "product_status": _string_or_none(plan.get("productStatus")),
        "mileage_unit": _string_or_none(plan.get("mileageUnit")),
        "products": products,
        "other_plans": [_string_or_none(p.get("name")) for p in plans[1:]],
    }
