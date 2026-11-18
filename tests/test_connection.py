"""Tests for gRPC connection setup."""

from __future__ import annotations


def test_grpclib_user_agent_is_patched_everywhere():
    """grpclib.client imports USER_AGENT by value, so patching grpclib.metadata
    alone does not change what's actually sent on the wire -- connection.py
    must also patch grpclib.client's own binding, or the C3 backend will see
    the real grpclib default user agent and reject calls with UNIMPLEMENTED.
    """
    import grpclib.client
    import grpclib.metadata

    import polestar_api.connection  # noqa: F401  (import triggers the patch)

    assert grpclib.metadata.USER_AGENT == "grpc-java-okhttp/1.68.2"
    assert grpclib.client.USER_AGENT == "grpc-java-okhttp/1.68.2"
