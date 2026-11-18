"""Tests for the lock entity's locking/unlocking pending state."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from .test_unsupported_entities import FakeRegistry, _load, _stub

PACKAGE = "_polestar_unsupported_under_test"


class FakeLockEntity:
    pass


class Timers:
    def __init__(self) -> None:
        self.scheduled: list[tuple[float, object]] = []
        self.cancelled = 0

    def call_later(self, hass, delay, action):
        self.scheduled.append((delay, action))

        def cancel() -> None:
            self.cancelled += 1

        return cancel


def _load_lock(monkeypatch, timers: Timers):
    _load(monkeypatch, FakeRegistry())
    _stub(monkeypatch, "homeassistant.components")
    _stub(monkeypatch, "homeassistant.components.lock", LockEntity=FakeLockEntity)
    _stub(monkeypatch, "homeassistant.config_entries", ConfigEntry=object)
    _stub(monkeypatch, "homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
    _stub(monkeypatch, "homeassistant.helpers.event", async_call_later=timers.call_later)
    path = Path(__file__).parents[1] / "custom_components" / "polestar" / "lock.py"
    spec = importlib.util.spec_from_file_location(f"{PACKAGE}.lock", path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, f"{PACKAGE}.lock", module)
    spec.loader.exec_module(module)
    return module


def _lock(module, *, locked: bool, fail: bool = False):
    exterior = SimpleNamespace(is_locked=locked)

    async def run_command(command, **kwargs):
        if fail:
            raise RuntimeError("command failed")
        return await command()

    async def noop():
        return None

    coordinator = SimpleNamespace(
        vehicle=SimpleNamespace(vin="TESTVIN", lock=noop, unlock=noop),
        data=SimpleNamespace(exterior=exterior),
        async_run_command=run_command,
        async_refresh_exterior_after_command=lambda: None,
    )
    entity = module.PolestarLock(coordinator)
    entity.hass = object()
    return entity, exterior


@pytest.mark.asyncio
async def test_unlocking_stays_until_car_reports_unlocked(monkeypatch):
    timers = Timers()
    module = _load_lock(monkeypatch, timers)
    entity, exterior = _lock(module, locked=True)

    await entity.async_unlock()

    assert entity.is_unlocking is True
    assert entity.is_locking is False
    assert timers.scheduled[0][0] == module.PENDING_TIMEOUT

    entity._handle_coordinator_update()
    assert entity.is_unlocking is True

    exterior.is_locked = False
    entity._handle_coordinator_update()

    assert entity.is_unlocking is False
    assert timers.cancelled == 1


@pytest.mark.asyncio
async def test_locking_stays_until_car_reports_locked(monkeypatch):
    module = _load_lock(monkeypatch, Timers())
    entity, exterior = _lock(module, locked=False)

    await entity.async_lock()

    assert entity.is_locking is True

    exterior.is_locked = True
    entity._handle_coordinator_update()

    assert entity.is_locking is False


@pytest.mark.asyncio
async def test_pending_state_expires_after_timeout(monkeypatch):
    timers = Timers()
    module = _load_lock(monkeypatch, timers)
    entity, _ = _lock(module, locked=True)

    await entity.async_unlock()
    _, expire = timers.scheduled[0]
    expire(None)

    assert entity.is_unlocking is False


@pytest.mark.asyncio
async def test_failed_command_clears_pending_state(monkeypatch):
    module = _load_lock(monkeypatch, Timers())
    entity, _ = _lock(module, locked=True, fail=True)

    with pytest.raises(RuntimeError):
        await entity.async_unlock()

    assert entity.is_unlocking is False


@pytest.mark.asyncio
async def test_no_pending_state_when_already_in_target_state(monkeypatch):
    timers = Timers()
    module = _load_lock(monkeypatch, timers)
    entity, _ = _lock(module, locked=False)

    await entity.async_unlock()

    assert entity.is_unlocking is False
    assert timers.scheduled == []


@pytest.mark.asyncio
async def test_command_failure_after_accept_clears_pending_state(monkeypatch):
    timers = Timers()
    module = _load_lock(monkeypatch, timers)
    entity, _ = _lock(module, locked=True)

    await entity.async_unlock()
    assert entity.is_unlocking is True

    entity._handle_command_failure()

    assert entity.is_unlocking is False
    assert timers.cancelled == 1


def _tailgate(module, lock_status, *, fail: bool = False):
    calls = {"unlock_trunk": 0, "lock": 0}
    status = SimpleNamespace(lock_status=lock_status)
    exterior = SimpleNamespace(is_locked=True, tailgate=SimpleNamespace(status=status))

    async def lock():
        calls["lock"] += 1

    async def run_command(command, **kwargs):
        return await command()

    async def unlock_trunk():
        if fail:
            raise RuntimeError("unlock trunk failed")
        calls["unlock_trunk"] += 1

    coordinator = SimpleNamespace(
        vehicle=SimpleNamespace(vin="TESTVIN", lock=lock),
        data=SimpleNamespace(exterior=exterior),
        async_run_command=run_command,
        async_unlock_trunk=unlock_trunk,
        async_refresh_exterior_after_command=lambda: None,
    )
    entity = module.PolestarTailgateLock(coordinator)
    entity.hass = object()
    return entity, status, calls


def test_tailgate_lock_state_follows_the_cars_tailgate_lock(monkeypatch):
    from polestar_api.models.exterior import LockStatus

    module = _load_lock(monkeypatch, Timers())

    for value, expected in ((LockStatus.LOCKED, True), (LockStatus.UNLOCKED, False), (LockStatus.UNSPECIFIED, None)):
        entity, _, _ = _tailgate(module, value)
        assert entity.is_locked is expected

    entity, _, _ = _tailgate(module, LockStatus.LOCKED)
    entity.coordinator.data = None
    assert entity.is_locked is None


@pytest.mark.asyncio
async def test_unlocking_the_tailgate_sends_the_trunk_unlock_and_waits_for_the_car(monkeypatch):
    from polestar_api.models.exterior import LockStatus

    module = _load_lock(monkeypatch, Timers())
    entity, status, calls = _tailgate(module, LockStatus.LOCKED)

    await entity.async_unlock()

    assert calls == {"unlock_trunk": 1, "lock": 0}
    assert entity.is_unlocking is True

    status.lock_status = LockStatus.UNLOCKED
    entity._handle_coordinator_update()

    assert entity.is_unlocking is False
    assert entity.is_locked is False


@pytest.mark.asyncio
async def test_locking_the_tailgate_sends_the_normal_lock_command(monkeypatch):
    from polestar_api.models.exterior import LockStatus

    module = _load_lock(monkeypatch, Timers())
    entity, status, calls = _tailgate(module, LockStatus.UNLOCKED)

    await entity.async_lock()

    assert calls == {"unlock_trunk": 0, "lock": 1}
    assert entity.is_locking is True

    status.lock_status = LockStatus.LOCKED
    entity._handle_coordinator_update()

    assert entity.is_locking is False


@pytest.mark.asyncio
async def test_a_failed_trunk_unlock_clears_the_pending_state(monkeypatch):
    from polestar_api.models.exterior import LockStatus

    module = _load_lock(monkeypatch, Timers())
    entity, _, _ = _tailgate(module, LockStatus.LOCKED, fail=True)

    with pytest.raises(RuntimeError):
        await entity.async_unlock()

    assert entity.is_unlocking is False
