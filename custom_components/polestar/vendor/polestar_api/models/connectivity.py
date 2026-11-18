"""Connectivity info — TCU connectivity status."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from ..wire import ProtoMessage
from .common import TimestampShort


class ConnectivityStatus(IntEnum):
    NOT_USED = 0
    UNAVAILABLE = 1
    DISCONNECTED = 2
    CONNECTED = 3


class NetworkType(IntEnum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    CDMA_1X = 2
    CDMA_EVDO = 3
    WCDMA = 4
    GSM = 5
    LTE = 6


class SignalStrength(IntEnum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    POOR = 2
    GOOD = 3
    STRONG = 4


@dataclass(frozen=True)
class ConnectivityInfo(ProtoMessage, schema={
    1: "status",
    2: "updated_timestamp",
    3: "network_type",
    4: "signal_strength",
}):
    status: ConnectivityStatus = ConnectivityStatus.NOT_USED
    updated_timestamp: TimestampShort | None = None
    network_type: NetworkType = NetworkType.UNSPECIFIED
    signal_strength: SignalStrength = SignalStrength.UNSPECIFIED

    @property
    def is_connected(self) -> bool:
        return self.status == ConnectivityStatus.CONNECTED
