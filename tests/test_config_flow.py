"""Tests for changing credentials (reauth / reconfigure) and token isolation."""

from __future__ import annotations

import enum
import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from polestar_api.auth import TokenData
from polestar_api.exceptions import ApiError, AuthError

VIN = "YV4TEST000T0000001"


class FakeState(enum.Enum):
    LOADED = "loaded"
    SETUP_ERROR = "setup_error"
    SETUP_RETRY = "setup_retry"


class FakeConfigFlow:
    """Minimal stand-in for homeassistant.config_entries.ConfigFlow."""

    def __init_subclass__(cls, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)

    def async_show_form(self, *, step_id, data_schema=None, errors=None, **kwargs):
        return {
            "type": "form",
            "step_id": step_id,
            "errors": errors or {},
            "suggested": self.suggested,
        }

    def async_abort(self, *, reason):
        return {"type": "abort", "reason": reason}

    def add_suggested_values_to_schema(self, schema, suggested):
        self.suggested = dict(suggested)
        return schema


class FakeStore:
    """In-memory replacement for homeassistant.helpers.storage.Store."""

    def __init__(self, hass, version, key) -> None:
        self.data = None

    async def async_load(self):
        return self.data

    async def async_save(self, data) -> None:
        self.data = data

    async def async_remove(self) -> None:
        self.data = None


def _stub(monkeypatch, name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)


@pytest.fixture
def component(monkeypatch):
    _stub(monkeypatch, "homeassistant")
    _stub(
        monkeypatch,
        "homeassistant.config_entries",
        ConfigEntry=object,
        ConfigEntryState=FakeState,
        ConfigFlow=FakeConfigFlow,
        ConfigFlowResult=dict,
        OptionsFlow=object,
    )
    _stub(monkeypatch, "homeassistant.const", CONF_EMAIL="email", CONF_PASSWORD="password")
    _stub(monkeypatch, "homeassistant.helpers")
    _stub(monkeypatch, "homeassistant.helpers.storage", Store=FakeStore)

    package_name = "_polestar_flow_under_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(Path(__file__).parents[1] / "custom_components" / "polestar")]
    monkeypatch.setitem(sys.modules, package_name, package)
    return SimpleNamespace(
        config_flow=importlib.import_module(f"{package_name}.config_flow"),
        token_store=importlib.import_module(f"{package_name}.token_store"),
    )


class FakeEntry:
    entry_id = "entry-id"

    def __init__(self, state=FakeState.SETUP_ERROR, **extra) -> None:
        self.data = {
            "email": "old@example.com",
            "password": "old-password",
            "vin": VIN,
            **extra,
        }
        self.state = state


class FakeHass:
    def __init__(self, entry: FakeEntry) -> None:
        self.entry = entry
        self.reloads: list[str] = []
        self.config_entries = SimpleNamespace(
            async_get_entry=lambda entry_id: entry,
            async_update_entry=self._update,
            async_reload=self._reload,
        )

    def _update(self, entry, *, data):
        entry.data = data

    async def _reload(self, entry_id) -> None:
        self.reloads.append(entry_id)


def _fake_api(monkeypatch, component, *, init_error=None, vehicles=(), vehicles_error=None):
    class FakeApi:
        instances: list[FakeApi] = []

        def __init__(self, email, password, *, token_store) -> None:
            self.email = email
            self.password = password
            self.closed = False
            self.instances.append(self)

        async def async_init(self) -> None:
            if init_error:
                raise init_error

        async def get_vehicles(self):
            if vehicles_error:
                raise vehicles_error
            return [SimpleNamespace(vin=v) for v in vehicles]

        async def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(component.config_flow, "PolestarApi", FakeApi)
    return FakeApi


def _flow(component, entry):
    flow = component.config_flow.PolestarConfigFlow()
    flow.hass = FakeHass(entry)
    flow.context = {"entry_id": entry.entry_id}
    return flow


NEW_CREDS = {"email": "new@example.com", "password": "new-password"}


@pytest.mark.parametrize("step", ["reauth_confirm", "reconfigure"])
async def test_form_prefills_email_but_not_password(component, step):
    flow = _flow(component, FakeEntry())

    result = await getattr(flow, f"async_step_{step}")()

    assert result["type"] == "form"
    assert result["step_id"] == step
    assert result["suggested"] == {"email": "old@example.com"}


async def test_reauth_entry_point_shows_credentials_form(component):
    flow = _flow(component, FakeEntry())

    result = await flow.async_step_reauth({"email": "old@example.com"})

    assert result["step_id"] == "reauth_confirm"


