import logging
import grpc
from concurrent import futures
from grpc_reflection.v1alpha import reflection

import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

from .stubs.search_pb2_grpc import SearchServiceServicer, add_SearchServiceServicer_to_server
from .stubs.search_pb2 import SearchRequest, SearchResponse, DESCRIPTOR


class SearchServer(SearchServiceServicer):
    _model = None
    _conn = None

    def __init__(self) -> None:
        super().__init__()

        self._model = SentenceTransformer('BAAI/bge-base-en', device='mps')
        self._init_db()

    def _init_db(self):
        conn = psycopg.connect(
            "dbname=hiro user=hiro password=hiro host=localhost port=5432")
        register_vector(conn)
        self._conn = conn
        logging.info('Database connection established.')

    def __del__(self):
        if self._conn.closed == 0:
            self._conn.close()
            logging.info('Database connection closed.')

    def Search(self, request: SearchRequest, context):
        try:
            search = self._model.encode(request.query)
            logging.debug('Search vector: %d', len(search))

            with self._conn.cursor() as cur:
                res = cur.execute(
                    'SELECT match_documents(%s, 0.78, 10)', (search,)).fetchall()

            context.set_code(grpc.StatusCode.OK)

            logging.info('Search request: %s', request.query)
            logging.debug('Search results: %d', len(res))
            logging.debug(res)

            # the db responds with the following in the respective order:
            # 1. document id
            # 2. document url
            # 3. document title
            # 4. document content
            # 5. document description
            # 6. similarity score
            return SearchResponse(results=[SearchResponse.Result(
                url=r[0][1],
                title=r[0][2],
                content=r[0][3],
                description=r[0][4],
            ) for r in res])

        except Exception as e:
            logging.error('Search request failed: %s', request.query)
            logging.error(e, exc_info=1)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return SearchResponse()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_SearchServiceServicer_to_server(SearchServer(), server)

    SERVICE_NAMES = (
        DESCRIPTOR.services_by_name['SearchService'].full_name,
        reflection.SERVICE_NAME,
    )

    reflection.enable_server_reflection(SERVICE_NAMES, server)

    logging.info('Starting server. Listening on port 50053.')
    server.add_insecure_port('[::]:50053')
    server.start()
    server.wait_for_termination()
