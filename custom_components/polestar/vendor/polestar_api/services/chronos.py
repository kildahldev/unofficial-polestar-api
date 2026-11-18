"""ChronosRequest envelope used by all chronos gRPC services.

APK structure:
    ChronosRequest {
        field 1: string id           — random UUID
        field 2: string vin
        field 3: string source       — always "RCS"
        field 4: TimeZone {
            field 1: int32 offset_minutes
        }
    }

Every chronos service request wraps this at field 1.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..codec import encode, encode_message


def _utc_offset_minutes() -> int:
    """Return the local UTC offset in minutes."""
    now = datetime.now(timezone.utc).astimezone()
    return int(now.utcoffset().total_seconds()) // 60


def build_chronos_request(vin: str) -> bytes:
    """Build a serialized ChronosRequest for the given VIN."""
    tz_bytes = encode({"offset": (1, "int32")}, {"offset": _utc_offset_minutes()})
    return encode(
        {
            "id": (1, "string"),
            "vin": (2, "string"),
            "source": (3, "string"),
            "time_zone": (4, "message"),
        },
        {
            "id": str(uuid.uuid4()),
            "vin": vin,
            "source": "RCS",
            "time_zone": tz_bytes,
        },
    )


def wrap_chronos(vin: str, payload: bytes = b"") -> bytes:
    """Wrap a chronos service request with ChronosRequest at field 1.

    If *payload* contains additional fields (starting at field 2+),
    they are appended after the ChronosRequest.
    """
    return encode_message(1, build_chronos_request(vin)) + payload
