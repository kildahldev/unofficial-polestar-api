import time

import pytest

from polestar_api.auth import MemoryTokenStore, TokenData


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
