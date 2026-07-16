import unittest

import numpy as np

from .generate_corpus import normalized_vectors
from .vector_search import percentile


class BenchmarkHelpersTest(unittest.TestCase):
    def test_percentile_interpolates(self):
        self.assertEqual(2.5, percentile([1.0, 2.0, 3.0, 4.0], 0.5))

    def test_generated_vectors_are_normalized(self):
        vectors = normalized_vectors(np.random.default_rng(42), 4, 8)
        norms = np.linalg.norm(vectors, axis=1)
        np.testing.assert_allclose(norms, np.ones(4), rtol=1e-5)


if __name__ == "__main__":
    unittest.main()
