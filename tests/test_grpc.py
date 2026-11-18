from __future__ import annotations

from collections import Counter

import pytest
from grpclib.const import Status
from grpclib.exceptions import GRPCError, StreamTerminatedError

from polestar_api import grpc as grpc_call

METHOD = "/test.Service/Method"
RESET = StreamTerminatedError("Stream reset by remote party, error_code: 2")


class _FakeStream:
    def __init__(self, outcome):
        self._outcome = outcome

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send_message(self, data, end=False):
        pass

    async def recv_message(self):
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome

    async def __aiter__(self):
        for item in self._outcome:
            if isinstance(item, BaseException):
                raise item
            yield item


class _FakeChannel:
    """Plays back one scripted outcome per call attempt."""

    def __init__(self, *outcomes):
        self._outcomes = list(outcomes)
        self.attempts = 0

    def request(self, method, cardinality, **kwargs):
        self.attempts += 1
        return _FakeStream(self._outcomes.pop(0))


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    monkeypatch.setattr(grpc_call, "_retry_delay", lambda attempt: 0)


async def _collect(channel, retries=2):
    return [m async for m in grpc_call.unary_stream(channel, METHOD, b"", retries=retries)]


class TestUnaryUnary:
    async def test_stream_reset_is_retried(self):
        channel = _FakeChannel(RESET, b"ok")

        assert await grpc_call.unary_unary(channel, METHOD, b"") == b"ok"
        assert channel.attempts == 2

    async def test_persistent_stream_reset_raises_after_retries(self):
        channel = _FakeChannel(RESET, RESET, RESET)

        with pytest.raises(StreamTerminatedError):
            await grpc_call.unary_unary(channel, METHOD, b"", retries=2)
        assert channel.attempts == 3

    async def test_non_transient_status_is_not_retried(self):
        channel = _FakeChannel(GRPCError(Status.UNIMPLEMENTED, "nope"), b"ok")

        with pytest.raises(GRPCError):
            await grpc_call.unary_unary(channel, METHOD, b"")
        assert channel.attempts == 1


class TestCallCounts:
    @pytest.fixture(autouse=True)
    def fresh_counts(self, monkeypatch):
        monkeypatch.setattr(grpc_call, "CALL_COUNTS", Counter())

    async def test_every_attempt_is_counted_per_method(self):
        await grpc_call.unary_unary(_FakeChannel(RESET, b"ok"), METHOD, b"")
        await grpc_call.unary_unary(_FakeChannel(b"ok"), "/other/Method", b"")
        await _collect(_FakeChannel([RESET], [b"a"]))

        assert grpc_call.CALL_COUNTS == {METHOD: 4, "/other/Method": 1}

    async def test_failed_calls_are_counted(self):
        with pytest.raises(GRPCError):
            await grpc_call.unary_unary(
                _FakeChannel(GRPCError(Status.UNIMPLEMENTED, "nope")), METHOD, b""
            )

        assert grpc_call.CALL_COUNTS == {METHOD: 1}


class TestUnaryStream:
    async def test_stream_reset_before_data_is_retried(self):
        channel = _FakeChannel([RESET], [b"a", b"b"])

        assert await _collect(channel) == [b"a", b"b"]
        assert channel.attempts == 2

    async def test_stream_reset_after_data_ends_without_retry(self):
        channel = _FakeChannel([b"a", RESET], [b"never"])

        assert await _collect(channel) == [b"a"]
        assert channel.attempts == 1

    async def test_persistent_stream_reset_raises_after_retries(self):
        channel = _FakeChannel([RESET], [RESET], [RESET])

        with pytest.raises(StreamTerminatedError):
            await _collect(channel, retries=2)
        assert channel.attempts == 3
