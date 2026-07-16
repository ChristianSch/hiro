import threading
import unittest
from types import SimpleNamespace

import numpy as np

from .chunking import chunk_content
from .server import EmbeddingServer
from .stubs.embedding_pb2 import (
    EmbeddingRequest,
    EmbeddingStatusRequest,
    QueryEmbeddingRequest,
)


class FakeTokenizer:
    def encode(self, content, add_special_tokens=False, verbose=True):
        return [int(value) for value in content.split()]

    def decode(
        self,
        token_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True,
    ):
        return " ".join(str(value) for value in token_ids)


class FakeContext:
    def abort(self, code, details):
        raise AssertionError(details)


class FakeModel:
    def encode(self, query, **kwargs):
        embedding = np.zeros(768, dtype=np.float32)
        embedding[:2] = [0.5, -0.5]
        return embedding


class EmbeddingRequestTest(unittest.TestCase):
    def test_canonicalizes_url_before_embedding(self):
        server = EmbeddingServer.__new__(EmbeddingServer)
        server._settings = SimpleNamespace(service_token=None)
        received = []
        server._embed = lambda *arguments: received.append(arguments)

        server.Embed(
            EmbeddingRequest(
                url="HTTPS://EXAMPLE.COM",
                title="Example",
                content="content",
                description="description",
            ),
            FakeContext(),
        )

        self.assertEqual("https://example.com/", received[0][0])
        self.assertEqual("example.com", received[0][4])

    def test_embeds_query_with_shared_model(self):
        server = EmbeddingServer.__new__(EmbeddingServer)
        server._settings = SimpleNamespace(service_token=None, model_name="shared-model")
        server._model = FakeModel()
        server._inference_lock = threading.Lock()

        response = server.EmbedQuery(
            QueryEmbeddingRequest(query="semantic search"),
            FakeContext(),
        )

        self.assertEqual(768, len(response.embedding))
        self.assertEqual([0.5, -0.5], list(response.embedding[:2]))

    def test_reports_model_readiness(self):
        server = EmbeddingServer.__new__(EmbeddingServer)
        server._settings = SimpleNamespace(service_token=None, model_name="shared-model")
        server._model = FakeModel()

        response = server.Status(EmbeddingStatusRequest(), FakeContext())

        self.assertTrue(response.ready)
        self.assertEqual("shared-model", response.model)


class EmbeddingChunkingTest(unittest.TestCase):
    def test_chunks_content_with_overlap(self):
        chunks = chunk_content(
            FakeTokenizer(),
            "0 1 2 3 4 5 6 7 8 9",
            max_tokens=4,
            overlap_tokens=1,
        )

        self.assertEqual(
            ["0 1 2 3", "3 4 5 6", "6 7 8 9"],
            chunks,
        )

    def test_short_content_stays_in_one_chunk(self):
        self.assertEqual(
            ["0 1 2"],
            chunk_content(
                FakeTokenizer(),
                "0 1 2",
                max_tokens=4,
                overlap_tokens=1,
            ),
        )


if __name__ == "__main__":
    unittest.main()
