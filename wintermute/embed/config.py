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
class EmbeddingSettings:
    database_url: str
    model_name: str
    model_device: str
    model_allow_download: bool
    log_level: str
    listen_address: str
    service_token: str | None
    tls_certificate: Path | None
    tls_private_key: Path | None
    max_workers: int
    max_message_bytes: int
    database_pool_size: int
    reflection_enabled: bool
    chunk_max_tokens: int
    chunk_overlap_tokens: int
    embedding_batch_size: int

    @classmethod
    def from_files(
        cls,
        global_path: Path,
        service_path: Path,
    ) -> "EmbeddingSettings":
        config = load_layered_config(global_path, service_path)
        database = section(config, "database")
        model = section(config, "model")
        logging = section(config, "logging")
        server = section(config, "server")
        chunking = section(config, "chunking")

        listen_address = required_string(server, "address")
        service_token = optional_string(server, "token")
        validate_listener(listen_address, service_token)
        certificate, private_key = tls_paths(server)
        chunk_max_tokens = positive_int(chunking, "max_tokens")
        chunk_overlap_tokens = positive_int(chunking, "overlap_tokens")
        if chunk_overlap_tokens >= chunk_max_tokens:
            raise ValueError("chunking.overlap_tokens must be smaller than max_tokens")

        return cls(
            database_url=required_string(database, "url"),
            model_name=required_string(model, "name"),
            model_device=required_string(model, "device"),
            model_allow_download=boolean(model, "allow_download"),
            log_level=required_string(logging, "level").upper(),
            listen_address=listen_address,
            service_token=service_token,
            tls_certificate=certificate,
            tls_private_key=private_key,
            max_workers=positive_int(server, "max_workers"),
            max_message_bytes=positive_int(server, "max_message_bytes"),
            database_pool_size=positive_int(database, "pool_size"),
            reflection_enabled=boolean(server, "reflection"),
            chunk_max_tokens=chunk_max_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens,
            embedding_batch_size=positive_int(chunking, "batch_size"),
        )
