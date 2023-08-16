import grpc
from concurrent import futures
from grpc_reflection.v1alpha import reflection
import logging

import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

from .stubs.embedding_pb2_grpc import EmbeddingServiceServicer, add_EmbeddingServiceServicer_to_server
from .stubs.embedding_pb2 import EmbeddingRequest, EmbeddingResponse, DESCRIPTOR


class EmbeddingServer(EmbeddingServiceServicer):
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

    def _embed(self, url, title, content, description):
        embedding = self._model.encode(content)

        with self._conn.cursor() as cur:
            cur.execute(
                'INSERT INTO documents (url, title, content, description, embedding) VALUES (%(url)s, %(title)s, %(content)s, %(description)s, %(embedding)s) ' +
                'ON CONFLICT (url) DO UPDATE SET (title, content, description, embedding) = (EXCLUDED.title, EXCLUDED.content, EXCLUDED.description, EXCLUDED.embedding)',
                {'url': url, 'title': title, 'content': content,
                    'description': description, 'embedding': embedding, }
            )
            self._conn.commit()

    def Embed(self, request: EmbeddingRequest, context):
        self._embed(request.url, request.title,
                    request.content, request.description)

        context.set_code(grpc.StatusCode.OK)

        return EmbeddingResponse(success=True)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_EmbeddingServiceServicer_to_server(EmbeddingServer(), server)

    SERVICE_NAMES = (
        DESCRIPTOR.services_by_name['EmbeddingService'].full_name,
        reflection.SERVICE_NAME,
    )

    reflection.enable_server_reflection(SERVICE_NAMES, server)

    logging.info('Starting server. Listening on port 50052.')
    server.add_insecure_port('[::]:50052')
    server.start()
    server.wait_for_termination()
