"""Charge override (charge now) response parsing."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from polestar_api.backend import C3, PCCS
from polestar_api.codec import decode, encode_int32
from polestar_api.models.common import ResponseStatusCode
from polestar_api.services.charge_now import ChargeNowServiceClient


@pytest.mark.parametrize("backend", [C3, PCCS])
@pytest.mark.parametrize("method,rpc_method", [
    ("start", "StartOverrideChargeTimer"),
    ("stop", "StopOverrideChargeTimer"),
])
# Start/StopOverrideChargeTimerResponse: field 1 = chronos ResponseStatus
# (UNKNOWN_ERROR 0, SUCCESS 1, VALIDATION_ERROR 2, INTERNAL_ERROR 3, NOT_FOUND 4),
# per the official app's proto for both C3 and PCCS. Only SUCCESS succeeds.
@pytest.mark.parametrize("wire,status", [
    (encode_int32(1, 1), ResponseStatusCode.SUCCESS),
    (bytes.fromhex("08 02"), ResponseStatusCode.ERROR),  # VALIDATION_ERROR
    (encode_int32(1, 3), ResponseStatusCode.ERROR),  # INTERNAL_ERROR
    (encode_int32(1, 4), ResponseStatusCode.ERROR),  # NOT_FOUND
    (encode_int32(1, 99), ResponseStatusCode.ERROR),  # unknown future value
    (b"", ResponseStatusCode.UNDEFINED),  # proto3 default: UNKNOWN_ERROR
])
async def test_override_response(monkeypatch, backend, method, rpc_method, wire, status):
    connection = SimpleNamespace(
        backend=backend, channel=object(), get_metadata=AsyncMock(return_value={})
    )
    rpc = AsyncMock(return_value=wire)
    monkeypatch.setattr("polestar_api.services.charge_now.grpc_call.unary_unary", rpc)

    result = await getattr(ChargeNowServiceClient(connection, "TESTVIN"), method)()

    assert result == status
    args, kwargs = rpc.call_args
    assert args[1] == f"{backend.charge_now_svc}/{rpc_method}"
    assert decode(decode(args[2])[1])[2] == b"TESTVIN"
    assert kwargs["metadata"]["vin"] == "TESTVIN"
