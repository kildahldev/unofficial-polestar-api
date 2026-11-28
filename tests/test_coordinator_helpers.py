"""Pure coordinator helpers (HA is not installed in the test env)."""

import ast
from pathlib import Path

from polestar_api.models.privacy import PrivacySetting, PrivacySettingType


def _load_merge():
    src = Path(__file__).parents[1] / "custom_components/polestar/coordinator.py"
    tree = ast.parse(src.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "merge_privacy_setting")
    ns = {"PrivacySetting": PrivacySetting, "PrivacySettingType": PrivacySettingType}
    exec(compile(ast.Module([fn], []), "coordinator", "exec"), ns)  # noqa: S102
    return ns["merge_privacy_setting"]


def test_merge_privacy_setting_keeps_other_types():
    merge = _load_merge()
    a = PrivacySetting(setting_type=PrivacySettingType.PRIVACY_SETTING, enabled=True)
    b = PrivacySetting(setting_type=PrivacySettingType.VEHICLE_LOCATION_SHARING, enabled=True)
    state = merge(None, a)
    state = merge(state, b)
    assert set(state) == {PrivacySettingType.PRIVACY_SETTING, PrivacySettingType.VEHICLE_LOCATION_SHARING}
    b2 = PrivacySetting(setting_type=PrivacySettingType.VEHICLE_LOCATION_SHARING, enabled=False)
    assert merge(state, b2)[PrivacySettingType.VEHICLE_LOCATION_SHARING].enabled is False
    assert state[PrivacySettingType.VEHICLE_LOCATION_SHARING].enabled is True  # not mutated
