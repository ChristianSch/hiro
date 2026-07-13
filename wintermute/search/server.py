import argparse
from pathlib import Path

import logging
import grpc
from concurrent import futures
from grpc_reflection.v1alpha import reflection

from contextlib import contextmanager

from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

from .stubs.search_pb2_grpc import SearchServiceServicer, add_SearchServiceServicer_to_server
from .stubs.search_pb2 import (
    DependencyStatus,
    DESCRIPTOR,
    OPERATIONAL_STATE_OPERATIONAL,
    OPERATIONAL_STATE_UNAVAILABLE,
    SearchRequest,
    SearchResponse,
    StatusRequest,
    StatusResponse,
)
from .config import SearchSettings
from ..grpc_utils import add_server_port, require_authorization


def _configure_connection(connection) -> None:
    register_vector(connection)


class SearchServer(SearchServiceServicer):
    _model = None
    _pool = None

    def __init__(self, settings: SearchSettings) -> None:
        super().__init__()
        self._settings = settings
        self._model = SentenceTransformer(
            settings.model_name,
            device=settings.model_device,
        )
        self._init_db()

    def _init_db(self):
        self._pool = ConnectionPool(
            conninfo=self._settings.database_url,
            min_size=1,
            max_size=self._settings.database_pool_size,
            kwargs={"autocommit": True},
            configure=_configure_connection,
            open=True,
        )
        self._pool.wait(timeout=10)
        logging.info('Database connection pool established.')

    @contextmanager
    def _connection(self):
        if self._pool is not None:
            with self._pool.connection() as connection:
                yield connection
            return
        # Compatibility path for lightweight unit-test fakes.
        yield self._conn

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            logging.info('Database connection pool closed.')

    def Status(self, request: StatusRequest, context):
        require_authorization(
            context,
            getattr(getattr(self, "_settings", None), "service_token", None),
        )
        database_state = OPERATIONAL_STATE_UNAVAILABLE

        try:
            with self._connection() as connection:
                with connection.cursor() as cur:
                    result = cur.execute('SELECT 1').fetchone()
            if result == (1,):
                database_state = OPERATIONAL_STATE_OPERATIONAL
        except Exception:
            logging.warning('PostgreSQL readiness check failed', exc_info=1)

        model_is_ready = self._model is not None
        is_operational = (
            model_is_ready
            and database_state == OPERATIONAL_STATE_OPERATIONAL
        )

        context.set_code(grpc.StatusCode.OK)
        return StatusResponse(
            state=(
                OPERATIONAL_STATE_OPERATIONAL
                if is_operational
                else OPERATIONAL_STATE_UNAVAILABLE
            ),
            dependencies=[DependencyStatus(
                name='postgresql',
                state=database_state,
            )],
        )

    def Search(self, request: SearchRequest, context):
        require_authorization(context, self._settings.service_token)
        if len(request.query) > 512:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "query is too long")

        page_number = request.page_number or 1
        result_per_page = request.result_per_page or 10
        if page_number < 1 or page_number > 100:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "page_number must be between 1 and 100")
        if result_per_page < 1 or result_per_page > 50:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "result_per_page must be between 1 and 50")
        offset = (page_number - 1) * result_per_page

        try:
            if not request.query.strip():
                with self._connection() as connection:
                    with connection.cursor() as cur:
                        res = cur.execute(
                        '''SELECT id, url, title, content, description
                           FROM documents
                           WHERE url IS NOT NULL AND url <> ''
                           ORDER BY id DESC
                           LIMIT %s OFFSET %s''',
                            (result_per_page, offset),
                        ).fetchall()
                logging.info('Recent websites request')
            else:
                search = self._model.encode(request.query)
                logging.debug('Search vector: %d', len(search))

                with self._connection() as connection:
                    with connection.cursor() as cur:
                        res = cur.execute(
                            'SELECT * FROM match_documents(%s, %s, 0.78, %s) OFFSET %s',
                            (search, request.query, result_per_page + offset, offset),
                        ).fetchall()

            context.set_code(grpc.StatusCode.OK)

            logging.info('Search request completed')
            logging.debug('Search results: %d', len(res))

            # the db responds with the following in the respective order:
            # 1. document id
            # 2. document url
            # 3. document title
            # 4. document content
            # 5. document description
            # 6. hybrid similarity score
            return SearchResponse(results=[SearchResponse.Result(
                url=r[1],
                title=r[2],
                content='',
                description=r[4],
            ) for r in res])

        except Exception:
            logging.exception('Search request failed')
            context.abort(grpc.StatusCode.INTERNAL, 'search request failed')


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Hiro search service")
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    args = parser.parse_args()
    settings = SearchSettings.from_files(
        args.config_dir / "global.yml",
        args.config_dir / "search.yml",
    )
    logging.basicConfig(level=settings.log_level)
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=settings.max_workers),
        options=(
            ("grpc.max_receive_message_length", settings.max_message_bytes),
            ("grpc.max_send_message_length", settings.max_message_bytes),
        ),
    )
    service = SearchServer(settings)
    add_SearchServiceServicer_to_server(service, server)

    if settings.reflection_enabled:
        service_names = (
            DESCRIPTOR.services_by_name["SearchService"].full_name,
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
            f"failed to bind search service to {settings.listen_address}"
        )

    logging.info("Starting search server on %s", settings.listen_address)
    server.start()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logging.info("Stopping search server")
        server.stop(grace=10).wait()
    finally:
        service.close()


if __name__ == "__main__":
    main()
