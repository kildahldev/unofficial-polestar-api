"""Diagnostics: the api_calls block that measures load on the Polestar backend."""

from __future__ import annotations

import importlib.util
import sys
import time
import types
from collections import Counter
from pathlib import Path

import pytest

from polestar_api import grpc as grpc_call


def _stub_module(monkeypatch, name: str, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _load_diagnostics(monkeypatch):
    """Load diagnostics.py standalone, without executing the real package __init__."""
    _stub_module(monkeypatch, "homeassistant")
    _stub_module(monkeypatch, "homeassistant.components")
    _stub_module(
        monkeypatch,
        "homeassistant.components.diagnostics",
        async_redact_data=lambda data, to_redact: data,
    )
    _stub_module(monkeypatch, "homeassistant.config_entries", ConfigEntry=object)
    _stub_module(monkeypatch, "homeassistant.const", CONF_EMAIL="email", CONF_PASSWORD="password")
    _stub_module(monkeypatch, "homeassistant.core", HomeAssistant=object)

    package_name = "_polestar_diagnostics_under_test"
    component_dir = Path(__file__).parents[1] / "custom_components" / "polestar"
    package = types.ModuleType(package_name)
    package.__path__ = [str(component_dir)]
    monkeypatch.setitem(sys.modules, package_name, package)
    _stub_module(monkeypatch, f"{package_name}.const", CONF_VIN="vin", DOMAIN="polestar")
    _stub_module(monkeypatch, f"{package_name}.coordinator", PolestarCoordinator=object)

    spec = importlib.util.spec_from_file_location(
        f"{package_name}.diagnostics", component_dir / "diagnostics.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, f"{package_name}.diagnostics", module)
    spec.loader.exec_module(module)
    return module


def test_api_calls_reports_counts_and_daily_rate(monkeypatch):
    diagnostics = _load_diagnostics(monkeypatch)
    started = time.time() - 12 * 60 * 60
    monkeypatch.setattr(grpc_call, "CALL_COUNTS", Counter({"/svc.B/Get": 30, "/svc.A/Get": 20}))
    monkeypatch.setattr(grpc_call, "CALL_COUNTS_SINCE", started)

    api_calls = diagnostics._api_call_diagnostics()

    assert api_calls["total"] == 50
    assert list(api_calls["per_method"]) == ["/svc.A/Get", "/svc.B/Get"]
    assert api_calls["per_method"]["/svc.B/Get"] == 30
    assert api_calls["since"].startswith(time.strftime("%Y-%m-%d", time.gmtime(started)))
    assert api_calls["per_day_rate"] == pytest.approx(100, rel=0.01)


def test_api_calls_with_no_traffic(monkeypatch):
    diagnostics = _load_diagnostics(monkeypatch)
    monkeypatch.setattr(grpc_call, "CALL_COUNTS", Counter())
    monkeypatch.setattr(grpc_call, "CALL_COUNTS_SINCE", time.time())

    api_calls = diagnostics._api_call_diagnostics()

    assert api_calls["total"] == 0
    assert api_calls["per_method"] == {}
    assert api_calls["per_day_rate"] == 0
