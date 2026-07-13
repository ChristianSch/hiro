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

const webConfig = `
http:
  address: 127.0.0.1:8973
  read_timeout: 10s
  write_timeout: 15s
  idle_timeout: 60s
  body_limit: 65536
  search_rate_limit: 60
search:
  address: 127.0.0.1:50053
  token: ""
  timeout: 5s
  insecure: true
  server_name: ""
`

func writeConfig(t *testing.T, name, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), name)
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write config: %v", err)
	}
	return path
}

func TestLoadMergesGlobalAndWebConfig(t *testing.T) {
	globalPath := writeConfig(t, "global.yml", globalConfig)
	webPath := writeConfig(t, "web.yml", webConfig)

	cfg, err := Load(globalPath, webPath)
	if err != nil {
		t.Fatalf("Load returned an error: %v", err)
	}
	if cfg.HTTP.Address != "127.0.0.1:8973" {
		t.Fatalf("unexpected HTTP address: %q", cfg.HTTP.Address)
	}
	if cfg.HTTP.ReadTimeout != 10*time.Second {
		t.Fatalf("unexpected read timeout: %s", cfg.HTTP.ReadTimeout)
	}
	if cfg.Search.Address != "127.0.0.1:50053" {
		t.Fatalf("unexpected search address: %q", cfg.Search.Address)
	}
}

func TestServiceConfigOverridesGlobalConfig(t *testing.T) {
	globalPath := writeConfig(t, "global.yml", globalConfig+"http:\n  search_rate_limit: 10\n")
	webPath := writeConfig(t, "web.yml", webConfig)

	cfg, err := Load(globalPath, webPath)
	if err != nil {
		t.Fatalf("Load returned an error: %v", err)
	}
	if cfg.HTTP.SearchLimit != 60 {
		t.Fatalf("expected service override, got %d", cfg.HTTP.SearchLimit)
	}
}

func TestLoadRejectsInvalidWebConfig(t *testing.T) {
	globalPath := writeConfig(t, "global.yml", globalConfig)
	invalid := strings.Replace(webConfig, "search_rate_limit: 60", "search_rate_limit: 0", 1)
	webPath := writeConfig(t, "web.yml", invalid)

	if _, err := Load(globalPath, webPath); err == nil {
		t.Fatal("expected invalid search rate limit to be rejected")
	}
}
