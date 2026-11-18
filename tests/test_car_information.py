"""Tests for the MyCars car information service and the vehicle details it fills in."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from polestar_api.codec import encode, encode_message
from polestar_api.models.car_information import MyCar
from polestar_api.services import car_information as service_module
from polestar_api.services.car_information import CarInformationServiceClient
from polestar_api.vehicle import Vehicle

CAR_SCHEMA = {
    "vin": (1, "string"),
    "code": (5, "string"),
    "name": (6, "string"),
    "year": (7, "string"),
    "software": (9, "string"),
    "market": (10, "string"),
}
MY_CAR_SCHEMA = {"linked": (2, "bool"), "owner": (3, "bool"), "plate": (4, "string")}


def _my_car(
    vin: str, name: str, *, plate: str | None = None, year: str = "2025", charging: bytes | None = None
) -> bytes:
    car = encode(
        CAR_SCHEMA,
        {"vin": vin, "code": "814", "name": name, "year": year, "software": "4.2.11", "market": "AU"},
    )
    if charging is not None:
        car += encode_message(35, charging)
    values = {"linked": True, "owner": True}
    if plate is not None:
        values["plate"] = plate
    return encode_message(1, car) + encode(MY_CAR_SCHEMA, values)


def _response(*my_cars: bytes) -> bytes:
    return b"".join(encode_message(1, my_car) for my_car in my_cars)


class FakeConnection:
    channel = object()
    backend = SimpleNamespace(car_information_svc="/car_information.CarInformation")

    async def get_metadata(self, vin=None):
        return {}


def _client(monkeypatch, response: bytes, calls: list | None = None) -> CarInformationServiceClient:
    async def fake_unary_unary(channel, method, request, **kwargs):
        if calls is not None:
            calls.append((method, request))
        return response

    monkeypatch.setattr(service_module.grpc_call, "unary_unary", fake_unary_unary)
    return CarInformationServiceClient(FakeConnection(), "VIN0000000000001")


@pytest.mark.asyncio
async def test_decodes_a_single_car(monkeypatch):
    calls: list = []
    client = _client(monkeypatch, _response(_my_car("VIN0000000000001", "Polestar 4", plate="ABC123")), calls)

    cars = await client.get_my_cars()

    assert calls == [("/car_information.CarInformation/GetMyCars", b"")]
    assert len(cars) == 1
    assert isinstance(cars[0], MyCar)
    assert cars[0].car.vin == "VIN0000000000001"
    assert cars[0].car.vehicle_type_name == "Polestar 4"
    assert cars[0].car.vehicle_type_code == "814"
    assert cars[0].car.model_year == "2025"
    assert cars[0].car.market == "AU"
    assert cars[0].car.consumer_software_version == "4.2.11"
    assert cars[0].registration_plate == "ABC123"
    assert cars[0].user_is_owner


@pytest.mark.asyncio
async def test_decodes_several_cars_and_picks_ours_by_vin(monkeypatch):
    client = _client(
        monkeypatch,
        _response(_my_car("OTHERVIN000000001", "Polestar 2"), _my_car("VIN0000000000001", "Polestar 4")),
    )

    assert len(await client.get_my_cars()) == 2
    assert (await client.get_my_car()).car.vehicle_type_name == "Polestar 4"


@pytest.mark.asyncio
async def test_returns_none_when_the_vin_is_not_on_the_account(monkeypatch):
    client = _client(monkeypatch, _response(_my_car("OTHERVIN000000001", "Polestar 2")))

    assert await client.get_my_car() is None


@pytest.mark.asyncio
async def test_empty_response_means_no_cars(monkeypatch):
    client = _client(monkeypatch, b"")

    assert await client.get_my_cars() == []


def _vehicle(monkeypatch, response: bytes, **details) -> Vehicle:
    monkeypatch.setattr(service_module.grpc_call, "unary_unary", _fixed(response))
    return Vehicle(vin="VIN0000000000001", connection=FakeConnection(), **details)


def _fixed(response: bytes):
    async def fake_unary_unary(channel, method, request, **kwargs):
        return response

    return fake_unary_unary


@pytest.mark.asyncio
async def test_vehicle_without_details_gets_them_from_car_information(monkeypatch):
    vehicle = _vehicle(monkeypatch, _response(_my_car("VIN0000000000001", "Polestar 4", plate="ABC123")))

    await vehicle.async_load_car_information()

    assert vehicle.model_name == "Polestar 4"
    assert vehicle.model_year == 2025
    assert vehicle.registration_no == "ABC123"


@pytest.mark.asyncio
async def test_details_from_discovery_are_kept(monkeypatch):
    vehicle = _vehicle(
        monkeypatch,
        _response(_my_car("VIN0000000000001", "Polestar 4", plate="ABC123")),
        model_name="Discovery name",
        model_year=2024,
        registration_no="XYZ789",
    )

    await vehicle.async_load_car_information()

    assert vehicle.model_name == "Discovery name"
    assert vehicle.model_year == 2024
    assert vehicle.registration_no == "XYZ789"


@pytest.mark.asyncio
async def test_a_missing_registration_stays_none(monkeypatch):
    vehicle = _vehicle(monkeypatch, _response(_my_car("VIN0000000000001", "Polestar 4")))

    await vehicle.async_load_car_information()

    assert vehicle.model_name == "Polestar 4"
    assert vehicle.registration_no is None


@pytest.mark.asyncio
async def test_failure_leaves_the_vehicle_unchanged(monkeypatch):
    async def failing(channel, method, request, **kwargs):
        raise ConnectionError("unreachable")

    monkeypatch.setattr(service_module.grpc_call, "unary_unary", failing)
    vehicle = Vehicle(vin="VIN0000000000001", connection=FakeConnection())

    await vehicle.async_load_car_information()

    assert vehicle.model_name is None
    assert vehicle.model_year is None
    assert vehicle.registration_no is None


# What the car reports under "charging": a global charge timer (field 11) but no per-location limit (field 16).
GLOBAL_TIMER_ONLY = encode({"global_timer": (11, "bool"), "type": (10, "int32")}, {"global_timer": True, "type": 2})
WITH_LOCATIONS = encode({"max_locations": (16, "int32")}, {"max_locations": 5})


@pytest.mark.asyncio
async def test_car_without_a_location_limit_has_no_charge_locations(monkeypatch):
    vehicle = _vehicle(monkeypatch, _response(_my_car("VIN0000000000001", "Polestar 4", charging=GLOBAL_TIMER_ONLY)))

    await vehicle.async_load_car_information()

    assert vehicle.supports_charge_locations is False


@pytest.mark.asyncio
async def test_car_with_a_location_limit_supports_charge_locations(monkeypatch):
    vehicle = _vehicle(monkeypatch, _response(_my_car("VIN0000000000001", "Polestar 2", charging=WITH_LOCATIONS)))

    await vehicle.async_load_car_information()

    assert vehicle.supports_charge_locations is True


@pytest.mark.asyncio
async def test_unknown_when_the_car_reports_no_charging_block(monkeypatch):
    vehicle = _vehicle(monkeypatch, _response(_my_car("VIN0000000000001", "Polestar 4")))

    await vehicle.async_load_car_information()

    assert vehicle.supports_charge_locations is None


# The "locks" block of a Polestar 4: lock type, unlock type and trunk unlock, but no window or sunroof control.
LOCKS_WITHOUT_WINDOWS = encode({"lock_type": (1, "int32"), "unlock_type": (2, "int32"), "trunk": (10, "bool")}, {"lock_type": 2, "unlock_type": 3, "trunk": True})
LOCKS_WITH_WINDOWS = encode({"windows": (5, "bool"), "sunroof": (6, "bool")}, {"windows": True, "sunroof": True})


def _my_car_with_locks(locks: bytes) -> bytes:
    car = encode(CAR_SCHEMA, {"vin": "VIN0000000000001", "name": "Polestar 4"}) + encode_message(36, locks)
    return encode_message(1, car) + encode(MY_CAR_SCHEMA, {"owner": True})


@pytest.mark.asyncio
async def test_car_without_window_and_sunroof_control_is_detected(monkeypatch):
    vehicle = _vehicle(monkeypatch, _response(_my_car_with_locks(LOCKS_WITHOUT_WINDOWS)))

    await vehicle.async_load_car_information()

    assert vehicle.supports_window_control is False
    assert vehicle.supports_sunroof_control is False


@pytest.mark.asyncio
async def test_car_with_window_and_sunroof_control_is_detected(monkeypatch):
    vehicle = _vehicle(monkeypatch, _response(_my_car_with_locks(LOCKS_WITH_WINDOWS)))

    await vehicle.async_load_car_information()

    assert vehicle.supports_window_control is True
    assert vehicle.supports_sunroof_control is True


@pytest.mark.asyncio
async def test_window_and_sunroof_support_is_unknown_without_a_locks_block(monkeypatch):
    vehicle = _vehicle(monkeypatch, _response(_my_car("VIN0000000000001", "Polestar 4")))

    await vehicle.async_load_car_information()

    assert vehicle.supports_window_control is None
    assert vehicle.supports_sunroof_control is None


# What a Polestar 4 reports: consumption since the last trip but not overall or since charge, no target
# charge level presets, one parking climate timer and no rear seat settings.
CHARGING_NO_PRESETS = encode_message(8, encode({"settings": (1, "bool"), "min": (2, "int32")}, {"settings": True, "min": 50}))
CLIMATE_ONE_TIMER = encode({"front": (8, "bool")}, {"front": True}) + encode_message(
    13, encode({"repeated": (2, "bool"), "max": (7, "int32")}, {"repeated": True, "max": 1})
)
LAST_TRIP_ONLY = encode({"last_trip": (48, "bool")}, {"last_trip": True})


def _capable_car(*, flat: bytes = b"", charging: bytes | None = None, climate: bytes | None = None) -> bytes:
    car = encode(CAR_SCHEMA, {"vin": "VIN0000000000001", "name": "Polestar 4"}) + flat
    if charging is not None:
        car += encode_message(35, charging)
    if climate is not None:
        car += encode_message(37, climate)
    return encode_message(1, car) + encode(MY_CAR_SCHEMA, {"owner": True})


@pytest.mark.asyncio
async def test_capabilities_of_a_polestar_4_are_read(monkeypatch):
    response = _response(_capable_car(flat=LAST_TRIP_ONLY, charging=CHARGING_NO_PRESETS, climate=CLIMATE_ONE_TIMER))
    vehicle = _vehicle(monkeypatch, response)

    await vehicle.async_load_car_information()

    assert vehicle.reports_avg_consumption is False
    assert vehicle.reports_avg_consumption_auto is True
    assert vehicle.reports_avg_consumption_since_charge is False
    assert vehicle.supports_target_soc_presets is False
    assert vehicle.supports_rear_seat_heating is False
    assert vehicle.max_climate_timers == 1


@pytest.mark.asyncio
async def test_a_car_that_supports_everything_is_detected(monkeypatch):
    everything = encode({"a": (20, "bool"), "b": (48, "bool"), "c": (49, "bool")}, {"a": True, "b": True, "c": True})
    charging = encode_message(8, encode({"presets": (3, "bool")}, {"presets": True}))
    climate = encode({"rear": (9, "bool")}, {"rear": True}) + encode_message(13, encode({"max": (7, "int32")}, {"max": 3}))
    vehicle = _vehicle(monkeypatch, _response(_capable_car(flat=everything, charging=charging, climate=climate)))

    await vehicle.async_load_car_information()

    assert vehicle.reports_avg_consumption is True
    assert vehicle.reports_avg_consumption_since_charge is True
    assert vehicle.supports_target_soc_presets is True
    assert vehicle.supports_rear_seat_heating is True
    assert vehicle.max_climate_timers == 3


@pytest.mark.asyncio
async def test_climate_timer_limit_is_zero_when_the_car_reports_no_timers(monkeypatch):
    vehicle = _vehicle(monkeypatch, _response(_capable_car(climate=encode({"front": (8, "bool")}, {"front": True}))))

    await vehicle.async_load_car_information()

    assert vehicle.max_climate_timers == 0
    assert vehicle.supports_rear_seat_heating is False


@pytest.mark.asyncio
async def test_target_charge_presets_unknown_without_a_settings_block(monkeypatch):
    vehicle = _vehicle(monkeypatch, _response(_capable_car(charging=encode({"max": (16, "int32")}, {"max": 4}))))

    await vehicle.async_load_car_information()

    assert vehicle.supports_target_soc_presets is None
