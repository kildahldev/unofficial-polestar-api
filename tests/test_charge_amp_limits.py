"""Tests for the per-car charge amperage range (car-information)."""

from __future__ import annotations

import httpx
import pytest

from polestar_api.discovery import (
    CAR_INFORMATION_PATH,
    PCCS_API_URL,
    ChargeAmpLimits,
    _parse_amp_limits,
    get_charge_amp_limits,
)

VIN = "YSMTEST0000000001"


def _fake_client(responses: dict[str, object], calls: list[tuple[str, dict]]):
    class FakeResponse:
        def __init__(self, status: int, body: object) -> None:
            self.status_code = status
            self._body = body

        def json(self):
            if isinstance(self._body, Exception):
                raise self._body
            return self._body

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            calls.append((url, headers))
            res = responses[url]
            if isinstance(res, Exception):
                raise res
            return FakeResponse(*res)

    return FakeClient


C3_URL = "https://c3.example" + CAR_INFORMATION_PATH
PCCS_URL = PCCS_API_URL + CAR_INFORMATION_PATH


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        (
            {"supportsGlobalChargeAmperageLimitSetting": True, "chargeAmperageMinLimit": 6, "chargeAmperageMaxLimit": 48},
            ChargeAmpLimits(True, 6, 48),
        ),
        (
            # PS4 as seen live: nothing reported
            {"supportsChargeAmperageLimitSetting": False, "chargeAmperageMinLimit": None, "chargeAmperageMaxLimit": None},
            ChargeAmpLimits(False, None, None),
        ),
        ({"chargeAmperageMinLimit": 40, "chargeAmperageMaxLimit": 16}, ChargeAmpLimits(False, None, None)),
        ({"chargeAmperageMinLimit": "6", "chargeAmperageMaxLimit": True}, ChargeAmpLimits(False, None, None)),
    ],
)
def test_parse_amp_limits(entry, expected):
    assert _parse_amp_limits(entry) == expected


@pytest.mark.asyncio
async def test_uses_c3_entry_when_vin_listed_there(monkeypatch):
    calls: list = []
    monkeypatch.setattr(
        "polestar_api.discovery.httpx.AsyncClient",
        _fake_client(
            {
                C3_URL: (200, [{"vin": VIN, "supportsGlobalChargeAmperageLimitSetting": True,
                                "chargeAmperageMinLimit": 6, "chargeAmperageMaxLimit": 32}]),
                PCCS_URL: (200, []),
            },
            calls,
        ),
    )
    limits = await get_charge_amp_limits("tok", "c3.example", VIN)
    assert limits == ChargeAmpLimits(True, 6, 32)
    assert [c[0] for c in calls] == [C3_URL]
    assert calls[0][1]["Authorization"] == "Bearer tok"


@pytest.mark.asyncio
async def test_falls_through_to_pccs(monkeypatch):
    calls: list = []
    monkeypatch.setattr(
        "polestar_api.discovery.httpx.AsyncClient",
        _fake_client(
            {
                C3_URL: (200, [{"vin": "OTHER"}]),
                PCCS_URL: (200, [{"vin": VIN, "supportsGlobalChargeAmperageLimitSetting": True,
                                  "chargeAmperageMinLimit": 6, "chargeAmperageMaxLimit": 48}]),
            },
            calls,
        ),
    )
    limits = await get_charge_amp_limits("tok", "c3.example", VIN)
    assert limits == ChargeAmpLimits(True, 6, 48)
    assert calls[1][0] == PCCS_URL
    assert calls[1][1]["x-api-key"] == ""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "c3_result",
    [(500, None), httpx.ConnectError("down"), (200, ValueError("not json"))],
)
async def test_failures_are_skipped_and_return_none(monkeypatch, c3_result):
    calls: list = []
    monkeypatch.setattr(
        "polestar_api.discovery.httpx.AsyncClient",
        _fake_client({C3_URL: c3_result, PCCS_URL: (401, None)}, calls),
    )
    assert await get_charge_amp_limits("tok", "c3.example", VIN) is None
    assert len(calls) == 2


def _amp_limit_range():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).parents[1] / "custom_components" / "polestar" / "amp_range.py"
    spec = importlib.util.spec_from_file_location("_amp_range_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.amp_limit_range


@pytest.mark.parametrize(
    ("limits", "expected"),
    [
        (None, (6, 32)),
        (ChargeAmpLimits(False, None, None), (6, 32)),
        (ChargeAmpLimits(True, 6, None), (6, 32)),
        (ChargeAmpLimits(True, 6, 48), (6, 48)),
        (ChargeAmpLimits(True, 8, 16), (8, 16)),
    ],
)
def test_amp_limit_range(limits, expected):
    assert _amp_limit_range()(limits) == expected
