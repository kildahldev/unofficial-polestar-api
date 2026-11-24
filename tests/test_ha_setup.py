"""Focused tests for Home Assistant config-entry setup boundaries."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from polestar_api.exceptions import ApiError, AuthError


class FakeConfigEntryAuthFailed(Exception):
    """Test stand-in for Home Assistant's auth failure."""


class FakeEntry:
    data = {"email": "owner@example.com", "password": "secret", "vin": "TESTVIN123"}
    options: dict[str, object] = {}
    entry_id = "entry-id"

    def add_update_listener(self, listener):
        return listener

    def async_on_unload(self, callback):
        return None


class FakeHass:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}
        self.http = SimpleNamespace(async_register_static_paths=self._async_noop)
        self.config_entries = SimpleNamespace(async_forward_entry_setups=self._async_noop)

    async def _async_noop(self, *args, **kwargs) -> None:
        return None


class FakeCoordinator:
    def __init__(self, hass, vehicle, entry) -> None:
        self.vehicle = vehicle

    async def async_config_entry_first_refresh(self) -> None:
        return None

    async def async_start_streams(self) -> None:
        return None

    async def async_shutdown(self) -> None:
        return None


class FakeTokenStore:
    def __init__(self, hass, entry_id, email=None) -> None:
        pass

    async def remove(self) -> None:
        return None


def _stub_module(monkeypatch, name: str, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def _load_component(monkeypatch):
    _stub_module(monkeypatch, "homeassistant")
    _stub_module(monkeypatch, "homeassistant.components")
    _stub_module(
        monkeypatch,
        "homeassistant.components.http",
        StaticPathConfig=lambda *args, **kwargs: (args, kwargs),
    )
    _stub_module(monkeypatch, "homeassistant.config_entries", ConfigEntry=object)
    _stub_module(
        monkeypatch,
        "homeassistant.const",
        CONF_EMAIL="email",
        CONF_PASSWORD="password",
    )
    _stub_module(monkeypatch, "homeassistant.core", HomeAssistant=object)
    _stub_module(
        monkeypatch,
        "homeassistant.exceptions",
        ConfigEntryAuthFailed=FakeConfigEntryAuthFailed,
    )

    package_name = "_polestar_component_under_test"
    component_dir = Path(__file__).parents[1] / "custom_components" / "polestar"
    package = types.ModuleType(package_name)
    package.__path__ = [str(component_dir)]
    monkeypatch.setitem(sys.modules, package_name, package)
    _stub_module(
        monkeypatch,
        f"{package_name}.const",
        CONF_DEMO="demo",
        CONF_VIN="vin",
        DOMAIN="polestar",
        PLATFORMS=(),
    )
    _stub_module(monkeypatch, f"{package_name}.coordinator", PolestarCoordinator=FakeCoordinator)
    _stub_module(monkeypatch, f"{package_name}.demo", DemoVehicle=object)
    _stub_module(
        monkeypatch,
        f"{package_name}.services",
        async_register_services=lambda hass: None,
        async_unregister_services=lambda hass: None,
    )
    _stub_module(monkeypatch, f"{package_name}.token_store", HassTokenStore=FakeTokenStore)

    spec = importlib.util.spec_from_file_location(
        package_name,
        component_dir / "__init__.py",
        submodule_search_locations=[str(component_dir)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, package_name, module)
    spec.loader.exec_module(module)
    return module


def _fake_api_class(error: Exception):
    class FakeApi:
        instances = []

        def __init__(self, email, password, *, token_store) -> None:
            self._connection = object()
            self.closed = False
            self.instances.append(self)

        async def async_init(self) -> None:
            return None

        async def get_vehicles(self):
            raise error

        async def close(self) -> None:
            self.closed = True

    return FakeApi


@pytest.mark.asyncio
async def test_api_error_uses_configured_vin_without_logging_backend_details(monkeypatch, caplog):
    component = _load_component(monkeypatch)
    api_class = _fake_api_class(ApiError("backend detail with PolestarId"))
    monkeypatch.setattr(component, "PolestarApi", api_class)

    assert await component.async_setup_entry(FakeHass(), FakeEntry()) is True

    assert api_class.instances[0].closed is False
    assert "Vehicle list lookup failed (GraphQL/API error); using configured VIN" in caplog.text
    assert "backend detail" not in caplog.text
    assert "PolestarId" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [AuthError("bad credentials"), RuntimeError("unexpected")])
async def test_non_api_errors_close_client_and_propagate(monkeypatch, error):
    component = _load_component(monkeypatch)
    api_class = _fake_api_class(error)
    monkeypatch.setattr(component, "PolestarApi", api_class)

    expected = FakeConfigEntryAuthFailed if isinstance(error, AuthError) else RuntimeError
    with pytest.raises(expected):
        await component.async_setup_entry(FakeHass(), FakeEntry())

    assert api_class.instances[0].closed is True
