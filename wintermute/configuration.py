from __future__ import annotations

import ipaddress
import os
from pathlib import Path


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value


def int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    value = default if raw is None else int(raw)
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def tls_paths(certificate_name: str, key_name: str) -> tuple[Path | None, Path | None]:
    certificate = os.getenv(certificate_name)
    private_key = os.getenv(key_name)
    if bool(certificate) != bool(private_key):
        raise ValueError(f"{certificate_name} and {key_name} must be configured together")
    return (
        Path(certificate) if certificate else None,
        Path(private_key) if private_key else None,
    )


def validate_listener(address: str, token: str | None) -> None:
    host = address.rsplit(":", 1)[0].strip("[]")
    if host.lower() == "localhost":
        return
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if not loopback and not token:
        raise ValueError("a service token is required when listening outside loopback")
