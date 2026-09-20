"""MyCars models — vehicle identity + installed software version.

Ported from pypolestar/pypolestar#79 (https://github.com/pypolestar/pypolestar/pull/79),
which reverse-engineered this gRPC service directly against a real account —
no external schema existed anywhere for it before that PR. Only fields with
a confirmed, ground-truth match against a live account are modeled here
(vin, model_name, model_year, market all matched known values exactly;
installed_software_version matched the version reported by the official
app). The real response has ~80 more fields per car (capability flags,
factory option codes, etc.) that are visible on the wire but not confidently
namable; they're left unmapped (protobuf silently preserves unknown fields
rather than erroring, so omitting them here is safe).

The upstream PR also claims a `registration_no` field on the car entry —
that did NOT hold up against a second live account (AU market, 2026 model
year): the entry only ever has one top-level field there, confirmed by
walking every field byte-by-byte, with no plate-like string anywhere in the
response. Likely account/market-dependent; left out of this port rather
than modeling a field that isn't reliably present.

Distinct from OtaDiscoveryService/GetSoftwareInfo (see ota.py): that service
only reports a *pending* update and returns an intentionally empty message
when nothing is queued, so it can't answer "what version is currently
installed" for a car that's already up to date. This service can.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..wire import ProtoMessage


@dataclass(frozen=True)
class CarDetails(ProtoMessage, schema={
    1: "vin",
    6: "model_name",
    7: "model_year",
    9: "installed_software_version",
    10: "market",
}):
    vin: str = ""
    model_name: str = ""
    model_year: str = ""
    installed_software_version: str = ""
    market: str = ""


@dataclass(frozen=True)
class MyCarEntry(ProtoMessage, schema={
    1: "details",
}):
    """A single car entry from GetMyCarsResponse.

    Only field 1 (``details``) is modeled — see the module docstring for
    why a claimed ``registration_no`` field isn't included.
    """

    details: CarDetails | None = None


# GetMyCarsResponse.cars (field 1) is `repeated MyCarEntry` — confirmed
# live against a two-car account, where it comes back as two separate
# length-delimited field-1 entries on the wire. This library's
# ProtoMessage wire helper doesn't decode repeated *message* fields into
# a list, so there's no GetMyCarsResponse model here — MyCarsServiceClient
# decodes the response directly with codec.decode() instead, which
# naturally accumulates repeated same-numbered fields into a list, and
# picks the right entry by matching VIN.
