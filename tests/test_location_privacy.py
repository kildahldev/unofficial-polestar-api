"""Location update filtering, privacy settings, car preview and error parsing."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from polestar_api.backend import C3
from polestar_api.codec import encode_bool, encode_int32, encode_message, encode_string
from polestar_api.models.common import Coordinate, Location, Timestamp, select_location_update
from polestar_api.models.mycars import CarPreview
from polestar_api.models.privacy import PrivacySetting, PrivacySettingType
from polestar_api.services.errors import parse_errors
from polestar_api.services.location import _parse_location_message
from polestar_api.services.mycars import MyCarsServiceClient
from polestar_api.services.privacy import PrivacyServiceClient


def _loc(lat=1.0, lon=2.0, secs=100, **kw):
    return Location(
        timestamp=Timestamp(seconds=secs), coordinate=Coordinate(longitude=lon, latitude=lat), **kw
    )


def test_select_location_first_update():
    new = _loc()
    assert select_location_update(None, new) is new


def test_select_location_ignores_older():
    assert select_location_update(_loc(secs=200), _loc(lat=5.0, secs=100)) is None


def test_select_location_ignores_identical():
    assert select_location_update(_loc(), _loc()) is None


def test_select_location_accepts_newer_or_moved():
    assert select_location_update(_loc(secs=100), _loc(secs=101)) is not None
    assert select_location_update(_loc(secs=100), _loc(lat=9.0, secs=100)) is not None


def test_select_location_accepts_stale_change():
    assert select_location_update(_loc(stale=False), _loc(stale=True)) is not None


def test_select_location_without_timestamps_dedupes_on_position():
    a = Location(coordinate=Coordinate(longitude=1.0, latitude=2.0))
    assert select_location_update(a, Location(coordinate=Coordinate(longitude=1.0, latitude=2.0))) is None
    assert select_location_update(a, Location(coordinate=Coordinate(longitude=1.5, latitude=2.0))) is not None


def _compact(lon=10.5, lat=59.9, secs=1700000000):
    from polestar_api.codec import encode_double

    return (
        encode_double(1, lon) + encode_double(2, lat)
        + encode_message(3, encode_int32(1, secs))
    )


def test_parked_location_stale_flag_parsed():
    data = encode_message(2, _compact()) + encode_bool(3, True)
    loc = _parse_location_message(data)
    assert loc.stale is True
    assert loc.coordinate.latitude == 59.9
    assert loc.timestamp.seconds == 1700000000


def test_parked_location_without_stale_is_none():
    loc = _parse_location_message(encode_message(2, _compact()))
    assert loc.stale is None
    assert loc.coordinate.longitude == 10.5


def test_timestamp_to_datetime():
    assert Timestamp().to_datetime() is None
    assert Timestamp(seconds=0, nanos=0).to_datetime() is None
    assert Timestamp(seconds=1700000000).to_datetime().isoformat() == "2023-11-14T22:13:20+00:00"


def test_privacy_setting_parse_missing_enabled_is_false():
    msg = PrivacySetting.from_bytes(encode_int32(1, 2))
    assert msg.setting_type == PrivacySettingType.VEHICLE_LOCATION_SHARING
    assert msg.enabled is False
    assert msg.read_only is False
    full = PrivacySetting.from_bytes(
        encode_int32(1, 1) + encode_string(2, "abc") + encode_bool(3, True) + encode_bool(4, True)
    )
    assert (full.service_id, full.enabled, full.read_only) == ("abc", True, True)


def test_privacy_unknown_type_maps_to_unspecified():
    assert PrivacySetting.from_bytes(encode_int32(1, 42)).setting_type == PrivacySettingType.UNSPECIFIED


async def test_privacy_stream_request_and_parse(monkeypatch):
    connection = SimpleNamespace(backend=C3, channel=object(), get_metadata=AsyncMock(return_value={}))
    calls = []

    async def fake_stream(channel, path, request, metadata=None):
        calls.append((path, request, metadata))
        yield encode_int32(1, 3) + encode_bool(3, True)

    monkeypatch.setattr("polestar_api.services.privacy.grpc_call.unary_stream", fake_stream)
    items = [s async for s in PrivacyServiceClient(connection, "VIN1").stream()]
    assert items[0].setting_type == PrivacySettingType.VEHICLE_DATA_SHARING and items[0].enabled
    path, request, metadata = calls[0]
    assert path == "/userServices.PrivacySettings/GetPrivacySettingsV2Stream"
    assert request == encode_string(1, "VIN1")
    assert metadata["vin"] == "VIN1"


async def test_car_preview(monkeypatch):
    connection = SimpleNamespace(backend=C3, channel=object(), get_metadata=AsyncMock(return_value={}))
    preview = (
        encode_string(1, "VIN1") + encode_bool(2, True) + encode_string(5, "Polestar 4")
        + encode_string(6, "2026") + encode_string(7, "DK") + encode_message(8, b"\x08\x01")
        + encode_string(10, "814")
    )
    rpc = AsyncMock(return_value=encode_message(1, preview))
    monkeypatch.setattr("polestar_api.services.mycars.grpc_call.unary_unary", rpc)
    result = await MyCarsServiceClient(connection, "VIN1").get_car_preview()
    assert isinstance(result, CarPreview)
    assert (result.vehicle_type_name, result.model_year, result.market, result.vehicle_type_code) == (
        "Polestar 4", "2026", "DK", "814",
    )
    assert result.has_owner is True
    assert rpc.call_args.args[1] == "/car_information.CarInformation/GetCarPreview"


async def test_car_preview_empty(monkeypatch):
    connection = SimpleNamespace(backend=C3, channel=object(), get_metadata=AsyncMock(return_value={}))
    monkeypatch.setattr("polestar_api.services.mycars.grpc_call.unary_unary", AsyncMock(return_value=b""))
    assert await MyCarsServiceClient(connection, "VIN1").get_car_preview() is None


def _ts(secs):
    return encode_message(9, encode_int32(1, secs))


def test_parse_errors_unwrapped():
    data = encode_string(1, "id1") + encode_string(2, "VIN") + encode_message(
        4, encode_int32(1, 3) + encode_int32(2, 2)
    ) + _ts(1700000000)
    err = parse_errors(data)
    assert err.category == "charge_location"
    assert (err.error_code, err.action_code) == (3, 2)
    assert err.error_name == "unknown_3"
    assert err.error_time.seconds == 1700000000
    assert err.error_id == "id1"


def test_parse_errors_wrapped_in_envelope():
    inner = encode_message(8, encode_int32(1, 5)) + _ts(1700000001)
    err = parse_errors(encode_string(1, "x") + encode_string(2, "VIN") + encode_message(3, inner))
    assert err.category == "target_soc"
    assert err.action_code is None
    assert err.error_code == 5


def test_parse_errors_amp_limit_unwrapped_and_empty():
    err = parse_errors(encode_message(3, encode_int32(1, 1)))
    assert err.category == "amp_limit" and err.error_code == 1
    assert parse_errors(b"") is None


async def test_privacy_get_reads_until_quiet_then_closes(monkeypatch):
    import asyncio

    connection = SimpleNamespace(backend=C3, channel=object(), get_metadata=AsyncMock(return_value={}))
    closed = []

    async def fake_stream(channel, path, request, metadata=None):
        try:
            yield encode_int32(1, 1) + encode_bool(3, True)
            yield encode_int32(1, 2) + encode_bool(3, True) + encode_bool(4, True)
            await asyncio.sleep(3600)  # server keeps the stream open
        finally:
            closed.append(True)

    monkeypatch.setattr("polestar_api.services.privacy.grpc_call.unary_stream", fake_stream)
    monkeypatch.setattr("polestar_api.services.privacy._IDLE_TIMEOUT", 0.05)
    settings = await PrivacyServiceClient(connection, "VIN1").get()
    assert set(settings) == {PrivacySettingType.PRIVACY_SETTING, PrivacySettingType.VEHICLE_LOCATION_SHARING}
    assert settings[PrivacySettingType.VEHICLE_LOCATION_SHARING].read_only is True
    assert closed == [True]


async def test_privacy_get_returns_none_when_nothing_arrives(monkeypatch):
    import asyncio

    connection = SimpleNamespace(backend=C3, channel=object(), get_metadata=AsyncMock(return_value={}))

    async def fake_stream(channel, path, request, metadata=None):
        await asyncio.sleep(3600)
        yield b""

    monkeypatch.setattr("polestar_api.services.privacy.grpc_call.unary_stream", fake_stream)
    monkeypatch.setattr("polestar_api.services.privacy._STREAM_TIMEOUT", 0.05)
    assert await PrivacyServiceClient(connection, "VIN1").get() is None
