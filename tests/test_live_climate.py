"""Seat, steering wheel and temperature changes are applied to a running climate (like the Polestar app)."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from polestar_api.models.climatization import HeatingIntensity

from .test_unsupported_entities import FakeRegistry, FakeVehicle, _coordinator, _load

OFF = HeatingIntensity.OFF
LEVEL1 = HeatingIntensity.LEVEL1
LEVEL2 = HeatingIntensity.LEVEL2
LEVEL3 = HeatingIntensity.LEVEL3


class ClimateVehicle(FakeVehicle):
    def __init__(self) -> None:
        super().__init__({})
        self.starts: list[dict] = []
        self.stops = 0

    async def start_climate(self, **kwargs):
        self.starts.append(kwargs)
        return object()

    async def stop_climate(self):
        self.stops += 1
        return object()


def _reported(**values):
    base = {
        "is_active": True,
        "target_temperature_celsius": 22.0,
        "front_left_seat": OFF,
        "front_right_seat": OFF,
        "rear_left_seat": OFF,
        "rear_right_seat": OFF,
        "steering_wheel": OFF,
    }
    base.update(values)
    return SimpleNamespace(**base)


def _climate_coordinator(monkeypatch, climate=None):
    module, _ = _load(monkeypatch, FakeRegistry())
    vehicle = ClimateVehicle()
    coordinator = _coordinator(module, vehicle)
    coordinator.vehicle = vehicle
    coordinator._climate_started_at = None
    coordinator._last_started_values = {}
    coordinator.climate_preferences = module.ClimateCommandPreferences()
    coordinator._schedule_background_refresh = lambda *attrs: None
    coordinator.data = SimpleNamespace(climate=climate)
    return coordinator, vehicle


@pytest.mark.asyncio
async def test_nothing_is_sent_when_the_climate_is_idle(monkeypatch):
    coordinator, vehicle = _climate_coordinator(monkeypatch, _reported(is_active=False))

    await coordinator.async_update_running_climate("front_left_seat")

    assert vehicle.starts == []


@pytest.mark.asyncio
async def test_only_the_changed_seat_takes_the_new_value(monkeypatch):
    climate = _reported(rear_right_seat=LEVEL2, steering_wheel=LEVEL3, target_temperature_celsius=19.5)
    coordinator, vehicle = _climate_coordinator(monkeypatch, climate)
    coordinator.climate_preferences.front_left_seat = LEVEL1
    coordinator.climate_preferences.rear_right_seat = OFF
    coordinator.climate_preferences.steering_wheel = OFF
    coordinator.climate_preferences.target_temperature = 25.0

    await coordinator.async_update_running_climate("front_left_seat")

    assert vehicle.starts == [
        {
            "temperature": 19.5,
            "front_left_seat": LEVEL1,
            "front_right_seat": OFF,
            "rear_left_seat": OFF,
            "rear_right_seat": LEVEL2,
            "steering_wheel": LEVEL3,
        }
    ]


@pytest.mark.asyncio
async def test_steering_wheel_can_be_changed_while_running(monkeypatch):
    coordinator, vehicle = _climate_coordinator(monkeypatch, _reported(front_left_seat=LEVEL1))
    coordinator.climate_preferences.steering_wheel = LEVEL3
    coordinator.climate_preferences.front_left_seat = OFF

    await coordinator.async_update_running_climate("steering_wheel")

    assert vehicle.starts[0]["steering_wheel"] == LEVEL3
    assert vehicle.starts[0]["front_left_seat"] == LEVEL1


@pytest.mark.asyncio
async def test_temperature_change_keeps_the_cars_seat_levels(monkeypatch):
    coordinator, vehicle = _climate_coordinator(monkeypatch, _reported(front_right_seat=LEVEL3))
    coordinator.climate_preferences.target_temperature = 24.0

    await coordinator.async_update_running_climate("temperature")

    assert vehicle.starts[0]["temperature"] == 24.0
    assert vehicle.starts[0]["front_right_seat"] == LEVEL3


@pytest.mark.asyncio
async def test_start_just_sent_counts_as_running_and_keeps_what_it_sent(monkeypatch):
    coordinator, vehicle = _climate_coordinator(monkeypatch, _reported(is_active=False))
    coordinator.climate_preferences.steering_wheel = LEVEL3
    coordinator.climate_preferences.front_left_seat = LEVEL2

    await coordinator.async_start_climate()
    assert coordinator.is_climate_running

    coordinator.climate_preferences.rear_left_seat = LEVEL1
    coordinator.climate_preferences.steering_wheel = OFF
    coordinator.climate_preferences.front_left_seat = OFF
    await coordinator.async_update_running_climate("rear_left_seat")

    assert len(vehicle.starts) == 2
    second = vehicle.starts[1]
    assert second["rear_left_seat"] == LEVEL1
    assert second["steering_wheel"] == LEVEL3
    assert second["front_left_seat"] == LEVEL2


@pytest.mark.asyncio
async def test_old_start_no_longer_counts_as_running(monkeypatch):
    coordinator, vehicle = _climate_coordinator(monkeypatch, _reported(is_active=False))
    coordinator._climate_started_at = time.monotonic() - 120

    await coordinator.async_update_running_climate("front_left_seat")

    assert not coordinator.is_climate_running
    assert vehicle.starts == []


@pytest.mark.asyncio
async def test_stopping_the_climate_ends_live_updates(monkeypatch):
    coordinator, vehicle = _climate_coordinator(monkeypatch, _reported(is_active=False))
    await coordinator.async_start_climate()

    await coordinator.async_stop_climate()
    await coordinator.async_update_running_climate("front_left_seat")

    assert vehicle.stops == 1
    assert len(vehicle.starts) == 1


@pytest.mark.asyncio
async def test_values_the_car_does_not_report_fall_back_to_the_stored_settings(monkeypatch):
    coordinator, vehicle = _climate_coordinator(
        monkeypatch, _reported(steering_wheel=None, target_temperature_celsius=None, rear_left_seat=LEVEL1)
    )
    coordinator.climate_preferences.steering_wheel = LEVEL3
    coordinator.climate_preferences.target_temperature = 23.0

    await coordinator.async_update_running_climate("front_left_seat")

    sent = vehicle.starts[0]
    assert sent["steering_wheel"] == LEVEL3
    assert sent["temperature"] == 23.0
    assert sent["rear_left_seat"] == LEVEL1
