import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "geocode_under_test", Path(__file__).parent.parent / "custom_components/polestar/geocode.py"
)
geocode = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geocode)

HOME = {"name": "Home", "latitude": -33.8688, "longitude": 151.2093, "radius": 100, "is_home": True}
WORK = {"name": "Work", "latitude": -33.8700, "longitude": 151.2100, "radius": 50}


def test_zone_wins_and_home_is_preferred():
    assert geocode.zone_name(-33.8688, 151.2093, [WORK, HOME]) == "Home"
    assert geocode.zone_name(-33.8700, 151.2100, [HOME, WORK]) == "Work"
    assert geocode.zone_name(-34.0, 151.0, [HOME, WORK]) is None


def test_smallest_zone_and_passive_zones_skipped():
    big = {"name": "Suburb", "latitude": -33.8700, "longitude": 151.2100, "radius": 5000}
    assert geocode.zone_name(-33.8700, 151.2100, [big, WORK]) == "Work"
    assert geocode.zone_name(-33.8700, 151.2100, [dict(WORK, passive=True)]) is None
    assert geocode.zone_name(-33.87, 151.21, [{"name": "bad"}]) is None


def test_pretty_address_like_the_volvo_sensor():
    reply = {
        "display_name": "long form",
        "address": {"house_number": "25", "road": "Martin Place", "suburb": "Sydney", "city": "Sydney", "postcode": "2000"},
    }
    text, details = geocode.pretty_address(reply)
    assert text == "25 Martin Place, Sydney, 2000"
    assert details["road"] == "Martin Place" and details["postcode"] == "2000"
    assert geocode.pretty_address({"display_name": "Somewhere"})[0] == "Somewhere"
    text, _ = geocode.pretty_address({"address": {"amenity": "Cafe", "town": "Berry"}})
    assert text == "Cafe, Berry"
