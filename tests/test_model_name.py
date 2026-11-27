"""Model name fallback from MyCars."""

from polestar_api.models.mycars import CarDetails, MyCarEntry
from polestar_api.vehicle import Vehicle


def _vehicle(result, **kwargs):
    vehicle = Vehicle(vin="TESTVIN123", connection=object(), **kwargs)
    calls = []

    async def get_mycars():
        calls.append(True)
        if isinstance(result, Exception):
            raise result
        return result

    vehicle.get_mycars = get_mycars
    return vehicle, calls


def _entry(model_name):
    return MyCarEntry(details=CarDetails(vin="TESTVIN123", model_name=model_name))


async def test_model_name_is_filled_when_missing():
    vehicle, _ = _vehicle(_entry("Polestar 4"))

    await vehicle.async_load_model_name()

    assert vehicle.model_name == "Polestar 4"


async def test_model_name_from_discovery_is_kept():
    vehicle, calls = _vehicle(_entry("Other"), model_name="Polestar 2")

    await vehicle.async_load_model_name()

    assert vehicle.model_name == "Polestar 2"
    assert calls == []


async def test_failures_leave_the_vehicle_unchanged():
    for result in (RuntimeError("unavailable"), None, MyCarEntry(), _entry("")):
        vehicle, _ = _vehicle(result)

        await vehicle.async_load_model_name()

        assert vehicle.model_name is None
