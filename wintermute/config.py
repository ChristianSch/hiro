from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    value = default if raw is None else int(raw)
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class ServiceSettings:
    database_dsn: str
    model_name: str
    model_device: str
    bind_address: str
    port: int
    service_token: str | None
    tls_certificate: Path | None
    tls_private_key: Path | None
    max_workers: int
    max_message_bytes: int
    database_pool_size: int

    @classmethod
    def from_env(cls, *, default_port: int) -> "ServiceSettings":
        database_dsn = os.getenv("HIRO_DATABASE_DSN")
        if not database_dsn:
            raise ValueError("HIRO_DATABASE_DSN is required")

        bind_address = os.getenv("HIRO_BIND_ADDRESS", "127.0.0.1")
        service_token = os.getenv("HIRO_SERVICE_TOKEN") or None
        certificate = os.getenv("HIRO_TLS_CERTIFICATE")
        private_key = os.getenv("HIRO_TLS_PRIVATE_KEY")
        if bool(certificate) != bool(private_key):
            raise ValueError(
                "HIRO_TLS_CERTIFICATE and HIRO_TLS_PRIVATE_KEY must be configured together"
            )
        if not _is_loopback(bind_address) and not service_token:
            raise ValueError(
                "HIRO_SERVICE_TOKEN is required when binding outside the loopback interface"
            )

        return cls(
            database_dsn=database_dsn,
            model_name=os.getenv("HIRO_MODEL_NAME", "BAAI/bge-base-en"),
            model_device=os.getenv("HIRO_MODEL_DEVICE", "cpu"),
            bind_address=bind_address,
            port=_int_env("HIRO_PORT", default_port),
            service_token=service_token,
            tls_certificate=Path(certificate) if certificate else None,
            tls_private_key=Path(private_key) if private_key else None,
            max_workers=_int_env("HIRO_MAX_WORKERS", 4),
            max_message_bytes=_int_env("HIRO_MAX_MESSAGE_BYTES", 1_048_576),
            database_pool_size=_int_env("HIRO_DATABASE_POOL_SIZE", 8),
        )

    @property
    def address(self) -> str:
        return f"{self.bind_address}:{self.port}"

    @property
    def tls_enabled(self) -> bool:
        return self.tls_certificate is not None
