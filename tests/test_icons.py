"""Icons that follow a binary sensor's state."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_utils(monkeypatch):
    """Load custom_components/polestar/utils.py with a stubbed homeassistant.util.dt.

    utils.py only needs ``homeassistant.util.dt`` for its timestamp helpers;
    ``state_icon`` itself has no Home Assistant dependency, so a bare stub
    module is enough to satisfy the import without installing homeassistant.
    """
    for name, attrs in (
        ("homeassistant", {}),
        ("homeassistant.util", {}),
        ("homeassistant.util.dt", {"utc_from_timestamp": lambda s: s, "utcnow": lambda: None}),
    ):
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        monkeypatch.setitem(sys.modules, name, module)

    utils_path = Path(__file__).parents[1] / "custom_components" / "polestar" / "utils.py"
    spec = importlib.util.spec_from_file_location("_polestar_utils_under_test", utils_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "_polestar_utils_under_test", module)
    spec.loader.exec_module(module)
    return module


def test_icon_follows_the_state(monkeypatch):
    state_icon = _load_utils(monkeypatch).state_icon

    assert state_icon(True, "mdi:open", "mdi:closed", "mdi:default") == "mdi:open"
    assert state_icon(False, "mdi:open", "mdi:closed", "mdi:default") == "mdi:closed"


def test_unknown_state_shows_the_off_icon(monkeypatch):
    state_icon = _load_utils(monkeypatch).state_icon

    assert state_icon(None, "mdi:open", "mdi:closed", "mdi:default") == "mdi:closed"


def test_entities_without_state_icons_keep_their_normal_icon(monkeypatch):
    state_icon = _load_utils(monkeypatch).state_icon

    assert state_icon(True, None, None, "mdi:default") == "mdi:default"
    assert state_icon(False, None, None, None) is None


def test_unavailable_reason_is_none_while_available(monkeypatch):
    from types import SimpleNamespace

    from polestar_api.models.availability import UnavailableReason

    state = _load_utils(monkeypatch).unavailable_reason_state

    assert state(None) is None
    assert state(SimpleNamespace(is_available=True, unavailable_reason=UnavailableReason.UNSPECIFIED)) == "none"
    assert state(SimpleNamespace(is_available=False, unavailable_reason=UnavailableReason.CAR_IN_USE)) == "car_in_use"
    assert state(SimpleNamespace(is_available=False, unavailable_reason=UnavailableReason.UNSPECIFIED)) is None


def test_cold_battery_is_hidden_when_the_car_never_fills_it_in(monkeypatch):
    from polestar_api.models.battery import Battery, ColdBatteryStatus

    reports = _load_utils(monkeypatch).reports_cold_battery

    assert reports(None) is True  # no reading yet: don't hide it
    assert reports(Battery()) is False  # Polestar 2: field 30 never sent
    assert reports(Battery(cold_battery_status=ColdBatteryStatus.NORMAL)) is True
