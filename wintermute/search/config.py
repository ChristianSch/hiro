from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..configuration import (
    boolean,
    load_layered_config,
    optional_string,
    positive_int,
    required_string,
    section,
    tls_paths,
    validate_listener,
)


@dataclass(frozen=True)
class SearchSettings:
    database_url: str
    model_name: str
    model_device: str
    log_level: str
    listen_address: str
    service_token: str | None
    tls_certificate: Path | None
    tls_private_key: Path | None
    max_workers: int
    max_message_bytes: int
    database_pool_size: int
    reflection_enabled: bool

    @classmethod
    def from_files(
        cls,
        global_path: Path,
        service_path: Path,
    ) -> "SearchSettings":
        config = load_layered_config(global_path, service_path)
        database = section(config, "database")
        model = section(config, "model")
        logging = section(config, "logging")
        server = section(config, "server")

        listen_address = required_string(server, "address")
        service_token = optional_string(server, "token")
        validate_listener(listen_address, service_token)
        certificate, private_key = tls_paths(server)

        return cls(
            database_url=required_string(database, "url"),
            model_name=required_string(model, "name"),
            model_device=required_string(model, "device"),
            log_level=required_string(logging, "level").upper(),
            listen_address=listen_address,
            service_token=service_token,
            tls_certificate=certificate,
            tls_private_key=private_key,
            max_workers=positive_int(server, "max_workers"),
            max_message_bytes=positive_int(server, "max_message_bytes"),
            database_pool_size=positive_int(database, "pool_size"),
            reflection_enabled=boolean(server, "reflection"),
        )
