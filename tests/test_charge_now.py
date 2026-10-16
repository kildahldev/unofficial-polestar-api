"""Charge override response shapes observed by Hisingen and the existing client."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from polestar_api.backend import C3, PCCS
from polestar_api.codec import decode, encode_int32, encode_message, encode_string
from polestar_api.models.common import ResponseStatusCode
from polestar_api.services.charge_now import ChargeNowServiceClient


@pytest.mark.parametrize("backend", [C3, PCCS])
@pytest.mark.parametrize("method,rpc_method", [
    ("start", "StartOverrideChargeTimer"),
    ("stop", "StopOverrideChargeTimer"),
])
@pytest.mark.parametrize("wire,status", [
    (bytes.fromhex("08 02"), ResponseStatusCode.WARNING),
    (encode_int32(1, 1), ResponseStatusCode.SUCCESS),
    (encode_int32(1, 3), ResponseStatusCode.ERROR),
    (encode_int32(1, 99), 99),
    (encode_message(3, encode_int32(1, 1)), ResponseStatusCode.SUCCESS),
    (encode_message(3, encode_int32(1, 3)), ResponseStatusCode.ERROR),
    (encode_string(1, "request") + encode_int32(3, 1), ResponseStatusCode.SUCCESS),
    (encode_string(1, "request") + encode_int32(3, 2), ResponseStatusCode.SUCCESS),
    (encode_string(1, "request") + encode_int32(3, 3), ResponseStatusCode.SUCCESS),
    (encode_string(1, "request") + encode_int32(3, 4), ResponseStatusCode.SUCCESS),
    (encode_string(1, "request") + encode_int32(3, 8), ResponseStatusCode.SUCCESS),
    (encode_string(1, "request") + encode_int32(3, 5), ResponseStatusCode.ERROR),
    (encode_string(1, "request") + encode_int32(3, 6), ResponseStatusCode.ERROR),
    (encode_string(1, "request") + encode_int32(3, 7), ResponseStatusCode.ERROR),
    (encode_string(1, "request") + encode_int32(3, 99), ResponseStatusCode.ERROR),
    (encode_string(1, "request"), ResponseStatusCode.UNDEFINED),
    (b"", ResponseStatusCode.UNDEFINED),
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
