import unittest
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
    def __init__(self, result=(1,), error=None):
        self._result = result
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
        return []


class FakeConnection:
    def __init__(self, result=(1,), error=None):
        self._result = result
        self._error = error
        self.last_cursor = None

    def cursor(self):
        self.last_cursor = FakeCursor(self._result, self._error)
        return self.last_cursor


class FakeContext:
    code = None

    def set_code(self, code):
        self.code = code


class SearchServerStatusTest(unittest.TestCase):
    def make_server(self, connection, model=object()):
        server = SearchServer.__new__(SearchServer)
        server._conn = connection
        server._model = model
        server._settings = SimpleNamespace(service_token=None)
        return server

    def test_reports_operational_when_model_and_database_are_ready(self):
        server = self.make_server(FakeConnection())
        context = FakeContext()

        response = server.Status(StatusRequest(), context)

        self.assertEqual(OPERATIONAL_STATE_OPERATIONAL, response.state)
        self.assertEqual(grpc.StatusCode.OK, context.code)
        self.assertEqual(1, len(response.dependencies))
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

        server.Search(SearchRequest(), FakeContext())

        self.assertIn("ORDER BY random()", connection.last_cursor.query)
        self.assertEqual((5, 0), connection.last_cursor.parameters)

    def test_reports_unavailable_when_model_is_not_loaded(self):
        server = self.make_server(FakeConnection(), model=None)

        response = server.Status(StatusRequest(), FakeContext())

        self.assertEqual(OPERATIONAL_STATE_UNAVAILABLE, response.state)
        self.assertEqual(
            OPERATIONAL_STATE_OPERATIONAL,
            response.dependencies[0].state,
        )


if __name__ == '__main__':
    unittest.main()
