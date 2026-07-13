import os
import unittest
from unittest.mock import patch

from .embed.config import EmbeddingSettings
from .search.config import SearchSettings


class ServiceConfigurationTest(unittest.TestCase):
    def test_embedding_configuration_has_service_defaults(self):
        with patch.dict(
            os.environ,
            {"HIRO_DATABASE_URL": "postgresql://hiro@localhost/hiro"},
            clear=True,
        ):
            settings = EmbeddingSettings.from_env()

        self.assertEqual("127.0.0.1:50052", settings.listen_address)
        self.assertEqual("cpu", settings.model_device)

    def test_search_configuration_has_service_defaults(self):
        with patch.dict(
            os.environ,
            {"HIRO_DATABASE_URL": "postgresql://hiro@localhost/hiro"},
            clear=True,
        ):
            settings = SearchSettings.from_env()

        self.assertEqual("127.0.0.1:50053", settings.listen_address)
        self.assertEqual("cpu", settings.model_device)

    def test_non_loopback_embedding_listener_requires_embedding_token(self):
        with patch.dict(
            os.environ,
            {
                "HIRO_DATABASE_URL": "postgresql://hiro@localhost/hiro",
                "HIRO_EMBED_LISTEN_ADDRESS": "0.0.0.0:50052",
            },
            clear=True,
        ):
            with self.assertRaises(ValueError):
                EmbeddingSettings.from_env()

    def test_non_loopback_search_listener_accepts_search_token(self):
        with patch.dict(
            os.environ,
            {
                "HIRO_DATABASE_URL": "postgresql://hiro@localhost/hiro",
                "HIRO_SEARCH_LISTEN_ADDRESS": "0.0.0.0:50053",
                "HIRO_SEARCH_TOKEN": "secret",
            },
            clear=True,
        ):
            settings = SearchSettings.from_env()

        self.assertEqual("secret", settings.service_token)


if __name__ == "__main__":
    unittest.main()
