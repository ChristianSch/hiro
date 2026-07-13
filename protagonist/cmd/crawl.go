package main

import (
	"flag"
	"path/filepath"

	"github.com/ChristianSch/hiro/protagonist/adapters/crawl"
	"github.com/ChristianSch/hiro/protagonist/adapters/index"
	appconfig "github.com/ChristianSch/hiro/protagonist/config"
	"github.com/ChristianSch/hiro/protagonist/infra/logging"
	"go.uber.org/zap"
)

func main() {
	configDir := flag.String("config-dir", "../config", "directory containing global.yml and crawler.yml")
	startURL := flag.String("url", "", "starting point of crawling")
	maxDepth := flag.Int("max-depth", 0, "override maximum crawl depth")
	debug := flag.Bool("debug", false, "enable debug logging")
	flag.Parse()

	cfg, err := appconfig.Load(
		filepath.Join(*configDir, "global.yml"),
		filepath.Join(*configDir, "crawler.yml"),
	)
	if err != nil {
		panic(err)
	}
	if *startURL != "" {
		cfg.Crawl.StartURL = *startURL
	}
	if *maxDepth > 0 {
		cfg.Crawl.MaxDepth = *maxDepth
	}
	if *debug {
		cfg.Logging.Debug = true
	}
	if cfg.Crawl.StartURL == "" {
		panic("URL is mandatory. Usage: ./crawl -url https://example.com")
	}
	run(cfg)
}

func run(cfg appconfig.Config) {
	logger := logging.InitLogger(cfg.Logging.Debug)
	defer logger.Sync()
	undo := zap.ReplaceGlobals(logger)
	defer undo()

	indexer, err := index.NewWintermuteIndexer(index.WintermuteConfig{
		Host:       cfg.Embedding.Address,
		Token:      cfg.Embedding.Token,
		Timeout:    cfg.Embedding.Timeout,
		Insecure:   cfg.Embedding.Insecure,
		ServerName: cfg.Embedding.ServerName,
	})
	if err != nil {
		panic(err)
	}
	defer indexer.Close()

	crawler := crawl.NewCollyCrawler(crawl.CollyConfig{
		Indexer:        indexer,
		MaxDepth:       &cfg.Crawl.MaxDepth,
		MaxBodySize:    cfg.Crawl.MaxBodyBytes,
		RequestTimeout: cfg.Crawl.RequestTimeout,
	})
	if err := crawler.Crawl(cfg.Crawl.StartURL); err != nil {
		panic(err)
	}
	logger.Info("crawling finished")
}
