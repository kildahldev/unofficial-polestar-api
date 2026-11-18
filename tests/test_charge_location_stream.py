"""Charge locations are read through the streaming methods the Polestar app uses."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from grpclib.const import Status
from grpclib.exceptions import GRPCError

from polestar_api.codec import encode, encode_message
from polestar_api.services import charge_location as module
from polestar_api.services.charge_location import ChargeLocationServiceClient

LOCATION_SCHEMA = {"id": (2, "string"), "alias": (3, "string")}


def _locations_response(*aliases: str) -> bytes:
    return b"".join(
        encode_message(3, encode(LOCATION_SCHEMA, {"id": f"id-{alias}", "alias": alias})) for alias in aliases
    )


IS_AT_RESPONSE_SCHEMA = {"status": (1, "int32"), "location_id": (2, "string"), "arrived_at": (3, "int64")}


class FakeConnection:
    channel = object()
    backend = SimpleNamespace(charge_location_svc="/chronos.services.v1.ChargeLocationService")

    async def get_metadata(self, vin=None):
        return {}


class Calls:
    def __init__(self) -> None:
        self.streams: list[str] = []
        self.unary: list[str] = []


def _patch(monkeypatch, *, stream=None, unary=None) -> Calls:
    calls = Calls()

    def fake_unary_stream(channel, method, request, **kwargs):
        calls.streams.append(method.rsplit("/", 1)[-1])
        return stream(method)

    async def fake_unary_unary(channel, method, request, **kwargs):
        calls.unary.append(method.rsplit("/", 1)[-1])
        return unary(method)

    monkeypatch.setattr(module.grpc_call, "unary_stream", fake_unary_stream)
    monkeypatch.setattr(module.grpc_call, "unary_unary", fake_unary_unary)
    return calls


def _client() -> ChargeLocationServiceClient:
    return ChargeLocationServiceClient(FakeConnection(), "TESTVIN")


@pytest.mark.asyncio
async def test_locations_come_from_the_stream_when_it_answers(monkeypatch):
    async def stream(method):
        yield _locations_response("Home", "Work")

    def unary(method):
        raise AssertionError("the unary method must not be used when the stream answers")

    calls = _patch(monkeypatch, stream=stream, unary=unary)

    locations = await _client().get_locations()

    assert [location.location_alias for location in locations] == ["Home", "Work"]
    assert calls.streams == ["GetChargeLocationsStream"]
    assert calls.unary == []


@pytest.mark.asyncio
async def test_an_empty_stream_message_means_no_saved_locations(monkeypatch):
    async def stream(method):
        yield b""

    calls = _patch(monkeypatch, stream=stream, unary=lambda method: b"")

    assert await _client().get_locations() == []
    assert calls.unary == []


@pytest.mark.asyncio
async def test_falls_back_to_the_unary_method_when_the_stream_is_rejected(monkeypatch):
    async def stream(method):
        raise GRPCError(Status.INVALID_ARGUMENT, "Validation failed")
        yield

    calls = _patch(monkeypatch, stream=stream, unary=lambda method: _locations_response("Home"))

    locations = await _client().get_locations()

    assert [location.location_alias for location in locations] == ["Home"]
    assert calls.unary == ["GetChargeLocations"]


@pytest.mark.asyncio
async def test_falls_back_to_the_unary_method_when_the_stream_stays_silent(monkeypatch):
    monkeypatch.setattr(module, "_STREAM_TIMEOUT", 0.05)

    async def stream(method):
        await asyncio.sleep(10)
        yield b""

    calls = _patch(monkeypatch, stream=stream, unary=lambda method: _locations_response("Home"))

    locations = await _client().get_locations()

    assert len(locations) == 1
    assert calls.unary == ["GetChargeLocations"]


@pytest.mark.asyncio
async def test_error_is_raised_when_both_methods_fail(monkeypatch):
    async def stream(method):
        raise GRPCError(Status.INVALID_ARGUMENT, "Validation failed")
        yield

    def unary(method):
        raise GRPCError(Status.INVALID_ARGUMENT, "Validation failed")

    _patch(monkeypatch, stream=stream, unary=unary)

    with pytest.raises(GRPCError):
        await _client().get_locations()


@pytest.mark.asyncio
async def test_current_location_uses_its_own_stream(monkeypatch):
    async def stream(method):
        yield encode(IS_AT_RESPONSE_SCHEMA, {"status": 1, "location_id": "home", "arrived_at": 1234})

    calls = _patch(monkeypatch, stream=stream, unary=lambda method: b"")

    result = await _client().is_at_location()

    assert result["location_id"] == "home"
    assert result["arrived_at"] == 1234
    assert calls.streams == ["isAtALocationStream"]
    assert calls.unary == []
