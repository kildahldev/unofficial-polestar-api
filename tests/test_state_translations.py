"""Every state an enum sensor can report has a display translation (and nothing else is translated)."""

from __future__ import annotations

import ast
import importlib
import json
import pkgutil
from pathlib import Path

ROOT = Path(__file__).parents[1] / "custom_components" / "polestar"
_EXCLUDED = {"UNSPECIFIED", "UNDEFINED", "UNKNOWN"}


def _enum_class(name: str):
    import polestar_api.models as models

    for info in pkgutil.iter_modules(models.__path__):
        module = importlib.import_module(f"polestar_api.models.{info.name}")
        if hasattr(module, name):
            return getattr(module, name)
    raise AssertionError(name)


def _enum_sensors() -> dict[str, tuple[str, bool]]:
    """translation_key -> (enum class name, exclude_unspecified), read from the sensor descriptions."""
    found: dict[str, tuple[str, bool]] = {}
    for node in ast.walk(ast.parse((ROOT / "sensor.py").read_text())):
        if not isinstance(node, ast.Call):
            continue
        keywords = {k.arg: k.value for k in node.keywords}
        options = keywords.get("options")
        if not (isinstance(options, ast.Call) and getattr(options.func, "id", "") == "enum_options"):
            continue
        key = ast.literal_eval(keywords["translation_key"])
        exclude = True
        for kw in options.keywords:
            if kw.arg == "exclude_unspecified":
                exclude = ast.literal_eval(kw.value)
        found[key] = (options.args[0].id, exclude)
    return found


def test_every_enum_state_has_a_translation():
    sensors = _enum_sensors()
    assert len(sensors) >= 9
    for path in ("strings.json", "translations/en.json"):
        translated = json.loads((ROOT / path).read_text())["entity"]["sensor"]
        for key, (cls, exclude) in sensors.items():
            options = {m.name.lower() for m in _enum_class(cls) if not (exclude and m.name in _EXCLUDED)}
            assert set(translated[key]["state"]) == options, f"{path}: {key}"
