"""Async OIDC/PKCE authentication for the Polestar API."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qs, urlparse

import ssl

import httpx

from .exceptions import AuthError, TokenExpiredError

# Pre-build SSL context at import time so httpx never triggers
# blocking load_verify_locations inside the HA event loop (Python 3.14).
_HTTPX_SSL_CONTEXT = ssl.create_default_context()

OIDC_PROVIDER = "https://polestarid.eu.polestar.com"
OIDC_DISCOVERY = f"{OIDC_PROVIDER}/.well-known/openid-configuration"
CLIENT_ID = "lp8dyrd_10"
REDIRECT_URI = "polestar-explore://explore.polestar.com"
SCOPES = "openid profile email customer:attributes customer:attributes:write"


@dataclass
class TokenData:
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int = 0
    obtained_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        if not self.expires_in:
            return False
        return time.time() > self.obtained_at + self.expires_in - 60  # 60s buffer

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "obtained_at": self.obtained_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TokenData:
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in", 0),
            obtained_at=data.get("obtained_at", 0),
        )


class TokenStore(Protocol):
    """Protocol for pluggable token persistence."""

    async def load(self) -> TokenData | None: ...
    async def save(self, tokens: TokenData) -> None: ...


class FileTokenStore:
    """Stores tokens in a JSON file."""

    def __init__(self, path: str | Path):
        self._path = Path(path).expanduser()

    async def load(self) -> TokenData | None:
        if not self._path.exists():
            return None
        data = json.loads(self._path.read_text())
        return TokenData.from_dict(data)

    async def save(self, tokens: TokenData) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(tokens.to_dict(), indent=2))
        self._path.chmod(0o600)


class MemoryTokenStore:
    """In-memory token store (no persistence)."""

    def __init__(self) -> None:
        self._tokens: TokenData | None = None

    async def load(self) -> TokenData | None:
        return self._tokens

    async def save(self, tokens: TokenData) -> None:
        self._tokens = tokens


def _b64urlencode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _generate_pkce() -> tuple[str, str]:
    verifier = _b64urlencode(os.urandom(32))
    challenge = _b64urlencode(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def _should_follow_callback(location: str) -> bool:
    """Return whether the callback URL can be fetched over HTTP."""
    return urlparse(location).scheme in {"http", "https"}


class AuthManager:
    """Manages OIDC authentication and token lifecycle."""

    def __init__(self, token_store: TokenStore | None = None) -> None:
        self._token_store = token_store or MemoryTokenStore()
        self._tokens: TokenData | None = None
        self._auth_endpoint: str | None = None
        self._token_endpoint: str | None = None
        self._email: str | None = None
        self._password: str | None = None

    @property
    def access_token(self) -> str | None:
        return self._tokens.access_token if self._tokens else None

    async def authenticate(self, email: str, password: str) -> None:
        """Full OIDC/PKCE auth flow. Tries token refresh first if available."""
        self._email = email
        self._password = password

        # Try loading stored tokens
        self._tokens = await self._token_store.load()

        await self._discover_endpoints()

        if self._tokens and self._tokens.refresh_token:
            try:
                await self._refresh()
                return
            except (AuthError, httpx.HTTPStatusError):
                pass  # Fall through to full auth

        await self._full_auth(email, password)

    async def ensure_valid_token(self) -> str:
        """Return a valid access token, refreshing or re-authenticating if needed."""
        if not self._tokens:
            raise AuthError("Not authenticated")

        if self._tokens.is_expired:
            if self._tokens.refresh_token:
                try:
                    await self._refresh()
                    return self._tokens.access_token
                except (AuthError, httpx.HTTPStatusError):
                    pass  # Refresh token also expired, fall through

            # Re-authenticate with stored credentials
            if self._email and self._password:
                await self._full_auth(self._email, self._password)
            else:
                raise TokenExpiredError("Token expired and no credentials available for re-auth")

        return self._tokens.access_token

    async def _discover_endpoints(self) -> None:
        async with httpx.AsyncClient(verify=_HTTPX_SSL_CONTEXT) as client:
            r = await client.get(OIDC_DISCOVERY)
            r.raise_for_status()
            config = r.json()
            self._auth_endpoint = config["authorization_endpoint"]
            self._token_endpoint = config["token_endpoint"]

    async def _full_auth(self, email: str, password: str) -> None:
        if not self._auth_endpoint or not self._token_endpoint:
            await self._discover_endpoints()

        code_verifier, code_challenge = _generate_pkce()
        code = await self._authorize(code_challenge, email, password)
        await self._exchange_token(code, code_verifier)

    async def _authorize(self, code_challenge: str, email: str, password: str) -> str:
        state = _b64urlencode(os.urandom(32))
        params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "response_mode": "query",
        }

        async with httpx.AsyncClient(verify=_HTTPX_SSL_CONTEXT, follow_redirects=True, timeout=30) as client:
            # Step 1: GET auth endpoint — lands on login page
            r = await client.get(self._auth_endpoint, params=params)

            # Extract resume path from PingFederate HTML/JS
            resume_match = re.search(r'(?:url|action):\s*"(.+)"', r.text)
            if not resume_match:
                raise AuthError(f"Could not find resume path in auth response (status {r.status_code})")

            resume_url = f"{OIDC_PROVIDER}{resume_match.group(1)}"

            # Step 2: POST credentials
            r = await client.post(
                resume_url,
                params=params,
                data={"pf.username": email, "pf.pass": password},
                follow_redirects=False,
            )

            if r.status_code not in (302, 303):
                if "ERR001" in r.text:
                    raise AuthError("Invalid username or password")
                raise AuthError(f"Auth failed with status {r.status_code}")

            # Step 3: Extract code from redirect
            location = r.headers.get("location", "")
            parsed = urlparse(location)
            qs = parse_qs(parsed.query)

            code = qs.get("code", [None])[0]
            uid = qs.get("uid", [None])[0]

            # Handle Terms & Conditions acceptance
            if code is None and uid is not None:
                r = await client.post(
                    resume_url,
                    params=params,
                    data={"pf.submit": "true", "subject": uid},
                    follow_redirects=False,
                )
                if r.status_code in (302, 303):
                    location = r.headers.get("location", "")
                    parsed = urlparse(location)
                    qs = parse_qs(parsed.query)
                    code = qs.get("code", [None])[0]

            if code is None:
                raise AuthError(f"No auth code in redirect: {location}")

            # Old web flows used an HTTPS callback we could fetch; the current
            # mobile-app flow redirects to a custom scheme that is not fetchable.
            if _should_follow_callback(location):
                await client.get(location)

        return code

    async def _exchange_token(self, code: str, code_verifier: str) -> None:
        async with httpx.AsyncClient(verify=_HTTPX_SSL_CONTEXT) as client:
            r = await client.post(
                self._token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                    "client_id": CLIENT_ID,
                    "code_verifier": code_verifier,
                },
            )
            r.raise_for_status()
            data = r.json()

        self._tokens = TokenData(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in", 0),
        )
        await self._token_store.save(self._tokens)

    async def _refresh(self) -> None:
        if not self._token_endpoint:
            await self._discover_endpoints()

        if not self._tokens or not self._tokens.refresh_token:
            raise AuthError("No refresh token available")

        async with httpx.AsyncClient(verify=_HTTPX_SSL_CONTEXT) as client:
            r = await client.post(
                self._token_endpoint,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._tokens.refresh_token,
                    "client_id": CLIENT_ID,
                },
            )
            if r.status_code >= 400:
                raise AuthError(f"Token refresh failed: {r.status_code}")
            data = r.json()

        self._tokens = TokenData(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", self._tokens.refresh_token),
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in", 0),
        )
        await self._token_store.save(self._tokens)
