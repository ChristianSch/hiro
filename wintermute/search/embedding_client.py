from __future__ import annotations

import grpc

from ..embed.stubs.embedding_pb2 import (
    EmbeddingStatusRequest,
    QueryEmbeddingRequest,
)
from ..embed.stubs.embedding_pb2_grpc import EmbeddingServiceStub
from .config import SearchSettings


class EmbeddingClient:
    def __init__(self, settings: SearchSettings) -> None:
        if settings.embedding_tls_ca_certificate is None:
            self._channel = grpc.insecure_channel(settings.embedding_address)
        else:
            credentials = grpc.ssl_channel_credentials(
                root_certificates=settings.embedding_tls_ca_certificate.read_bytes()
            )
            options = ()
            if settings.embedding_server_name:
                options = (
                    (
                        "grpc.ssl_target_name_override",
                        settings.embedding_server_name,
                    ),
                )
            self._channel = grpc.secure_channel(
                settings.embedding_address,
                credentials,
                options=options,
            )
        self._stub = EmbeddingServiceStub(self._channel)
        self._timeout = settings.embedding_timeout_seconds
        self._metadata = (
            (("authorization", f"Bearer {settings.embedding_token}"),)
            if settings.embedding_token
            else None
        )

    def close(self) -> None:
        self._channel.close()

    def embed_query(self, query: str) -> list[float]:
        response = self._stub.EmbedQuery(
            QueryEmbeddingRequest(query=query),
            timeout=self._timeout,
            metadata=self._metadata,
        )
        if len(response.embedding) != 768:
            raise RuntimeError(
                f"embedding service returned {len(response.embedding)} values; expected 768"
            )
        return list(response.embedding)

    def ready(self) -> bool:
        response = self._stub.Status(
            EmbeddingStatusRequest(),
            timeout=self._timeout,
            metadata=self._metadata,
        )
        return response.ready
