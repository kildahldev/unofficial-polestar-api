import pytest


@pytest.fixture
def mock_token_response():
    return {
        "access_token": "test-access-token-12345",
        "refresh_token": "test-refresh-token-67890",
        "token_type": "Bearer",
        "expires_in": 3600,
    }


@pytest.fixture
def mock_oidc_config():
    return {
        "authorization_endpoint": "https://polestarid.eu.polestar.com/as/authorization.oauth2",
        "token_endpoint": "https://polestarid.eu.polestar.com/as/token.oauth2",
    }


@pytest.fixture
def mock_vehicles_response():
    return {
        "data": {
            "vdms": {
                "getVehiclesInformation": [
                    {
                        "vin": "YV4TEST000T0000001",
                        "internalVehicleIdentifier": "abc-123",
                        "registrationNo": "AB12345",
                        "modelYear": 2026,
                        "content": {"model": {"name": "Polestar 4"}},
                    },
                ]
            }
        }
    }
