"""Privacy settings models (userServices.PrivacySettings/GetPrivacySettingsV2Stream).

Live-verified on C3: the server streams one setting per message, then keeps
the stream open for changes. proto3 omits false/0 fields, so a missing
``enabled`` field means ``False``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage


class PrivacySettingType(IntEnum):
    UNSPECIFIED = 0
    PRIVACY_SETTING = 1
    VEHICLE_LOCATION_SHARING = 2
    VEHICLE_DATA_SHARING = 3

    @classmethod
    def _missing_(cls, value: object) -> PrivacySettingType:
        return cls.UNSPECIFIED


@dataclass(frozen=True)
class PrivacySetting(ProtoMessage, schema={
    1: "setting_type",
    2: "service_id",
    3: "enabled",
    4: "read_only",
}):
    setting_type: PrivacySettingType = PrivacySettingType.UNSPECIFIED
    service_id: str = ""
    enabled: bool = False
    read_only: bool = False
