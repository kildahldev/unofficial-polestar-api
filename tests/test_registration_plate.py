"""The optional registration-plate override in the config flow and device info."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "polestar"


def _load_config_flow_helpers():
    """Load only the pure helpers from config_flow.py without Home Assistant installed."""
    src = (ROOT / "config_flow.py").read_text()
    start = src.index("def _normalise_plate")
    end = src.index("class PolestarOptionsFlow")
    ns: dict = {"Any": object, "CONF_REGISTRATION_PLATE": "registration_plate"}
    exec(src[start:end], ns)  # noqa: S102 - trusted repo source, pure functions only
    return ns["_normalise_plate"], ns["_clean_options"]


def test_plate_is_trimmed_and_upper_cased():
    normalise, _ = _load_config_flow_helpers()
    assert normalise("  nby42p ") == "NBY42P"
    assert normalise(None) == ""
    assert normalise("") == ""


def test_blank_plate_is_dropped_from_options():
    _, clean = _load_config_flow_helpers()
    assert clean({"update_interval": 600, "registration_plate": "  "}) == {"update_interval": 600}
    assert clean({"update_interval": 600, "registration_plate": "abc 123"}) == {
        "update_interval": 600,
        "registration_plate": "ABC 123",
    }
    assert clean({"update_interval": 600}) == {"update_interval": 600}


def test_reconfigure_keeps_the_vin_and_only_updates_the_login():
    src = (ROOT / "config_flow.py").read_text()
    step = src.split("async def async_step_reconfigure", 1)[1]
    assert "async_update_reload_and_abort" in step
    assert "data_updates={CONF_EMAIL: email, CONF_PASSWORD: password}" in step
    assert "CONF_VIN:" not in step.split("async_update_reload_and_abort", 1)[1].split(")", 1)[0]
    assert "async_set_unique_id" not in step


def test_every_entity_translation_key_has_an_english_name():
    import json
    import re

    strings = json.loads((ROOT / "strings.json").read_text())
    shipped = json.loads((ROOT / "translations" / "en.json").read_text())
    assert strings == shipped
    for platform, entries in strings["entity"].items():
        source = (ROOT / f"{platform}.py").read_text()
        for key, value in entries.items():
            assert value["name"], (platform, key)
            assert f'"{key}"' in source, (platform, key)
    # No description may still carry a literal name next to its key.
    for platform in strings["entity"]:
        source = (ROOT / f"{platform}.py").read_text()
        assert not re.search(r'\n\s+name="[^"]+",', source), platform
