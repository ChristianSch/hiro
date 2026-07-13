import unittest

import grpc

from .server import SearchServer
from .stubs.search_pb2 import (
    OPERATIONAL_STATE_OPERATIONAL,
    OPERATIONAL_STATE_UNAVAILABLE,
    StatusRequest,
)


class FakeCursor:
    def __init__(self, result=(1,), error=None):
        self._result = result
        self._error = error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query):
        if self._error is not None:
            raise self._error
        return self

    def fetchone(self):
        return self._result


class FakeConnection:
    def __init__(self, result=(1,), error=None):
        self._result = result
        self._error = error

    def cursor(self):
        return FakeCursor(self._result, self._error)


class FakeContext:
    code = None

    def set_code(self, code):
        self.code = code


class SearchServerStatusTest(unittest.TestCase):
    def make_server(self, connection, model=object()):
        server = SearchServer.__new__(SearchServer)
        server._conn = connection
        server._model = model
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
