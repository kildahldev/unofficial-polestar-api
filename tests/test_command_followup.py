"""Tests for following remote commands to their final status and reacting to failures."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from polestar_api.models.invocation import InvocationEnvelope, InvocationResponse, InvocationStatus
from polestar_api.services import invocation as invocation_module
from polestar_api.services.invocation import InvocationServiceClient

from .test_unsupported_entities import FakeRegistry, FakeVehicle, _coordinator, _load


def _message(status: InvocationStatus, text: str = "") -> bytes:
    return InvocationEnvelope(response=InvocationResponse(status=status, message=text)).to_bytes()


class FakeConnection:
    channel = object()
    backend = SimpleNamespace(invocation_svc="/svc")

    async def get_metadata(self, vin):
        return {}


def _client(monkeypatch, stream_factory) -> InvocationServiceClient:
    monkeypatch.setattr(invocation_module.grpc_call, "unary_stream", stream_factory)
    return InvocationServiceClient(FakeConnection(), "TESTVIN")


@pytest.mark.asyncio
async def test_command_returns_on_first_message_and_reports_final_status(monkeypatch):
    release = asyncio.Event()

    async def stream(*args, **kwargs):
        yield _message(InvocationStatus.SENT)
        await release.wait()
        yield _message(InvocationStatus.SUCCESS)

    client = _client(monkeypatch, stream)
    results = []
    client.add_listener(lambda method, response: results.append((method, response.status)))

    first = await client._call("Unlock", b"")

    assert InvocationEnvelope.from_bytes(first).response.status == InvocationStatus.SENT
    assert results == []

    release.set()
    await asyncio.gather(*client._follow_ups)

    assert results == [("Unlock", InvocationStatus.SUCCESS)]


@pytest.mark.asyncio
async def test_final_failure_is_reported(monkeypatch):
    async def stream(*args, **kwargs):
        yield _message(InvocationStatus.SENT)
        yield _message(InvocationStatus.DELIVERED)
        yield _message(InvocationStatus.CAR_OFFLINE, "Car is offline")

    client = _client(monkeypatch, stream)
    results = []
    client.add_listener(lambda method, response: results.append((response.status, response.message)))

    await client._call("Lock", b"")
    await asyncio.gather(*client._follow_ups)

    assert results == [(InvocationStatus.CAR_OFFLINE, "Car is offline")]


@pytest.mark.asyncio
async def test_stream_error_after_first_message_reports_last_known_status(monkeypatch):
    async def stream(*args, **kwargs):
        yield _message(InvocationStatus.SENT)
        raise ConnectionError("stream dropped")

    client = _client(monkeypatch, stream)
    results = []
    client.add_listener(lambda method, response: results.append(response.status))

    await client._call("Lock", b"")
    await asyncio.gather(*client._follow_ups)

    assert results == [InvocationStatus.SENT]


@pytest.mark.asyncio
async def test_removed_listener_is_not_called_and_cancel_stops_follow_up(monkeypatch):
    release = asyncio.Event()

    async def stream(*args, **kwargs):
        yield _message(InvocationStatus.SENT)
        await release.wait()
        yield _message(InvocationStatus.SUCCESS)

    client = _client(monkeypatch, stream)
    calls = []
    remove = client.add_listener(lambda method, response: calls.append(method))
    remove()

    await client._call("Lock", b"")
    await client.cancel_follow_ups()

    assert calls == []
    assert not client._follow_ups


@pytest.mark.asyncio
async def test_no_message_raises(monkeypatch):
    async def stream(*args, **kwargs):
        return
        yield

    client = _client(monkeypatch, stream)

    with pytest.raises(invocation_module.ApiError):
        await client._call("Lock", b"")


def _invocation_coordinator(module):
    coordinator = _coordinator(module, FakeVehicle({}))
    coordinator.hass = object()
    coordinator._command_failure_listeners = []
    coordinator.refreshes = []
    coordinator._schedule_background_refresh = lambda *attrs: coordinator.refreshes.append(attrs)
    notifications = []
    module.persistent_notification = SimpleNamespace(async_create=lambda *args, **kwargs: notifications.append((args, kwargs)))
    return coordinator, notifications


def test_failed_command_notifies_reverts_entities_and_refreshes(monkeypatch):
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator, notifications = _invocation_coordinator(module)
    reverted = []
    coordinator.async_add_command_failure_listener(lambda: reverted.append(True))

    coordinator._handle_invocation_result(
        "Unlock", InvocationResponse(status=InvocationStatus.RESPONSE_TIMEOUT, message="")
    )

    assert reverted == [True]
    assert coordinator.refreshes == [("exterior",)]
    assert len(notifications) == 1
    assert "response timeout" in notifications[0][0][1]


def test_successful_command_only_refreshes(monkeypatch):
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator, notifications = _invocation_coordinator(module)
    reverted = []
    coordinator.async_add_command_failure_listener(lambda: reverted.append(True))

    coordinator._handle_invocation_result("ClimatizationStart", InvocationResponse(status=InvocationStatus.SUCCESS))
    coordinator._handle_invocation_result("HonkFlash", InvocationResponse(status=InvocationStatus.SUCCESS))

    assert reverted == []
    assert notifications == []
    assert coordinator.refreshes == [("climate",)]


def test_unsubscribed_failure_listener_is_not_called(monkeypatch):
    module, _ = _load(monkeypatch, FakeRegistry())
    coordinator, _ = _invocation_coordinator(module)
    called = []
    remove = coordinator.async_add_command_failure_listener(lambda: called.append(True))
    remove()

    coordinator._handle_invocation_result("Lock", InvocationResponse(status=InvocationStatus.CAR_OFFLINE))

    assert called == []


class Timers:
    def __init__(self) -> None:
        self.scheduled: list[tuple[float, object]] = []
        self.cancelled = 0

    def call_later(self, hass, delay, action):
        self.scheduled.append((delay, action))

        def cancel() -> None:
            self.cancelled += 1

        return cancel


def _optimistic_entity(monkeypatch, timers: Timers):
    _, entity_module = _load(monkeypatch, FakeRegistry())
    monkeypatch.setattr(entity_module, "async_call_later", timers.call_later)

    class Base:
        writes = 0
        hass = object()

        def async_write_ha_state(self) -> None:
            self.writes += 1

        async def async_will_remove_from_hass(self) -> None:
            return None

    class Entity(entity_module.OptimisticStateMixin, Base):
        pass

    return Entity(), entity_module


def test_optimistic_value_holds_for_a_minute_then_expires(monkeypatch):
    timers = Timers()
    entity, entity_module = _optimistic_entity(monkeypatch, timers)

    entity._set_optimistic(True)

    assert entity_module.OptimisticStateMixin._OPTIMISTIC_TTL == 60.0
    assert timers.scheduled[0][0] == 60.0
    assert entity._resolve_optimistic(False) is True

    writes = entity.writes
    timers.scheduled[0][1](None)

    assert entity._resolve_optimistic(False) is False
    assert entity.writes == writes + 1


def test_optimistic_value_clears_when_car_confirms(monkeypatch):
    timers = Timers()
    entity, _ = _optimistic_entity(monkeypatch, timers)

    entity._set_optimistic(True)

    assert entity._resolve_optimistic(True) is True
    assert timers.cancelled == 1
    assert entity._resolve_optimistic(False) is False


def test_optimistic_value_reverts_when_command_later_fails(monkeypatch):
    timers = Timers()
    entity, _ = _optimistic_entity(monkeypatch, timers)
    entity._set_optimistic(True)
    writes = entity.writes

    entity._handle_command_failure()

    assert entity._resolve_optimistic(False) is False
    assert entity.writes == writes + 1
    assert timers.cancelled == 1
