package main

import (
	"flag"
	"fmt"
	"os"
	"strconv"
	"time"

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

	indexer, err := index.NewWintermuteIndexer(index.WintermuteConfig{
		Host:       envOrDefault("HIRO_EMBED_GRPC_ADDRESS", "127.0.0.1:50052"),
		Token:      os.Getenv("HIRO_SERVICE_TOKEN"),
		Timeout:    durationEnv("HIRO_EMBED_TIMEOUT", 30*time.Second),
		Insecure:   boolEnv("HIRO_GRPC_INSECURE", true),
		ServerName: os.Getenv("HIRO_GRPC_SERVER_NAME"),
	})
	if err != nil {
		panic(err)
	}
	defer indexer.Close()
	crawler := crawl.NewCollyCrawler(crawl.CollyConfig{
		Indexer:        indexer,
		MaxDepth:       &cfg.MaxDepth,
		MaxBodySize:    intEnv("HIRO_CRAWL_MAX_BODY_BYTES", 2*1024*1024),
		RequestTimeout: durationEnv("HIRO_CRAWL_REQUEST_TIMEOUT", 15*time.Second),
		AllowPrivate:   boolEnv("HIRO_CRAWL_ALLOW_PRIVATE", false),
	})
	err = crawler.Crawl(cfg.StartingPoint)
	if err != nil {
		panic(err)
	}
	logger.Info("crawling finished")
}

func envOrDefault(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func boolEnv(name string, fallback bool) bool {
	raw := os.Getenv(name)
	if raw == "" {
		return fallback
	}
	value, err := strconv.ParseBool(raw)
	if err != nil {
		panic(fmt.Errorf("invalid %s: %w", name, err))
	}
	return value
}

func intEnv(name string, fallback int) int {
	raw := os.Getenv(name)
	if raw == "" {
		return fallback
	}
	value, err := strconv.Atoi(raw)
	if err != nil || value <= 0 {
		panic(fmt.Errorf("invalid %s integer %q", name, raw))
	}
	return value
}

func durationEnv(name string, fallback time.Duration) time.Duration {
	raw := os.Getenv(name)
	if raw == "" {
		return fallback
	}
	value, err := time.ParseDuration(raw)
	if err != nil || value <= 0 {
		panic(fmt.Errorf("invalid %s duration %q", name, raw))
	}
	return value
}
