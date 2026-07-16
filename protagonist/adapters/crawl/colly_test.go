package crawl

import "testing"

func TestNormalizeURLCanonicalizesEquivalentURLs(t *testing.T) {
	t.Parallel()

	cases := map[string]string{
		"https://EXAMPLE.com":                  "https://example.com/",
		"https://example.com/":                 "https://example.com/",
		"https://example.com/path/":            "https://example.com/path",
		"https://example.com:443/path#section": "https://example.com/path",
		"http://example.com:80":                "http://example.com/",
	}
	for input, expected := range cases {
		if actual := normalizeURL(input); actual != expected {
			t.Errorf("normalizeURL(%q) = %q, want %q", input, actual, expected)
		}
	}
}
