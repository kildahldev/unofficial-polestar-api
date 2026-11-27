import pytest

from polestar_api.discovery import (
    APP_BACKEND_GRAPHQL_URL,
    APP_FORCE_UPDATE_VERSION,
    APP_USER_AGENT,
    _app_backend_headers,
    get_vehicles,
)
from polestar_api.exceptions import ApiError


class TestAppBackendHeaders:
    def test_spoofs_current_official_android_app(self):
        headers = _app_backend_headers("test-token")

        assert APP_FORCE_UPDATE_VERSION == "5.15.1"
        assert APP_USER_AGENT == "PolestarApp/5.15.1b9417 Android/14"
        assert headers["User-Agent"] == APP_USER_AGENT
        assert headers["X-Polestar-Force-Update-Version"] == APP_FORCE_UPDATE_VERSION
        assert headers["X-PolestarId-Authorization"] == "Bearer test-token"


class TestGetVehicles:
    @pytest.mark.asyncio
    async def test_sends_current_app_version_headers(
        self, monkeypatch, mock_vehicles_response
    ):
        captured: dict[str, object] = {}

        class FakeResponse:
            status_code = 200

            def json(self):
                return mock_vehicles_response

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, headers=None, json=None):
                captured["url"] = url
                captured["headers"] = headers
                captured["json"] = json
                return FakeResponse()

        monkeypatch.setattr("polestar_api.discovery.httpx.AsyncClient", FakeClient)

        vehicles = await get_vehicles("test-token")

        assert captured["url"] == APP_BACKEND_GRAPHQL_URL
        headers = captured["headers"]
        assert isinstance(headers, dict)
        assert headers["User-Agent"] == "PolestarApp/5.15.1b9417 Android/14"
        assert headers["X-Polestar-Force-Update-Version"] == "5.15.1"
        assert headers["X-PolestarId-Authorization"] == "Bearer test-token"
        assert len(vehicles) == 1
        assert vehicles[0].vin == "YV4TEST000T0000001"

    @pytest.mark.asyncio
    async def test_upgrade_required_is_api_error(self, monkeypatch):
        class FakeResponse:
            status_code = 426
            text = ""

            def json(self):
                raise ValueError("not json")

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def post(self, url, headers=None, json=None):
                return FakeResponse()

        monkeypatch.setattr("polestar_api.discovery.httpx.AsyncClient", FakeClient)

        with pytest.raises(ApiError, match="426") as exc_info:
            await get_vehicles("test-token")
        assert exc_info.value.status_code == 426
