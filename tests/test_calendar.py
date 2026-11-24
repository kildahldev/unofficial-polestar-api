"""Tests for the parking climate timer calendar entity."""

from __future__ import annotations

import enum
import importlib.util
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from polestar_api.models.common import Weekday
from polestar_api.models.parking_climate_timer import ParkingClimateTimer

# Keys Home Assistant uses when it passes calendar events to an entity
EVENT_START = "dtstart"
EVENT_END = "dtend"
EVENT_RRULE = "rrule"
EVENT_SUMMARY = "summary"


class FakeCalendarEntityFeature(enum.IntFlag):
    CREATE_EVENT = 1
    DELETE_EVENT = 2
    UPDATE_EVENT = 4


class FakeHomeAssistantError(Exception):
    """Test stand-in for Home Assistant's service error."""


class FakeEntity:
    def __init__(self, coordinator) -> None:
        self.coordinator = coordinator
        self._vehicle = coordinator.vehicle


class FakeCoordinator:
    def __init__(self, timers: tuple[ParkingClimateTimer, ...] = ()) -> None:
        self.vehicle = SimpleNamespace(vin="TESTVIN123")
        self.data = SimpleNamespace(climate_timers=list(timers))
        self.set_timers: list[ParkingClimateTimer] = []

    async def async_set_climate_timer(self, timer: ParkingClimateTimer) -> int:
        self.set_timers.append(timer)
        return 1


def _stub_module(monkeypatch, name: str, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _load_calendar(monkeypatch):
    _stub_module(monkeypatch, "dateutil")
    _stub_module(monkeypatch, "dateutil.rrule", DAILY=3, WEEKLY=2, rrulestr=None)
    _stub_module(monkeypatch, "homeassistant")
    _stub_module(monkeypatch, "homeassistant.components")
    _stub_module(
        monkeypatch,
        "homeassistant.components.calendar",
        EVENT_RRULE=EVENT_RRULE,
        EVENT_START=EVENT_START,
        CalendarEntity=object,
        CalendarEntityFeature=FakeCalendarEntityFeature,
        CalendarEvent=lambda **kwargs: SimpleNamespace(**kwargs),
    )
    _stub_module(monkeypatch, "homeassistant.config_entries", ConfigEntry=object)
    _stub_module(monkeypatch, "homeassistant.core", HomeAssistant=object)
    _stub_module(monkeypatch, "homeassistant.exceptions", HomeAssistantError=FakeHomeAssistantError)
    _stub_module(monkeypatch, "homeassistant.helpers")
    _stub_module(monkeypatch, "homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
    _stub_module(
        monkeypatch,
        "homeassistant.util",
        dt=SimpleNamespace(DEFAULT_TIME_ZONE=timezone.utc, as_local=lambda value: value),
    )

    package_name = "_polestar_calendar_under_test"
    component_dir = Path(__file__).parents[1] / "custom_components" / "polestar"
    package = types.ModuleType(package_name)
    package.__path__ = [str(component_dir)]
    monkeypatch.setitem(sys.modules, package_name, package)
    _stub_module(monkeypatch, f"{package_name}.const", DOMAIN="polestar")
    _stub_module(monkeypatch, f"{package_name}.coordinator", PolestarCoordinator=FakeCoordinator)
    _stub_module(monkeypatch, f"{package_name}.entity", PolestarEntity=FakeEntity)
    _stub_module(monkeypatch, f"{package_name}.utils", serialize_parking_climate_timer=lambda timer: {})

    spec = importlib.util.spec_from_file_location(f"{package_name}.calendar", component_dir / "calendar.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def _event(start: datetime) -> dict[str, object]:
    return {EVENT_START: start, EVENT_END: start + timedelta(minutes=1), EVENT_SUMMARY: "Departure"}


@pytest.mark.asyncio
async def test_create_event_reads_home_assistant_start_key(monkeypatch):
    calendar = _load_calendar(monkeypatch)
    coordinator = FakeCoordinator()
    entity = calendar.PolestarParkingClimateTimerCalendar(coordinator, 2)

    # Tuesday 21:40
    await entity.async_create_event(**_event(datetime(2026, 11, 3, 21, 40, tzinfo=timezone.utc)))

    assert coordinator.set_timers == [
        ParkingClimateTimer(
            timer_id="",
            index=2,
            ready_at_hour=21,
            ready_at_minute=40,
            activated=True,
            repeat=False,
            weekdays=(Weekday.TUESDAY,),
        )
    ]


@pytest.mark.asyncio
async def test_update_event_reads_home_assistant_start_key(monkeypatch):
    calendar = _load_calendar(monkeypatch)
    existing = ParkingClimateTimer(timer_id="timer-1", index=0, ready_at_hour=7, ready_at_minute=35)
    coordinator = FakeCoordinator((existing,))
    entity = calendar.PolestarParkingClimateTimerCalendar(coordinator, 0)

    # Friday 08:15
    await entity.async_update_event("timer-1", _event(datetime(2026, 11, 6, 8, 15, tzinfo=timezone.utc)))

    assert coordinator.set_timers == [
        ParkingClimateTimer(
            timer_id="timer-1",
            index=0,
            ready_at_hour=8,
            ready_at_minute=15,
            activated=True,
            repeat=False,
            weekdays=(Weekday.FRIDAY,),
        )
    ]
