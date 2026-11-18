"""Stream and command updates must not restart the coordinator's poll timer."""

from __future__ import annotations

import asyncio

import pytest

from .test_unsupported_entities import FakeRegistry, FakeVehicle, _coordinator, _load, _unsupported


def _push_coordinator(module):
    coordinator = _coordinator(module, FakeVehicle({}))
    coordinator.data = None
    coordinator.last_update_success = False
    coordinator.listener_calls = 0

    def update_listeners() -> None:
        coordinator.listener_calls += 1

    def set_updated_data(data) -> None:
        raise AssertionError("async_set_updated_data restarts the poll timer")

    coordinator.async_update_listeners = update_listeners
    coordinator.async_set_updated_data = set_updated_data
    return coordinator


def test_apply_values_updates_data_and_notifies_without_resetting_timer(monkeypatch):
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator = _push_coordinator(module)
    generation = coordinator.next_fetch_generation()

    coordinator._async_apply_values({"battery": "battery-1"}, generation)

    assert coordinator.data.battery == "battery-1"
    assert coordinator.last_update_success is True
    assert coordinator.listener_calls == 1


def test_apply_values_with_an_unchanged_value_does_not_notify(monkeypatch):
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator = _push_coordinator(module)
    coordinator.data = module.PolestarVehicleData(battery="battery-1")

    coordinator._async_apply_values({"battery": "battery-1"}, coordinator.next_fetch_generation())

    assert coordinator.listener_calls == 0


@pytest.mark.asyncio
async def test_stream_updates_do_not_reset_poll_timer(monkeypatch):
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator = _push_coordinator(module)

    async def stream():
        yield "battery-1"
        yield "battery-2"
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        async with asyncio.timeout(5):
            await coordinator._async_run_stream("battery", stream)

    assert coordinator.data.battery == "battery-2"
    assert coordinator.listener_calls == 2


@pytest.mark.asyncio
async def test_post_command_refresh_skips_unsupported_endpoints(monkeypatch):
    """A command's follow-up refreshes must not re-call an UNIMPLEMENTED endpoint.

    Each command schedules several follow-up refreshes; with probing on by
    default a command touching an endpoint the car doesn't serve would call
    it that many extra times. Re-probing is left to the scheduled daily probe.
    """
    module, _ = _load(monkeypatch, FakeRegistry())
    vehicle = FakeVehicle({"amp_limit": _unsupported("AMP_LIMIT")})
    coordinator = _push_coordinator(module)
    coordinator.vehicle = vehicle

    values, successful = await coordinator._async_fetch_values(
        ("amp_limit", "battery"), module.PolestarVehicleData()
    )
    assert "amp_limit" in coordinator._unsupported_fetches

    vehicle.calls.clear()
    await coordinator.async_request_attrs_refresh("amp_limit", "battery")

    assert vehicle.calls == ["battery"]


@pytest.mark.asyncio
async def test_post_command_refresh_stops_once_the_value_changes(monkeypatch):
    """Stop polling once the car has reported back, rather than running the
    whole fixed schedule regardless."""
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator = _push_coordinator(module)
    coordinator.data = module.PolestarVehicleData(battery="old")

    async def get_battery():
        return "new"

    coordinator.vehicle.get_battery = get_battery

    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)

    await coordinator.async_refresh_after_command("battery")

    assert sleeps == [module._POST_COMMAND_REFRESH_DELAYS[0]]
    assert coordinator.data.battery == "new"


@pytest.mark.asyncio
async def test_post_command_refresh_runs_the_full_schedule_without_a_change(monkeypatch):
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator = _push_coordinator(module)
    coordinator.data = module.PolestarVehicleData(battery="battery")  # FakeVehicle's default

    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)

    await coordinator.async_refresh_after_command("battery")

    assert sleeps == list(module._POST_COMMAND_REFRESH_DELAYS)


@pytest.mark.asyncio
async def test_streamed_attr_only_gets_the_late_fallback_refreshes(monkeypatch):
    """A running stream reports the change itself; skip the early steps."""
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator = _push_coordinator(module)
    coordinator.data = module.PolestarVehicleData(battery="battery")
    coordinator._stream_tasks["battery"] = asyncio.get_event_loop().create_future()

    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)

    await coordinator.async_refresh_after_command("battery")

    assert sleeps == list(module._STREAMED_POST_COMMAND_REFRESH_DELAYS)


@pytest.mark.asyncio
async def test_resubscribe_after_clean_close_respects_the_floor(monkeypatch):
    """A server closing the stream after every message must not become a tight loop."""
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator = _push_coordinator(module)

    clock = [1_000.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])

    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)

    calls = 0

    async def stream():
        nonlocal calls
        calls += 1
        if calls > 2:
            raise asyncio.CancelledError
        yield f"battery-{calls}"

    with pytest.raises(asyncio.CancelledError):
        async with asyncio.timeout(5):
            await coordinator._async_run_stream("battery", stream)

    assert calls == 3
    assert sleeps == [module.STREAM_MIN_RESUBSCRIBE_INTERVAL] * 2


@pytest.mark.asyncio
async def test_partial_refresh_after_command_does_not_reset_poll_timer(monkeypatch):
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator = _push_coordinator(module)

    await coordinator.async_request_attrs_refresh("battery")

    assert coordinator.data.battery == "battery"
    assert coordinator.listener_calls == 1
