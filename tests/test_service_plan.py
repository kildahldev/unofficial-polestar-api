"""The Service plan sensor: the app's PolestarServicePlansForVin query and the sensor's attributes."""

import asyncio

import httpx

from polestar_api import discovery

from .test_climate_sync import utils  # noqa: F401  (the utils.py loader fixture)

# Shape reported from a UK-market account (Nov 2026), ids and VIN replaced.
REPLY = {"data": {"servicePlan": {"getServicePlan": [{
    "id": "plan-id", "vin": "VIN", "name": "PS Service Contract, 60 months", "mileageUnit": "km",
    "status": "VALID", "productStatus": "ACTIVE",
    "products": [
        {"id": "a", "name": "Car Wash", "qw90ClaimType": "PSICW", "startDate": "2025-10-29T00:00:00+00:00",
         "endDate": "2030-10-28T00:00:00+00:00", "mileage": 100000},
        {"id": "b", "name": "Scheduled Maintenance", "qw90ClaimType": "PSISM", "startDate": "2025-10-29T00:00:00+00:00",
         "endDate": "2030-10-28T00:00:00+00:00", "mileage": 100000},
        {"id": "c", "name": "Pick-up and delivery", "qw90ClaimType": "PSIPD", "startDate": "2025-10-29T00:00:00+00:00",
         "endDate": "2030-10-28T00:00:00+00:00", "mileage": 100000},
    ],
}]}}}


def _run(monkeypatch, reply, status=200):
    sent = {}

    class FakeClient:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def post(self, url, headers=None, json=None):
            sent.update(json)
            return httpx.Response(status, json=reply)

    monkeypatch.setattr(discovery.httpx, "AsyncClient", FakeClient)
    return asyncio.run(discovery.get_service_plan("tok", "VIN")), sent


def test_plan_is_read_without_ids_or_vin(monkeypatch):
    plan, sent = _run(monkeypatch, REPLY)

    assert sent["operationName"] == "PolestarServicePlansForVin" and sent["variables"] == {"vin": "VIN"}
    assert "mutation" not in sent["query"]
    assert plan["name"] == "PS Service Contract, 60 months"
    assert (plan["status"], plan["product_status"], plan["mileage_unit"]) == ("VALID", "ACTIVE", "km")
    assert plan["products"][0] == {"name": "Car Wash", "start": "2025-10-29", "end": "2030-10-28", "mileage": 100000}
    assert "VIN" not in repr(plan) and "plan-id" not in repr(plan)


def test_no_plan_or_a_failure_gives_none(monkeypatch):
    assert _run(monkeypatch, {"data": {"servicePlan": {"getServicePlan": []}}})[0] is None
    assert _run(monkeypatch, {"data": {"servicePlan": None}})[0] is None
    assert _run(monkeypatch, {"errors": [{"message": "nope"}]})[0] is None
    assert _run(monkeypatch, {}, status=500)[0] is None


def test_attributes_are_flat_and_readable(monkeypatch, utils):
    plan, _ = _run(monkeypatch, REPLY)

    assert utils.service_plan_attributes(plan) == {
        "status": "valid",
        "product_status": "active",
        "ends": "2030-10-28",
        "car_wash_start": "2025-10-29",
        "car_wash_end": "2030-10-28",
        "car_wash_mileage_limit": "100000 km",
        "scheduled_maintenance_start": "2025-10-29",
        "scheduled_maintenance_end": "2030-10-28",
        "scheduled_maintenance_mileage_limit": "100000 km",
        "pick_up_and_delivery_start": "2025-10-29",
        "pick_up_and_delivery_end": "2030-10-28",
        "pick_up_and_delivery_mileage_limit": "100000 km",
    }
    assert utils.service_plan_attributes(None) == {}
