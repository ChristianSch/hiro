import unittest

from .url_utils import canonicalize_url


class CanonicalizeURLTest(unittest.TestCase):
    def test_canonicalizes_equivalent_urls(self):
        cases = {
            "https://EXAMPLE.com": "https://example.com/",
            "https://example.com/": "https://example.com/",
            "https://example.com/path/": "https://example.com/path",
            "https://example.com:443/path#section": "https://example.com/path",
            "http://example.com:80": "http://example.com/",
        }
        for raw_url, expected in cases.items():
            with self.subTest(raw_url=raw_url):
                self.assertEqual(expected, canonicalize_url(raw_url))

    def test_preserves_query_parameters(self):
        self.assertEqual(
            "https://example.com/?ref=source",
            canonicalize_url("https://example.com?ref=source#fragment"),
        )

    def test_rejects_non_http_urls(self):
        with self.assertRaises(ValueError):
            canonicalize_url("file:///tmp/document")


if __name__ == "__main__":
    unittest.main()
