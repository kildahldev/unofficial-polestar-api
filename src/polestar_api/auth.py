"""Async OIDC/PKCE authentication for the Polestar API."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qs, urljoin, urlparse

import ssl

import httpx

from .exceptions import AuthError, MfaRequiredError, TokenExpiredError

# Pre-build SSL context at import time so httpx never triggers
# blocking load_verify_locations inside the HA event loop (Python 3.14).
_HTTPX_SSL_CONTEXT = ssl.create_default_context()

OIDC_PROVIDER = "https://polestarid.eu.polestar.com"
OIDC_DISCOVERY = f"{OIDC_PROVIDER}/.well-known/openid-configuration"
CLIENT_ID = "lp8dyrd_10"
REDIRECT_URI = "polestar-explore://explore.polestar.com"
SCOPES = "openid profile email customer:attributes customer:attributes:write"
REAUTH_COOLDOWN = 300  # seconds between password logins from ensure_valid_token

# Since late November 2026 Polestar ID (PingFederate) hands the login over to a
# Keycloak realm on auth.polestar.com. The login page embeds a ``kcContext``
# object with the form target in ``loginAction`` and the page type in ``pageId``.
_KC_LOGIN_ACTION_RE = re.compile(r'"loginAction":\s*"([^"]+)"')
_KC_PAGE_ID_RE = re.compile(r'"pageId":\s*"([^"]+)"')
_KC_INVALID_CREDENTIALS = "Invalid username or password"
_MAX_REDIRECTS = 10
_REDIRECT_STATUSES = (301, 302, 303, 307, 308)


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


def _unescape_js_url(value: str) -> str:
    """Undo the JS/HTML escaping Keycloak applies to URLs in ``kcContext``."""
    return html.unescape(value.replace("\\/", "/"))


def _kc_page_id(text: str) -> str | None:
    match = _KC_PAGE_ID_RE.search(text)
    return match.group(1) if match else None


def _raise_for_kc_step(r: httpx.Response) -> None:
    """Raise ``MfaRequiredError`` if ``r`` is a Keycloak page asking for another step.

    Seen in November 2026: after the password, accounts with a pending
    "required action" are sent to ``/login-actions/required-action``, for
    example ``otp-phone`` (a one-time SMS code to verify the phone number).
    It happens once per account; signing in once at polestar.com or in the
    Polestar app clears it. Accepting new terms would land on the same path.
    """
    page_id = _kc_page_id(r.text)
    on_required_action = "/login-actions/required-action" in r.url.path
    if on_required_action or (page_id and page_id != "login"):
        raise MfaRequiredError(
            f"Polestar ID asked for another step after the password ({page_id or 'required action'}), "
            "for example a one-time code by SMS or accepting new terms. "
            "Sign in once at polestar.com or in the Polestar app with the same account, then retry."
        )


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
        self._refresh_lock = asyncio.Lock()
        self._last_reauth: float | None = None
        # Set when Polestar ID asks for a step we can't do (see _raise_for_kc_step);
        # blocks further automatic password logins until authenticate() is called.
        self._pending_step: str | None = None

    @property
    def access_token(self) -> str | None:
        return self._tokens.access_token if self._tokens else None

    async def authenticate(self, email: str, password: str) -> None:
        """Full OIDC/PKCE auth flow. Tries token refresh first if available."""
        self._email = email
        self._password = password
        self._pending_step = None

        # Try loading stored tokens
        self._tokens = await self._token_store.load()

        await self._discover_endpoints()

        if self._tokens and not self._tokens.is_expired:
            return

        if self._tokens and self._tokens.refresh_token:
            try:
                await self._refresh()
                return
            except (AuthError, httpx.HTTPStatusError):
                pass  # Fall through to full auth

        await self._full_auth(email, password)

    async def ensure_valid_token(self) -> str:
        """Return a valid access token, refreshing or re-authenticating if needed.

        Concurrent callers share a single refresh: the first one through the
        lock renews the token and the rest reuse it. A password login is
        attempted at most once per ``REAUTH_COOLDOWN`` seconds.
        """
        if not self._tokens:
            raise AuthError("Not authenticated")

        if not self._tokens.is_expired:
            return self._tokens.access_token

        async with self._refresh_lock:
            if not self._tokens.is_expired:
                return self._tokens.access_token

            if self._reauth_on_cooldown():
                raise TokenExpiredError("Token expired and re-authentication is on cooldown")

            if self._tokens.refresh_token:
                try:
                    await self._refresh()
                    return self._tokens.access_token
                except (AuthError, httpx.HTTPStatusError):
                    pass  # Refresh token also expired, fall through

            # Re-authenticate with stored credentials
            if not (self._email and self._password):
                raise TokenExpiredError("Token expired and no credentials available for re-auth")
            if self._pending_step is not None:
                # Each password login can send another SMS; wait for the user.
                raise MfaRequiredError(self._pending_step)
            self._last_reauth = time.monotonic()
            try:
                await self._full_auth(self._email, self._password)
            except MfaRequiredError as err:
                self._pending_step = str(err)
                raise

        return self._tokens.access_token

    def _reauth_on_cooldown(self) -> bool:
        if self._last_reauth is None:
            return False
        return time.monotonic() - self._last_reauth < REAUTH_COOLDOWN

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

            kc_match = _KC_LOGIN_ACTION_RE.search(r.text)
            if kc_match:
                return await self._authorize_keycloak(
                    client, _unescape_js_url(kc_match.group(1)), params, email, password
                )

            # Legacy PingFederate login form
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

    async def _authorize_keycloak(
        self,
        client: httpx.AsyncClient,
        login_action: str,
        params: dict[str, str],
        email: str,
        password: str,
    ) -> str:
        """Log in on the Keycloak page and follow the redirects back to the app."""
        r = await client.post(
            login_action,
            data={"username": email, "password": password, "credentialId": ""},
            follow_redirects=False,
        )
        if r.status_code not in _REDIRECT_STATUSES:
            if _KC_INVALID_CREDENTIALS in r.text:
                raise AuthError("Invalid username or password")
            _raise_for_kc_step(r)
            raise AuthError(
                f"Keycloak login failed (status {r.status_code}, page {_kc_page_id(r.text) or 'unknown'})"
            )

        # Keycloak -> PingFederate (/sp/.../cb.openid) -> app redirect URI with ?code=
        location = ""
        for _ in range(_MAX_REDIRECTS):
            location = urljoin(str(r.url), r.headers.get("location", ""))
            if not _should_follow_callback(location) or location.startswith(REDIRECT_URI):
                break
            r = await client.get(location, follow_redirects=False)
            if r.status_code not in _REDIRECT_STATUSES:
                # A Keycloak page here (rather than a redirect onwards) is a step
                # the account must finish first, e.g. a one-time SMS code to
                # verify the phone number or accepting new terms.
                _raise_for_kc_step(r)
                break
        else:
            raise AuthError("Too many redirects after Keycloak login")

        code = parse_qs(urlparse(location).query).get("code", [None])[0]
        if code is None:
            if _should_follow_callback(location):
                location = f"{urlparse(location).netloc}{urlparse(location).path}"
            raise AuthError(f"No auth code after Keycloak login (status {r.status_code}, at {location})")
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
