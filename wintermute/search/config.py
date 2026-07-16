from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..configuration import (
    boolean,
    load_layered_config,
    number,
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
    embedding_address: str
    embedding_token: str | None
    embedding_timeout_seconds: int
    embedding_tls_ca_certificate: Path | None
    embedding_server_name: str | None
    log_level: str
    listen_address: str
    service_token: str | None
    tls_certificate: Path | None
    tls_private_key: Path | None
    max_workers: int
    max_message_bytes: int
    database_pool_size: int
    reflection_enabled: bool
    match_threshold: float
    vector_candidates: int
    text_candidates: int
    hnsw_ef_search: int
    hnsw_iterative_scan: str

    @classmethod
    def from_files(
        cls,
        global_path: Path,
        service_path: Path,
    ) -> "SearchSettings":
        config = load_layered_config(global_path, service_path)
        database = section(config, "database")
        logging = section(config, "logging")
        server = section(config, "server")
        retrieval = section(config, "retrieval")
        embedding_service = section(config, "embedding_service")

        listen_address = required_string(server, "address")
        service_token = optional_string(server, "token")
        validate_listener(listen_address, service_token)
        certificate, private_key = tls_paths(server)
        match_threshold = number(retrieval, "match_threshold")
        if not -1 <= match_threshold <= 1:
            raise ValueError("retrieval.match_threshold must be between -1 and 1")
        iterative_scan = required_string(retrieval, "hnsw_iterative_scan")
        if iterative_scan not in {"off", "strict_order", "relaxed_order"}:
            raise ValueError(
                "retrieval.hnsw_iterative_scan must be off, strict_order, or relaxed_order"
            )

        embedding_ca = optional_string(embedding_service, "tls_ca_certificate")
        return cls(
            database_url=required_string(database, "url"),
            embedding_address=required_string(embedding_service, "address"),
            embedding_token=optional_string(embedding_service, "token"),
            embedding_timeout_seconds=positive_int(embedding_service, "timeout_seconds"),
            embedding_tls_ca_certificate=Path(embedding_ca) if embedding_ca else None,
            embedding_server_name=optional_string(embedding_service, "server_name"),
            log_level=required_string(logging, "level").upper(),
            listen_address=listen_address,
            service_token=service_token,
            tls_certificate=certificate,
            tls_private_key=private_key,
            max_workers=positive_int(server, "max_workers"),
            max_message_bytes=positive_int(server, "max_message_bytes"),
            database_pool_size=positive_int(database, "pool_size"),
            reflection_enabled=boolean(server, "reflection"),
            match_threshold=match_threshold,
            vector_candidates=positive_int(retrieval, "vector_candidates"),
            text_candidates=positive_int(retrieval, "text_candidates"),
            hnsw_ef_search=positive_int(retrieval, "hnsw_ef_search"),
            hnsw_iterative_scan=iterative_scan,
        )
