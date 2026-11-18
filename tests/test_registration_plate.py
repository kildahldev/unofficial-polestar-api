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
