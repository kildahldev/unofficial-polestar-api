"""Login flow against the Keycloak page Polestar ID redirects to (since 2026-11)."""

import json
from urllib.parse import parse_qs

import httpx
import pytest

from polestar_api import auth as auth_mod
from polestar_api.auth import AuthManager, MemoryTokenStore
from polestar_api.exceptions import AuthError, MfaRequiredError

PING = "https://polestarid.eu.polestar.com"
KC = "https://auth.polestar.com"
LOGIN_ACTION = (
    f"{KC}/realms/polestar/login-actions/authenticate"
    "?session_code=abc&execution=exec-1&client_id=volvocars-pingfederate-client&tab_id=tab-1"
)


def _kc_page(page_id: str, summary: str | None = None) -> str:
    """Minimal stand-in for the Keycloak login page with its kcContext."""
    # Keycloak escapes "/" as "\/" and "&" as "&amp;" inside kcContext
    action = LOGIN_ACTION.replace("/", "\\/").replace("&", "&amp;")
    message = (
        f'"message": {{ "summary": "{summary}", "type": "error" }},' if summary else ""
    )
    return f"""<html><script>
    const kcContext = {{
        "url": {{
            "loginAction": "{action}",
            "loginUrl": "\\/realms/polestar/login-actions/authenticate?client_id=x",
        }},
        {message}
        "pageId": "{page_id}",
    }};
    </script></html>"""


class FakePolestarId:
    """Mock transport: PingFederate -> Keycloak -> PingFederate -> app redirect."""

    def __init__(self, password: str = "secret", after_password: str | None = None):
        self.password = password
        self.after_password = after_password  # e.g. "login-otp" to simulate 2FA
        self.login_form: dict[str, list[str]] | None = None
        self.state: str | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        if url.path == "/.well-known/openid-configuration":
            return httpx.Response(
                200,
                json={
                    "authorization_endpoint": f"{PING}/as/authorization.oauth2",
                    "token_endpoint": f"{PING}/as/token.oauth2",
                },
            )
        if url.host == "polestarid.eu.polestar.com" and url.path == "/as/authorization.oauth2":
            self.state = url.params["state"]
            return httpx.Response(
                302, headers={"location": f"{KC}/realms/polestar/protocol/openid-connect/auth?x=1"}
            )
        if url.host == "auth.polestar.com" and url.path.endswith("/openid-connect/auth"):
            return httpx.Response(200, text=_kc_page("login"))
        if request.method == "POST" and url.path.endswith("/login-actions/authenticate"):
            assert url.params["session_code"] == "abc"
            self.login_form = parse_qs(request.content.decode())
            if self.login_form["password"] != [self.password]:
                return httpx.Response(
                    200, text=_kc_page("login", "Invalid username or password.")
                )
            if self.after_password:
                return httpx.Response(200, text=_kc_page(self.after_password))
            return httpx.Response(
                302, headers={"location": f"{PING}/sp/abc/cb.openid?code=kc-code&state=kc"}
            )
        if url.path == "/sp/abc/cb.openid":
            # relative redirect, as PingFederate sends it
            return httpx.Response(302, headers={"location": "/as/resume/as/xyz/resume/as/authorization.ping"})
        if url.path.endswith("/resume/as/authorization.ping"):
            return httpx.Response(
                302,
                headers={
                    "location": f"{auth_mod.REDIRECT_URI}?code=app-code&state={self.state}"
                },
            )
        if url.path == "/as/token.oauth2":
            form = parse_qs(request.content.decode())
            assert form["code"] == ["app-code"]
            assert form["grant_type"] == ["authorization_code"]
            return httpx.Response(
                200,
                json={"access_token": "at", "refresh_token": "rt", "expires_in": 3600},
            )
        return httpx.Response(404, text=f"unexpected {request.method} {url}")


@pytest.fixture
def fake_id(monkeypatch):
    def install(server: FakePolestarId) -> FakePolestarId:
        real_client = httpx.AsyncClient

        def client(*args, **kwargs):
            kwargs.pop("verify", None)
            return real_client(*args, transport=httpx.MockTransport(server), **kwargs)

        monkeypatch.setattr(auth_mod.httpx, "AsyncClient", client)
        return server

    return install


async def test_keycloak_login_gets_tokens(fake_id):
    server = fake_id(FakePolestarId())
    store = MemoryTokenStore()
    manager = AuthManager(token_store=store)

    await manager.authenticate("user@example.com", "secret")

    assert manager.access_token == "at"
    assert (await store.load()).refresh_token == "rt"
    assert server.login_form["username"] == ["user@example.com"]


async def test_keycloak_wrong_password(fake_id):
    fake_id(FakePolestarId())
    manager = AuthManager()

    with pytest.raises(AuthError, match="Invalid username or password"):
        await manager.authenticate("user@example.com", "wrong")


async def test_keycloak_one_time_code_is_reported(fake_id):
    fake_id(FakePolestarId(after_password="login-otp"))
    manager = AuthManager()

    with pytest.raises(MfaRequiredError, match="login-otp"):
        await manager.authenticate("user@example.com", "secret")


def test_mfa_error_is_an_auth_error():
    # Callers that only catch AuthError (e.g. the HA config flow) keep working
    assert issubclass(MfaRequiredError, AuthError)


def test_unescape_js_url():
    assert auth_mod._unescape_js_url("https:\\/\\/a.b\\/c?x=1&amp;y=2") == "https://a.b/c?x=1&y=2"
