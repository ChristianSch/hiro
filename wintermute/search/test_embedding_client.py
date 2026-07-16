import unittest
from types import SimpleNamespace

from .embedding_client import EmbeddingClient


class FakeStub:
    def __init__(self, values=None, ready=True, dimensions=3):
        self.values = values if values is not None else [0.0] * dimensions
        self.is_ready = ready
        self.dimensions = dimensions
        self.query_request = None

    def EmbedQuery(self, request, **kwargs):
        self.query_request = request
        return SimpleNamespace(embedding=self.values)

    def Status(self, request, **kwargs):
        return SimpleNamespace(
            ready=self.is_ready,
            dimensions=self.dimensions,
        )


class EmbeddingClientTest(unittest.TestCase):
    def make_client(self, stub):
        client = EmbeddingClient.__new__(EmbeddingClient)
        client._stub = stub
        client._dimensions = 3
        client._timeout = 5
        client._metadata = None
        return client

    def test_embeds_query(self):
        stub = FakeStub()
        client = self.make_client(stub)

        embedding = client.embed_query("semantic search")

        self.assertEqual(3, len(embedding))
        self.assertEqual("semantic search", stub.query_request.query)

    def test_rejects_wrong_embedding_dimensions(self):
        client = self.make_client(FakeStub(values=[0.0, 1.0]))

        with self.assertRaisesRegex(RuntimeError, "expected 3"):
            client.embed_query("semantic search")

    def test_reports_readiness(self):
        client = self.make_client(FakeStub(ready=True, dimensions=3))

        self.assertTrue(client.ready())

    def test_reports_not_ready_when_dimensions_differ(self):
        client = self.make_client(FakeStub(ready=True, dimensions=4))

        self.assertFalse(client.ready())


if __name__ == "__main__":
    unittest.main()
