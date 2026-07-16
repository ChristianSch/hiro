import unittest

from .run_eval import deduplicate_urls, recall_at


class EvaluationMetricsTest(unittest.TestCase):
    def test_deduplicates_normalized_result_urls_in_order(self):
        self.assertEqual(
            ["https://example.com/", "https://example.com/about"],
            deduplicate_urls(
                [
                    "https://example.com/",
                    "https://example.com/",
                    "https://example.com/about",
                ]
            ),
        )

    def test_duplicate_results_cannot_inflate_recall_after_deduplication(self):
        results = deduplicate_urls(
            ["https://example.com/", "https://example.com/"]
        )

        self.assertEqual(
            1.0,
            recall_at(results, {"https://example.com/"}, k=10),
        )


if __name__ == "__main__":
    unittest.main()
