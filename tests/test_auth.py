import asyncio
import time
from urllib.parse import parse_qs

import httpx
import pytest

from polestar_api import auth
from polestar_api.auth import AuthManager, MemoryTokenStore, TokenData
from polestar_api.exceptions import AuthError, TokenExpiredError


class TestTokenData:
    def test_not_expired(self):
        token = TokenData(
            access_token="test",
            expires_in=3600,
            obtained_at=time.time(),
        )
        assert not token.is_expired

    def test_expired(self):
        token = TokenData(
            access_token="test",
            expires_in=3600,
            obtained_at=time.time() - 3700,
        )
        assert token.is_expired

    def test_expired_with_buffer(self):
        # Token that expires in 30s should be considered expired (60s buffer)
        token = TokenData(
            access_token="test",
            expires_in=3600,
            obtained_at=time.time() - 3580,
        )
        assert token.is_expired

    def test_round_trip_dict(self):
        token = TokenData(
            access_token="access",
            refresh_token="refresh",
            token_type="Bearer",
            expires_in=3600,
        )
        restored = TokenData.from_dict(token.to_dict())
        assert restored.access_token == token.access_token
        assert restored.refresh_token == token.refresh_token
        assert restored.expires_in == token.expires_in


class TestMemoryTokenStore:
    @pytest.mark.asyncio
    async def test_load_empty(self):
        store = MemoryTokenStore()
        assert await store.load() is None

    @pytest.mark.asyncio
    async def test_save_and_load(self):
        store = MemoryTokenStore()
        token = TokenData(access_token="test", refresh_token="refresh")
        await store.save(token)
        loaded = await store.load()
        assert loaded is not None
        assert loaded.access_token == "test"


class _FakeOidc:
    """In-process stand-in for the PingFederate endpoints, counting each call."""

    def __init__(self, oidc_config, token_response):
        self.oidc_config = oidc_config
        self.token_response = token_response
        self.refresh_status = 200
        self.login_ok = True
        self.refreshes = 0
        self.logins = 0

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.01)
        url = str(request.url)
        if url.startswith(auth.OIDC_DISCOVERY):
            return httpx.Response(200, json=self.oidc_config)
        if url.startswith(self.oidc_config["authorization_endpoint"]):
            return httpx.Response(200, text='action: "/as/resume/abc"')
        if url.startswith(f"{auth.OIDC_PROVIDER}/as/resume/abc"):
            self.logins += 1
            if not self.login_ok:
                return httpx.Response(200, text="ERR001")
            return httpx.Response(302, headers={"location": f"{auth.REDIRECT_URI}?code=c0de"})
        if url.startswith(self.oidc_config["token_endpoint"]):
            form = parse_qs(request.content.decode())
            if form["grant_type"] == ["refresh_token"]:
                self.refreshes += 1
                if self.refresh_status >= 400:
                    return httpx.Response(self.refresh_status, json={"error": "invalid_grant"})
            return httpx.Response(200, json=self.token_response)
        raise AssertionError(f"unexpected request {request.method} {url}")


@pytest.fixture
def fake_oidc(monkeypatch, mock_oidc_config, mock_token_response):
    fake = _FakeOidc(mock_oidc_config, mock_token_response)
    transport = httpx.MockTransport(fake)
    real_client = httpx.AsyncClient

    def _client(**kwargs):
        kwargs.pop("verify", None)
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(auth.httpx, "AsyncClient", _client)
    return fake


def _expired_tokens() -> TokenData:
    return TokenData(
        access_token="old-access",
        refresh_token="old-refresh",
        expires_in=3600,
        obtained_at=time.time() - 7200,
    )


async def _manager_with_expired_token(fake_oidc) -> AuthManager:
    manager = AuthManager()
    await manager.authenticate("user@example.com", "pw")
    manager._tokens = _expired_tokens()
    fake_oidc.refreshes = 0
    fake_oidc.logins = 0
    return manager


