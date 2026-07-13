import grpc
from concurrent import futures
from grpc_reflection.v1alpha import reflection
import logging
import os
from urllib.parse import urlsplit

from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

from .stubs.embedding_pb2_grpc import EmbeddingServiceServicer, add_EmbeddingServiceServicer_to_server
from .stubs.embedding_pb2 import EmbeddingRequest, EmbeddingResponse, DESCRIPTOR
from ..config import ServiceSettings
from ..grpc_utils import add_server_port, require_authorization


def _configure_connection(connection) -> None:
    register_vector(connection)
    connection.commit()


class EmbeddingServer(EmbeddingServiceServicer):
    _model = None
    _pool = None

    def __init__(self, settings: ServiceSettings) -> None:
        super().__init__()
        self._settings = settings
        self._model = SentenceTransformer(
            settings.model_name,
            device=settings.model_device,
        )
        self._init_db()

    def _init_db(self):
        self._pool = ConnectionPool(
            conninfo=self._settings.database_dsn,
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

    def _embed(self, url, title, content, description):
        embedding = self._model.encode(content)

        with self._pool.connection() as connection:
            with connection.cursor() as cur:
                cur.execute(
                'INSERT INTO documents (url, title, content, description, embedding) VALUES (%(url)s, %(title)s, %(content)s, %(description)s, %(embedding)s) ' +
                'ON CONFLICT (url) DO UPDATE SET (title, content, description, embedding) = (EXCLUDED.title, EXCLUDED.content, EXCLUDED.description, EXCLUDED.embedding)',
                    {'url': url, 'title': title, 'content': content,
                        'description': description, 'embedding': embedding, }
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
        parsed_url = urlsplit(request.url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "url must be HTTP or HTTPS")
        if len(request.title) > 1_000 or len(request.description) > 4_000:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "document metadata is too long")
        if len(request.content.encode("utf-8")) > 900_000:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "document content is too large")

        try:
            self._embed(
                request.url,
                request.title,
                request.content,
                request.description,
            )
        except Exception:
            logging.exception("Embedding request failed")
            context.abort(grpc.StatusCode.INTERNAL, "embedding request failed")

        return EmbeddingResponse(success=True)


def main() -> None:
    settings = ServiceSettings.from_env(default_port=50052)
    logging.basicConfig(level=os.getenv("HIRO_LOG_LEVEL", "INFO").upper())
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=settings.max_workers),
        options=(
            ("grpc.max_receive_message_length", settings.max_message_bytes),
            ("grpc.max_send_message_length", settings.max_message_bytes),
        ),
    )
    service = EmbeddingServer(settings)
    add_EmbeddingServiceServicer_to_server(service, server)

    if os.getenv("HIRO_ENABLE_REFLECTION", "false").lower() == "true":
        service_names = (
            DESCRIPTOR.services_by_name["EmbeddingService"].full_name,
            reflection.SERVICE_NAME,
        )
        reflection.enable_server_reflection(service_names, server)

    if add_server_port(
        server,
        settings.address,
        settings.tls_certificate,
        settings.tls_private_key,
    ) == 0:
        raise RuntimeError(f"failed to bind embedding service to {settings.address}")

    logging.info("Starting embedding server on %s", settings.address)
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
