"""Steering wheel heat options follow the number of levels the car reports."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from polestar_api.codec import encode, encode_message
from polestar_api.models.climatization import HeatingIntensity
from polestar_api.models.mycars import CarDetails, MyCarEntry, ParkingClimatizationCapabilities

PACKAGE = "_polestar_steering_under_test"


class FakeEntity:
    def __init__(self, coordinator) -> None:
        self.coordinator = coordinator
        self._vehicle = coordinator.vehicle

    @property
    def options(self):
        return getattr(self, "_attr_options", self.entity_description.options)

    async def async_added_to_hass(self) -> None:
        return None

    def async_write_ha_state(self) -> None:
        return None


class FakeRestoreEntity:
    last_state: str | None = None

    async def async_get_last_state(self):
        return SimpleNamespace(state=self.last_state) if self.last_state else None


class FakeDescription:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


def _stub(monkeypatch, name: str, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _load_select(monkeypatch):
    from dataclasses import dataclass

    @dataclass(frozen=True, kw_only=True)
    class SelectEntityDescription:
        key: str = ""
        name: str = ""
        icon: str | None = None
        entity_category: str | None = None
        options: list[str] | None = None

    _stub(monkeypatch, "homeassistant")
    _stub(monkeypatch, "homeassistant.components")
    _stub(
        monkeypatch,
        "homeassistant.components.select",
        SelectEntity=object,
        SelectEntityDescription=SelectEntityDescription,
    )
    _stub(monkeypatch, "homeassistant.config_entries", ConfigEntry=object)
    _stub(monkeypatch, "homeassistant.core", HomeAssistant=object)
    _stub(monkeypatch, "homeassistant.helpers")
    _stub(monkeypatch, "homeassistant.helpers.entity", EntityCategory=SimpleNamespace(CONFIG="config"))
    _stub(monkeypatch, "homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
    _stub(monkeypatch, "homeassistant.helpers.restore_state", RestoreEntity=FakeRestoreEntity)

    component = Path(__file__).parents[1] / "custom_components" / "polestar"
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(component)]
    monkeypatch.setitem(sys.modules, PACKAGE, package)
    _stub(monkeypatch, f"{PACKAGE}.const", DOMAIN="polestar")
    _stub(monkeypatch, f"{PACKAGE}.coordinator", PolestarCoordinator=object)

    class OptimisticStateMixin:
        pass

    _stub(monkeypatch, f"{PACKAGE}.entity", OptimisticStateMixin=OptimisticStateMixin, PolestarEntity=FakeEntity)

    spec = importlib.util.spec_from_file_location(f"{PACKAGE}.select", component / "select.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, f"{PACKAGE}.select", module)
    spec.loader.exec_module(module)
    return module


def _select(module, key: str, levels: int | None):
    climate = None if levels is None else ParkingClimatizationCapabilities(steering_wheel_setting_levels=levels)
    coordinator = SimpleNamespace(
        vehicle=SimpleNamespace(vin="TESTVIN123"),
        data=SimpleNamespace(mycars=MyCarEntry(details=CarDetails(parking_climatization=climate))),
        climate_preferences=SimpleNamespace(
            steering_wheel=HeatingIntensity.UNSPECIFIED, front_left_seat=HeatingIntensity.UNSPECIFIED
        ),
    )
    description = next(item for item in module.SELECTS if item.key == key)
    return module.PolestarSelect(coordinator, description)


def test_steering_wheel_levels_are_read_from_mycars():
    climate = encode({"levels": (16, "int32")}, {"levels": 1})
    details = encode_message(37, climate)

    car = CarDetails.from_bytes(details)

    assert car.parking_climatization.steering_wheel_setting_levels == 1


def test_one_level_offers_only_off_and_level3(monkeypatch):
    module = _load_select(monkeypatch)

    select = _select(module, "climate_steering_wheel", 1)

    assert select.options == ["unspecified", "off", "level3"]


@pytest.mark.parametrize("levels", [None, 0, 3])
def test_other_cars_keep_every_level(monkeypatch, levels):
    module = _load_select(monkeypatch)

    select = _select(module, "climate_steering_wheel", levels)

    assert select.options == ["unspecified", "off", "level1", "level2", "level3"]


def test_seat_selects_are_not_limited(monkeypatch):
    module = _load_select(monkeypatch)

    select = _select(module, "climate_front_left_seat", 1)

    assert "level1" in select.options


@pytest.mark.asyncio
async def test_a_restored_lower_level_becomes_level3(monkeypatch):
    module = _load_select(monkeypatch)
    select = _select(module, "climate_steering_wheel", 1)
    select.last_state = "level2"

    await select.async_added_to_hass()

    assert select.coordinator.climate_preferences.steering_wheel == HeatingIntensity.LEVEL3
    assert select.current_option == "level3"
