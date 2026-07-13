package config

import (
	"testing"
	"time"
)

func TestLoadUsesWebScopedEnvironment(t *testing.T) {
	t.Setenv("HIRO_WEB_HTTP_ADDRESS", "127.0.0.1:9999")
	t.Setenv("HIRO_WEB_HTTP_READ_TIMEOUT", "3s")
	t.Setenv("HIRO_WEB_SEARCH_ADDRESS", "search.internal:7443")

	cfg, err := Load()
	if err != nil {
		t.Fatalf("Load returned an error: %v", err)
	}
	if cfg.HTTP.Address != "127.0.0.1:9999" {
		t.Fatalf("unexpected HTTP address: %q", cfg.HTTP.Address)
	}
	if cfg.HTTP.ReadTimeout != 3*time.Second {
		t.Fatalf("unexpected read timeout: %s", cfg.HTTP.ReadTimeout)
	}
	if cfg.Search.Address != "search.internal:7443" {
		t.Fatalf("unexpected search address: %q", cfg.Search.Address)
	}
}

func TestLoadRejectsInvalidWebConfig(t *testing.T) {
	t.Setenv("HIRO_WEB_HTTP_SEARCH_RATE_LIMIT", "0")
	if _, err := Load(); err == nil {
		t.Fatal("expected invalid search rate limit to be rejected")
	}
}
