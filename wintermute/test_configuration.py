import tempfile
import unittest
from pathlib import Path

from .embed.config import EmbeddingSettings
from .search.config import SearchSettings


GLOBAL_CONFIG = """
database:
  url: postgresql://hiro@localhost/hiro
model:
  name: shared-model
  device: cpu
  dimensions: 768
  allow_download: false
logging:
  level: INFO
"""

EMBED_CONFIG = """
server:
  address: 127.0.0.1:50052
  token: ""
  tls_certificate: ""
  tls_private_key: ""
  max_workers: 4
  max_message_bytes: 1048576
  reflection: false
database:
  pool_size: 8
chunking:
  max_tokens: 384
  overlap_tokens: 64
  batch_size: 32
"""

SEARCH_CONFIG = """
server:
  address: 127.0.0.1:50053
  token: ""
  tls_certificate: ""
  tls_private_key: ""
  max_workers: 4
  max_message_bytes: 1048576
  reflection: false
database:
  pool_size: 8
embedding_service:
  address: 127.0.0.1:50052
  token: ""
  timeout_seconds: 5
  tls_ca_certificate: ""
  server_name: ""
retrieval:
  match_threshold: 0.78
  vector_candidates: 200
  text_candidates: 200
  hnsw_ef_search: 200
  hnsw_iterative_scan: relaxed_order
"""


class ServiceConfigurationTest(unittest.TestCase):
    def write_configs(self, service_name: str, service_config: str):
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        global_path = root / "global.yml"
        service_path = root / f"{service_name}.yml"
        global_path.write_text(GLOBAL_CONFIG)
        service_path.write_text(service_config)
        self.addCleanup(directory.cleanup)
        return global_path, service_path

    def test_embedding_configuration_merges_global_and_service_files(self):
        paths = self.write_configs("embed", EMBED_CONFIG)
        settings = EmbeddingSettings.from_files(*paths)

        self.assertEqual("postgresql://hiro@localhost/hiro", settings.database_url)
        self.assertEqual("shared-model", settings.model_name)
        self.assertEqual(768, settings.model_dimensions)
        self.assertFalse(settings.model_allow_download)
        self.assertEqual("127.0.0.1:50052", settings.listen_address)
        self.assertEqual(384, settings.chunk_max_tokens)
        self.assertEqual(64, settings.chunk_overlap_tokens)

    def test_search_configuration_merges_global_and_service_files(self):
        paths = self.write_configs("search", SEARCH_CONFIG)
        settings = SearchSettings.from_files(*paths)

        self.assertEqual("postgresql://hiro@localhost/hiro", settings.database_url)
        self.assertEqual(768, settings.model_dimensions)
        self.assertEqual("127.0.0.1:50052", settings.embedding_address)
        self.assertEqual(5, settings.embedding_timeout_seconds)
        self.assertEqual("127.0.0.1:50053", settings.listen_address)
        self.assertEqual(0.78, settings.match_threshold)
        self.assertEqual(200, settings.hnsw_ef_search)
        self.assertEqual("relaxed_order", settings.hnsw_iterative_scan)

    def test_service_file_overrides_global_values(self):
        global_config = GLOBAL_CONFIG + "\nserver:\n  max_workers: 2\n"
        service_config = EMBED_CONFIG.replace("max_workers: 4", "max_workers: 6")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / "global.yml").write_text(global_config)
        (root / "embed.yml").write_text(service_config)

        settings = EmbeddingSettings.from_files(root / "global.yml", root / "embed.yml")

        self.assertEqual(6, settings.max_workers)

    def test_non_loopback_listener_requires_service_token(self):
        service_config = EMBED_CONFIG.replace(
            "address: 127.0.0.1:50052",
            "address: 0.0.0.0:50052",
        )
        paths = self.write_configs("embed", service_config)

        with self.assertRaises(ValueError):
            EmbeddingSettings.from_files(*paths)


if __name__ == "__main__":
    unittest.main()
