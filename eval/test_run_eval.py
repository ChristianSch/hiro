import json
import tempfile
import unittest
from pathlib import Path

from .run_eval import load_cases, recall_at, write_results


class EvaluationMetricsTest(unittest.TestCase):
    def test_loads_urls_without_rewriting_them(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "queries.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "query": "example",
                            "relevant_urls": ["https://EXAMPLE.com"],
                        }
                    ]
                )
            )

            cases = load_cases(path)

        self.assertEqual(
            {"https://EXAMPLE.com": 1.0},
            cases[0].relevance,
        )

    def test_creates_json_output_parent_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "results.json"

            write_results(path, [{"query": "example"}])

            self.assertTrue(path.is_file())
            self.assertEqual(
                {"cases": [{"query": "example"}]},
                json.loads(path.read_text()),
            )

    def test_recall_uses_stored_urls_directly(self):
        self.assertEqual(
            1.0,
            recall_at(
                ["https://example.com/"],
                {"https://example.com/"},
                k=10,
            ),
        )


if __name__ == "__main__":
    unittest.main()
