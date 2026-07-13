from __future__ import annotations

import hmac
from pathlib import Path

import grpc


def require_authorization(context: grpc.ServicerContext, expected_token: str | None) -> None:
    if expected_token is None:
        return

    supplied = ""
    for item in context.invocation_metadata():
        if item.key.lower() == "authorization":
            supplied = item.value
            break

    expected = f"Bearer {expected_token}"
    if not hmac.compare_digest(supplied, expected):
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "authentication required")


def add_server_port(
    server: grpc.Server,
    address: str,
    certificate: Path | None,
    private_key: Path | None,
) -> int:
    if certificate is None or private_key is None:
        return server.add_insecure_port(address)

    credentials = grpc.ssl_server_credentials(
        ((private_key.read_bytes(), certificate.read_bytes()),)
    )
    return server.add_secure_port(address, credentials)
