package main

import (
	"flag"

	"github.com/ChristianSch/hiro/protagonist/adapters/crawl"
	"github.com/ChristianSch/hiro/protagonist/adapters/index"
	"github.com/ChristianSch/hiro/protagonist/infra/logging"
	"go.uber.org/zap"
)

type AppConfig struct {
	Debug         bool
	StartingPoint string
	MaxDepth      int
}

func main() {
	var maxDepth = flag.Int("max-depth", 2, "max depth of crawling")
	var startingPoint = flag.String("url", "", "starting point of crawling")
	var debug = flag.Bool("debug", false, "debug mode")

	flag.Parse()

	if *startingPoint == "" {
		panic("Url is mandatory. Usage: ./crawl -url https://andinfinity.eu")
	}

	// get the starting point
	run(AppConfig{
		Debug:         *debug,
		StartingPoint: *startingPoint,
		MaxDepth:      *maxDepth,
	})
}

func run(cfg AppConfig) {
	logger := logging.InitLogger(cfg.Debug)
	zap.ReplaceGlobals(logger)

	indexer := index.NewWintermuteIndexer(index.WintermuteConfig{
		Host: "localhost:50052",
	})
	crawler := crawl.NewCollyCrawler(crawl.CollyConfig{
		Indexer:  indexer,
		MaxDepth: &cfg.MaxDepth,
	})
	err := crawler.Crawl(cfg.StartingPoint)
	if err != nil {
		panic(err)
	}
	logger.Info("crawling finished")
}
