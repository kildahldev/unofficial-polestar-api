"""Error service — last command errors reported by the car (server-streaming).

UNVERIFIED: live, the stream opened but sent nothing (no errors present), so
the parser below is based on the app's schema.

GetErrorsResponse: f1 id, f2 vin, f3 amp_limit_error{f1 error},
f4 charge_location_error{f1 error, f2 action}, f5 charge_now_error{f1, f2},
f6 global_charge_timer_error{f1}, f7 parking_climate_timer_error{f1, f2},
f8 target_soc_error{f1}, f9 error_time (Timestamp).

The response may be wrapped in a chronos envelope (payload at f3 bytes, as in
amp_limit.py) — parsing handles both.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode
from ..models.common import Timestamp
from ..models.errors import CommandError
from .chronos import wrap_chronos

if TYPE_CHECKING:
    from ..connection import GrpcConnection

# field number -> (category, has_action)
_CATEGORIES: dict[int, tuple[str, bool]] = {
    3: ("amp_limit", False),
    4: ("charge_location", True),
    5: ("charge_now", True),
    6: ("global_charge_timer", False),
    7: ("parking_climate_timer", True),
    8: ("target_soc", False),
}


def _has_error_fields(raw: dict) -> bool:
    return any(isinstance(raw.get(n), bytes) for n in range(4, 9)) or isinstance(raw.get(9), bytes)


def parse_errors(data: bytes) -> CommandError | None:
    """Parse a GetErrorsResponse (wrapped or not); ``None`` if no error is present."""
    raw = decode(data)
    if not _has_error_fields(raw):
        # Either wrapped (payload at f3 holds a GetErrorsResponse) or an
        # unwrapped message whose only category is amp_limit_error at f3.
        payload = raw.get(3)
        if isinstance(payload, bytes):
            inner = decode(payload)
            if _has_error_fields(inner) or isinstance(inner.get(3), bytes):
                raw = inner
    error_id = raw.get(1)
    error_time = raw.get(9)
    parsed_time = Timestamp.from_bytes(error_time) if isinstance(error_time, bytes) else None
    for number, (category, has_action) in _CATEGORIES.items():
        body = raw.get(number)
        if not isinstance(body, bytes):
            continue
        fields = decode(body)
        error = fields.get(1, 0)
        action = fields.get(2, 0) if has_action else None
        return CommandError(
            category=category,
            error_code=int(error) if isinstance(error, int) else 0,
            action_code=int(action) if isinstance(action, int) else None,
            error_id=error_id.decode("utf-8", "replace") if isinstance(error_id, bytes) else "",
            error_time=parsed_time,
        )
    return None


class ErrorServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _svc(self) -> str:
        return self._connection.backend.error_svc

    async def stream(self) -> AsyncIterator[CommandError]:
        """Stream command errors; messages without a recognised error are skipped."""
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        async for data in grpc_call.unary_stream(
            self._connection.channel,
            f"{self._svc}/GetErrors",
            wrap_chronos(self._vin),
            metadata=metadata,
        ):
            parsed = parse_errors(data)
            if parsed is not None:
                yield parsed
