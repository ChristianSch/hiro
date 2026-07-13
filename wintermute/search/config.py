from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ..configuration import int_env, required_env, tls_paths, validate_listener


@dataclass(frozen=True)
class SearchSettings:
    database_url: str
    model_name: str
    model_device: str
    listen_address: str
    service_token: str | None
    tls_certificate: Path | None
    tls_private_key: Path | None
    max_workers: int
    max_message_bytes: int
    database_pool_size: int
    reflection_enabled: bool

    @classmethod
    def from_env(cls) -> "SearchSettings":
        listen_address = os.getenv("HIRO_SEARCH_LISTEN_ADDRESS", "127.0.0.1:50053")
        service_token = os.getenv("HIRO_SEARCH_TOKEN") or None
        validate_listener(listen_address, service_token)
        certificate, private_key = tls_paths(
            "HIRO_SEARCH_TLS_CERTIFICATE",
            "HIRO_SEARCH_TLS_PRIVATE_KEY",
        )
        return cls(
            database_url=required_env("HIRO_DATABASE_URL"),
            model_name=os.getenv("HIRO_SEARCH_MODEL_NAME", "BAAI/bge-base-en"),
            model_device=os.getenv("HIRO_SEARCH_MODEL_DEVICE", "cpu"),
            listen_address=listen_address,
            service_token=service_token,
            tls_certificate=certificate,
            tls_private_key=private_key,
            max_workers=int_env("HIRO_SEARCH_MAX_WORKERS", 4),
            max_message_bytes=int_env("HIRO_SEARCH_MAX_MESSAGE_BYTES", 1_048_576),
            database_pool_size=int_env("HIRO_SEARCH_DATABASE_POOL_SIZE", 8),
            reflection_enabled=os.getenv("HIRO_SEARCH_REFLECTION", "false").lower() == "true",
        )
