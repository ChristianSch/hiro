import unittest

from .reembed import prepared_contents


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


class PreparedContentsTest(unittest.TestCase):
    def test_rechunks_single_legacy_chunk(self):
        contents = prepared_contents(
            FakeTokenizer(),
            [("0 1 2 3 4 5 6", "legacy")],
            max_tokens=4,
            overlap_tokens=1,
            rechunk_legacy=True,
        )

        self.assertEqual(["0 1 2 3", "3 4 5 6"], contents)

    def test_preserves_current_chunk_boundaries(self):
        contents = prepared_contents(
            FakeTokenizer(),
            [("0 1 2", "old-model"), ("2 3 4", "old-model")],
            max_tokens=4,
            overlap_tokens=1,
            rechunk_legacy=True,
        )

        self.assertEqual(["0 1 2", "2 3 4"], contents)

    def test_can_preserve_legacy_chunk(self):
        contents = prepared_contents(
            FakeTokenizer(),
            [("0 1 2 3 4", "legacy")],
            max_tokens=4,
            overlap_tokens=1,
            rechunk_legacy=False,
        )

        self.assertEqual(["0 1 2 3 4"], contents)


if __name__ == "__main__":
    unittest.main()
