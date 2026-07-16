import unittest
from contextlib import nullcontext
from types import SimpleNamespace

import grpc

from .server import SearchServer
from .stubs.search_pb2 import (
    OPERATIONAL_STATE_OPERATIONAL,
    OPERATIONAL_STATE_UNAVAILABLE,
    SearchRequest,
    StatusRequest,
)


class FakeCursor:
    def __init__(self, result=(1,), rows=None, error=None):
        self._result = result
        self._rows = rows or []
        self._error = error
        self.query = None
        self.parameters = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, parameters=None):
        if self._error is not None:
            raise self._error
        self.query = query
        self.parameters = parameters
        return self

    def fetchone(self):
        return self._result

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self, result=(1,), rows=None, error=None):
        self._result = result
        self._rows = rows or []
        self._error = error
        self.last_cursor = None

    def cursor(self):
        self.last_cursor = FakeCursor(self._result, self._rows, self._error)
        return self.last_cursor

    def transaction(self):
        return nullcontext()


class FakeContext:
    code = None

    def set_code(self, code):
        self.code = code


class FakeEmbeddingClient:
    def __init__(self, ready=True):
        self.is_ready = ready
        self.queries = []

    def ready(self):
        return self.is_ready

    def embed_query(self, query):
        self.queries.append(query)
        return [0.0] * 768


class SearchServerStatusTest(unittest.TestCase):
    def make_server(self, connection, embedding_ready=True):
        server = SearchServer.__new__(SearchServer)
        server._conn = connection
        server._embedding_client = FakeEmbeddingClient(embedding_ready)
        server._settings = SimpleNamespace(
            service_token=None,
            match_threshold=0.78,
            vector_candidates=200,
            text_candidates=200,
            hnsw_ef_search=200,
            hnsw_iterative_scan="relaxed_order",
        )
        return server

    def test_reports_operational_when_model_and_database_are_ready(self):
        server = self.make_server(FakeConnection())
        context = FakeContext()

        response = server.Status(StatusRequest(), context)

        self.assertEqual(OPERATIONAL_STATE_OPERATIONAL, response.state)
        self.assertEqual(grpc.StatusCode.OK, context.code)
        self.assertEqual(2, len(response.dependencies))
        self.assertEqual('postgresql', response.dependencies[0].name)
        self.assertEqual(
            OPERATIONAL_STATE_OPERATIONAL,
            response.dependencies[0].state,
        )

    def test_reports_unavailable_when_database_check_fails(self):
        server = self.make_server(FakeConnection(error=RuntimeError('offline')))

        response = server.Status(StatusRequest(), FakeContext())

        self.assertEqual(OPERATIONAL_STATE_UNAVAILABLE, response.state)
        self.assertEqual(
            OPERATIONAL_STATE_UNAVAILABLE,
            response.dependencies[0].state,
        )

    def test_empty_query_returns_five_random_pages_by_default(self):
        connection = FakeConnection()
        server = self.make_server(connection)

        response = server.Search(SearchRequest(), FakeContext())

        self.assertIn("random_documents", connection.last_cursor.query)
        self.assertEqual((5,), connection.last_cursor.parameters)
        self.assertEqual(1, response.page_number)
        self.assertFalse(response.has_next)

    def test_search_returns_page_metadata_and_trims_lookahead(self):
        rows = [
            (1, "https://example.com/1", "One", "First", "snippet", 0.9),
            (2, "https://example.com/2", "Two", "Second", "snippet", 0.8),
            (3, "https://example.com/3", "Three", "Third", "snippet", 0.7),
        ]
        connection = FakeConnection(rows=rows)
        server = self.make_server(connection)
        response = server.Search(
            SearchRequest(query="example", page_number=2, result_per_page=2),
            FakeContext(),
        )

        self.assertEqual(2, response.page_number)
        self.assertTrue(response.has_next)
        self.assertEqual(2, len(response.results))
        self.assertIn("match_documents", connection.last_cursor.query)
        self.assertEqual(0.78, connection.last_cursor.parameters[2])
        self.assertEqual(2, connection.last_cursor.parameters[3])
        self.assertEqual(3, connection.last_cursor.parameters[4])
        self.assertEqual(["example"], server._embedding_client.queries)

    def test_reports_unavailable_when_embedding_service_is_not_ready(self):
        server = self.make_server(FakeConnection(), embedding_ready=False)

        response = server.Status(StatusRequest(), FakeContext())

        self.assertEqual(OPERATIONAL_STATE_UNAVAILABLE, response.state)
        self.assertEqual(
            OPERATIONAL_STATE_UNAVAILABLE,
            response.dependencies[1].state,
        )


if __name__ == '__main__':
    unittest.main()
