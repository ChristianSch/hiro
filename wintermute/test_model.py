import unittest
from unittest.mock import call, patch

from .model import load_embedding_model


class FakeModel:
    def __init__(self, dimensions=3):
        self.dimensions = dimensions

    def get_embedding_dimension(self):
        return self.dimensions


class ModelLoadingTest(unittest.TestCase):
    @patch("wintermute.model.SentenceTransformer")
    def test_uses_local_files_without_network_fallback(self, constructor):
        expected = FakeModel()
        constructor.return_value = expected

        actual = load_embedding_model(
            "model", "cpu", dimensions=3, allow_download=True
        )

        self.assertIs(expected, actual)
        constructor.assert_called_once_with(
            "model",
            device="cpu",
            local_files_only=True,
        )

    @patch("wintermute.model.SentenceTransformer")
    def test_falls_back_to_download_only_after_local_miss(self, constructor):
        expected = FakeModel()
        constructor.side_effect = [OSError("not cached"), expected]

        actual = load_embedding_model(
            "model", "cpu", dimensions=3, allow_download=True
        )

        self.assertIs(expected, actual)
        self.assertEqual(
            [
                call("model", device="cpu", local_files_only=True),
                call("model", device="cpu", local_files_only=False),
            ],
            constructor.call_args_list,
        )

    @patch("wintermute.model.SentenceTransformer")
    def test_offline_mode_fails_without_attempting_download(self, constructor):
        constructor.side_effect = OSError("not cached")

        with self.assertRaisesRegex(RuntimeError, "downloads are disabled"):
            load_embedding_model(
                "model", "cpu", dimensions=3, allow_download=False
            )

        constructor.assert_called_once_with(
            "model",
            device="cpu",
            local_files_only=True,
        )

    @patch("wintermute.model.SentenceTransformer")
    def test_rejects_model_with_different_dimensions(self, constructor):
        constructor.return_value = FakeModel(dimensions=4)

        with self.assertRaisesRegex(RuntimeError, "configured dimensions is 3"):
            load_embedding_model(
                "model", "cpu", dimensions=3, allow_download=False
            )


if __name__ == "__main__":
    unittest.main()