@pytest.mark.parametrize(
    ("step", "reason"),
    [("reauth_confirm", "reauth_successful"), ("reconfigure", "reconfigure_successful")],
)
async def test_email_and_password_change_keeps_vin(monkeypatch, component, step, reason):
    api = _fake_api(monkeypatch, component, vehicles=[VIN])
    entry = FakeEntry()
    flow = _flow(component, entry)

    result = await getattr(flow, f"async_step_{step}")(NEW_CREDS)

    assert result == {"type": "abort", "reason": reason}
    assert entry.data == {"email": "new@example.com", "password": "new-password", "vin": VIN}
    assert (api.instances[0].email, api.instances[0].password) == (
        "new@example.com",
        "new-password",
    )
    assert api.instances[0].closed is True
    assert flow.hass.reloads == [entry.entry_id]


async def test_password_only_change_with_same_email(monkeypatch, component):
    _fake_api(monkeypatch, component, vehicles=[VIN])
    entry = FakeEntry()
    flow = _flow(component, entry)

    await flow.async_step_reauth_confirm(
        {"email": "old@example.com", "password": "rotated"}
    )

    assert entry.data["email"] == "old@example.com"
    assert entry.data["password"] == "rotated"


async def test_email_whitespace_is_stripped(monkeypatch, component):
    _fake_api(monkeypatch, component, vehicles=[VIN])
    entry = FakeEntry()
    flow = _flow(component, entry)

    await flow.async_step_reconfigure({"email": "  new@example.com ", "password": "pw"})

    assert entry.data["email"] == "new@example.com"


async def test_loaded_entry_is_reloaded_by_update_listener_only(monkeypatch, component):
    _fake_api(monkeypatch, component, vehicles=[VIN])
    entry = FakeEntry(state=FakeState.LOADED)
    flow = _flow(component, entry)

    result = await flow.async_step_reconfigure(NEW_CREDS)

    assert result["reason"] == "reconfigure_successful"
    assert entry.data["email"] == "new@example.com"
    assert flow.hass.reloads == []


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"init_error": AuthError("bad credentials")}, "invalid_auth"),
        ({"init_error": RuntimeError("boom")}, "cannot_connect"),
        ({"vehicles_error": AuthError("expired")}, "invalid_auth"),
        ({"vehicles": ["YV4OTHER0000000002"]}, "vin_mismatch"),
    ],
)
@pytest.mark.parametrize("step", ["reauth_confirm", "reconfigure"])
async def test_failures_leave_entry_untouched(monkeypatch, component, step, kwargs, error):
    api = _fake_api(monkeypatch, component, **kwargs)
    entry = FakeEntry()
    original = dict(entry.data)
    flow = _flow(component, entry)

    result = await getattr(flow, f"async_step_{step}")(NEW_CREDS)

    assert result["type"] == "form"
    assert result["step_id"] == step
    assert result["errors"] == {"base": error}
    # The email the user typed is kept in the form so they only fix what is wrong.
    assert result["suggested"] == {"email": "new@example.com"}
    assert entry.data == original
    assert flow.hass.reloads == []
    assert api.instances[0].closed is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"vehicles": []},  # guest / secondary account: no vehicles listed
        {"vehicles_error": ApiError("lookup failed", 500)},  # discovery is best-effort
        {"vehicles": ["YV4OTHER0000000002", VIN]},  # our VIN among several
    ],
)
async def test_accepts_accounts_that_setup_would_accept(monkeypatch, component, kwargs):
    _fake_api(monkeypatch, component, **kwargs)
    entry = FakeEntry()
    flow = _flow(component, entry)

    result = await flow.async_step_reauth_confirm(NEW_CREDS)

    assert result["reason"] == "reauth_successful"
    assert entry.data["email"] == "new@example.com"


async def test_reconfigure_rejects_demo_entries(component):
    flow = _flow(component, FakeEntry(demo=True))

    result = await flow.async_step_reconfigure()

    assert result == {"type": "abort", "reason": "demo_mode"}


def _tokens() -> TokenData:
    return TokenData(access_token="access", refresh_token="refresh", expires_in=3600)


async def test_tokens_are_reused_for_the_same_email(component):
    store = component.token_store.HassTokenStore(None, "e", "Owner@Example.com")
    await store.save(_tokens())

    same_account = component.token_store.HassTokenStore(None, "e", "owner@example.com")
    same_account._store = store._store

    assert (await same_account.load()).refresh_token == "refresh"


async def test_tokens_from_a_previous_email_are_ignored(component):
    old = component.token_store.HassTokenStore(None, "e", "old@example.com")
    await old.save(_tokens())

    new = component.token_store.HassTokenStore(None, "e", "new@example.com")
    new._store = old._store

    assert await new.load() is None


async def test_untagged_legacy_tokens_are_still_used(component):
    legacy = component.token_store.HassTokenStore(None, "e")
    await legacy.save(_tokens())
    assert "email" not in legacy._store.data

    current = component.token_store.HassTokenStore(None, "e", "owner@example.com")
    current._store = legacy._store

    assert (await current.load()).access_token == "access"
