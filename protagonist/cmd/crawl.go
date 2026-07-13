package main

import (
	"flag"

	"github.com/ChristianSch/hiro/protagonist/adapters/crawl"
	"github.com/ChristianSch/hiro/protagonist/adapters/index"
	appconfig "github.com/ChristianSch/hiro/protagonist/config"
	"github.com/ChristianSch/hiro/protagonist/infra/logging"
	"go.uber.org/zap"
)

func main() {
	cfg, err := appconfig.Load()
	if err != nil {
		panic(err)
	}

	flag.StringVar(&cfg.Crawl.StartURL, "url", cfg.Crawl.StartURL, "starting point of crawling")
	flag.IntVar(&cfg.Crawl.MaxDepth, "max-depth", cfg.Crawl.MaxDepth, "max depth of crawling")
	flag.BoolVar(&cfg.Debug, "debug", cfg.Debug, "debug mode")
	flag.Parse()

	if cfg.Crawl.StartURL == "" {
		panic("URL is mandatory. Usage: ./crawl -url https://example.com")
	}
	run(cfg)
}

func run(cfg appconfig.Config) {
	logger := logging.InitLogger(cfg.Debug)
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
