"""MyCars service — vehicle identity + installed software version.

Ported from pypolestar/pypolestar#79 (https://github.com/pypolestar/pypolestar/pull/79).
Unlike OtaDiscoveryService/GetSoftwareInfo (ota.py), which only reports a
*pending* update and returns an intentionally empty message when nothing is
queued, this service reports the currently-installed software version
regardless of whether an update is pending. Confirmed C3-only in the
upstream PR, and live-tested end to end against two separate accounts here.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from .. import grpc as grpc_call
from ..codec import decode, encode
from ..models.mycars import MyCarEntry

if TYPE_CHECKING:
    from ..connection import GrpcConnection

_LOGGER = logging.getLogger(__name__)


class MyCarsServiceClient:
    def __init__(self, connection: GrpcConnection, vin: str) -> None:
        self._connection = connection
        self._vin = vin

    @property
    def _service(self) -> str:
        return self._connection.backend.mycars_svc

    async def _metadata(self) -> dict:
        metadata = await self._connection.get_metadata(self._vin)
        metadata["vin"] = self._vin
        return metadata

    async def get_mycars(self) -> MyCarEntry | None:
        """Get vehicle identity + installed software version, or ``None`` if unavailable."""
        req = encode(
            {"id": (1, "string"), "vin": (2, "string")},
            {"id": str(uuid.uuid4()), "vin": self._vin},
        )
        metadata = await self._metadata()
        data = await grpc_call.unary_unary(
            self._connection.channel,
            f"{self._service}/GetMyCars",
            req,
            metadata=metadata,
        )

        # GetMyCarsResponse.cars is `repeated MyCarEntry` (field 1). This
        # library's ProtoMessage wire helper doesn't decode repeated
        # *message* fields into a list on its own — codec.decode() just
        # accumulates raw bytes blobs under the same key, which can come
        # back as a single bytes object (one car on the account) or a
        # list of bytes objects (more than one car). Confirmed live: a
        # multi-car account returns a list here, so both shapes must be
        # handled and the right entry picked by matching VIN.
        raw = decode(data, {1: ("car", "message")})
        car_field = raw.get("car")
        if car_field is None:
            _LOGGER.warning("GetMyCars vin=%s: no car entry in response", self._vin)
            return None

        raw_entries = car_field if isinstance(car_field, list) else [car_field]
        entries = [MyCarEntry.from_bytes(entry_bytes) for entry_bytes in raw_entries]

        matching = next(
            (entry for entry in entries if entry.details and entry.details.vin == self._vin),
            None,
        )
        if matching is None and len(entries) == 1:
            # Single-car accounts sometimes don't echo the vin back
            # identically; fall back to the only entry present.
            matching = entries[0]
        if matching is None:
            _LOGGER.warning(
                "GetMyCars vin=%s: %d entries in response, none matched this VIN",
                self._vin,
                len(entries),
            )
            return None
        return matching
