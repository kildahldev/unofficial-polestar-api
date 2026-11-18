"""The app's CarInformationByVins query supplies the plate when account discovery does not."""

from polestar_api.discovery import _extract_car_information_by_vins


def test_extracts_plate_and_year_by_vin():
    data = {"data": {"cars": {"carInformationByVins": [
        {"vin": "V1", "registrationNumber": "ABC123", "modelYear": "2026"},
        {"vin": "V2", "registrationNumber": "", "modelYear": None},
    ]}}}
    result = _extract_car_information_by_vins(data)
    assert result["V1"].registration_no == "ABC123"
    assert result["V1"].model_year == 2026
    assert result["V2"].registration_no is None
    assert result["V2"].model_year is None


def test_missing_or_malformed_data_gives_empty_result():
    assert _extract_car_information_by_vins({}) == {}
    assert _extract_car_information_by_vins({"data": {"cars": None}}) == {}
    assert _extract_car_information_by_vins({"data": {"cars": {"carInformationByVins": ["x", {"vin": ""}]}}}) == {}


def test_by_vins_also_returns_build_data():
    data = {"data": {"cars": {"carInformationByVins": [
        {"vin": "V1", "registrationNumber": "ABC123", "modelYear": "2026", "slug": "polestar-2",
         "structureWeek": "202611", "pno34": "534X", "isPrimaryDriver": True, "isBstEdition": False},
    ]}}}
    info = _extract_car_information_by_vins(data)["V1"]
    assert (info.slug, info.structure_week, info.pno34) == ("polestar-2", "202611", "534X")
    assert info.is_primary_driver is True and info.is_bst_edition is False


def test_model_name_falls_back_to_the_slug():
    from polestar_api.naming import model_from_slug
    from polestar_api.vehicle import Vehicle

    assert model_from_slug("polestar-2") == "Polestar 2"
    assert model_from_slug("polestar-4") == "Polestar 4"
    assert model_from_slug(None) is None and model_from_slug("") is None
    assert Vehicle(vin="YSMVSFDR8TL421810", connection=None, slug="polestar-2").model_name == "Polestar 2"
    assert Vehicle(vin="X", connection=None, model_name="Polestar 3", slug="polestar-2").model_name == "Polestar 3"


def test_failed_app_backend_query_logs_a_warning(monkeypatch, caplog):
    import asyncio
    import logging

    import httpx

    from polestar_api import discovery

    class FakeClient:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def post(self, *a, **k):
            return httpx.Response(401, json={})

    monkeypatch.setattr(discovery.httpx, "AsyncClient", FakeClient)
    with caplog.at_level(logging.WARNING):
        assert asyncio.run(discovery.get_car_information_by_vins("tok", ["V1"])) == {}
    messages = [r.getMessage() for r in caplog.records]
    assert any("HTTP 401" in m and "CarInformationByVins" in m for m in messages) or any("HTTP 401" in m for m in messages)
    assert not any("tok" == m for m in messages)


def test_vin_sensor_model_year_is_text():
    from pathlib import Path

    src = (Path(__file__).parents[1] / "custom_components" / "polestar" / "sensor.py").read_text()
    assert '"model_year": str(v.model_year) if v.model_year else None' in src
