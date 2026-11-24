# CLAUDE.md

Project-specific guidance for the `unofficial-polestar-api` repo. The general
behavioral guidelines live in `~/.claude/CLAUDE.md` — do not duplicate them
here.

## What this repo is

Async Python client for Polestar's gRPC cloud APIs (C3 / Volvo Cars Cloud
Connectivity backend) plus a Home Assistant custom integration that consumes it.
Reverse-engineered from the official mobile app — APIs are undocumented and may
break.

## Layout

- `src/polestar_api/` — library (packaged as `polestar_api` on PyPI)
  - `client.py` — `PolestarApi` entry point (async context manager)
  - `auth.py` — OIDC/PKCE + token refresh, pluggable `TokenStore`
  - `connection.py` — `GrpcConnection` (grpclib `Channel` + bearer injection)
  - `discovery.py` — C3 endpoint + app-backend GraphQL vehicle list
  - `grpc.py` — `unary_unary` / `unary_stream` raw-bytes helpers with retry
  - `wire.py` + `codec.py` — hand-rolled protobuf (no `.proto`, no protoc)
  - `backend.py` — `BackendProfile` (C3 default, PCCS variant)
  - `vehicle.py` — `Vehicle` facade with ~50 high-level methods
  - `models/` — frozen dataclasses using `ProtoMessage` mixin + `IntEnum`s
  - `services/` — one client per gRPC service
- `custom_components/polestar/` — HACS-distributed HA integration
  - `__init__.py`, `config_flow.py`, `coordinator.py` (DataUpdateCoordinator)
  - `services.py` + `services.yaml` — HA service registrations
  - `token_store.py` — HA-backed `TokenStore` implementation
  - `demo.py` — fake vehicle for demo mode
  - Platforms: `sensor`, `binary_sensor`, `lock`, `switch`, `button`, `number`,
    `select`, `time`, `calendar`, `update`, `device_tracker`
- `tests/` — pytest + pytest-asyncio (`asyncio_mode = "auto"`)
- `docs/` — mkdocs + mkdocstrings reference

## Conventions

- **Python ≥ 3.12**, `from __future__ import annotations` everywhere.
- **frozen dataclasses** for all protobuf message types. Mutating state goes
  through `dataclasses.replace(...)` (see `coordinator.py`).
- **No protoc**. Protobuf schemas live in the `schema={field_num: name, ...}`
  class arg of `ProtoMessage` subclasses. Wire types are inferred from type
  hints in `wire._infer_wire_type`. If you add a new field type, update that
  function.
- **`IntEnum` for enums**, value `0` is `UNSPECIFIED` (matches proto3 default).
- **Service path strings** live in `backend.py`, never hard-coded in services.
  Services resolve them via `self._connection.backend.<x>_svc`.
- **Service methods** take a `VehicleRequest(vin=...)` envelope by default and
  return parsed dataclasses. Errors propagate as `ApiError` / `GRPCError`.
- **Streaming endpoints** retry only when no data has been yielded yet
  (subscription semantics). See `grpc.unary_stream`.
- **HA integration must not block the event loop.** `ssl.create_default_context()`
  and `_HTTPX_SSL_CONTEXT` are built at import time for exactly this reason —
  preserve that pattern.
- **gRPC user agent is faked** (`grpc-java-okhttp/1.68.2`) in `connection.py` —
  the C3 server rejects other UAs with `UNIMPLEMENTED`. Do not change.
- **No comments in code** unless the surrounding code has explanatory ones;
  match the local style.

## Testing

- `uv run pytest` (or `pytest` inside a `.venv` with the dev extras).
- Tests use `pytest-asyncio` with `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` decorator needed.
- `tests/conftest.py` provides mock fixtures for OIDC config, token responses,
  and vehicle list responses.
- There is no live API integration test — don't add one without explicit
  approval, it would require real Polestar credentials.

## CI

GitHub Actions workflows in `.github/workflows/`:
- `validate.yml` — HACS action validates the custom component.
- `hassfest.yml` — HA manifest validation.
- `docs.yml` — builds mkdocs site.
- `release-ha-ha.yml` — HA release automation.

## Common pitfalls

- **Do not add `protoc` or generated stubs.** The whole point of
  `wire.py` / `codec.py` is avoiding a codegen step.
- **Do not change gRPC user agent** in `connection.py` — C3 rejects it.
- **Do not introduce sync I/O** in the HA integration paths
  (`__init__.py`, `coordinator.py`, `entity.py`).
- **Do not break the public `polestar_api` API** without a deprecation note
  in the changelog; the HA integration imports it directly.
- **TLS / `keepalive` settings** in `connection.py` match the Android app's
  OkHttp channel — changing them has caused `UNAVAILABLE` errors before.
- **APIs are undocumented and may break without notice.** When adding a new
  endpoint, mark per-model availability (P2 vs P4) in docstrings, mirroring
  the existing entries in `vehicle.py`.

## Reference

- Full library docs: https://kildahldev.github.io/unofficial-polestar-api/
- HA install / entities: `ha_integration_README.md`
- Dashboard card examples: `example-dashboard-cards.md`
