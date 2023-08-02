package cmd

import (
	// "github.com/stevenferrer/solr-go"
	"github.com/ChristianSch/hiro/protagonist/adapters/crawl"
)

func main(args []string) {
	println(args)

	crawler := crawl.NewNetCrawler()
	crawler.Crawl("https://www.google.com")
}