class TestAuthenticate:
    async def test_valid_stored_token_is_reused_without_refresh(self, fake_oidc):
        store = MemoryTokenStore()
        await store.save(TokenData(access_token="stored", refresh_token="r", expires_in=3600))
        manager = AuthManager(token_store=store)

        await manager.authenticate("user@example.com", "pw")

        assert manager.access_token == "stored"
        assert fake_oidc.refreshes == 0
        assert fake_oidc.logins == 0

    async def test_expired_stored_token_is_refreshed(self, fake_oidc, mock_token_response):
        store = MemoryTokenStore()
        await store.save(_expired_tokens())
        manager = AuthManager(token_store=store)

        await manager.authenticate("user@example.com", "pw")

        assert manager.access_token == mock_token_response["access_token"]
        assert fake_oidc.refreshes == 1
        assert fake_oidc.logins == 0

    async def test_no_stored_token_logs_in(self, fake_oidc, mock_token_response):
        manager = AuthManager()

        await manager.authenticate("user@example.com", "pw")

        assert manager.access_token == mock_token_response["access_token"]
        assert fake_oidc.logins == 1


class TestEnsureValidToken:
    async def test_valid_token_makes_no_calls(self, fake_oidc):
        manager = await _manager_with_expired_token(fake_oidc)
        manager._tokens = TokenData(access_token="fresh", expires_in=3600)

        assert await manager.ensure_valid_token() == "fresh"
        assert fake_oidc.refreshes == 0
        assert fake_oidc.logins == 0

    async def test_concurrent_callers_share_one_refresh(self, fake_oidc, mock_token_response):
        manager = await _manager_with_expired_token(fake_oidc)

        tokens = await asyncio.gather(*(manager.ensure_valid_token() for _ in range(20)))

        assert fake_oidc.refreshes == 1
        assert fake_oidc.logins == 0
        assert set(tokens) == {mock_token_response["access_token"]}

    async def test_refresh_failure_triggers_exactly_one_login(
        self, fake_oidc, mock_token_response
    ):
        manager = await _manager_with_expired_token(fake_oidc)
        fake_oidc.refresh_status = 400

        tokens = await asyncio.gather(*(manager.ensure_valid_token() for _ in range(20)))

        assert fake_oidc.refreshes == 1
        assert fake_oidc.logins == 1
        assert set(tokens) == {mock_token_response["access_token"]}

    async def test_failed_login_is_not_retried_within_cooldown(self, fake_oidc):
        manager = await _manager_with_expired_token(fake_oidc)
        fake_oidc.refresh_status = 400
        fake_oidc.login_ok = False

        results = await asyncio.gather(
            *(manager.ensure_valid_token() for _ in range(20)), return_exceptions=True
        )

        assert fake_oidc.logins == 1
        assert fake_oidc.refreshes == 1
        assert all(isinstance(r, AuthError) for r in results)
        assert sum(isinstance(r, TokenExpiredError) for r in results) == 19

        with pytest.raises(TokenExpiredError):
            await manager.ensure_valid_token()
        assert fake_oidc.logins == 1

    async def test_login_is_retried_after_cooldown(self, fake_oidc):
        manager = await _manager_with_expired_token(fake_oidc)
        fake_oidc.refresh_status = 400
        fake_oidc.login_ok = False
        with pytest.raises(AuthError):
            await manager.ensure_valid_token()

        fake_oidc.login_ok = True
        manager._last_reauth -= auth.REAUTH_COOLDOWN + 1
        await manager.ensure_valid_token()

        assert fake_oidc.logins == 2

    async def test_no_credentials_raises_token_expired(self, fake_oidc):
        manager = AuthManager()
        manager._tokens = TokenData(access_token="old", expires_in=3600, obtained_at=0)

        with pytest.raises(TokenExpiredError):
            await manager.ensure_valid_token()
        assert fake_oidc.logins == 0
