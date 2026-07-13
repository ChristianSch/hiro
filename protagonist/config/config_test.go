package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

const globalConfig = `
logging:
  debug: false
`

const crawlerConfig = `
embedding:
  address: 127.0.0.1:50052
  token: ""
  timeout: 30s
  insecure: true
  server_name: ""
crawl:
  start_url: ""
  max_depth: 2
  max_body_bytes: 2097152
  request_timeout: 15s
`

func writeConfig(t *testing.T, name, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), name)
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write config: %v", err)
	}
	return path
}

func TestLoadMergesGlobalAndCrawlerConfig(t *testing.T) {
	globalPath := writeConfig(t, "global.yml", globalConfig)
	crawlerPath := writeConfig(t, "crawler.yml", crawlerConfig)

	cfg, err := Load(globalPath, crawlerPath)
	if err != nil {
		t.Fatalf("Load returned an error: %v", err)
	}
	if cfg.Embedding.Address != "127.0.0.1:50052" {
		t.Fatalf("unexpected embedding address: %q", cfg.Embedding.Address)
	}
	if cfg.Embedding.Timeout != 30*time.Second {
		t.Fatalf("unexpected embedding timeout: %s", cfg.Embedding.Timeout)
	}
	if cfg.Crawl.MaxDepth != 2 {
		t.Fatalf("unexpected max depth: %d", cfg.Crawl.MaxDepth)
	}
}

func TestServiceConfigOverridesGlobalConfig(t *testing.T) {
	globalPath := writeConfig(t, "global.yml", globalConfig+"crawl:\n  max_depth: 1\n")
	crawlerPath := writeConfig(t, "crawler.yml", crawlerConfig)

	cfg, err := Load(globalPath, crawlerPath)
	if err != nil {
		t.Fatalf("Load returned an error: %v", err)
	}
	if cfg.Crawl.MaxDepth != 2 {
		t.Fatalf("expected service override, got %d", cfg.Crawl.MaxDepth)
	}
}

func TestLoadRejectsInvalidCrawlerConfig(t *testing.T) {
	globalPath := writeConfig(t, "global.yml", globalConfig)
	invalid := strings.Replace(crawlerConfig, "request_timeout: 15s", "request_timeout: 0s", 1)
	crawlerPath := writeConfig(t, "crawler.yml", invalid)

	if _, err := Load(globalPath, crawlerPath); err == nil {
		t.Fatal("expected invalid request timeout to be rejected")
	}
}
