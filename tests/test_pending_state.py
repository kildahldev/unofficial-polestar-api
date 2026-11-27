"""Lock and optimistic states stay until the car confirms them or they time out."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

PACKAGE = "_polestar_pending_under_test"


class FakeEntity:
    hass = None

    def __class_getitem__(cls, item):
        return cls

    def __init__(self, coordinator) -> None:
        self.coordinator = coordinator

    def async_write_ha_state(self) -> None:
        self.writes = getattr(self, "writes", 0) + 1

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        return None


class Timers:
    def __init__(self) -> None:
        self.scheduled: list[tuple[float, object]] = []
        self.cancelled = 0

    def call_later(self, hass, delay, action):
        self.scheduled.append((delay, action))

        def cancel() -> None:
            self.cancelled += 1

        return cancel


def _stub(monkeypatch, name: str, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _load(monkeypatch):
    timers = Timers()
    _stub(monkeypatch, "homeassistant")
    _stub(monkeypatch, "homeassistant.components")
    _stub(monkeypatch, "homeassistant.components.lock", LockEntity=object)
    _stub(monkeypatch, "homeassistant.config_entries", ConfigEntry=object)
    _stub(monkeypatch, "homeassistant.core", HomeAssistant=object, callback=lambda func: func)
    _stub(monkeypatch, "homeassistant.helpers")
    _stub(monkeypatch, "homeassistant.helpers.device_registry", DeviceInfo=dict)
    _stub(monkeypatch, "homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
    _stub(monkeypatch, "homeassistant.helpers.event", async_call_later=timers.call_later)
    _stub(monkeypatch, "homeassistant.helpers.update_coordinator", CoordinatorEntity=FakeEntity)

    component = Path(__file__).parents[1] / "custom_components" / "polestar"
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(component)]
    monkeypatch.setitem(sys.modules, PACKAGE, package)
    _stub(monkeypatch, f"{PACKAGE}.const", DOMAIN="polestar")
    _stub(monkeypatch, f"{PACKAGE}.coordinator", PolestarCoordinator=object)

    modules = []
    for name in ("entity", "lock"):
        spec = importlib.util.spec_from_file_location(f"{PACKAGE}.{name}", component / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, f"{PACKAGE}.{name}", module)
        spec.loader.exec_module(module)
        modules.append(module)
    return (*modules, timers)


def _lock(module, *, locked: bool, error: Exception | None = None):
    exterior = SimpleNamespace(is_locked=locked)

    async def run_command(command, **kwargs):
        if error is not None:
            raise error

    coordinator = SimpleNamespace(
        vehicle=SimpleNamespace(vin="TESTVIN", lock=None, unlock=None),
        data=SimpleNamespace(exterior=exterior),
        async_run_command=run_command,
        async_refresh_exterior_after_command=lambda: None,
    )
    return module.PolestarLock(coordinator), exterior


@pytest.mark.asyncio
async def test_lock_stays_unlocking_until_the_car_reports_it(monkeypatch):
    _, module, timers = _load(monkeypatch)
    lock, exterior = _lock(module, locked=True)

    await lock.async_unlock()
    lock._handle_coordinator_update()

    assert lock.is_unlocking and lock.is_locked

    exterior.is_locked = False
    lock._handle_coordinator_update()

    assert not lock.is_unlocking and not lock.is_locked
    assert timers.cancelled == 1


@pytest.mark.asyncio
async def test_lock_gives_up_after_the_timeout(monkeypatch):
    _, module, timers = _load(monkeypatch)
    lock, _ = _lock(module, locked=False)

    await lock.async_lock()
    delay, expire = timers.scheduled[0]
    expire(None)

    assert delay == 60
    assert not lock.is_locking and not lock.is_locked


@pytest.mark.asyncio
async def test_lock_clears_at_once_when_the_command_fails(monkeypatch):
    _, module, timers = _load(monkeypatch)
    lock, _ = _lock(module, locked=True, error=RuntimeError("refused"))

    with pytest.raises(RuntimeError):
        await lock.async_unlock()

    assert not lock.is_unlocking
    assert timers.cancelled == 1


@pytest.mark.asyncio
async def test_nothing_is_pending_when_already_in_that_state(monkeypatch):
    _, module, timers = _load(monkeypatch)
    lock, _ = _lock(module, locked=True)

    await lock.async_lock()

    assert not lock.is_locking
    assert timers.scheduled == []


def _optimistic(module):
    class Entity(module.OptimisticStateMixin, FakeEntity):
        pass

    return Entity(None)


def test_optimistic_value_is_kept_until_confirmed(monkeypatch):
    module, _, timers = _load(monkeypatch)
    entity = _optimistic(module)

    entity._set_optimistic(True)

    assert entity._resolve_optimistic(False) is True
    assert timers.scheduled[0][0] == 60

    assert entity._resolve_optimistic(True) is True
    assert entity._resolve_optimistic(False) is False
    assert timers.cancelled == 1


def test_expired_optimistic_value_rewrites_the_state(monkeypatch):
    module, _, timers = _load(monkeypatch)
    entity = _optimistic(module)
    entity._set_optimistic(True)
    writes = entity.writes

    timers.scheduled[0][1](None)

    assert entity._resolve_optimistic(False) is False
    assert entity.writes == writes + 1


@pytest.mark.asyncio
async def test_timers_are_cancelled_on_removal_and_replacement(monkeypatch):
    module, _, timers = _load(monkeypatch)
    entity = _optimistic(module)

    entity._set_optimistic(1)
    entity._set_optimistic(2)
    await entity.async_will_remove_from_hass()

    assert timers.cancelled == 2
