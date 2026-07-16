import unittest
from unittest.mock import call, patch

from .model import load_embedding_model


class ModelLoadingTest(unittest.TestCase):
    @patch("wintermute.model.SentenceTransformer")
    def test_uses_local_files_without_network_fallback(self, constructor):
        expected = object()
        constructor.return_value = expected

        actual = load_embedding_model("model", "cpu", allow_download=True)

        self.assertIs(expected, actual)
        constructor.assert_called_once_with(
            "model",
            device="cpu",
            local_files_only=True,
        )

    @patch("wintermute.model.SentenceTransformer")
    def test_falls_back_to_download_only_after_local_miss(self, constructor):
        expected = object()
        constructor.side_effect = [OSError("not cached"), expected]

        actual = load_embedding_model("model", "cpu", allow_download=True)

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
            load_embedding_model("model", "cpu", allow_download=False)

        constructor.assert_called_once_with(
            "model",
            device="cpu",
            local_files_only=True,
        )


if __name__ == "__main__":
    unittest.main()
