import unittest
from .chunking import chunk_content


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
