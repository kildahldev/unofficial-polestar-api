"""Amp-limit read payloads and command delivery acknowledgements differ."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from polestar_api.backend import C3, PCCS
from polestar_api.codec import decode, encode_int32, encode_message, encode_string
from polestar_api.models.common import ResponseStatusCode
from polestar_api.services.amp_limit import AmpLimitServiceClient


@pytest.mark.parametrize("backend", [C3, PCCS])
@pytest.mark.parametrize("status", [0, 1, 2, 3, 4, 5, 6, 7, 8, 99])
async def test_set_checks_flat_delivery_status(monkeypatch, backend, status):
    connection = SimpleNamespace(
        backend=backend, channel=object(), get_metadata=AsyncMock(return_value={})
    )
    response = (
        encode_string(1, "test-request")
        + encode_string(2, "TESTVIN")
        + encode_int32(3, status)
    )
    rpc = AsyncMock(return_value=response)
    monkeypatch.setattr("polestar_api.services.amp_limit.grpc_call.unary_unary", rpc)

    result = await AmpLimitServiceClient(connection, "TESTVIN").set(16)

    assert result.response_status is not None
    assert result.response_status.status_code == status
    expected = ResponseStatusCode.SUCCESS if status in {1, 2, 3, 4, 8} else ResponseStatusCode.ERROR
    assert result.response_status.status == expected
    # Acknowledgements do not report the current measured limit.
    assert result.amperage_limit == 0
    args, kwargs = rpc.call_args
    assert args[1] == f"{backend.amp_limit_svc}/SetAmpLimit"
    request = decode(args[2])
    assert request[2] == 16
    assert decode(request[1])[2] == b"TESTVIN"
    assert kwargs["metadata"]["vin"] == "TESTVIN"


@pytest.mark.parametrize("response", [b"", encode_message(3, encode_int32(1, 16))])
async def test_set_rejects_missing_or_non_scalar_status(monkeypatch, response):
    connection = SimpleNamespace(
        backend=C3, channel=object(), get_metadata=AsyncMock(return_value={})
    )
    monkeypatch.setattr(
        "polestar_api.services.amp_limit.grpc_call.unary_unary",
        AsyncMock(return_value=response),
    )
    result = await AmpLimitServiceClient(connection, "TESTVIN").set(16)
    assert result.response_status is not None
    assert result.response_status.status == ResponseStatusCode.ERROR


def test_get_still_decodes_nested_limit():
    result = AmpLimitServiceClient._parse(encode_message(3, encode_int32(1, 16)))
    assert result.amperage_limit == 16
    assert result.response_status is None
