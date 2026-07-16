import argparse
import hashlib
import threading
from pathlib import Path
from urllib.parse import urlsplit

import grpc
from concurrent import futures
from grpc_reflection.v1alpha import reflection
import logging

from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector
from .stubs.embedding_pb2_grpc import EmbeddingServiceServicer, add_EmbeddingServiceServicer_to_server
from .stubs.embedding_pb2 import (
    DESCRIPTOR,
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingStatusRequest,
    EmbeddingStatusResponse,
    QueryEmbeddingRequest,
    QueryEmbeddingResponse,
)
from .chunking import chunk_content
from .config import EmbeddingSettings
from ..grpc_utils import add_server_port, require_authorization
from ..model import load_embedding_model
from ..url_utils import canonicalize_url


def _configure_connection(connection) -> None:
    register_vector(connection)
    connection.commit()


class EmbeddingServer(EmbeddingServiceServicer):
    _model = None
    _pool = None

    def __init__(self, settings: EmbeddingSettings) -> None:
        super().__init__()
        self._settings = settings
        self._model = load_embedding_model(
            settings.model_name,
            settings.model_device,
            settings.model_dimensions,
            settings.model_allow_download,
        )
        self._inference_lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        self._pool = ConnectionPool(
            conninfo=self._settings.database_url,
            min_size=1,
            max_size=self._settings.database_pool_size,
            configure=_configure_connection,
            open=True,
        )
        self._pool.wait(timeout=10)
        logging.info('Database connection pool established.')

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            logging.info('Database connection pool closed.')

    def _document_is_current(
        self,
        url: str,
        content_hash: str,
        title: str,
        description: str,
        source_host: str,
    ) -> bool:
        with self._pool.connection() as connection:
            with connection.cursor() as cur:
                row = cur.execute(
                    '''SELECT documents.id
                       FROM documents
                       WHERE documents.url = %s
                         AND documents.content_hash = %s
                         AND EXISTS (
                           SELECT 1 FROM document_chunks
                           WHERE document_chunks.document_id = documents.id
                         )
                         AND NOT EXISTS (
                           SELECT 1 FROM document_chunks
                           WHERE document_chunks.document_id = documents.id
                             AND document_chunks.embedding_model <> %s
                         )''',
                    (url, content_hash, self._settings.model_name),
                ).fetchone()
                if row is None:
                    return False
                cur.execute(
                    '''UPDATE documents
                       SET title = %s,
                           description = %s,
                           content = null,
                           source_host = %s,
                           crawled_at = now(),
                           updated_at = now()
                       WHERE id = %s''',
                    (title, description, source_host, row[0]),
                )
                return True

    def _embed(self, url, title, content, description, source_host):
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if self._document_is_current(
            url,
            content_hash,
            title,
            description,
            source_host,
        ):
            logging.info("Document unchanged; skipped embedding")
            return

        chunks = chunk_content(
            self._model.tokenizer,
            content,
            self._settings.chunk_max_tokens,
            self._settings.chunk_overlap_tokens,
        )
        with self._inference_lock:
            embeddings = self._model.encode(
                chunks,
                batch_size=self._settings.embedding_batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

        with self._pool.connection() as connection:
            with connection.cursor() as cur:
                document_id = cur.execute(
                    '''INSERT INTO documents (
                         url, title, content, description,
                         source_host, content_hash, crawled_at, updated_at
                       ) VALUES (%s, %s, null, %s, %s, %s, now(), now())
                       ON CONFLICT (url) DO UPDATE SET
                         title = EXCLUDED.title,
                         content = null,
                         description = EXCLUDED.description,
                         source_host = EXCLUDED.source_host,
                         content_hash = EXCLUDED.content_hash,
                         crawled_at = now(),
                         updated_at = now()
                       RETURNING id''',
                    (
                        url,
                        title,
                        description,
                        source_host,
                        content_hash,
                    ),
                ).fetchone()[0]
                cur.execute(
                    "DELETE FROM document_chunks WHERE document_id = %s",
                    (document_id,),
                )
                cur.executemany(
                    '''INSERT INTO document_chunks (
                         document_id, chunk_index, content, embedding, embedding_model
                       ) VALUES (%s, %s, %s, %s, %s)''',
                    [
                        (
                            document_id,
                            index,
                            chunk,
                            embeddings[index],
                            self._settings.model_name,
                        )
                        for index, chunk in enumerate(chunks)
                    ],
                )
        logging.info("Embedded document into %d chunks", len(chunks))

    def EmbedQuery(self, request: QueryEmbeddingRequest, context):
        require_authorization(context, self._settings.service_token)
        query = request.query.strip()
        if not query:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "query is required")
        if len(query) > 512:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "query is too long")
        try:
            with self._inference_lock:
                embedding = self._model.encode(
                    query,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                if len(embedding) != self._settings.model_dimensions:
                    raise RuntimeError(
                        f"embedding model returned {len(embedding)} values; "
                        f"expected {self._settings.model_dimensions}"
                    )
        except Exception:
            logging.exception("Query embedding failed")
            context.abort(grpc.StatusCode.INTERNAL, "query embedding failed")
        return QueryEmbeddingResponse(
            embedding=[float(value) for value in embedding],
        )

    def Status(self, request: EmbeddingStatusRequest, context):
        require_authorization(context, self._settings.service_token)
        return EmbeddingStatusResponse(
            ready=self._model is not None,
            model=self._settings.model_name,
            dimensions=self._settings.model_dimensions,
        )

    def Embed(self, request: EmbeddingRequest, context):
        require_authorization(context, self._settings.service_token)
        if not request.url.strip() or not request.content.strip():
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "url and content are required",
            )
        if len(request.url) > 2_048:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "url is too long")
        try:
            canonical_url = canonicalize_url(request.url)
        except ValueError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "url must be HTTP or HTTPS")
        parsed_url = urlsplit(canonical_url)
        if len(request.title) > 1_000 or len(request.description) > 4_000:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "document metadata is too long")
        if len(request.content.encode("utf-8")) > 900_000:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "document content is too large")

        try:
            self._embed(
                canonical_url,
                request.title,
                request.content,
                request.description,
                parsed_url.hostname.lower(),
            )
        except Exception:
            logging.exception("Embedding request failed")
            context.abort(grpc.StatusCode.INTERNAL, "embedding request failed")

        return EmbeddingResponse(success=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Hiro embedding service")
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    args = parser.parse_args()
    settings = EmbeddingSettings.from_files(
        args.config_dir / "global.yml",
        args.config_dir / "embed.yml",
    )
    logging.basicConfig(level=settings.log_level)
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=settings.max_workers),
        options=(
            ("grpc.max_receive_message_length", settings.max_message_bytes),
            ("grpc.max_send_message_length", settings.max_message_bytes),
        ),
    )
    service = EmbeddingServer(settings)
    add_EmbeddingServiceServicer_to_server(service, server)

    if settings.reflection_enabled:
        service_names = (
            DESCRIPTOR.services_by_name["EmbeddingService"].full_name,
            reflection.SERVICE_NAME,
        )
        reflection.enable_server_reflection(service_names, server)

    if add_server_port(
        server,
        settings.listen_address,
        settings.tls_certificate,
        settings.tls_private_key,
    ) == 0:
        raise RuntimeError(
            f"failed to bind embedding service to {settings.listen_address}"
        )

    logging.info("Starting embedding server on %s", settings.listen_address)
    server.start()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logging.info("Stopping embedding server")
        server.stop(grace=10).wait()
    finally:
        service.close()


if __name__ == "__main__":
    main()
