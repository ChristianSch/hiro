import unittest
from types import SimpleNamespace

from .server import EmbeddingServer


class FakeTokenizer:
    def encode(self, content, add_special_tokens=False):
        return [int(value) for value in content.split()]

    def decode(
        self,
        token_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True,
    ):
        return " ".join(str(value) for value in token_ids)


class EmbeddingServerChunkingTest(unittest.TestCase):
    def make_server(self, max_tokens=4, overlap_tokens=1):
        server = EmbeddingServer.__new__(EmbeddingServer)
        server._settings = SimpleNamespace(
            chunk_max_tokens=max_tokens,
            chunk_overlap_tokens=overlap_tokens,
        )
        server._model = SimpleNamespace(tokenizer=FakeTokenizer())
        return server

    def test_chunks_content_with_overlap(self):
        server = self.make_server()

        chunks = server._chunk_content("0 1 2 3 4 5 6 7 8 9")

        self.assertEqual(
            ["0 1 2 3", "3 4 5 6", "6 7 8 9"],
            chunks,
        )

    def test_short_content_stays_in_one_chunk(self):
        server = self.make_server()

        self.assertEqual(["0 1 2"], server._chunk_content("0 1 2"))


if __name__ == "__main__":
    unittest.main()
