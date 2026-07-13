package config

import (
	"testing"
	"time"
)

func TestLoadUsesCrawlerScopedEnvironment(t *testing.T) {
	t.Setenv("HIRO_CRAWLER_EMBEDDING_ADDRESS", "embed.internal:7443")
	t.Setenv("HIRO_CRAWLER_EMBEDDING_TIMEOUT", "45s")
	t.Setenv("HIRO_CRAWLER_CRAWL_MAX_DEPTH", "4")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load returned an error: %v", err)
	}
	if cfg.Embedding.Address != "embed.internal:7443" {
		t.Fatalf("unexpected embedding address: %q", cfg.Embedding.Address)
	}
	if cfg.Embedding.Timeout != 45*time.Second {
		t.Fatalf("unexpected embedding timeout: %s", cfg.Embedding.Timeout)
	}
	if cfg.Crawl.MaxDepth != 4 {
		t.Fatalf("unexpected max depth: %d", cfg.Crawl.MaxDepth)
	}
}

func TestLoadRejectsInvalidCrawlerConfig(t *testing.T) {
	t.Setenv("HIRO_CRAWLER_CRAWL_MAX_BODY_BYTES", "0")
	if _, err := Load(); err == nil {
		t.Fatal("expected invalid body size to be rejected")
	}
}
