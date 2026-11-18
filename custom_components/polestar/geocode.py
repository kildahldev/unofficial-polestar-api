"""Street address for the car's position: pure helpers (no Home Assistant imports) so they can be tested.

The address comes from OpenStreetMap Nominatim; a Home Assistant zone the car is inside wins over it (Home, Work).
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
EARTH_RADIUS_M = 6371000.0


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


def zone_name(lat: float, lon: float, zones: list[dict[str, Any]]) -> str | None:
    """Name of the zone the position is inside. ``zones`` hold name, latitude, longitude, radius, passive, is_home.

    Home wins when the car is inside it; otherwise the smallest zone that contains it. Passive zones are skipped.
    """
    best: tuple[float, str] | None = None
    for zone in zones:
        if zone.get("passive"):
            continue
        try:
            radius = float(zone["radius"])
            inside = distance_m(lat, lon, float(zone["latitude"]), float(zone["longitude"])) <= radius
        except (KeyError, TypeError, ValueError):
            continue
        if not inside:
            continue
        if zone.get("is_home"):
            return zone["name"]
        if best is None or radius < best[0]:
            best = (radius, zone["name"])
    return best[1] if best else None


def pretty_address(reply: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """(short address such as "25 Martin Place, Sydney 2000", details) from a Nominatim reverse reply."""
    addr = reply.get("address") or {}
    house_number = addr.get("house_number")
    road = addr.get("road") or addr.get("pedestrian") or addr.get("footway")
    suburb = addr.get("suburb") or addr.get("neighbourhood") or addr.get("city_district")
    city = addr.get("city") or addr.get("town") or addr.get("village")
    postcode = addr.get("postcode")
    parts: list[str] = []
    if road:
        parts.append(f"{house_number} {road}" if house_number else road)
    elif addr.get("shop") or addr.get("amenity") or addr.get("building"):
        parts.append(addr.get("shop") or addr.get("amenity") or addr.get("building"))
    if suburb:
        parts.append(suburb)
    if city and city != suburb:
        parts.append(city)
    if postcode:
        parts.append(postcode)
    text = ", ".join(p for p in parts if p) or reply.get("display_name")
    details = {
        "house_number": house_number, "road": road, "suburb": suburb, "city": city,
        "postcode": postcode, "country": addr.get("country"),
    }
    return text, details
