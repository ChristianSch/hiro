package main

import (
	"github.com/ChristianSch/hiro/protagonist/adapters/crawl"
	"github.com/ChristianSch/hiro/protagonist/adapters/index"
	"github.com/ChristianSch/hiro/protagonist/infra/logging"
	"go.uber.org/zap"
)

func main() {
	logger := logging.InitLogger(true)
	zap.ReplaceGlobals(logger)

	indexer := index.NewWintermuteIndexer(index.WintermuteConfig{
		Host: "localhost:50052",
	})
	crawler := crawl.NewCollyCrawler(crawl.CollyConfig{
		Indexer: indexer,
	})
	err := crawler.Crawl("https://andinfinity.eu")
	if err != nil {
		panic(err)
	}
	logger.Info("crawling finished")
}
