package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestAssetURLIncludesContentVersion(t *testing.T) {
	staticDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(staticDir, "base.css"), []byte("body{}"), 0o600); err != nil {
		t.Fatal(err)
	}

	asset, err := newAssetURL(staticDir, []string{"/static/base.css"})
	if err != nil {
		t.Fatalf("newAssetURL returned an error: %v", err)
	}
	versioned := asset("/static/base.css")
	if !strings.HasPrefix(versioned, "/static/base.css?v=") {
		t.Fatalf("asset URL is not versioned: %q", versioned)
	}
	if got := asset("/static/unknown.css"); got != "/static/unknown.css" {
		t.Fatalf("unknown asset changed: %q", got)
	}
}

func TestAssetURLChangesWithContent(t *testing.T) {
	staticDir := t.TempDir()
	path := filepath.Join(staticDir, "base.css")
	if err := os.WriteFile(path, []byte("body{}"), 0o600); err != nil {
		t.Fatal(err)
	}
	first, err := newAssetURL(staticDir, []string{"/static/base.css"})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("body{color:red}"), 0o600); err != nil {
		t.Fatal(err)
	}
	second, err := newAssetURL(staticDir, []string{"/static/base.css"})
	if err != nil {
		t.Fatal(err)
	}

	if first("/static/base.css") == second("/static/base.css") {
		t.Fatal("asset version did not change with content")
	}
}
