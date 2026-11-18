"""Data-sharing / privacy-consent models (``userServices.PrivacySettings``).

Field numbers were recovered from the official app's protobuf-generated
message classes (``ServicesProtos`` on the C3 backend), not from live
traffic capture. ``RemoteFunctionDataSharing`` and ``PrivacySetting`` back
directly observed read calls (``GetRemoteFunctionDataSharing``,
``GetPrivacySettingsV2Stream``, ``GetPrivacySettingStateEx``); the write
path (``SetPrivacySettingStateRequest``) is schema-accurate but its RPC
call site was not seen in the decompiled app, so treat writes as
best-effort.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .common import Timestamp


class PrivacySettingType(IntEnum):
    UNSPECIFIED = 0
    PRIVACY_SETTING = 1
    VEHICLE_LOCATION_SHARING = 2
    VEHICLE_DATA_SHARING = 3


@dataclass(frozen=True)
class RemoteFunctionDataSharingRequest(ProtoMessage, schema={1: "vin"}):
    vin: str = ""


@dataclass(frozen=True)
class RemoteFunctionDataSharing(ProtoMessage, schema={
    1: "enabled",
    2: "car_in_sync",
    3: "read_only",
}):
    """Overall "share remote function data" consent toggle for a car."""

    enabled: bool = False
    car_in_sync: bool = False
    read_only: bool = False


@dataclass(frozen=True)
class PrivacySettingsStreamRequest(ProtoMessage, schema={1: "vin"}):
    vin: str = ""


@dataclass(frozen=True)
class PrivacySetting(ProtoMessage, schema={
    1: "setting_type",
    2: "service_id",
    3: "enabled",
    4: "read_only",
}):
    """One entry from the ``GetPrivacySettingsV2Stream`` subscription."""

    setting_type: PrivacySettingType = PrivacySettingType.UNSPECIFIED
    service_id: str = ""
    enabled: bool = False
    read_only: bool = False


@dataclass(frozen=True)
class PrivacySettingStateExRequest(ProtoMessage, schema={
    1: "vin",
    2: "service_id",
    3: "locale",
}):
    vin: str = ""
    service_id: str = ""
    locale: str = ""


@dataclass(frozen=True)
class PrivacySettingTexts(ProtoMessage, schema={
    1: "service_name",
    2: "service_description",
    3: "privacy_notice_name",
    4: "privacy_notice_url",
    5: "privacy_notice_version",
    6: "privacy_notice_market",
}):
    """Display text for a privacy setting, in the requested locale."""

    service_name: str = ""
    service_description: str = ""
    privacy_notice_name: str = ""
    privacy_notice_url: str = ""
    privacy_notice_version: str = ""
    privacy_notice_market: str = ""


@dataclass(frozen=True)
class PrivacySettingDetail(ProtoMessage, schema={
    1: "texts",
    2: "enabled",
    3: "set_by_user",
    4: "read_only",
    5: "read_only_reason",
    6: "expiry_time",
}):
    """A single named privacy setting's state, with display text."""

    texts: PrivacySettingTexts | None = None
    enabled: bool = False
    set_by_user: bool = False
    read_only: bool = False
    read_only_reason: str = ""
    expiry_time: Timestamp | None = None


@dataclass(frozen=True)
class SetPrivacySettingStateRequest(ProtoMessage, schema={
    1: "vin",
    2: "service_id",
    3: "enabled",
    4: "expiry_time",
    5: "privacy_notice_market",
    6: "privacy_notice_version",
}):
    """Best-effort: schema-accurate, but the RPC call site was not observed."""

    vin: str = ""
    service_id: str = ""
    enabled: bool = False
    expiry_time: Timestamp | None = None
    privacy_notice_market: str = ""
    privacy_notice_version: str = ""
